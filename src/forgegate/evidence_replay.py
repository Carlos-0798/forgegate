"""Bounded file-only report replay. No commands, plugins, network or extraction."""

from __future__ import annotations

import hashlib
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any, Literal

from pydantic import Field

from forgegate import __version__
from forgegate.artifacts import ArtifactBoundaryError, ArtifactRegistry, RegisteredArtifact
from forgegate.assembly import CollectionResultLoader, assemble_evidence_bundle
from forgegate.assurance import AssuranceBundle
from forgegate.assurance.portable import _strict_json, render_assurance_bundle_json
from forgegate.canonical import canonical_json, sha256_fingerprint
from forgegate.collectors import (
    BenchmarkCollectionRequest,
    BenchmarkJsonCollector,
    CoverageCollectionRequest,
    CoverageXmlCollector,
    JUnitCollectionRequest,
    JUnitCollector,
    LcovCollector,
    SarifCollectionRequest,
    SarifCollector,
)
from forgegate.collectors.base import CollectionResult
from forgegate.domain.models import ArtifactReference, StrictModel
from forgegate.policy.engine import evaluate_policy_material

MAX_SOURCE_BYTES = 1024 * 1024
MAX_TOTAL_SOURCE_BYTES = 2 * MAX_SOURCE_BYTES
MAX_REPLAY_ARCHIVE_BYTES = 20 * MAX_SOURCE_BYTES
MAX_BUNDLE_BYTES = 16 * MAX_SOURCE_BYTES
MAX_FILES = 32


class EvidenceReplayError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class ReplayFile(StrictModel):
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0, le=MAX_SOURCE_BYTES)


class EvidenceReplayManifest(StrictModel):
    schema_version: Literal["forgegate.evidence-replay.v1"] = "forgegate.evidence-replay.v1"
    replay_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    bundle_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    candidate_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    forgegate_version: str = Field(min_length=1, max_length=120)
    files: list[ReplayFile] = Field(min_length=2, max_length=MAX_FILES)
    assurance: Literal["unsigned_local"] = "unsigned_local"
    producer_authentication: Literal["NOT_PERFORMED"] = "NOT_PERFORMED"
    scope: Literal["report_parsing_and_retained_policy"] = "report_parsing_and_retained_policy"


class EvidenceReplayVerification(StrictModel):
    schema_version: Literal["forgegate.evidence-replay-verification.v1"] = (
        "forgegate.evidence-replay-verification.v1"
    )
    status: Literal["VALID"] = "VALID"
    replay_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    bundle_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    candidate_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    decision: Literal["PASS", "FAIL", "REVIEW", "ERROR"]
    collections_replayed: int = Field(ge=1, le=16)
    evidence_records: int = Field(ge=1, le=4096)
    source_files: int = Field(ge=2, le=MAX_FILES)
    producer_authentication: Literal["NOT_PERFORMED"] = "NOT_PERFORMED"
    hardware_access: Literal["NOT_PERFORMED"] = "NOT_PERFORMED"


def required_replay_files(bundle: AssuranceBundle) -> dict[str, ArtifactReference]:
    assembly = bundle.evidence_binding.assembly
    if len(assembly.collections) > 16 or len(assembly.bundle.evidence) > 4096:
        raise EvidenceReplayError("REPLAY_LIMIT", "Replay exceeds collection or record limits.")
    references: dict[str, ArtifactReference] = {}
    paths: dict[str, ArtifactReference] = {}
    for receipt in assembly.collections:
        if receipt.collector_name not in {
            "junit",
            "coverage_xml",
            "lcov",
            "sarif",
            "benchmark_json",
        }:
            raise EvidenceReplayError(
                "REPLAY_UNSUPPORTED", "Collector is outside software replay v1."
            )
        if len(receipt.artifacts) != 1:
            raise EvidenceReplayError("REPLAY_UNSUPPORTED", "One source per collector is required.")
        for ref in [receipt.source, *receipt.artifacts]:
            if ref.size_bytes > MAX_SOURCE_BYTES:
                raise EvidenceReplayError("REPLAY_LIMIT", "A required file exceeds 1 MiB.")
            if ref.path_or_uri in paths and paths[ref.path_or_uri] != ref:
                raise EvidenceReplayError("REPLAY_REFERENCE", "Conflicting source references.")
            paths[ref.path_or_uri] = ref
            if ref.sha256 in references and references[ref.sha256].size_bytes != ref.size_bytes:
                raise EvidenceReplayError("REPLAY_REFERENCE", "Conflicting digest sizes.")
            references[ref.sha256] = ref
    if (
        len(references) > MAX_FILES
        or sum(r.size_bytes for r in references.values()) > MAX_TOTAL_SOURCE_BYTES
    ):
        raise EvidenceReplayError("REPLAY_LIMIT", "Selection exceeds 32 files or 2 MiB.")
    return references


class _ReplaySource:
    def __init__(self, bundle: AssuranceBundle, files: dict[str, bytes]) -> None:
        self.files = files
        self.references = {
            r.path_or_uri: r
            for receipt in bundle.evidence_binding.assembly.collections
            for r in [receipt.source, *receipt.artifacts]
        }

    def register(self, source_path: str | Path, *, media_type: str) -> RegisteredArtifact:
        ref = self.references.get(str(source_path))
        if ref is None or ref.media_type != media_type:
            raise ArtifactBoundaryError("Replay source is not an exact retained reference.")
        return RegisteredArtifact(reference=ref, content=self.files[ref.sha256])


def _collect(result: CollectionResult, source: _ReplaySource) -> CollectionResult:
    first = result.evidence[0]
    common: dict[str, Any] = {
        "source_path": result.artifacts[0].path_or_uri,
        "execution_context": first.execution_context,
        "collected_at": first.collected_at,
        "trust": first.trust,
        "verification_level": first.verification_level,
        "scope": first.scope,
    }
    if result.collector_name == "sarif":
        return SarifCollector(source).collect(SarifCollectionRequest.model_validate(common))
    if result.collector_name == "benchmark_json":
        # v1 replay uses the default fallback for metrics without an embedded scope.
        common.pop("scope")
        return BenchmarkJsonCollector(source).collect(
            BenchmarkCollectionRequest.model_validate(common)
        )
    common.update(source_tool=first.source_tool, source_version=first.source_version)
    if result.collector_name == "junit":
        return JUnitCollector(source).collect(JUnitCollectionRequest.model_validate(common))
    request = CoverageCollectionRequest.model_validate(common)
    if result.collector_name == "coverage_xml":
        return CoverageXmlCollector(source).collect(request)
    return LcovCollector(source).collect(request)


def _replay(bundle: AssuranceBundle, files: dict[str, bytes]) -> None:
    required = required_replay_files(bundle)
    if set(required) != set(files):
        raise EvidenceReplayError(
            "REPLAY_FILES", "Required source/receipt files are missing or extra."
        )
    for digest, ref in required.items():
        content = files[digest]
        if len(content) != ref.size_bytes or hashlib.sha256(content).hexdigest() != digest:
            raise EvidenceReplayError(
                "REPLAY_HASH", "Source bytes differ from the retained hash or size."
            )
    source = _ReplaySource(bundle, files)
    assembly = bundle.evidence_binding.assembly
    loaded = []
    for receipt in assembly.collections:
        # Same loader verifies receipt files against their exact referenced source bytes.
        item = CollectionResultLoader(source).load(receipt.source.path_or_uri)
        if item.result.status != "COMPLETE" or not item.result.evidence:
            raise EvidenceReplayError("REPLAY_RESULT", "A retained collection is incomplete.")
        actual = _collect(item.result, source)
        if canonical_json(actual.model_dump(mode="json")) != canonical_json(
            item.result.model_dump(mode="json")
        ):
            raise EvidenceReplayError(
                "REPLAY_PARSER_MISMATCH", "Current parser differs from the retained result."
            )
        loaded.append(item)
    rebuilt = assemble_evidence_bundle(
        loaded,
        candidate_commit=assembly.bundle.candidate_commit,
        generated_at=assembly.bundle.generated_at,
        producer=assembly.bundle.producer,
        producer_version=assembly.bundle.producer_version,
        retain_warnings=assembly.warning_disposition == "retained",
    )
    if rebuilt != assembly:
        raise EvidenceReplayError(
            "REPLAY_ASSEMBLY_MISMATCH", "Sources do not reconstruct the retained assembly."
        )
    evaluation = bundle.attestation.policy_evaluation
    assert evaluation is not None
    actual_evaluation = evaluate_policy_material(
        bundle.policy_material,
        rebuilt.bundle,
        evaluated_at=evaluation.evaluated_at,
    )
    if canonical_json(actual_evaluation.model_dump(mode="json")) != canonical_json(
        evaluation.model_dump(mode="json")
    ):
        raise EvidenceReplayError(
            "REPLAY_POLICY_MISMATCH", "Recomputed policy differs from the retained evaluation."
        )


def _manifest(bundle: AssuranceBundle, files: dict[str, bytes]) -> EvidenceReplayManifest:
    values = dict(
        bundle_id=bundle.bundle_id,
        candidate_commit=bundle.attestation.candidate.commit_sha,
        forgegate_version=__version__,
        files=[
            ReplayFile(sha256=digest, size_bytes=len(data)).model_dump()
            for digest, data in sorted(files.items())
        ],
    )
    return EvidenceReplayManifest.model_validate(
        {**values, "replay_id": sha256_fingerprint(values)}
    )


def _archive(bundle: AssuranceBundle, files: dict[str, bytes]) -> bytes:
    manifest = _manifest(bundle, files)
    content = {
        "manifest.json": canonical_json(manifest.model_dump(mode="json")).encode(),
        "assurance-bundle.json": render_assurance_bundle_json(bundle).encode(),
        **{f"blobs/{digest}": payload for digest, payload in files.items()},
    }
    if len(content["assurance-bundle.json"]) > MAX_BUNDLE_BYTES:
        raise EvidenceReplayError("REPLAY_LIMIT", "Assurance document exceeds 16 MiB.")
    output = BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, payload in sorted(content.items()):
            entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, payload)
    return output.getvalue()


def render_evidence_replay(bundle: AssuranceBundle, files: dict[str, bytes]) -> tuple[str, bytes]:
    _replay(bundle, files)
    manifest = _manifest(bundle, files)
    return f"replay-{manifest.replay_id.removeprefix('sha256:')}.zip", _archive(bundle, files)


def verify_evidence_replay(payload: bytes, *, expected_commit: str) -> EvidenceReplayVerification:
    """Verify in memory; never extract paths or execute embedded commands."""
    if len(payload) > MAX_REPLAY_ARCHIVE_BYTES:
        raise EvidenceReplayError("REPLAY_LIMIT", "Replay archive exceeds 20 MiB.")
    try:
        with zipfile.ZipFile(BytesIO(payload)) as archive:
            members = archive.infolist()
            names = [item.filename for item in members]
            if len(names) > MAX_FILES + 2 or len(set(names)) != len(names):
                raise EvidenceReplayError("REPLAY_FILES", "Duplicate or excessive ZIP members.")
            if sum(i.file_size for i in members) > MAX_REPLAY_ARCHIVE_BYTES:
                raise EvidenceReplayError(
                    "REPLAY_LIMIT", "Declared unpacked size exceeds the limit."
                )
            for item in members:
                limit = (
                    MAX_BUNDLE_BYTES
                    if item.filename == "assurance-bundle.json"
                    else MAX_SOURCE_BYTES
                )
                if (
                    item.compress_type != zipfile.ZIP_STORED
                    or item.flag_bits & 1
                    or item.file_size > limit
                ):
                    raise EvidenceReplayError(
                        "REPLAY_ZIP", "Compressed, encrypted or oversized member."
                    )
            manifest = EvidenceReplayManifest.model_validate(
                _strict_json(archive.read("manifest.json"))
            )
            expected_names = {
                "manifest.json",
                "assurance-bundle.json",
                *[f"blobs/{f.sha256}" for f in manifest.files],
            }
            if set(names) != expected_names:
                raise EvidenceReplayError("REPLAY_FILES", "Archive has missing or extra members.")
            if manifest.forgegate_version != __version__:
                raise EvidenceReplayError(
                    "REPLAY_VERSION", "Use the matching ForgeGate replay version."
                )
            bundle = AssuranceBundle.model_validate(
                _strict_json(archive.read("assurance-bundle.json"))
            )
            if bundle.attestation.candidate.commit_sha != expected_commit:
                raise EvidenceReplayError(
                    "REPLAY_COMMIT", "Candidate differs from the independently supplied commit."
                )
            files = {f.sha256: archive.read(f"blobs/{f.sha256}") for f in manifest.files}
        if manifest != _manifest(bundle, files) or payload != _archive(bundle, files):
            raise EvidenceReplayError(
                "REPLAY_CANONICAL", "Archive bytes or manifest differ from canonical content."
            )
        _replay(bundle, files)
        evaluation = bundle.attestation.policy_evaluation
        assert evaluation is not None
        return EvidenceReplayVerification.model_validate(
            dict(
                replay_id=manifest.replay_id,
                bundle_id=bundle.bundle_id,
                candidate_commit=expected_commit,
                decision=evaluation.decision.value,
                collections_replayed=len(bundle.evidence_binding.assembly.collections),
                evidence_records=len(bundle.evidence_binding.assembly.bundle.evidence),
                source_files=len(files),
            )
        )
    except EvidenceReplayError:
        raise
    except (ValueError, KeyError, IndexError, OSError, zipfile.BadZipFile) as exc:
        raise EvidenceReplayError(
            "REPLAY_INVALID", "Invalid replay archive or retained report contract."
        ) from exc


def load_replay_sources(bundle: AssuranceBundle, source_root: Path) -> dict[str, bytes]:
    registry = ArtifactRegistry(source_root, max_bytes=MAX_SOURCE_BYTES)
    return {
        digest: registry.register(ref.path_or_uri, media_type=ref.media_type).content
        for digest, ref in required_replay_files(bundle).items()
    }


def publish_evidence_replay(bundle: AssuranceBundle, source_root: Path, destination: Path) -> Path:
    filename, payload = render_evidence_replay(bundle, load_replay_sources(bundle, source_root))
    for path in (destination, *destination.parents):
        if path.is_symlink() or path.is_junction():
            raise EvidenceReplayError(
                "REPLAY_OUTPUT", "Output path cannot contain links or junctions."
            )
    destination.mkdir(parents=True, exist_ok=False)
    target = destination / filename
    with target.open("xb") as handle:
        handle.write(payload)
    return target
