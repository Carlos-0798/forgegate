from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest

from forgegate.candidates import (
    CandidateLifecycleError,
    CandidateTransition,
    CandidateTransitionResult,
    ReleaseCandidate,
    create_candidate,
    transition_candidate,
)
from forgegate.canonical import canonical_json, sha256_fingerprint
from forgegate.domain.enums import Aggregation, CandidateStatus, Decision, Operator
from forgegate.policy.models import PolicyEvaluation, RuleEvaluation

CREATED = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)
COMMIT = "a" * 40


def draft(**updates: Any) -> ReleaseCandidate:
    values: dict[str, Any] = {
        "project_id": "sample-api",
        "version": "1.2.0",
        "commit_sha": COMMIT,
        "source_branch": "main",
        "release_track": "pull-request",
        "created_at": CREATED,
    }
    values.update(updates)
    return create_candidate(**values)


def advance_to_evaluating() -> ReleaseCandidate:
    candidate = draft()
    for index, status in enumerate(
        (CandidateStatus.COLLECTING, CandidateStatus.READY, CandidateStatus.EVALUATING),
        start=1,
    ):
        candidate = transition_candidate(
            candidate,
            status,
            occurred_at=CREATED + timedelta(minutes=index),
        ).candidate
    return candidate


def policy_evaluation(
    decision: Decision,
    *,
    evaluated_at: datetime,
    commit: str = COMMIT,
    marker: str = "1",
) -> PolicyEvaluation:
    fingerprint = "sha256:" + marker * 64
    return PolicyEvaluation(
        evaluation_id=fingerprint,
        policy_name="pull-request",
        policy_fingerprint="sha256:" + "2" * 64,
        evidence_fingerprint="sha256:" + "3" * 64,
        candidate_commit=commit,
        evaluated_at=evaluated_at,
        decision=decision,
        rule_results=[
            RuleEvaluation(
                rule_id="rule-01",
                claim="tests.required-pass",
                decision=decision,
                mandatory=True,
                evidence_kind="test.summary",
                aggregation=Aggregation.VALUE,
                operator=Operator.EQUALS,
                expected=0,
                actual=0,
                evidence_ids=["evidence-01"],
                reason_code="RULE_RESULT",
                explanation="Synthetic lifecycle binding fixture.",
            )
        ],
        evaluated_evidence_ids=["evidence-01"],
    )


def test_create_candidate_is_deterministic_and_normalizes_identity() -> None:
    eastern = timezone(timedelta(hours=-4))
    first = draft(
        project_id=" sample-api ",
        version=" 1.2.0 ",
        commit_sha=COMMIT.upper(),
        source_branch=" main ",
        release_track=" pull-request ",
        created_at=datetime(2026, 8, 30, 8, 0, tzinfo=eastern),
    )
    second = draft()

    assert first == second
    assert first.candidate_id == "cand-dab25eb0be1a0107b3996080"
    assert first.status is CandidateStatus.DRAFT
    assert first.revision == 0
    assert first.created_at == CREATED
    assert first.updated_at == CREATED
    assert first.evaluated_at is None


def test_canonical_hashing_is_order_independent_and_rejects_non_finite() -> None:
    assert canonical_json({"b": 2, "a": 1}) == '{"a":1,"b":2}'
    assert sha256_fingerprint({"a": 1}) == sha256_fingerprint({"a": 1})
    with pytest.raises(ValueError, match="Out of range float values"):
        canonical_json(float("inf"))


def test_create_rejects_naive_time_and_invalid_identity() -> None:
    with pytest.raises(CandidateLifecycleError, match="CANDIDATE_TIMESTAMP_NAIVE"):
        draft(created_at=datetime(2026, 8, 30, 12, 0))
    with pytest.raises(ValueError, match="project_id"):
        draft(project_id="INVALID")


@pytest.mark.parametrize(
    "terminal",
    [
        CandidateStatus.PASS,
        CandidateStatus.FAIL,
        CandidateStatus.REVIEW,
        CandidateStatus.ERROR,
    ],
)
def test_complete_legal_lifecycle_emits_auditable_terminal_event(
    terminal: CandidateStatus,
) -> None:
    evaluating = advance_to_evaluating()
    evaluated_at = CREATED + timedelta(minutes=4)
    result = transition_candidate(
        evaluating,
        terminal,
        occurred_at=evaluated_at,
        reason=" policy evaluation completed ",
        evaluation=policy_evaluation(Decision(terminal.value), evaluated_at=evaluated_at),
    )

    assert evaluating.status is CandidateStatus.EVALUATING
    assert result.candidate.status is terminal
    assert result.candidate.revision == 4
    assert result.candidate.evaluated_at == CREATED + timedelta(minutes=4)
    assert result.transition.reason == "policy evaluation completed"
    assert result.transition.from_status is CandidateStatus.EVALUATING
    assert result.transition.to_status is terminal
    assert result.transition.from_revision == 3
    assert result.transition.to_revision == 4
    assert result.candidate.evaluation_id == "sha256:" + "1" * 64
    assert result.transition.evaluation_id == result.candidate.evaluation_id
    assert result.transition.transition_id.startswith("sha256:")
    assert result.transition.prior_candidate_fingerprint == sha256_fingerprint(
        evaluating.model_dump(mode="json")
    )
    assert result.transition.result_candidate_fingerprint == sha256_fingerprint(
        result.candidate.model_dump(mode="json")
    )


def test_transition_is_deterministic_and_allows_equal_timestamps() -> None:
    candidate = draft()
    first = transition_candidate(
        candidate,
        CandidateStatus.COLLECTING,
        occurred_at=CREATED,
        reason=None,
    )
    second = transition_candidate(
        candidate,
        CandidateStatus.COLLECTING,
        occurred_at=CREATED,
        reason=None,
    )
    assert first == second
    assert first.candidate.evaluated_at is None


@pytest.mark.parametrize(
    ("candidate_factory", "target"),
    [
        (draft, CandidateStatus.READY),
        (draft, CandidateStatus.DRAFT),
        (advance_to_evaluating, CandidateStatus.COLLECTING),
        (
            lambda: (
                transition_candidate(
                    advance_to_evaluating(),
                    CandidateStatus.PASS,
                    occurred_at=CREATED + timedelta(minutes=4),
                    evaluation=policy_evaluation(
                        Decision.PASS,
                        evaluated_at=CREATED + timedelta(minutes=4),
                    ),
                ).candidate
            ),
            CandidateStatus.COLLECTING,
        ),
    ],
)
def test_illegal_or_terminal_transition_fails_closed(
    candidate_factory: Any, target: CandidateStatus
) -> None:
    with pytest.raises(CandidateLifecycleError, match="CANDIDATE_TRANSITION_INVALID"):
        transition_candidate(
            candidate_factory(),
            target,
            occurred_at=CREATED + timedelta(minutes=10),
        )


def test_transition_rejects_time_regression_naive_time_and_blank_reason() -> None:
    collecting = transition_candidate(
        draft(), CandidateStatus.COLLECTING, occurred_at=CREATED + timedelta(minutes=1)
    ).candidate
    with pytest.raises(CandidateLifecycleError, match="CANDIDATE_TIME_REGRESSION"):
        transition_candidate(collecting, CandidateStatus.READY, occurred_at=CREATED)
    with pytest.raises(CandidateLifecycleError, match="CANDIDATE_TIMESTAMP_NAIVE"):
        transition_candidate(
            collecting,
            CandidateStatus.READY,
            occurred_at=datetime(2026, 8, 30, 12, 2),
        )
    with pytest.raises(CandidateLifecycleError, match="CANDIDATE_REASON_EMPTY"):
        transition_candidate(
            collecting,
            CandidateStatus.READY,
            occurred_at=CREATED + timedelta(minutes=2),
            reason="  ",
        )


def test_terminal_transitions_require_matching_policy_evaluation() -> None:
    evaluating = advance_to_evaluating()
    terminal_time = CREATED + timedelta(minutes=4)

    with pytest.raises(CandidateLifecycleError, match="CANDIDATE_EVALUATION_REQUIRED"):
        transition_candidate(evaluating, CandidateStatus.PASS, occurred_at=terminal_time)
    with pytest.raises(CandidateLifecycleError, match="CANDIDATE_EVALUATION_COMMIT_MISMATCH"):
        transition_candidate(
            evaluating,
            CandidateStatus.PASS,
            occurred_at=terminal_time,
            evaluation=policy_evaluation(
                Decision.PASS, evaluated_at=terminal_time, commit="b" * 40
            ),
        )
    with pytest.raises(CandidateLifecycleError, match="CANDIDATE_EVALUATION_DECISION_MISMATCH"):
        transition_candidate(
            evaluating,
            CandidateStatus.PASS,
            occurred_at=terminal_time,
            evaluation=policy_evaluation(Decision.FAIL, evaluated_at=terminal_time),
        )
    with pytest.raises(CandidateLifecycleError, match="CANDIDATE_EVALUATION_TIME_MISMATCH"):
        transition_candidate(
            evaluating,
            CandidateStatus.PASS,
            occurred_at=terminal_time,
            evaluation=policy_evaluation(
                Decision.PASS, evaluated_at=terminal_time + timedelta(seconds=1)
            ),
        )

    valid_pass = transition_candidate(
        evaluating,
        CandidateStatus.PASS,
        occurred_at=terminal_time,
        evaluation=policy_evaluation(Decision.PASS, evaluated_at=terminal_time),
    )
    with pytest.raises(ValueError, match="transition requires evaluation_id"):
        CandidateTransition.model_validate(
            {**valid_pass.transition.model_dump(), "evaluation_id": None}
        )

    error_result = transition_candidate(
        evaluating, CandidateStatus.ERROR, occurred_at=terminal_time
    )
    assert error_result.candidate.evaluation_id is None

    with pytest.raises(CandidateLifecycleError, match="CANDIDATE_EVALUATION_UNEXPECTED"):
        transition_candidate(
            draft(),
            CandidateStatus.COLLECTING,
            occurred_at=CREATED + timedelta(minutes=1),
            evaluation=policy_evaluation(
                Decision.PASS, evaluated_at=CREATED + timedelta(minutes=1)
            ),
        )


def candidate_payload(**updates: Any) -> dict[str, Any]:
    payload = draft().model_dump(mode="python")
    payload.update(updates)
    return payload


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"updated_at": CREATED - timedelta(seconds=1)}, "cannot precede"),
        ({"status": CandidateStatus.COLLECTING, "revision": 0}, "revision"),
        (
            {
                "status": CandidateStatus.PASS,
                "revision": 4,
                "evaluated_at": None,
                "evaluation_id": "sha256:" + "1" * 64,
            },
            "requires evaluated_at",
        ),
        (
            {
                "status": CandidateStatus.PASS,
                "revision": 4,
                "updated_at": CREATED + timedelta(seconds=2),
                "evaluated_at": CREATED - timedelta(seconds=1),
                "evaluation_id": "sha256:" + "1" * 64,
            },
            "within the candidate lifetime",
        ),
        ({"evaluated_at": CREATED}, "non-terminal"),
        (
            {
                "status": CandidateStatus.PASS,
                "revision": 4,
                "evaluated_at": CREATED,
            },
            "requires evaluation_id",
        ),
        ({"evaluation_id": "sha256:" + "1" * 64}, "non-terminal candidate"),
    ],
)
def test_candidate_model_rejects_inconsistent_lifecycle_fields(
    updates: dict[str, Any], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        ReleaseCandidate.model_validate(candidate_payload(**updates))


@pytest.mark.parametrize("field", ["created_at", "updated_at", "evaluated_at"])
def test_candidate_model_rejects_naive_timestamps(field: str) -> None:
    payload = candidate_payload()
    payload[field] = datetime(2026, 8, 30, 12, 0)
    with pytest.raises(ValueError, match="UTC offset"):
        ReleaseCandidate.model_validate(payload)


def test_transition_models_reject_inconsistent_documents() -> None:
    valid = transition_candidate(
        draft(), CandidateStatus.COLLECTING, occurred_at=CREATED + timedelta(minutes=1)
    )
    event = valid.transition.model_dump(mode="python")

    invalid_revision = {**event, "to_revision": 3}
    with pytest.raises(ValueError, match="increment revision"):
        CandidateTransition.model_validate(invalid_revision)

    illegal = {
        **event,
        "from_status": CandidateStatus.DRAFT,
        "to_status": CandidateStatus.READY,
        "from_revision": 0,
        "to_revision": 1,
    }
    with pytest.raises(ValueError, match="illegal candidate transition"):
        CandidateTransition.model_validate(illegal)

    wrong_status_revisions = {**event, "from_revision": 1, "to_revision": 2}
    with pytest.raises(ValueError, match="revisions do not match"):
        CandidateTransition.model_validate(wrong_status_revisions)

    same_fingerprints = {
        **event,
        "result_candidate_fingerprint": event["prior_candidate_fingerprint"],
    }
    with pytest.raises(ValueError, match="fingerprints must differ"):
        CandidateTransition.model_validate(same_fingerprints)

    unexpected_evaluation = {**event, "evaluation_id": "sha256:" + "1" * 64}
    with pytest.raises(ValueError, match="non-terminal transition"):
        CandidateTransition.model_validate(unexpected_evaluation)

    with pytest.raises(ValueError, match="transition_id does not match"):
        CandidateTransition.model_validate({**event, "transition_id": "sha256:" + "0" * 64})

    with pytest.raises(ValueError, match="UTC offset"):
        CandidateTransition.model_validate({**event, "occurred_at": datetime(2026, 8, 30, 12, 1)})


def test_transition_result_rejects_mismatched_candidate_event() -> None:
    valid = transition_candidate(
        draft(), CandidateStatus.COLLECTING, occurred_at=CREATED + timedelta(minutes=1)
    )
    other = transition_candidate(
        draft(version="2.0.0"),
        CandidateStatus.COLLECTING,
        occurred_at=CREATED + timedelta(minutes=1),
    )
    with pytest.raises(ValueError, match="candidate_id does not match"):
        CandidateTransitionResult(candidate=valid.candidate, transition=other.transition)

    ready = transition_candidate(
        valid.candidate,
        CandidateStatus.READY,
        occurred_at=CREATED + timedelta(minutes=2),
    ).candidate
    with pytest.raises(ValueError, match="result state does not match"):
        CandidateTransitionResult(candidate=ready, transition=valid.transition)

    shifted_candidate = ReleaseCandidate.model_validate(
        {**valid.candidate.model_dump(), "updated_at": CREATED + timedelta(minutes=2)}
    )
    with pytest.raises(ValueError, match="transition time"):
        CandidateTransitionResult(candidate=shifted_candidate, transition=valid.transition)

    wrong_fingerprint_payload = {
        **valid.transition.model_dump(mode="json"),
        "result_candidate_fingerprint": "sha256:" + "0" * 64,
    }
    wrong_fingerprint_identity = {
        key: value
        for key, value in wrong_fingerprint_payload.items()
        if key not in {"schema_version", "transition_id"}
    }
    wrong_fingerprint_payload["transition_id"] = sha256_fingerprint(wrong_fingerprint_identity)
    wrong_fingerprint = CandidateTransition.model_validate(wrong_fingerprint_payload)
    with pytest.raises(ValueError, match="fingerprint"):
        CandidateTransitionResult(candidate=valid.candidate, transition=wrong_fingerprint)


def test_transition_result_rejects_mismatched_evaluation_binding() -> None:
    evaluating = advance_to_evaluating()
    terminal_time = CREATED + timedelta(minutes=4)
    first = transition_candidate(
        evaluating,
        CandidateStatus.PASS,
        occurred_at=terminal_time,
        evaluation=policy_evaluation(Decision.PASS, evaluated_at=terminal_time, marker="1"),
    )
    second = transition_candidate(
        evaluating,
        CandidateStatus.PASS,
        occurred_at=terminal_time,
        evaluation=policy_evaluation(Decision.PASS, evaluated_at=terminal_time, marker="4"),
    )
    with pytest.raises(ValueError, match="evaluation_id does not match"):
        CandidateTransitionResult(
            candidate=first.candidate,
            transition=second.transition,
        )
