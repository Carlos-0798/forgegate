"""Prepare a private AVS report handoff using files only; never import upstream code."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from forgegate import __version__
from forgegate.application import (
    CandidateAdvanceCommand,
    CandidateApplication,
    CandidateCreateCommand,
    ProjectRegisterCommand,
)
from forgegate.artifacts import ArtifactRegistry
from forgegate.assembly import CollectionResultLoader, assemble_evidence_bundle
from forgegate.canonical import canonical_json
from forgegate.collectors import (
    BenchmarkCollectionRequest,
    BenchmarkJsonCollector,
    CoverageCollectionRequest,
    CoverageXmlCollector,
    JUnitCollectionRequest,
    JUnitCollector,
    SarifCollectionRequest,
    SarifCollector,
)
from forgegate.config import load_config
from forgegate.domain.enums import CandidateStatus
from forgegate.domain.models import ExecutionContext, ProjectConfig

REPORT_MTIME_FUTURE_TOLERANCE = timedelta(seconds=1)

QUALITY_CHECKS = frozenset(
    {
        "demo_manifest",
        "demo_pass",
        "demo_synthetic",
        "demo_time",
        "event_10k_time",
        "event_cleanup",
        "event_queue_bounded",
        "event_terminal_state",
        "live_10k_peak_memory",
        "live_10k_time",
        "live_eviction_accounted",
        "live_ring_bounded",
        "live_status_accounted",
        "replay_10k_peak_memory",
        "replay_10k_time",
    }
)


def quality_benchmark(document: dict[str, Any]) -> dict[str, Any]:
    """Copy selected host measurements; keep false upstream checks visible."""
    if (
        document.get("schema_version") != "phase5-product-quality-acceptance.v1"
        or document.get("scope") != "HOST_SOFTWARE_ONLY"
        or document.get("hardware_validation") is not False
    ):
        raise ValueError("expected the versioned host-only quality report")
    checks = document.get("checks")
    if not isinstance(checks, dict) or set(checks) != QUALITY_CHECKS:
        raise ValueError("the complete known quality check set is required")
    if any(type(value) is not bool for value in checks.values()):
        raise ValueError("quality check results must be booleans")
    if document.get("passed") is not all(checks.values()):
        raise ValueError("quality passed flag contradicts its check results")
    measurements = document["measurements"]
    replay = [item for item in measurements["replay"] if item["records"] == 10_000]
    if len(replay) != 1:
        raise ValueError("exactly one 10000-record replay measurement is required")
    live = measurements["live_monitor"]
    events = measurements["event_volume"]
    if live["requested_points"] != 10_000 or events["requested_progress_events"] != 10_000:
        raise ValueError("host workload must match the reviewed 10000-item policy")
    values = [
        ("replay.10000.elapsed", replay[0]["elapsed_seconds"], "s"),
        ("replay.10000.peak_memory", replay[0]["peak_memory_mib"], "MiB"),
        ("events.10000.elapsed", events["elapsed_seconds"], "s"),
        ("live.10000.elapsed", live["elapsed_seconds"], "s"),
        ("live.10000.peak_memory", live["peak_memory_mib"], "MiB"),
        ("demo.elapsed", measurements["demo"]["elapsed_seconds"], "s"),
        ("upstream.checks.failed", sum(not value for value in checks.values()), "count"),
    ]
    for _, value, _ in values:
        if type(value) not in {int, float} or not math.isfinite(value) or value < 0:
            raise ValueError("host measurements must be finite nonnegative numbers")
    return {
        "schema_version": "forgegate.benchmark.v1",
        "tool": {"name": "avs-product-quality-file-mapping", "version": "1"},
        "metrics": [{"name": name, "value": value, "unit": unit} for name, value, unit in values],
    }


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("duplicate quality JSON key")
        result[name] = value
    return result


def prepare_handoff(
    reports: Path,
    output: Path,
    *,
    commit: str,
    pytest_version: str,
    coverage_version: str,
    retain_warnings: bool = False,
) -> dict[str, Any]:
    context = ExecutionContext(commit_sha=commit)
    registry = ArtifactRegistry(reports)
    original = registry.register("product-quality.json", media_type="application/json")
    quality = json.loads(original.content, object_pairs_hook=_unique_object)
    benchmark = quality_benchmark(quality)
    # Read bounded originals before making a new output workspace.
    source_files = {
        name: registry.register(name, media_type=media).content
        for name, media in [
            ("junit.xml", "application/xml"),
            ("coverage.xml", "application/xml"),
            ("security.sarif", "application/sarif+json"),
        ]
    }
    original_times = {
        name: datetime.fromtimestamp((reports / name).stat().st_mtime, UTC)
        for name in [*source_files, "product-quality.json"]
    }
    # Windows filesystem timestamps and the wall clock can differ by a few
    # milliseconds around file creation. Keep a narrow tolerance while still
    # rejecting materially future-dated inputs.
    if any(
        time > datetime.now(UTC) + REPORT_MTIME_FUTURE_TOLERANCE for time in original_times.values()
    ):
        raise ValueError("original report file time cannot be in the future")
    output.mkdir(parents=True, exist_ok=False)
    artifacts = output / "artifacts"
    artifacts.mkdir()
    for name, content in {**source_files, "product-quality.json": original.content}.items():
        (artifacts / name).write_bytes(content)
    (artifacts / "benchmark.json").write_text(canonical_json(benchmark), encoding="utf-8")
    pack = Path(__file__).resolve().parents[1] / "examples/analog-validation-studio-host"
    shutil.copyfile(pack / "forgegate.yaml", output / "forgegate.yaml")
    shutil.copytree(pack / "policies", output / "policies")
    collector_registry = ArtifactRegistry(output)
    common = dict(execution_context=context, trust="unsigned_local", verification_level="declared")
    receipts = []
    warnings: list[str] = []
    results = [
        JUnitCollector(collector_registry).collect(
            JUnitCollectionRequest.model_validate(
                {
                    **common,
                    "source_path": "artifacts/junit.xml",
                    "source_tool": "pytest",
                    "source_version": pytest_version,
                    "collected_at": original_times["junit.xml"],
                }
            ),
        ),
        CoverageXmlCollector(collector_registry).collect(
            CoverageCollectionRequest.model_validate(
                {
                    **common,
                    "source_path": "artifacts/coverage.xml",
                    "source_tool": "coverage.py",
                    "source_version": coverage_version,
                    "collected_at": original_times["coverage.xml"],
                }
            ),
        ),
        SarifCollector(collector_registry).collect(
            SarifCollectionRequest.model_validate(
                {
                    **common,
                    "source_path": "artifacts/security.sarif",
                    "collected_at": original_times["security.sarif"],
                }
            ),
        ),
        BenchmarkJsonCollector(collector_registry).collect(
            BenchmarkCollectionRequest.model_validate(
                {
                    **common,
                    "source_path": "artifacts/benchmark.json",
                    "collected_at": original_times["product-quality.json"],
                }
            ),
        ),
    ]
    collections = output / "collections"
    collections.mkdir()
    for index, result in enumerate(results):
        if result.status != "COMPLETE":
            raise ValueError(f"report rejected: {result.collector_name}")
        warnings.extend(issue.code for issue in result.warnings)
        relative = f"collections/{index}.json"
        (output / relative).write_text(
            canonical_json(result.model_dump(mode="json")), encoding="utf-8"
        )
        receipts.append(CollectionResultLoader(collector_registry).load(relative))
    assembly = assemble_evidence_bundle(
        receipts,
        candidate_commit=commit,
        generated_at=datetime.now(UTC),
        producer="forgegate-avs-host-handoff",
        producer_version=__version__,
        retain_warnings=retain_warnings,
    )
    (output / "assembly.json").write_text(
        canonical_json(assembly.model_dump(mode="json")), encoding="utf-8"
    )
    application = CandidateApplication.for_database(output / "forgegate.db")
    application.initialize()
    config = load_config(output / "forgegate.yaml")
    assert isinstance(config, ProjectConfig)
    application.register_project(
        ProjectRegisterCommand(config=config, registered_at=datetime.now(UTC)),
        idempotency_key="avs:register",
    )
    candidate = application.create_candidate(
        CandidateCreateCommand(
            project_id=config.project.id,
            version=f"host-review-{commit[:12]}",
            commit_sha=commit,
            release_track="host-review",
            created_at=datetime.now(UTC),
        ),
        idempotency_key="avs:create",
    )
    application.advance_candidate(
        candidate.candidate_id,
        CandidateAdvanceCommand(
            to_status=CandidateStatus.COLLECTING,
            expected_revision=0,
            occurred_at=datetime.now(UTC),
        ),
        idempotency_key="avs:collecting",
    )
    material = application.materialize_policy(candidate.candidate_id, output)
    (output / "policy-material.json").write_text(
        material.model_dump_json(indent=2), encoding="utf-8"
    )
    manifest = {
        "format": "avs-host-handoff.v1",
        "candidate_id": candidate.candidate_id,
        "reported_commit": commit,
        "project_id": config.project.id,
        "candidate_status": "COLLECTING",
        "bound": False,
        "warnings": warnings,
        "source_quality_sha256": hashlib.sha256(original.content).hexdigest(),
        "benchmark_sha256": hashlib.sha256((artifacts / "benchmark.json").read_bytes()).hexdigest(),
        "source_files": {
            name: {
                "sha256": hashlib.sha256(content).hexdigest(),
                "size_bytes": len(content),
                "declared_collected_at": original_times[name].isoformat(),
            }
            for name, content in source_files.items()
        },
        "time_basis": "observed producer output file modification times; unauthenticated",
        "assembly_id": assembly.assembly_id,
        "evidence_records": len(assembly.bundle.evidence),
        "hardware_access": "NOT_PERFORMED",
        "producer_authentication": "NOT_PERFORMED",
        "notes": [
            "Private originals may contain local paths.",
            "Performance values describe host execution of synthetic workloads.",
            "Ruff S-rule findings require review; they are not confirmed vulnerabilities.",
        ],
    }
    (output / "handoff.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--pytest-version", required=True)
    parser.add_argument("--coverage-version", required=True)
    parser.add_argument("--retain-warnings", action="store_true")
    args = parser.parse_args()
    result = prepare_handoff(
        args.reports,
        args.output,
        commit=args.commit,
        pytest_version=args.pytest_version,
        coverage_version=args.coverage_version,
        retain_warnings=args.retain_warnings,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
