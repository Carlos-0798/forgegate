import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from forgegate.artifacts import ArtifactRegistry
from forgegate.assembly import (
    CollectionResultLoader,
    CollectionResultLoadError,
    EvidenceAssemblyError,
    EvidenceBundleAssembly,
    LoadedCollectionResult,
    assemble_evidence_bundle,
)
from forgegate.assembly.models import CollectionReceipt, assembly_identity
from forgegate.canonical import sha256_fingerprint
from forgegate.cli import app
from forgegate.collectors import CollectionIssue, CollectionResult
from forgegate.config import load_config
from forgegate.domain.models import ArtifactReference, EvidenceRecord, ExecutionContext

COMMIT = "a" * 40
COLLECTED_AT = datetime(2026, 8, 30, 20, 30, tzinfo=UTC)
GENERATED_AT = datetime(2026, 8, 30, 20, 31, tzinfo=UTC)
runner = CliRunner()


def artifact_reference(
    tmp_path: Path,
    name: str,
    content: bytes = b"evidence",
    media_type: str = "application/octet-stream",
) -> ArtifactReference:
    (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / name).write_bytes(content)
    return ArtifactRegistry(tmp_path).register(name, media_type=media_type).reference


def evidence(
    artifact: ArtifactReference,
    evidence_id: str = "test-summary-12345678",
    *,
    kind: str = "test.summary",
    collected_at: datetime = COLLECTED_AT,
) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id,
        kind=kind,
        scope="repository",
        value={"failures": 0},
        status="passed",
        source_tool="pytest",
        source_version="8.4.2",
        execution_context=ExecutionContext(commit_sha=COMMIT),
        artifact=artifact,
        collected_at=collected_at,
        trust="claimed_ci_metadata",
        verification_level="ci_validated",
    )


def collection_result(
    artifact: ArtifactReference,
    evidence_id: str = "test-summary-12345678",
    *,
    warning: bool = False,
) -> CollectionResult:
    warnings = (
        [
            CollectionIssue(
                code="COLLECTION_WARNING",
                severity="WARNING",
                message="retained warning",
            )
        ]
        if warning
        else []
    )
    return CollectionResult(
        collector_name="test",
        collector_version="forgegate-test.v1",
        status="COMPLETE",
        artifacts=[artifact],
        evidence=[evidence(artifact, evidence_id)],
        warnings=warnings,
    )


def source_reference(name: str, marker: str) -> ArtifactReference:
    return ArtifactReference(
        path_or_uri=name,
        media_type="application/vnd.forgegate.collection-result+json",
        sha256=marker * 64,
        size_bytes=100,
    )


def loaded(
    result: CollectionResult, name: str = "collections/result.json", marker: str = "c"
) -> LoadedCollectionResult:
    return LoadedCollectionResult(source=source_reference(name, marker), result=result)


def assemble(*inputs: LoadedCollectionResult, retain_warnings: bool = False):
    return assemble_evidence_bundle(
        inputs,
        candidate_commit=COMMIT,
        generated_at=GENERATED_AT,
        producer="forgegate-test",
        producer_version="1.0.0",
        retain_warnings=retain_warnings,
    )


def write_result(path: Path, result: CollectionResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(result.model_dump_json(indent=2), encoding="utf-8")


def test_assembly_preserves_raw_and_normalized_provenance(tmp_path: Path) -> None:
    first_artifact = artifact_reference(tmp_path, "artifacts/tests.xml", b"tests")
    second_artifact = artifact_reference(tmp_path, "artifacts/coverage.xml", b"coverage")
    first_path = tmp_path / "collections/tests.json"
    second_path = tmp_path / "collections/coverage.json"
    write_result(first_path, collection_result(first_artifact))
    write_result(
        second_path,
        collection_result(second_artifact, "coverage-summary-12345678"),
    )
    loader = CollectionResultLoader(ArtifactRegistry(tmp_path))

    result = assemble(
        loader.load("collections/tests.json"), loader.load("collections/coverage.json")
    )

    assert result.schema_version == "forgegate.evidence-bundle-assembly.v1"
    assert result.warning_disposition == "none"
    assert result.bundle.candidate_commit == COMMIT
    assert [record.evidence_id for record in result.bundle.evidence] == [
        "test-summary-12345678",
        "coverage-summary-12345678",
    ]
    assert [receipt.source.path_or_uri for receipt in result.collections] == [
        "collections/tests.json",
        "collections/coverage.json",
    ]
    assert all(receipt.result_fingerprint.startswith("sha256:") for receipt in result.collections)
    assert result.assembly_id == sha256_fingerprint(
        assembly_identity(result.warning_disposition, result.bundle, result.collections)
    )


def test_assembly_matches_committed_golden(repository_root: Path) -> None:
    artifact = ArtifactReference(
        path_or_uri="artifacts/junit.xml",
        media_type="application/junit+xml",
        sha256="b" * 64,
        size_bytes=100,
    )
    result = assemble(loaded(collection_result(artifact)))
    expected = json.loads(
        (repository_root / "tests/golden/evidence_bundle_assembly.json").read_text(encoding="utf-8")
    )
    assert result.model_dump(mode="json") == expected


def test_assembly_warning_requires_explicit_retention(tmp_path: Path) -> None:
    artifact = artifact_reference(tmp_path, "artifact.bin")
    item = loaded(collection_result(artifact, warning=True))

    with pytest.raises(EvidenceAssemblyError, match="explicit --retain-warnings") as exc_info:
        assemble(item)
    retained = assemble(item, retain_warnings=True)

    assert exc_info.value.code == "ASSEMBLY_WARNINGS_PRESENT"
    assert retained.warning_disposition == "retained"
    assert retained.collections[0].warnings[0].code == "COLLECTION_WARNING"


def test_assembly_rejects_empty_rejected_and_unbound_inputs(tmp_path: Path) -> None:
    with pytest.raises(EvidenceAssemblyError) as empty:
        assemble()

    rejected = CollectionResult(
        collector_name="test",
        collector_version="v1",
        status="REJECTED",
        rejected_records=[
            CollectionIssue(code="TEST_REJECTED", severity="REJECTION", message="bad")
        ],
    )
    with pytest.raises(EvidenceAssemblyError) as rejected_error:
        assemble(loaded(rejected))

    artifact = artifact_reference(tmp_path, "artifact.bin")
    unbound = collection_result(artifact).model_copy(update={"artifacts": []})
    with pytest.raises(EvidenceAssemblyError) as unbound_error:
        assemble(loaded(unbound))

    assert empty.value.code == "ASSEMBLY_INPUTS_EMPTY"
    assert rejected_error.value.code == "ASSEMBLY_COLLECTION_REJECTED"
    assert unbound_error.value.code == "ASSEMBLY_ARTIFACT_MISMATCH"


@pytest.mark.parametrize(
    ("candidate_commit", "generated_at", "match"),
    [
        ("b" * 40, GENERATED_AT, "evidence commit does not match"),
        (COMMIT, datetime(2026, 8, 30, 20, 29, tzinfo=UTC), "cannot precede"),
    ],
)
def test_assembly_wraps_cross_document_validation(
    tmp_path: Path, candidate_commit: str, generated_at: datetime, match: str
) -> None:
    artifact = artifact_reference(tmp_path, "artifact.bin")
    with pytest.raises(EvidenceAssemblyError, match=match) as exc_info:
        assemble_evidence_bundle(
            [loaded(collection_result(artifact))],
            candidate_commit=candidate_commit,
            generated_at=generated_at,
            producer="forgegate-test",
            producer_version="1.0.0",
        )
    assert exc_info.value.code == "ASSEMBLY_MODEL_INVALID"


def test_assembly_rejects_duplicate_results_and_conflicting_artifact_paths(tmp_path: Path) -> None:
    artifact = artifact_reference(tmp_path, "artifact.bin")
    result = collection_result(artifact)
    with pytest.raises(EvidenceAssemblyError, match="fingerprints must be unique"):
        assemble(
            loaded(result, "first.json", "1"),
            loaded(result, "second.json", "2"),
        )

    with pytest.raises(EvidenceAssemblyError, match="source paths must be unique"):
        assemble(
            loaded(result, "same.json", "1"),
            loaded(
                collection_result(artifact, "coverage-summary-12345678"),
                "same.json",
                "2",
            ),
        )

    conflicting = artifact.model_copy(update={"sha256": "f" * 64})
    second = collection_result(conflicting, "coverage-summary-12345678")
    with pytest.raises(EvidenceAssemblyError, match="conflicting content"):
        assemble(
            loaded(result, "first.json", "1"),
            loaded(second, "second.json", "2"),
        )


def test_assembly_model_rejects_tampering_and_receipt_inconsistency(tmp_path: Path) -> None:
    artifact = artifact_reference(tmp_path, "artifact.bin")
    valid = assemble(loaded(collection_result(artifact)))
    payload = valid.model_dump(mode="json")

    duplicate_source = deepcopy(payload)
    duplicate_source["collections"] *= 2
    with pytest.raises(ValidationError, match="source paths must be unique"):
        EvidenceBundleAssembly.model_validate(duplicate_source)

    duplicate_result = deepcopy(payload)
    duplicate_result["collections"].append(deepcopy(duplicate_result["collections"][0]))
    duplicate_result["collections"][1]["source"]["path_or_uri"] = "other.json"
    with pytest.raises(ValidationError, match="fingerprints must be unique"):
        EvidenceBundleAssembly.model_validate(duplicate_result)

    tampered_id = deepcopy(payload)
    tampered_id["assembly_id"] = "sha256:" + "0" * 64
    with pytest.raises(ValidationError, match="assembly_id does not match"):
        EvidenceBundleAssembly.model_validate(tampered_id)

    wrong_disposition = deepcopy(payload)
    wrong_disposition["warning_disposition"] = "retained"
    with pytest.raises(ValidationError, match="warning disposition"):
        EvidenceBundleAssembly.model_validate(wrong_disposition)

    wrong_order = deepcopy(payload)
    wrong_order["collections"][0]["evidence_ids"] = ["unknown-evidence-12345678"]
    with pytest.raises(ValidationError, match="must match bundle evidence order"):
        EvidenceBundleAssembly.model_validate(wrong_order)

    wrong_artifact = deepcopy(payload)
    wrong_artifact["collections"][0]["artifacts"][0]["sha256"] = "e" * 64
    with pytest.raises(ValidationError, match="must belong"):
        EvidenceBundleAssembly.model_validate(wrong_artifact)


def test_collection_receipt_rejects_invalid_source_duplicates_and_severity(
    tmp_path: Path,
) -> None:
    artifact = artifact_reference(tmp_path, "artifact.bin")
    base = {
        "source": source_reference("result.json", "c"),
        "collector_name": "test",
        "collector_version": "v1",
        "result_fingerprint": "sha256:" + "d" * 64,
        "artifacts": [artifact],
        "evidence_ids": ["test-summary-12345678"],
        "warnings": [],
    }
    invalid_source = deepcopy(base)
    invalid_source["source"] = artifact
    with pytest.raises(ValidationError, match="collection-result JSON"):
        CollectionReceipt.model_validate(invalid_source)

    duplicate_ids = deepcopy(base)
    duplicate_ids["evidence_ids"] *= 2
    with pytest.raises(ValidationError, match="evidence IDs must be unique"):
        CollectionReceipt.model_validate(duplicate_ids)

    duplicate_artifacts = deepcopy(base)
    duplicate_artifacts["artifacts"] *= 2
    with pytest.raises(ValidationError, match="artifacts must be unique"):
        CollectionReceipt.model_validate(duplicate_artifacts)

    invalid_warning = deepcopy(base)
    invalid_warning["warnings"] = [
        {"code": "BAD_RECORD", "severity": "REJECTION", "message": "bad", "location": None}
    ]
    with pytest.raises(ValidationError, match="warnings must use WARNING"):
        CollectionReceipt.model_validate(invalid_warning)


def test_collection_result_loader_validates_contract_and_referenced_bytes(tmp_path: Path) -> None:
    artifact = artifact_reference(tmp_path, "artifact.bin", b"original")
    result_path = tmp_path / "result.json"
    write_result(result_path, collection_result(artifact))

    loaded_result = CollectionResultLoader(ArtifactRegistry(tmp_path)).load("result.json")
    assert loaded_result.result == collection_result(artifact)
    assert loaded_result.source.path_or_uri == "result.json"

    (tmp_path / "artifact.bin").write_bytes(b"changed")
    with pytest.raises(CollectionResultLoadError, match="does not match bytes") as mismatch:
        CollectionResultLoader(ArtifactRegistry(tmp_path)).load("result.json")
    assert mismatch.value.code == "COLLECTION_ARTIFACT_MISMATCH"
    assert mismatch.value.location == "artifact.bin"

    result_path.write_text(
        collection_result(artifact)
        .model_copy(
            update={"artifacts": [artifact.model_copy(update={"path_or_uri": "missing.bin"})]}
        )
        .model_dump_json(),
        encoding="utf-8",
    )
    with pytest.raises(CollectionResultLoadError, match="cannot verify") as unavailable:
        CollectionResultLoader(ArtifactRegistry(tmp_path)).load("result.json")
    assert unavailable.value.code == "COLLECTION_ARTIFACT_UNAVAILABLE"


@pytest.mark.parametrize(
    ("content", "code"),
    [
        (b"\x00{}", "COLLECTION_RESULT_UNSUPPORTED_ENCODING"),
        (b"\xff", "COLLECTION_RESULT_UNSUPPORTED_ENCODING"),
        (b'{"collector_name":"a","collector_name":"b"}', "COLLECTION_RESULT_DUPLICATE_KEY"),
        (b'{"value":NaN}', "COLLECTION_RESULT_NUMBER_INVALID"),
        (b"{", "COLLECTION_RESULT_JSON_INVALID"),
        (b"[]", "COLLECTION_RESULT_ROOT_INVALID"),
        (b'{"collector_name":"test"}', "COLLECTION_RESULT_CONTRACT_INVALID"),
    ],
)
def test_collection_result_loader_rejects_unsafe_json(
    tmp_path: Path, content: bytes, code: str
) -> None:
    (tmp_path / "result.json").write_bytes(content)
    with pytest.raises(CollectionResultLoadError) as exc_info:
        CollectionResultLoader(ArtifactRegistry(tmp_path)).load("result.json")
    assert exc_info.value.code == code


def test_collection_result_loader_enforces_resource_limits(tmp_path: Path) -> None:
    (tmp_path / "result.json").write_text('{"outer":{"inner":1}}', encoding="utf-8")
    with pytest.raises(CollectionResultLoadError) as nodes:
        CollectionResultLoader(ArtifactRegistry(tmp_path), max_nodes=2).load("result.json")
    with pytest.raises(CollectionResultLoadError) as depth:
        CollectionResultLoader(ArtifactRegistry(tmp_path), max_depth=2).load("result.json")
    with pytest.raises(ValueError, match="limits must be positive"):
        CollectionResultLoader(ArtifactRegistry(tmp_path), max_nodes=0)
    assert nodes.value.code == "COLLECTION_RESULT_NODE_LIMIT"
    assert depth.value.code == "COLLECTION_RESULT_DEPTH_LIMIT"


def test_cli_assembly_config_loading_and_policy_evaluation(tmp_path: Path) -> None:
    junit = b'<testsuite tests="1" failures="0"><testcase name="ok" /></testsuite>'
    (tmp_path / "junit.xml").write_bytes(junit)
    collected = runner.invoke(
        app,
        [
            "collect-junit",
            "junit.xml",
            "--root",
            str(tmp_path),
            "--commit",
            COMMIT,
            "--collected-at",
            "2026-08-30T20:30:00Z",
            "--source-tool",
            "pytest",
            "--source-version",
            "8.4.2",
            "--trust",
            "claimed_ci_metadata",
            "--verification-level",
            "ci_validated",
        ],
    )
    assert collected.exit_code == 0
    (tmp_path / "collection.json").write_text(collected.stdout, encoding="utf-8")

    assembled = runner.invoke(
        app,
        [
            "assemble-evidence",
            "collection.json",
            "--root",
            str(tmp_path),
            "--commit",
            COMMIT,
            "--generated-at",
            "2026-08-30T20:31:00Z",
            "--retain-warnings",
        ],
    )
    assert assembled.exit_code == 0, assembled.output
    assembly_path = tmp_path / "assembly.json"
    assembly_path.write_text(assembled.stdout, encoding="utf-8")
    assert isinstance(load_config(assembly_path), EvidenceBundleAssembly)

    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text(
        """schema_version: forgegate.policy.v1
name: assembly-policy
rules:
  - id: tests-pass
    claim: tests.required-pass
    evidence_kind: test.summary
    operator: equals
    expected: 0
    where: {field: failures}
    minimum_trust: claimed_ci_metadata
    minimum_verification: ci_validated
""",
        encoding="utf-8",
    )
    evaluated = runner.invoke(
        app,
        [
            "evaluate-policy",
            str(policy_path),
            str(assembly_path),
            "--evaluated-at",
            "2026-08-30T20:32:00Z",
        ],
    )
    assert evaluated.exit_code == 0
    assert json.loads(evaluated.stdout)["decision"] == "PASS"


def test_cli_assembly_reports_user_facing_failures(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.json"
    invalid.write_text("{}", encoding="utf-8")
    command = [
        "assemble-evidence",
        "invalid.json",
        "--root",
        str(tmp_path),
        "--commit",
        COMMIT,
        "--generated-at",
        "2026-08-30T20:31:00Z",
    ]
    invalid_contract = runner.invoke(app, command)
    invalid_timestamp = runner.invoke(app, [*command[:-1], "not-a-timestamp"])
    outside_root = runner.invoke(app, [*command[:1], "../outside.json", *command[2:]])

    assert invalid_contract.exit_code == 3
    assert "violates its contract" in invalid_contract.output
    assert invalid_timestamp.exit_code == 3
    assert "violates its contract" in invalid_timestamp.output
    assert outside_root.exit_code == 3
    assert "parent traversal" in outside_root.output
