from __future__ import annotations

from datetime import UTC, datetime

from forgegate.candidates.models import (
    ALLOWED_CANDIDATE_TRANSITIONS,
    TERMINAL_CANDIDATE_STATUSES,
    CandidateTransition,
    CandidateTransitionResult,
    ReleaseCandidate,
)
from forgegate.canonical import sha256_fingerprint
from forgegate.domain.enums import CandidateStatus
from forgegate.policy.models import PolicyEvaluation


class CandidateLifecycleError(ValueError):
    """A stable, user-facing candidate lifecycle failure."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


def create_candidate(
    *,
    project_id: str,
    version: str,
    commit_sha: str,
    source_branch: str,
    release_track: str,
    created_at: datetime,
) -> ReleaseCandidate:
    timestamp = _normalized_timestamp(created_at, field_name="created_at")
    identity = {
        "project_id": project_id.strip(),
        "version": version.strip(),
        "commit_sha": commit_sha.lower(),
        "source_branch": source_branch.strip(),
        "release_track": release_track.strip(),
        "created_at": _json_timestamp(timestamp),
    }
    candidate_id = "cand-" + sha256_fingerprint(identity).removeprefix("sha256:")[:24]
    return ReleaseCandidate(
        candidate_id=candidate_id,
        project_id=identity["project_id"],
        version=identity["version"],
        commit_sha=identity["commit_sha"],
        source_branch=identity["source_branch"],
        release_track=identity["release_track"],
        created_at=timestamp,
        updated_at=timestamp,
    )


def transition_candidate(
    candidate: ReleaseCandidate,
    to_status: CandidateStatus,
    *,
    occurred_at: datetime,
    reason: str | None = None,
    evaluation: PolicyEvaluation | None = None,
) -> CandidateTransitionResult:
    timestamp = _normalized_timestamp(occurred_at, field_name="occurred_at")
    if to_status not in ALLOWED_CANDIDATE_TRANSITIONS[candidate.status]:
        raise CandidateLifecycleError(
            "CANDIDATE_TRANSITION_INVALID",
            f"{candidate.status} cannot transition to {to_status}",
        )
    if timestamp < candidate.updated_at:
        raise CandidateLifecycleError(
            "CANDIDATE_TIME_REGRESSION",
            "transition time cannot precede the candidate's updated_at",
        )
    normalized_reason = _normalized_reason(reason)
    evaluation_id = _validated_evaluation_id(
        candidate,
        to_status,
        timestamp=timestamp,
        evaluation=evaluation,
    )
    next_values = candidate.model_dump(mode="python")
    next_values.update(
        status=to_status,
        revision=candidate.revision + 1,
        updated_at=timestamp,
        evaluated_at=(timestamp if to_status in TERMINAL_CANDIDATE_STATUSES else None),
        evaluation_id=evaluation_id,
    )
    next_candidate = ReleaseCandidate.model_validate(next_values)
    prior_fingerprint = sha256_fingerprint(candidate.model_dump(mode="json"))
    result_fingerprint = sha256_fingerprint(next_candidate.model_dump(mode="json"))
    event_values = {
        "candidate_id": candidate.candidate_id,
        "from_status": candidate.status,
        "to_status": to_status,
        "from_revision": candidate.revision,
        "to_revision": next_candidate.revision,
        "prior_candidate_fingerprint": prior_fingerprint,
        "result_candidate_fingerprint": result_fingerprint,
        "occurred_at": _json_timestamp(timestamp),
        "evaluation_id": evaluation_id,
        "reason": normalized_reason,
    }
    transition = CandidateTransition(
        transition_id=sha256_fingerprint(event_values),
        candidate_id=candidate.candidate_id,
        from_status=candidate.status,
        to_status=to_status,
        from_revision=candidate.revision,
        to_revision=next_candidate.revision,
        prior_candidate_fingerprint=prior_fingerprint,
        result_candidate_fingerprint=result_fingerprint,
        occurred_at=timestamp,
        evaluation_id=evaluation_id,
        reason=normalized_reason,
    )
    return CandidateTransitionResult(candidate=next_candidate, transition=transition)


def _normalized_timestamp(value: datetime, *, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise CandidateLifecycleError(
            "CANDIDATE_TIMESTAMP_NAIVE", f"{field_name} must include a UTC offset"
        )
    return value.astimezone(UTC)


def _normalized_reason(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        raise CandidateLifecycleError("CANDIDATE_REASON_EMPTY", "transition reason cannot be blank")
    return normalized


def _json_timestamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _validated_evaluation_id(
    candidate: ReleaseCandidate,
    to_status: CandidateStatus,
    *,
    timestamp: datetime,
    evaluation: PolicyEvaluation | None,
) -> str | None:
    if to_status not in TERMINAL_CANDIDATE_STATUSES:
        if evaluation is not None:
            raise CandidateLifecycleError(
                "CANDIDATE_EVALUATION_UNEXPECTED",
                "non-terminal transition cannot bind a policy evaluation",
            )
        return None
    if evaluation is None:
        if to_status is CandidateStatus.ERROR:
            return None
        raise CandidateLifecycleError(
            "CANDIDATE_EVALUATION_REQUIRED",
            f"{to_status} transition requires a policy evaluation",
        )
    if evaluation.candidate_commit.lower() != candidate.commit_sha.lower():
        raise CandidateLifecycleError(
            "CANDIDATE_EVALUATION_COMMIT_MISMATCH",
            "policy evaluation commit does not match candidate",
        )
    if evaluation.policy_name != candidate.release_track:
        raise CandidateLifecycleError(
            "CANDIDATE_EVALUATION_POLICY_MISMATCH",
            "policy evaluation name does not match the candidate release track",
        )
    if evaluation.decision.value != to_status.value:
        raise CandidateLifecycleError(
            "CANDIDATE_EVALUATION_DECISION_MISMATCH",
            "policy evaluation decision does not match target status",
        )
    if evaluation.evaluated_at.astimezone(UTC) != timestamp:
        raise CandidateLifecycleError(
            "CANDIDATE_EVALUATION_TIME_MISMATCH",
            "transition time must equal policy evaluation time",
        )
    return evaluation.evaluation_id
