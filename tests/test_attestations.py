from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

import forgegate.attestations.publisher as publisher_module
import forgegate.candidates as candidates_package
from forgegate.attestations import (
    AttestationError,
    AttestationPublishError,
    ReleaseAttestation,
    create_release_attestation,
    publish_attestation_bundle,
    render_attestation_json,
    render_attestation_markdown,
)
from forgegate.candidates import create_candidate, transition_candidate
from forgegate.candidates.models import CandidateTransition, ReleaseCandidate
from forgegate.canonical import sha256_fingerprint
from forgegate.domain.enums import Aggregation, CandidateStatus, Decision, Operator
from forgegate.policy.models import PolicyEvaluation, RuleEvaluation

CREATED = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)
TERMINAL_TIME = datetime(2026, 8, 30, 21, 0, tzinfo=UTC)
ISSUED = datetime(2026, 8, 31, 1, 0, tzinfo=UTC)
COMMIT = "a" * 40


def evaluation(
    decision: Decision,
    *,
    evaluated_at: datetime = TERMINAL_TIME,
    rule_decision: Decision | None = None,
    evidence_ids: list[str] | None = None,
) -> PolicyEvaluation:
    policy_fingerprint = "sha256:" + "2" * 64
    evidence_fingerprint = "sha256:" + "3" * 64
    evaluation_id = sha256_fingerprint(
        {
            "policy_fingerprint": policy_fingerprint,
            "evidence_fingerprint": evidence_fingerprint,
            "evaluated_at": evaluated_at.isoformat(),
        }
    )
    referenced = ["evidence-01"] if evidence_ids is None else evidence_ids
    return PolicyEvaluation(
        evaluation_id=evaluation_id,
        policy_name="pull-request",
        policy_fingerprint=policy_fingerprint,
        evidence_fingerprint=evidence_fingerprint,
        candidate_commit=COMMIT,
        evaluated_at=evaluated_at,
        decision=decision,
        rule_results=[
            RuleEvaluation(
                rule_id="rule-01",
                claim="tests.required-pass",
                decision=rule_decision or decision,
                mandatory=True,
                evidence_kind="test.summary",
                aggregation=Aggregation.VALUE,
                operator=Operator.EQUALS,
                expected=0,
                actual=0,
                evidence_ids=referenced,
                reason_code="RULE_RESULT",
                explanation="deterministic attestation fixture",
            )
        ],
        evaluated_evidence_ids=sorted(set(referenced)),
    )


def terminal_history(
    decision: Decision = Decision.PASS,
    *,
    with_evaluation: bool = True,
    version: str = "1.2.0",
) -> tuple[ReleaseCandidate, tuple[CandidateTransition, ...], PolicyEvaluation | None]:
    candidate = create_candidate(
        project_id="sample-api",
        version=version,
        commit_sha=COMMIT,
        source_branch="main",
        release_track="pull-request",
        created_at=CREATED,
    )
    transitions: list[CandidateTransition] = []
    for index, status in enumerate(
        (CandidateStatus.COLLECTING, CandidateStatus.READY, CandidateStatus.EVALUATING),
        start=1,
    ):
        result = transition_candidate(
            candidate, status, occurred_at=CREATED + timedelta(minutes=index)
        )
        candidate = result.candidate
        transitions.append(result.transition)
    policy_evaluation = evaluation(decision) if with_evaluation else None
    result = transition_candidate(
        candidate,
        CandidateStatus(decision.value),
        occurred_at=TERMINAL_TIME,
        evaluation=policy_evaluation,
        reason="policy completed" if policy_evaluation is not None else "evaluation failed",
    )
    transitions.append(result.transition)
    return result.candidate, tuple(transitions), policy_evaluation


def attestation(
    decision: Decision = Decision.PASS,
    *,
    with_evaluation: bool = True,
    version: str = "1.2.0",
) -> ReleaseAttestation:
    candidate, transitions, policy_evaluation = terminal_history(
        decision, with_evaluation=with_evaluation, version=version
    )
    return create_release_attestation(
        candidate,
        transitions,
        policy_evaluation=policy_evaluation,
        issued_at=ISSUED,
        generator_version="0.1.0.dev8",
    )


def mutate(source: ReleaseAttestation, **updates: Any) -> dict[str, Any]:
    values = source.model_dump(mode="python")
    values.update(updates)
    return values


def test_attestation_is_deterministic_and_matches_committed_goldens(
    repository_root: Path,
) -> None:
    first = attestation()
    second = attestation()
    json_output = render_attestation_json(first)
    markdown = render_attestation_markdown(first)

    assert first == second
    assert json.loads(json_output) == first.model_dump(mode="json")
    assert json_output.endswith("\n")
    assert "# ForgeGate release attestation" in markdown
    assert "unsigned local ForgeGate record" in markdown
    assert "| rule-01 | PASS | true | RULE_RESULT |" in markdown
    assert "- evidence-01" in markdown
    assert markdown.endswith("\n")
    assert json_output == (
        repository_root / "tests/golden/release_attestation_pass.json"
    ).read_text(encoding="utf-8")
    assert markdown == (repository_root / "tests/golden/release_attestation_pass.md").read_text(
        encoding="utf-8"
    )


def test_fail_closed_error_attestation_needs_no_evaluation() -> None:
    result = attestation(Decision.ERROR, with_evaluation=False)
    markdown = render_attestation_markdown(result)

    assert result.policy_evaluation is None
    assert result.evaluation_fingerprint is None
    assert "No policy evaluation was produced" in markdown


def test_markdown_escapes_untrusted_candidate_text() -> None:
    result = attestation(version="1.2|`preview`\nline<script>")
    markdown = render_attestation_markdown(result)
    assert "1.2\\|\\`preview\\`\\nline&lt;script&gt;" in markdown


def test_attestation_rejects_naive_or_early_issue_time() -> None:
    candidate, transitions, policy_evaluation = terminal_history()
    with pytest.raises(AttestationError, match="ATTESTATION_TIMESTAMP_NAIVE"):
        create_release_attestation(
            candidate,
            transitions,
            policy_evaluation=policy_evaluation,
            issued_at=datetime(2026, 8, 31, 1, 0),
            generator_version="0.1.0.dev8",
        )
    result = attestation()
    with pytest.raises(ValidationError, match="issued_at must include"):
        ReleaseAttestation.model_validate(mutate(result, issued_at=datetime(2026, 8, 31, 1, 0)))
    with pytest.raises(ValidationError, match="issued_at cannot precede"):
        create_release_attestation(
            candidate,
            transitions,
            policy_evaluation=policy_evaluation,
            issued_at=CREATED,
            generator_version="0.1.0.dev8",
        )


def test_attestation_rejects_nonterminal_candidate_and_bad_fingerprints() -> None:
    result = attestation()
    draft = create_candidate(
        project_id="sample-api",
        version="1.2.0",
        commit_sha=COMMIT,
        source_branch="main",
        release_track="pull-request",
        created_at=CREATED,
    )
    with pytest.raises(ValidationError, match="terminal revision-four"):
        ReleaseAttestation.model_validate(mutate(result, candidate=draft))
    detached_candidate = result.candidate.model_copy(update={"candidate_id": "cand-" + "0" * 24})
    with pytest.raises(ValidationError, match="candidate_id does not match"):
        ReleaseAttestation.model_validate(mutate(result, candidate=detached_candidate))
    with pytest.raises(ValidationError, match="candidate_fingerprint"):
        ReleaseAttestation.model_validate(
            mutate(result, candidate_fingerprint="sha256:" + "0" * 64)
        )
    with pytest.raises(ValidationError, match="transition_chain_fingerprint"):
        ReleaseAttestation.model_validate(
            mutate(result, transition_chain_fingerprint="sha256:" + "0" * 64)
        )
    with pytest.raises(ValidationError, match="attestation_id"):
        ReleaseAttestation.model_validate(mutate(result, attestation_id="sha256:" + "0" * 64))


def test_attestation_rejects_detached_transition_chains() -> None:
    result = attestation()
    _, alternate, _ = terminal_history(version="2.0.0")
    with pytest.raises(ValidationError, match="candidate ID"):
        ReleaseAttestation.model_validate(mutate(result, transitions=list(alternate)))

    candidate, original, policy_evaluation = terminal_history()
    collecting = transition_candidate(
        create_candidate(
            project_id="sample-api",
            version="1.2.0",
            commit_sha=COMMIT,
            source_branch="main",
            release_track="pull-request",
            created_at=CREATED,
        ),
        CandidateStatus.COLLECTING,
        occurred_at=CREATED + timedelta(seconds=30),
    ).transition
    broken = (collecting, *original[1:])
    with pytest.raises(ValidationError, match="reconstructed candidate snapshots"):
        create_release_attestation(
            candidate,
            broken,
            policy_evaluation=policy_evaluation,
            issued_at=ISSUED,
            generator_version="0.1.0.dev8",
        )

    fail_candidate, fail_transitions, _ = terminal_history(Decision.FAIL)
    assert fail_candidate.status is CandidateStatus.FAIL
    with pytest.raises(ValidationError, match="terminal transition"):
        ReleaseAttestation.model_validate(
            mutate(result, transitions=[*original[:3], fail_transitions[-1]])
        )

    regression_values = original[1].model_dump(mode="json")
    regression_values["occurred_at"] = (
        (CREATED + timedelta(seconds=30)).isoformat().replace("+00:00", "Z")
    )
    regression_values["transition_id"] = sha256_fingerprint(
        {
            key: value
            for key, value in regression_values.items()
            if key not in {"schema_version", "transition_id"}
        }
    )
    regression = CandidateTransition.model_validate(regression_values)
    with pytest.raises(ValidationError, match="reconstructed candidate snapshots"):
        create_release_attestation(
            candidate,
            (original[0], regression, *original[2:]),
            policy_evaluation=policy_evaluation,
            issued_at=ISSUED,
            generator_version="0.1.0.dev8",
        )


def test_attestation_rejects_missing_or_detached_evaluation() -> None:
    result = attestation()
    with pytest.raises(ValidationError, match="requires its policy evaluation"):
        ReleaseAttestation.model_validate(
            mutate(result, policy_evaluation=None, evaluation_fingerprint=None)
        )
    with pytest.raises(ValidationError, match="evaluation_fingerprint"):
        ReleaseAttestation.model_validate(
            mutate(result, evaluation_fingerprint="sha256:" + "0" * 64)
        )

    error_result = attestation(Decision.ERROR, with_evaluation=False)
    with pytest.raises(ValidationError, match="evaluation_fingerprint requires"):
        ReleaseAttestation.model_validate(
            mutate(error_result, evaluation_fingerprint="sha256:" + "0" * 64)
        )


def test_attestation_rejects_malformed_policy_evaluation_semantics() -> None:
    result = attestation()
    valid = result.policy_evaluation
    assert valid is not None

    bad_id_values = valid.model_dump(mode="python")
    bad_id_values["evaluation_id"] = "sha256:" + "0" * 64
    bad_id = PolicyEvaluation.model_validate(bad_id_values)
    with pytest.raises(ValidationError, match="does not match the terminal candidate"):
        create_release_attestation(
            result.candidate,
            tuple(result.transitions),
            policy_evaluation=bad_id,
            issued_at=ISSUED,
            generator_version="0.1.0.dev8",
        )

    changed_input_values = valid.model_dump(mode="python")
    changed_input_values["policy_fingerprint"] = "sha256:" + "9" * 64
    changed_input = PolicyEvaluation.model_validate(changed_input_values)
    with pytest.raises(ValidationError, match="declared inputs and time"):
        create_release_attestation(
            result.candidate,
            tuple(result.transitions),
            policy_evaluation=changed_input,
            issued_at=ISSUED,
            generator_version="0.1.0.dev8",
        )

    duplicate_values = valid.model_dump(mode="python")
    duplicate_values["rule_results"] = [valid.rule_results[0], valid.rule_results[0]]
    duplicate = PolicyEvaluation.model_validate(duplicate_values)
    with pytest.raises(ValidationError, match="rule IDs must be unique"):
        create_release_attestation(
            result.candidate,
            tuple(result.transitions),
            policy_evaluation=duplicate,
            issued_at=ISSUED,
            generator_version="0.1.0.dev8",
        )

    evidence_values = valid.model_dump(mode="python")
    evidence_values["evaluated_evidence_ids"] = []
    inconsistent_evidence = PolicyEvaluation.model_validate(evidence_values)
    with pytest.raises(ValidationError, match="evidence references"):
        create_release_attestation(
            result.candidate,
            tuple(result.transitions),
            policy_evaluation=inconsistent_evidence,
            issued_at=ISSUED,
            generator_version="0.1.0.dev8",
        )

    decision_values = valid.model_dump(mode="python")
    decision_values["rule_results"] = [
        valid.rule_results[0].model_copy(update={"decision": Decision.FAIL})
    ]
    inconsistent_decision = PolicyEvaluation.model_validate(decision_values)
    with pytest.raises(ValidationError, match="mandatory rule results"):
        create_release_attestation(
            result.candidate,
            tuple(result.transitions),
            policy_evaluation=inconsistent_decision,
            issued_at=ISSUED,
            generator_version="0.1.0.dev8",
        )


def test_publisher_creates_atomic_bundle_and_exact_replay(tmp_path: Path) -> None:
    result = attestation()
    first = publish_attestation_bundle(result, tmp_path / "outputs")
    second = publish_attestation_bundle(result, tmp_path / "outputs")

    assert first.replayed is False
    assert second.replayed is True
    assert first.directory == second.directory
    assert first.json_path.read_text(encoding="utf-8") == render_attestation_json(result)
    assert first.markdown_path.read_text(encoding="utf-8") == render_attestation_markdown(result)


def test_publisher_rejects_output_conflicts(tmp_path: Path) -> None:
    result = attestation()
    output_root = tmp_path / "outputs"
    published = publish_attestation_bundle(result, output_root)
    published.markdown_path.write_text("different\n", encoding="utf-8")
    with pytest.raises(AttestationPublishError, match="ATTESTATION_OUTPUT_CONFLICT"):
        publish_attestation_bundle(result, output_root)

    output_file = tmp_path / "not-a-directory"
    output_file.write_text("occupied", encoding="utf-8")
    with pytest.raises(AttestationPublishError, match="ATTESTATION_OUTPUT_ROOT_INVALID"):
        publish_attestation_bundle(result, output_file)


def test_publisher_rejects_unsafe_existing_targets(tmp_path: Path) -> None:
    result = attestation()
    root = tmp_path / "outputs"
    root.mkdir()
    name = "attestation-" + result.attestation_id.removeprefix("sha256:")
    target = root / name
    target.write_text("occupied", encoding="utf-8")
    with pytest.raises(AttestationPublishError, match="not a safe directory"):
        publish_attestation_bundle(result, root)

    target.unlink()
    target.mkdir()
    (target / "unexpected").write_text("occupied", encoding="utf-8")
    with pytest.raises(AttestationPublishError, match="unexpected contents"):
        publish_attestation_bundle(result, root)

    (target / "unexpected").unlink()
    (target / "attestation.json").mkdir()
    (target / "attestation.md").write_text("occupied", encoding="utf-8")
    with pytest.raises(AttestationPublishError, match="not safe regular files"):
        publish_attestation_bundle(result, root)


def test_publisher_translates_filesystem_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = attestation()
    root = tmp_path / "outputs"
    original_mkdir = Path.mkdir

    def fail_root_mkdir(path: Path, *args: Any, **kwargs: Any) -> None:
        if path == root.resolve(strict=False):
            raise OSError("mkdir denied")
        original_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", fail_root_mkdir)
    with pytest.raises(AttestationPublishError, match="cannot create output root"):
        publish_attestation_bundle(result, root)
    monkeypatch.setattr(Path, "mkdir", original_mkdir)

    root.mkdir()

    def fail_staging(*_args: Any, **_kwargs: Any) -> str:
        raise OSError("staging denied")

    monkeypatch.setattr(publisher_module.tempfile, "mkdtemp", fail_staging)
    with pytest.raises(AttestationPublishError, match="cannot create staging directory"):
        publish_attestation_bundle(result, root)
    monkeypatch.undo()

    with pytest.raises(AttestationPublishError, match="cannot stage attestation file"):
        publisher_module._write_file(tmp_path / "absent" / "file", b"payload")


def test_publisher_translates_existing_bundle_inspection_and_read_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = attestation()
    published = publish_attestation_bundle(result, tmp_path / "outputs")
    original_iterdir = Path.iterdir

    def fail_iterdir(path: Path) -> Any:
        if path == published.directory:
            raise OSError("inspection denied")
        return original_iterdir(path)

    monkeypatch.setattr(Path, "iterdir", fail_iterdir)
    with pytest.raises(AttestationPublishError, match="cannot inspect existing"):
        publish_attestation_bundle(result, tmp_path / "outputs")
    monkeypatch.setattr(Path, "iterdir", original_iterdir)

    original_read_bytes = Path.read_bytes

    def fail_read(path: Path) -> bytes:
        if path == published.json_path:
            raise OSError("read denied")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", fail_read)
    with pytest.raises(AttestationPublishError, match="cannot read existing"):
        publish_attestation_bundle(result, tmp_path / "outputs")


def test_publisher_handles_concurrent_exact_replay_and_rename_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = attestation()
    root = tmp_path / "concurrent"
    original_replace = Path.replace

    def concurrent_replace(staging: Path, target: Path) -> Path:
        target.mkdir()
        (target / "attestation.json").write_bytes(render_attestation_json(result).encode("utf-8"))
        (target / "attestation.md").write_bytes(render_attestation_markdown(result).encode("utf-8"))
        raise OSError("concurrent publisher won")

    monkeypatch.setattr(Path, "replace", concurrent_replace)
    replay = publish_attestation_bundle(result, root)
    assert replay.replayed is True
    monkeypatch.setattr(Path, "replace", original_replace)

    def fail_replace(_staging: Path, _target: Path) -> Path:
        raise OSError("rename denied")

    monkeypatch.setattr(Path, "replace", fail_replace)
    with pytest.raises(AttestationPublishError, match="cannot publish attestation bundle"):
        publish_attestation_bundle(result, tmp_path / "rename-failure")


def test_publisher_preserves_stable_publish_errors_and_rejects_root_symlink_signal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = attestation()
    root = tmp_path / "outputs"
    original_is_symlink = Path.is_symlink

    def report_root_symlink(path: Path) -> bool:
        return path == root or original_is_symlink(path)

    monkeypatch.setattr(Path, "is_symlink", report_root_symlink)
    with pytest.raises(AttestationPublishError, match="ATTESTATION_OUTPUT_ROOT_INVALID"):
        publish_attestation_bundle(result, root)
    monkeypatch.setattr(Path, "is_symlink", original_is_symlink)

    def stable_failure(_path: Path, _payload: bytes) -> None:
        raise AttestationPublishError("STABLE", "preserved")

    monkeypatch.setattr(publisher_module, "_write_file", stable_failure)
    with pytest.raises(AttestationPublishError, match="STABLE: preserved"):
        publish_attestation_bundle(result, tmp_path / "stable")


def test_candidate_package_unknown_attribute_is_explicit() -> None:
    name = "not_a_candidate_symbol"
    with pytest.raises(AttributeError, match="no attribute"):
        getattr(candidates_package, name)
