from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from forgegate.canonical import canonical_json, sha256_fingerprint
from forgegate.domain.enums import (
    Aggregation,
    Decision,
    EvidenceTrust,
    Operator,
    VerificationLevel,
)
from forgegate.domain.models import EvidenceBundle, EvidenceRecord, PolicyConfig, PolicyRule
from forgegate.policy.materials import PolicyMaterial
from forgegate.policy.models import (
    PolicyEvaluation,
    ProfileAuthorizedPolicyEvaluation,
    RuleEvaluation,
)

TRUST_RANK = {
    EvidenceTrust.UNSIGNED_LOCAL: 0,
    EvidenceTrust.CLAIMED_CI_METADATA: 1,
    EvidenceTrust.VERIFIED_CI_IDENTITY: 2,
    EvidenceTrust.SIGNED_ATTESTATION: 3,
}

VERIFICATION_RANK = {
    VerificationLevel.DECLARED: 0,
    VerificationLevel.SIMULATED: 1,
    VerificationLevel.REPLAYED: 2,
    VerificationLevel.HOST_TESTED: 3,
    VerificationLevel.TARGET_BUILT: 4,
    VerificationLevel.CI_VALIDATED: 5,
    VerificationLevel.SYSTEM_OBSERVED: 6,
    VerificationLevel.PHYSICALLY_VERIFIED: 7,
}

DECISION_RANK = {
    Decision.PASS: 0,
    Decision.REVIEW: 1,
    Decision.FAIL: 2,
    Decision.ERROR: 3,
}

_RESERVED_FILTERS = {
    "field",
    "scope",
    "status",
    "unit",
    "source_tool",
    "source_version",
}


def evaluate_policy(
    policy: PolicyConfig,
    bundle: EvidenceBundle,
    *,
    evaluated_at: datetime,
) -> PolicyEvaluation:
    """Evaluate immutable policy and evidence inputs at an explicit point in time."""
    _require_timezone(evaluated_at)
    if bundle.generated_at > evaluated_at:
        raise ValueError("evaluated_at cannot precede evidence bundle generation")
    policy_fingerprint = sha256_fingerprint(policy.model_dump(mode="json"))
    evidence_fingerprint = sha256_fingerprint(bundle.model_dump(mode="json"))
    results = [_evaluate_rule(rule, bundle.evidence, evaluated_at) for rule in policy.rules]
    mandatory_decisions = [result.decision for result in results if result.mandatory]
    decision = max(mandatory_decisions, key=DECISION_RANK.__getitem__, default=Decision.PASS)
    evaluated_evidence_ids = sorted(
        {evidence_id for result in results for evidence_id in result.evidence_ids}
    )
    evaluation_input = {
        "policy_fingerprint": policy_fingerprint,
        "evidence_fingerprint": evidence_fingerprint,
        "evaluated_at": evaluated_at.isoformat(),
    }
    return PolicyEvaluation(
        evaluation_id=sha256_fingerprint(evaluation_input),
        policy_name=policy.name,
        policy_fingerprint=policy_fingerprint,
        evidence_fingerprint=evidence_fingerprint,
        candidate_commit=bundle.candidate_commit.lower(),
        evaluated_at=evaluated_at,
        decision=decision,
        rule_results=results,
        evaluated_evidence_ids=evaluated_evidence_ids,
    )


def evaluate_policy_material(
    material: PolicyMaterial,
    bundle: EvidenceBundle,
    *,
    evaluated_at: datetime,
) -> ProfileAuthorizedPolicyEvaluation:
    """Evaluate exact profile-authorized policy bytes and bind them into identity."""
    legacy = evaluate_policy(material.policy, bundle, evaluated_at=evaluated_at)
    evaluation_input = {
        "policy_material_id": material.material_id,
        "evidence_fingerprint": legacy.evidence_fingerprint,
        "evaluated_at": evaluated_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
    }
    return ProfileAuthorizedPolicyEvaluation(
        evaluation_id=sha256_fingerprint(evaluation_input),
        policy_name=legacy.policy_name,
        policy_fingerprint=legacy.policy_fingerprint,
        evidence_fingerprint=legacy.evidence_fingerprint,
        candidate_commit=legacy.candidate_commit,
        evaluated_at=legacy.evaluated_at,
        decision=legacy.decision,
        rule_results=legacy.rule_results,
        evaluated_evidence_ids=legacy.evaluated_evidence_ids,
        policy_material_id=material.material_id,
        policy_artifact_sha256=material.artifact.sha256,
        project_profile_id=material.project_profile_id,
        project_profile_version=material.project_profile_version,
    )


def _evaluate_rule(
    rule: PolicyRule,
    evidence: list[EvidenceRecord],
    evaluated_at: datetime,
) -> RuleEvaluation:
    try:
        return _evaluate_rule_checked(rule, evidence, evaluated_at)
    except Exception as exc:  # defensive boundary: a malformed expression fails closed
        return _result(
            rule,
            Decision.ERROR,
            actual=None,
            evidence_ids=[],
            reason_code="EVALUATION_ERROR",
            explanation=f"Rule could not be evaluated: {type(exc).__name__}: {exc}",
            remediation_hint="Correct the policy expression or normalized evidence shape.",
        )


def _evaluate_rule_checked(
    rule: PolicyRule,
    evidence: list[EvidenceRecord],
    evaluated_at: datetime,
) -> RuleEvaluation:
    kind_records = [record for record in evidence if record.kind == rule.evidence_kind]
    if not kind_records:
        return _missing_result(rule, "No evidence of the required kind was supplied.")

    trusted = [
        record
        for record in kind_records
        if TRUST_RANK[record.trust] >= TRUST_RANK[rule.minimum_trust]
        and VERIFICATION_RANK[record.verification_level]
        >= VERIFICATION_RANK[rule.minimum_verification]
    ]
    if not trusted:
        return _result(
            rule,
            Decision.REVIEW,
            actual=None,
            evidence_ids=[record.evidence_id for record in kind_records],
            reason_code="INSUFFICIENT_ASSURANCE",
            explanation=(
                "Evidence exists but does not meet the required trust or verification level."
            ),
            remediation_hint="Collect the same claim at the policy-required assurance levels.",
        )

    fresh = [record for record in trusted if _is_fresh(record, rule, evaluated_at)]
    if not fresh:
        return _result(
            rule,
            Decision.REVIEW,
            actual=None,
            evidence_ids=[record.evidence_id for record in trusted],
            reason_code="STALE_OR_FUTURE_EVIDENCE",
            explanation="Eligible evidence is stale or has a timestamp after evaluation time.",
            remediation_hint="Recollect the evidence and verify synchronized clocks.",
        )

    if rule.aggregation is Aggregation.COUNT and "field" in rule.where:
        raise ValueError("count aggregation cannot use where.field")

    matched = [record for record in fresh if _matches_filters(record, rule.where)]
    if rule.aggregation is not Aggregation.COUNT and not matched:
        return _missing_result(rule, "No eligible evidence matched the rule filters.")

    if rule.aggregation is Aggregation.COUNT:
        actual: Any = len(matched)
        evidence_ids = [record.evidence_id for record in fresh]
        passed = _apply_operator(rule.operator, actual, rule.expected, present=True)
    else:
        values = [_extract_value(record, rule.where.get("field")) for record in matched]
        evidence_ids = [record.evidence_id for record in matched]
        if rule.aggregation is Aggregation.VALUE:
            canonical_values = {canonical_json(value) for value, present in values if present}
            if rule.operator is not Operator.EXISTS and any(not present for _, present in values):
                raise ValueError("selected value field is missing")
            if rule.operator is Operator.EXISTS:
                actual = [present for _, present in values]
                if len(actual) == 1 or len(set(actual)) == 1:
                    actual = actual[0]
                    passed = _apply_operator(rule.operator, actual, rule.expected, present=actual)
                else:
                    return _conflict_result(rule, actual, evidence_ids)
            elif len(canonical_values) != 1:
                return _conflict_result(rule, [value for value, _ in values], evidence_ids)
            else:
                actual = next(value for value, present in values if present)
                passed = _apply_operator(rule.operator, actual, rule.expected, present=True)
        else:
            checks = [
                _apply_operator(rule.operator, value, rule.expected, present=present)
                for value, present in values
            ]
            actual = [value if present else None for value, present in values]
            passed = all(checks) if rule.aggregation is Aggregation.ALL else any(checks)

    decision = Decision.PASS if passed else Decision.FAIL
    reason_code = "RULE_SATISFIED" if passed else "RULE_NOT_SATISFIED"
    explanation = (
        "Eligible evidence satisfies the policy expression."
        if passed
        else "Eligible evidence does not satisfy the policy expression."
    )
    return _result(
        rule,
        decision,
        actual=actual,
        evidence_ids=evidence_ids,
        reason_code=reason_code,
        explanation=explanation,
        remediation_hint=(
            None if passed else f"Provide evidence that satisfies {rule.operator.value}."
        ),
    )


def _missing_result(rule: PolicyRule, explanation: str) -> RuleEvaluation:
    if not rule.require_presence:
        return _result(
            rule,
            Decision.PASS,
            actual=None,
            evidence_ids=[],
            reason_code="ABSENCE_PERMITTED",
            explanation=explanation + " This optional rule permits absence.",
        )
    return _result(
        rule,
        rule.on_missing,
        actual=None,
        evidence_ids=[],
        reason_code="EVIDENCE_MISSING",
        explanation=explanation,
        remediation_hint="Collect eligible evidence for this rule.",
    )


def _conflict_result(rule: PolicyRule, actual: Any, evidence_ids: list[str]) -> RuleEvaluation:
    return _result(
        rule,
        Decision.REVIEW,
        actual=actual,
        evidence_ids=evidence_ids,
        reason_code="CONFLICTING_VALUES",
        explanation="Eligible value evidence contains conflicting normalized values.",
        remediation_hint="Resolve duplicate producers or select a narrower evidence scope.",
    )


def _result(
    rule: PolicyRule,
    decision: Decision,
    *,
    actual: Any,
    evidence_ids: list[str],
    reason_code: str,
    explanation: str,
    remediation_hint: str | None = None,
) -> RuleEvaluation:
    return RuleEvaluation(
        rule_id=rule.id,
        claim=rule.claim,
        decision=decision,
        mandatory=rule.mandatory,
        evidence_kind=rule.evidence_kind,
        aggregation=rule.aggregation,
        operator=rule.operator,
        expected=rule.expected,
        actual=actual,
        evidence_ids=sorted(evidence_ids),
        reason_code=reason_code,
        explanation=explanation,
        remediation_hint=remediation_hint,
    )


def _is_fresh(record: EvidenceRecord, rule: PolicyRule, evaluated_at: datetime) -> bool:
    age_seconds = (evaluated_at - record.collected_at).total_seconds()
    if not math.isfinite(age_seconds) or age_seconds < 0:
        return False
    return rule.maximum_age_seconds is None or age_seconds <= rule.maximum_age_seconds


def _matches_filters(record: EvidenceRecord, where: dict[str, Any]) -> bool:
    for key, expected in where.items():
        if key == "field":
            continue
        if key in _RESERVED_FILTERS:
            actual = getattr(record, key)
            present = True
        elif key.startswith("tags."):
            actual, present = _resolve_path(record.tags, key.removeprefix("tags."))
        elif key.startswith("context."):
            actual, present = _resolve_path(
                record.execution_context.model_dump(mode="python"),
                key.removeprefix("context."),
            )
        else:
            actual, present = _resolve_path(record.value, key)
        if not present or not _strict_equal(actual, expected):
            return False
    return True


def _extract_value(record: EvidenceRecord, field: Any) -> tuple[Any, bool]:
    if field is None:
        return record.value, True
    if not isinstance(field, str) or not field:
        raise ValueError("where.field must be a non-empty dot path")
    return _resolve_path(record.value, field)


def _resolve_path(value: Any, path: str) -> tuple[Any, bool]:
    current = value
    for part in path.split("."):
        if not part:
            return None, False
        if isinstance(current, Mapping) and part in current:
            current = current[part]
        elif isinstance(current, Sequence) and not isinstance(current, (str, bytes)):
            try:
                index = int(part)
                if index < 0:
                    return None, False
                current = current[index]
            except (ValueError, IndexError):
                return None, False
        else:
            return None, False
    return current, True


def _apply_operator(operator: Operator, actual: Any, expected: Any, *, present: bool) -> bool:
    if operator is Operator.EXISTS:
        if not isinstance(expected, bool):
            raise ValueError("exists operator expects a boolean")
        return present is expected
    if not present:
        return False
    if operator is Operator.EQUALS:
        return _strict_equal(actual, expected)
    if operator is Operator.NOT_EQUALS:
        return not _strict_equal(actual, expected)
    if operator in {
        Operator.GREATER_THAN,
        Operator.GREATER_THAN_OR_EQUAL,
        Operator.LESS_THAN,
        Operator.LESS_THAN_OR_EQUAL,
    }:
        if not _is_number(actual) or not _is_number(expected):
            raise ValueError(f"{operator.value} requires finite numeric operands")
        if not math.isfinite(float(actual)) or not math.isfinite(float(expected)):
            raise ValueError(f"{operator.value} requires finite numeric operands")
        if operator is Operator.GREATER_THAN:
            return bool(actual > expected)
        if operator is Operator.GREATER_THAN_OR_EQUAL:
            return bool(actual >= expected)
        if operator is Operator.LESS_THAN:
            return bool(actual < expected)
        return bool(actual <= expected)
    if operator is Operator.CONTAINS:
        if isinstance(actual, str):
            return isinstance(expected, str) and expected in actual
        if isinstance(actual, Mapping):
            return bool(expected in actual)
        if isinstance(actual, Sequence) and not isinstance(actual, (str, bytes)):
            return any(_strict_equal(item, expected) for item in actual)
        raise ValueError("contains requires a string, mapping, or sequence actual value")
    raise ValueError(f"unsupported operator: {operator}")


def _strict_equal(left: Any, right: Any) -> bool:
    if _is_number(left) and _is_number(right):
        return bool(left == right)
    if type(left) is not type(right):
        return False
    return bool(left == right)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _require_timezone(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("evaluated_at must include a UTC offset")
