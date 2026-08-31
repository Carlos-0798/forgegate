from __future__ import annotations

import json
from datetime import UTC, datetime
from html import escape

from forgegate.attestations.models import ReleaseAttestation
from forgegate.candidates.models import CandidateDocument, CandidateTransition
from forgegate.canonical import sha256_fingerprint
from forgegate.policy.models import PolicyEvaluationDocument


class AttestationError(ValueError):
    """Stable failure at the deterministic attestation boundary."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


def create_release_attestation(
    candidate: CandidateDocument,
    transitions: tuple[CandidateTransition, ...],
    *,
    policy_evaluation: PolicyEvaluationDocument | None,
    issued_at: datetime,
    generator_version: str,
) -> ReleaseAttestation:
    timestamp = _normalized_timestamp(issued_at)
    candidate_fingerprint = sha256_fingerprint(candidate.model_dump(mode="json"))
    transition_list = list(transitions)
    transition_chain_fingerprint = sha256_fingerprint(
        [transition.transition_id for transition in transitions]
    )
    evaluation_fingerprint = (
        sha256_fingerprint(policy_evaluation.model_dump(mode="json"))
        if policy_evaluation is not None
        else None
    )
    identity = {
        "generator": "forgegate",
        "generator_version": generator_version,
        "assurance": "unsigned_local",
        "issued_at": _json_timestamp(timestamp),
        "candidate": candidate.model_dump(mode="json"),
        "candidate_fingerprint": candidate_fingerprint,
        "transitions": [transition.model_dump(mode="json") for transition in transitions],
        "transition_chain_fingerprint": transition_chain_fingerprint,
        "policy_evaluation": (
            policy_evaluation.model_dump(mode="json") if policy_evaluation is not None else None
        ),
        "evaluation_fingerprint": evaluation_fingerprint,
    }
    return ReleaseAttestation(
        attestation_id=sha256_fingerprint(identity),
        generator_version=generator_version,
        issued_at=timestamp,
        candidate=candidate,
        candidate_fingerprint=candidate_fingerprint,
        transitions=transition_list,
        transition_chain_fingerprint=transition_chain_fingerprint,
        policy_evaluation=policy_evaluation,
        evaluation_fingerprint=evaluation_fingerprint,
    )


def render_attestation_json(attestation: ReleaseAttestation) -> str:
    return (
        json.dumps(
            attestation.model_dump(mode="json"),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n"
    )


def render_attestation_markdown(attestation: ReleaseAttestation) -> str:
    candidate = attestation.candidate
    lines = [
        "# ForgeGate release attestation",
        "",
        "> This is an unsigned local ForgeGate record. It establishes content",
        "> consistency and association, not producer identity or authorization.",
        "",
        "## Release decision",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Decision | {_cell(candidate.status.value)} |",
        f"| Project | {_cell(candidate.project_id)} |",
        f"| Version | {_cell(candidate.version)} |",
        f"| Commit | {_cell(candidate.commit_sha)} |",
        f"| Branch | {_cell(candidate.source_branch)} |",
        f"| Release track | {_cell(candidate.release_track)} |",
        f"| Candidate ID | {_cell(candidate.candidate_id)} |",
        f"| Candidate fingerprint | {_cell(attestation.candidate_fingerprint)} |",
        f"| Evaluation ID | {_cell(candidate.evaluation_id)} |",
        f"| Terminal time | {_cell(_json_timestamp(candidate.updated_at))} |",
        f"| Issued at | {_cell(_json_timestamp(attestation.issued_at))} |",
        f"| Attestation ID | {_cell(attestation.attestation_id)} |",
        f"| Assurance | {_cell(attestation.assurance)} |",
        "",
        "## Candidate transition chain",
        "",
        "| Revision | Transition | State | Occurred at |",
        "|---:|---|---|---|",
    ]
    lines.extend(
        f"| {transition.to_revision} | {_cell(transition.transition_id)} | "
        f"{_cell(transition.to_status.value)} | {_cell(_json_timestamp(transition.occurred_at))} |"
        for transition in attestation.transitions
    )
    lines.extend(
        [
            "",
            f"Transition-chain fingerprint: {_cell(attestation.transition_chain_fingerprint)}",
            "",
            "## Policy evaluation",
            "",
        ]
    )
    evaluation = attestation.policy_evaluation
    if evaluation is None:
        lines.append("No policy evaluation was produced for this fail-closed ERROR outcome.")
    else:
        lines.extend(
            [
                f"Policy: {_cell(evaluation.policy_name)}",
                "",
                f"Evaluation fingerprint: {_cell(attestation.evaluation_fingerprint)}",
                "",
                "| Rule | Decision | Mandatory | Reason |",
                "|---|---|---|---|",
            ]
        )
        lines.extend(
            f"| {_cell(result.rule_id)} | {_cell(result.decision.value)} | "
            f"{_cell(str(result.mandatory).lower())} | {_cell(result.reason_code)} |"
            for result in evaluation.rule_results
        )
        lines.extend(["", "Evaluated evidence IDs:", ""])
        lines.extend(f"- {_cell(evidence_id)}" for evidence_id in evaluation.evaluated_evidence_ids)
    lines.extend(
        [
            "",
            "## Generator",
            "",
            f"ForgeGate version: {_cell(attestation.generator_version)}",
            "",
        ]
    )
    return "\n".join(lines)


def _normalized_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise AttestationError("ATTESTATION_TIMESTAMP_NAIVE", "issued_at must include a UTC offset")
    return value.astimezone(UTC)


def _json_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _cell(value: object | None) -> str:
    if value is None:
        return "—"
    return (
        escape(str(value), quote=False)
        .replace("\\", "\\\\")
        .replace("|", "\\|")
        .replace("`", "\\`")
        .replace("\r", "\\r")
        .replace("\n", "\\n")
    )
