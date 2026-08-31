from __future__ import annotations

from datetime import UTC, datetime, timedelta
from time import perf_counter
from typing import Any, cast

import pytest

from forgegate.domain.enums import (
    Aggregation,
    Decision,
    EvidenceTrust,
    Operator,
    VerificationLevel,
)
from forgegate.domain.models import (
    ArtifactReference,
    EvidenceBundle,
    EvidenceRecord,
    ExecutionContext,
    PolicyConfig,
    PolicyRule,
)
from forgegate.policy import evaluate_policy
from forgegate.policy.engine import _apply_operator, _extract_value, _resolve_path
from forgegate.policy.models import PolicyEvaluation

NOW = datetime(2026, 8, 30, 16, 0, tzinfo=UTC)
COMMIT = "a" * 40


def make_record(
    *,
    evidence_id: str = "ev-01",
    kind: str = "metric.value",
    value: Any = 5,
    collected_at: datetime = NOW,
    trust: EvidenceTrust = EvidenceTrust.CLAIMED_CI_METADATA,
    verification: VerificationLevel = VerificationLevel.CI_VALIDATED,
    scope: str = "repository",
    status: str = "passed",
    unit: str | None = "count",
    source_tool: str = "test-tool",
    source_version: str = "1.0",
    tags: dict[str, str] | None = None,
    context_tags: dict[str, str] | None = None,
) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id,
        kind=kind,
        scope=scope,
        value=value,
        unit=unit,
        status=status,
        source_tool=source_tool,
        source_version=source_version,
        execution_context=ExecutionContext(
            commit_sha=COMMIT,
            operating_system="linux",
            tags=context_tags or {"runner": "hosted"},
        ),
        artifact=ArtifactReference(
            path_or_uri="artifacts/result.json",
            media_type="application/json",
            sha256="b" * 64,
            size_bytes=10,
        ),
        collected_at=collected_at,
        trust=trust,
        verification_level=verification,
        tags=tags or {"track": "pr"},
    )


def make_rule(**updates: Any) -> PolicyRule:
    values: dict[str, Any] = {
        "id": "rule-01",
        "claim": "metric.required",
        "evidence_kind": "metric.value",
        "aggregation": Aggregation.VALUE,
        "operator": Operator.EQUALS,
        "expected": 5,
        "minimum_trust": EvidenceTrust.CLAIMED_CI_METADATA,
        "minimum_verification": VerificationLevel.CI_VALIDATED,
    }
    values.update(updates)
    return PolicyRule(**values)


def run(
    rule: PolicyRule,
    records: list[EvidenceRecord] | None = None,
    *,
    evaluated_at: datetime = NOW,
) -> Any:
    policy = PolicyConfig(schema_version="forgegate.policy.v1", name="test-policy", rules=[rule])
    bundle = EvidenceBundle(
        schema_version="forgegate.evidence-bundle.v1",
        producer="tests",
        producer_version="1",
        candidate_commit=COMMIT,
        generated_at=NOW,
        evidence=records or [make_record()],
    )
    return evaluate_policy(policy, bundle, evaluated_at=evaluated_at)


def result(rule: PolicyRule, records: list[EvidenceRecord] | None = None) -> Any:
    return run(rule, records).rule_results[0]


def test_evaluation_is_deterministic_and_fingerprinted() -> None:
    first = run(make_rule())
    second = run(make_rule())

    assert first == second
    assert first.decision is Decision.PASS
    assert first.evaluation_id.startswith("sha256:")
    assert first.policy_fingerprint.startswith("sha256:")
    assert first.evidence_fingerprint.startswith("sha256:")
    assert first.candidate_commit == COMMIT
    assert first.evaluated_evidence_ids == ["ev-01"]


def test_evaluates_1000_evidence_records_under_two_seconds() -> None:
    records = [make_record(evidence_id=f"ev-{index:04d}") for index in range(1000)]
    rule = make_rule(
        aggregation=Aggregation.COUNT,
        where={"status": "passed"},
        expected=1000,
    )

    started = perf_counter()
    evaluation = run(rule, records)
    elapsed = perf_counter() - started

    assert evaluation.decision is Decision.PASS
    assert evaluation.rule_results[0].actual == 1000
    assert elapsed < 2.0


def test_evaluation_requires_explicit_aware_time() -> None:
    with pytest.raises(ValueError, match="UTC offset"):
        run(make_rule(), evaluated_at=datetime(2026, 8, 30, 16, 0))

    valid = run(make_rule()).model_dump()
    valid["evaluated_at"] = datetime(2026, 8, 30, 16, 0)
    with pytest.raises(ValueError, match="UTC offset"):
        PolicyEvaluation.model_validate(valid)

    with pytest.raises(ValueError, match="cannot precede"):
        run(make_rule(), evaluated_at=NOW - timedelta(seconds=1))


def test_expression_helpers_reject_invalid_paths_and_operators() -> None:
    record = make_record(value={"metrics": [5]})

    for field in ("", 1):
        with pytest.raises(ValueError, match="non-empty dot path"):
            _extract_value(record, field)
    assert _resolve_path(record.value, "metrics..value") == (None, False)
    assert _resolve_path(record.value, "metrics.not-an-index") == (None, False)
    assert _resolve_path(record.value, "metrics.2") == (None, False)
    assert _resolve_path(record.value, "metrics.-1") == (None, False)
    assert _apply_operator(Operator.EQUALS, None, None, present=False) is False
    assert _apply_operator(Operator.CONTAINS, "abc", 1, present=True) is False
    with pytest.raises(ValueError, match="unsupported operator"):
        _apply_operator(cast(Operator, "unsupported"), 1, 1, present=True)


@pytest.mark.parametrize(
    ("operator", "actual", "expected", "decision"),
    [
        (Operator.EQUALS, 5, 5.0, Decision.PASS),
        (Operator.EQUALS, True, 1, Decision.FAIL),
        (Operator.NOT_EQUALS, "five", 5, Decision.PASS),
        (Operator.GREATER_THAN, 5, 4, Decision.PASS),
        (Operator.GREATER_THAN_OR_EQUAL, 5, 5, Decision.PASS),
        (Operator.LESS_THAN, 4, 5, Decision.PASS),
        (Operator.LESS_THAN_OR_EQUAL, 5, 5, Decision.PASS),
        (Operator.CONTAINS, "forgegate", "gate", Decision.PASS),
        (Operator.CONTAINS, ["a", 2], 2.0, Decision.PASS),
        (Operator.CONTAINS, {"quality": 5}, "quality", Decision.PASS),
    ],
)
def test_value_operators(
    operator: Operator, actual: Any, expected: Any, decision: Decision
) -> None:
    evaluation = result(
        make_rule(operator=operator, expected=expected), [make_record(value=actual)]
    )
    assert evaluation.decision is decision


@pytest.mark.parametrize(
    ("operator", "actual", "expected", "message"),
    [
        (Operator.GREATER_THAN, "5", 4, "finite numeric operands"),
        (Operator.CONTAINS, 5, 5, "contains requires"),
        (Operator.CONTAINS, {"a": 1}, ["unhashable"], "unhashable"),
    ],
)
def test_invalid_operator_operands_fail_closed(
    operator: Operator, actual: Any, expected: Any, message: str
) -> None:
    evaluation = result(
        make_rule(operator=operator, expected=expected), [make_record(value=actual)]
    )
    assert evaluation.decision is Decision.ERROR
    assert evaluation.reason_code == "EVALUATION_ERROR"
    assert message in evaluation.explanation


def test_non_finite_input_cannot_be_fingerprinted() -> None:
    with pytest.raises(ValueError, match="must be finite"):
        make_record(value=float("inf"))
    with pytest.raises(ValueError, match="must be finite"):
        make_rule(expected=float("nan"))
    with pytest.raises(ValueError, match="keys must be strings"):
        make_record(value={1: "invalid"})
    with pytest.raises(ValueError, match="not JSON-compatible"):
        make_record(value=(1, 2))

    cyclic: list[Any] = []
    cyclic.append(cyclic)
    with pytest.raises(ValueError, match="cyclic JSON"):
        make_record(value=cyclic)

    deeply_nested: Any = None
    for _ in range(1100):
        deeply_nested = [deeply_nested]
    with pytest.raises(ValueError, match="nesting depth"):
        make_record(value=deeply_nested)

    with pytest.raises(ValueError, match="finite numeric operands"):
        _apply_operator(Operator.GREATER_THAN, float("inf"), 4, present=True)


def test_missing_required_and_optional_evidence() -> None:
    unrelated = make_record(kind="other.value")

    required = result(make_rule(on_missing=Decision.FAIL), [unrelated])
    optional = result(
        make_rule(mandatory=False, require_presence=False, on_missing=Decision.REVIEW),
        [unrelated],
    )

    assert (required.decision, required.reason_code) == (Decision.FAIL, "EVIDENCE_MISSING")
    assert (optional.decision, optional.reason_code) == (Decision.PASS, "ABSENCE_PERMITTED")


@pytest.mark.parametrize(
    "record",
    [
        make_record(trust=EvidenceTrust.UNSIGNED_LOCAL),
        make_record(verification=VerificationLevel.HOST_TESTED),
    ],
)
def test_insufficient_assurance_requires_review(record: EvidenceRecord) -> None:
    evaluation = result(make_rule(), [record])
    assert evaluation.decision is Decision.REVIEW
    assert evaluation.reason_code == "INSUFFICIENT_ASSURANCE"
    assert evaluation.evidence_ids == ["ev-01"]


@pytest.mark.parametrize(
    "collected_at",
    [NOW + timedelta(microseconds=1), NOW - timedelta(seconds=61)],
)
def test_future_or_stale_evidence_requires_review(collected_at: datetime) -> None:
    evaluation = result(make_rule(maximum_age_seconds=60), [make_record(collected_at=collected_at)])
    assert evaluation.decision is Decision.REVIEW
    assert evaluation.reason_code == "STALE_OR_FUTURE_EVIDENCE"


def test_maximum_age_boundary_is_inclusive() -> None:
    evaluation = result(
        make_rule(maximum_age_seconds=60),
        [make_record(collected_at=NOW - timedelta(seconds=60))],
    )
    assert evaluation.decision is Decision.PASS


def test_filters_cover_record_tags_context_and_nested_values() -> None:
    rule = make_rule(
        where={
            "field": "metrics.0.value",
            "scope": "repository",
            "status": "passed",
            "unit": "count",
            "source_tool": "test-tool",
            "source_version": "1.0",
            "tags.track": "pr",
            "context.tags.runner": "hosted",
            "context.operating_system": "linux",
            "meta.severity": "critical",
        }
    )
    record = make_record(value={"metrics": [{"value": 5}], "meta": {"severity": "critical"}})
    assert result(rule, [record]).decision is Decision.PASS

    null_unit = result(make_rule(where={"unit": None}), [make_record(unit=None)])
    assert null_unit.decision is Decision.PASS


@pytest.mark.parametrize(
    "where",
    [
        {"scope": "package"},
        {"unit": "percent"},
        {"tags.missing": "x"},
        {"context.tags.runner": "self-hosted"},
        {"meta.missing": "x"},
    ],
)
def test_unmatched_filter_is_missing_not_zero(where: dict[str, Any]) -> None:
    evaluation = result(
        make_rule(where={"field": "metric", **where}),
        [make_record(value={"metric": 5})],
    )
    assert evaluation.decision is Decision.REVIEW
    assert evaluation.reason_code == "EVIDENCE_MISSING"


def test_value_duplicate_agreement_and_conflict() -> None:
    same = make_record(evidence_id="ev-02")
    different = make_record(evidence_id="ev-03", value=6)

    agreed = result(make_rule(), [make_record(), same])
    conflicted = result(make_rule(), [make_record(), different])

    assert agreed.decision is Decision.PASS
    assert agreed.evidence_ids == ["ev-01", "ev-02"]
    assert conflicted.decision is Decision.REVIEW
    assert conflicted.reason_code == "CONFLICTING_VALUES"


def test_missing_value_field_is_error_except_for_exists() -> None:
    missing = make_record(value={"other": 5})

    invalid = result(make_rule(where={"field": "metric"}), [missing])
    exists_false = result(
        make_rule(where={"field": "metric"}, operator=Operator.EXISTS, expected=False),
        [missing],
    )
    exists_true = result(
        make_rule(where={"field": "other"}, operator=Operator.EXISTS, expected=True),
        [missing],
    )

    assert invalid.decision is Decision.ERROR
    assert exists_false.decision is Decision.PASS
    assert exists_false.actual is False
    assert exists_true.decision is Decision.PASS


def test_exists_rejects_non_boolean_expected_and_conflicting_presence() -> None:
    bad_expected = result(make_rule(operator=Operator.EXISTS, expected="yes"))
    conflict = result(
        make_rule(where={"field": "metric"}, operator=Operator.EXISTS, expected=True),
        [make_record(value={"metric": 5}), make_record(evidence_id="ev-02", value={})],
    )

    assert bad_expected.decision is Decision.ERROR
    assert conflict.decision is Decision.REVIEW
    assert conflict.reason_code == "CONFLICTING_VALUES"


def test_count_all_and_any_aggregations() -> None:
    records = [
        make_record(evidence_id="ev-01", value={"severity": "critical", "score": 5}),
        make_record(evidence_id="ev-02", value={"severity": "low", "score": 3}),
    ]
    counted = result(
        make_rule(
            aggregation=Aggregation.COUNT,
            where={"severity": "critical"},
            expected=1,
        ),
        records,
    )
    zero = result(
        make_rule(aggregation=Aggregation.COUNT, where={"severity": "high"}, expected=0),
        records,
    )
    all_result = result(
        make_rule(
            aggregation=Aggregation.ALL,
            where={"field": "score"},
            operator=Operator.GREATER_THAN_OR_EQUAL,
            expected=3,
        ),
        records,
    )
    any_result = result(
        make_rule(
            aggregation=Aggregation.ANY,
            where={"field": "score"},
            operator=Operator.GREATER_THAN,
            expected=4,
        ),
        records,
    )

    assert (counted.actual, counted.decision) == (1, Decision.PASS)
    assert (zero.actual, zero.decision, zero.evidence_ids) == (
        0,
        Decision.PASS,
        ["ev-01", "ev-02"],
    )
    assert all_result.decision is Decision.PASS
    assert any_result.decision is Decision.PASS


def test_all_and_any_handle_missing_selected_fields_without_vacuous_pass() -> None:
    records = [make_record(value={"score": 5}), make_record(evidence_id="ev-02", value={})]
    all_result = result(
        make_rule(
            aggregation=Aggregation.ALL,
            where={"field": "score"},
            operator=Operator.EXISTS,
            expected=True,
        ),
        records,
    )
    any_result = result(
        make_rule(
            aggregation=Aggregation.ANY,
            where={"field": "score"},
            operator=Operator.EXISTS,
            expected=True,
        ),
        records,
    )
    no_matches = result(make_rule(aggregation=Aggregation.ALL, where={"status": "failed"}), records)

    assert all_result.decision is Decision.FAIL
    assert any_result.decision is Decision.PASS
    assert no_matches.reason_code == "EVIDENCE_MISSING"


def test_count_rejects_field_selector() -> None:
    evaluation = result(make_rule(aggregation=Aggregation.COUNT, where={"field": "score"}))
    assert evaluation.decision is Decision.ERROR
    assert "count aggregation" in evaluation.explanation


def test_optional_rule_failures_do_not_block_overall_policy() -> None:
    policy = PolicyConfig(
        schema_version="forgegate.policy.v1",
        name="test-policy",
        rules=[
            make_rule(id="required", expected=5),
            make_rule(id="optional", expected=6, mandatory=False),
        ],
    )
    bundle = EvidenceBundle(
        schema_version="forgegate.evidence-bundle.v1",
        producer="tests",
        producer_version="1",
        candidate_commit=COMMIT,
        generated_at=NOW,
        evidence=[make_record()],
    )
    evaluation = evaluate_policy(policy, bundle, evaluated_at=NOW)

    assert evaluation.decision is Decision.PASS
    assert [item.decision for item in evaluation.rule_results] == [Decision.PASS, Decision.FAIL]


@pytest.mark.parametrize(
    ("decisions", "expected"),
    [
        ([Decision.PASS, Decision.REVIEW], Decision.REVIEW),
        ([Decision.REVIEW, Decision.FAIL], Decision.FAIL),
        ([Decision.FAIL, Decision.ERROR], Decision.ERROR),
    ],
)
def test_overall_decision_uses_fail_closed_precedence(
    decisions: list[Decision], expected: Decision
) -> None:
    rules: list[PolicyRule] = []
    records: list[EvidenceRecord] = []
    for index, decision in enumerate(decisions):
        rule_id = f"rule-{index}"
        kind = f"metric.value-{index}"
        if decision is Decision.REVIEW:
            rules.append(make_rule(id=rule_id, evidence_kind=kind))
            continue
        if decision is Decision.ERROR:
            rules.append(
                make_rule(
                    id=rule_id,
                    evidence_kind=kind,
                    operator=Operator.GREATER_THAN,
                    expected="invalid",
                )
            )
        else:
            rules.append(
                make_rule(
                    id=rule_id,
                    evidence_kind=kind,
                    expected=5 if decision is Decision.PASS else 6,
                )
            )
        records.append(make_record(evidence_id=f"ev-{index}", kind=kind))

    policy = PolicyConfig(schema_version="forgegate.policy.v1", name="precedence", rules=rules)
    bundle = EvidenceBundle(
        schema_version="forgegate.evidence-bundle.v1",
        producer="tests",
        producer_version="1",
        candidate_commit=COMMIT,
        generated_at=NOW,
        evidence=records or [make_record(kind="other.value")],
    )

    assert evaluate_policy(policy, bundle, evaluated_at=NOW).decision is expected
