from __future__ import annotations

import argparse
import base64
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from forgegate.config import load_config
from forgegate.dashboard.collection import DashboardCollectionPreviewRequest, preview_collection
from forgegate.domain.models import PolicyConfig
from forgegate.policy import evaluate_policy

ROOT = Path(__file__).resolve().parents[1]
POLICY_SOURCE = ROOT / "examples/dashboard-standard-ci/policies/pull-request.yaml"
COLLECTED_AT = "2026-09-08T16:00:00Z"

PACKS: dict[str, dict[str, Any]] = {
    "A": {
        "commit": "c" * 40,
        "suite": "service-alpha",
        "tests": 7,
        "scanner": "NorthwindScan",
        "rule": "NW100",
        "latency": 41.2,
        "slow_latency": 72.4,
    },
    "B": {
        "commit": "d" * 40,
        "suite": "service-bravo",
        "tests": 9,
        "scanner": "SouthridgeScan",
        "rule": "SR200",
        "latency": 43.8,
        "slow_latency": 69.6,
    },
}

CASES: dict[str, dict[str, Any]] = {
    "01": {"variant": "baseline", "expected": "PASS"},
    "02": {"variant": "finding", "expected": "FAIL"},
    "03": {"variant": "slow", "expected": "FAIL"},
    "04": {"variant": "missing-security", "expected": "REVIEW"},
    "05": {"variant": "missing-performance", "expected": "REVIEW"},
    "06": {"variant": "invalid-security", "expected": "INPUT_REJECTED"},
}

# Each semantic case receives a different neutral run number in each pack. The
# participant receives only the run paths, so public protocol case numbers do
# not disclose the expected outcome.
RUN_BY_CASE: dict[str, dict[str, str]] = {
    "A": {"01": "03", "02": "05", "03": "01", "04": "06", "05": "04", "06": "02"},
    "B": {"01": "04", "02": "02", "03": "06", "04": "01", "05": "03", "06": "05"},
}


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_report(spec: dict[str, Any]) -> bytes:
    return (
        f'<testsuite name="{spec["suite"]}" tests="{spec["tests"]}" '
        'failures="0" errors="0" skipped="0"/>\n'
    ).encode()


def coverage_report(spec: dict[str, Any]) -> bytes:
    return (
        f'<coverage><packages><package name="{spec["suite"]}"><classes>'
        f'<class filename="{spec["suite"]}.py"><lines>'
        '<line number="1" hits="1" branch="true" condition-coverage="100% (2/2)"/>'
        '<line number="2" hits="1"/>'
        "</lines></class></classes></package></packages></coverage>\n"
    ).encode()


def security_report(spec: dict[str, Any], variant: str) -> bytes:
    if variant == "invalid-security":
        return canonical_json({"runs": "invalid blinded input", "version": "2.1.0"})
    results: list[dict[str, Any]] = []
    if variant == "finding":
        results.append(
            {
                "level": "error",
                "message": {"text": "Synthetic Phase 53 finding; not a vulnerability claim."},
                "ruleId": spec["rule"],
            }
        )
    return canonical_json(
        {
            "runs": [
                {
                    "invocations": [{"executionSuccessful": True}],
                    "results": results,
                    "tool": {"driver": {"name": spec["scanner"], "version": "1.0"}},
                }
            ],
            "version": "2.1.0",
        }
    )


def benchmark_report(spec: dict[str, Any], variant: str) -> bytes:
    value = spec["slow_latency"] if variant == "slow" else spec["latency"]
    return canonical_json(
        {
            "metrics": [{"name": "latency.p95", "unit": "ms", "value": value}],
            "schema_version": "forgegate.benchmark.v1",
            "tool": {"name": f"{spec['suite']}-benchmark", "version": "1.0"},
        }
    )


def files_for(spec: dict[str, Any], variant: str) -> dict[str, tuple[str, bytes]]:
    reports = {
        "junit": ("report-01.xml", test_report(spec)),
        "coverage_xml": ("report-02.xml", coverage_report(spec)),
        "sarif": ("report-03.json", security_report(spec, variant)),
        "benchmark_json": ("report-04.json", benchmark_report(spec, variant)),
    }
    if variant == "missing-security":
        del reports["sarif"]
    if variant == "missing-performance":
        del reports["benchmark_json"]
    return reports


def expected_reasons(spec: dict[str, Any], variant: str) -> list[dict[str, Any]]:
    reasons: list[dict[str, Any]] = []
    if variant == "finding":
        reasons.append(
            {"rule_id": "security-clean", "actual": 1, "expected": 0, "source": "report-03.json"}
        )
    elif variant == "slow":
        reasons.append(
            {
                "rule_id": "latency-bound",
                "actual": spec["slow_latency"],
                "expected": 50,
                "source": "report-04.json",
            }
        )
    elif variant == "missing-security":
        reasons.append({"rule_id": "security-clean", "actual": None, "expected": 0, "source": None})
    elif variant == "missing-performance":
        reasons.append({"rule_id": "latency-bound", "actual": None, "expected": 50, "source": None})
    elif variant == "invalid-security":
        reasons.append(
            {
                "rule_id": None,
                "actual": "invalid SARIF runs",
                "expected": "valid SARIF 2.1.0",
                "source": "report-03.json",
            }
        )
    return reasons


def preview_payload(commit: str, reports: dict[str, tuple[str, bytes]]) -> dict[str, Any]:
    return {
        "expected_revision": 1,
        "reported_commit": commit,
        "reports": [
            {
                "format": report_format,
                "content_base64": base64.b64encode(content).decode(),
                "source_tool": "phase53-declared-source",
                "source_version": "1",
                "collected_at": COLLECTED_AT,
            }
            for report_format, (_, content) in reports.items()
        ],
    }


def validate_with_forgegate(
    pack: str,
    case: str,
    spec: dict[str, Any],
    reports: dict[str, tuple[str, bytes]],
) -> dict[str, Any]:
    result = preview_collection(
        f"phase53-{pack.lower()}-{case}",
        DashboardCollectionPreviewRequest.model_validate(preview_payload(spec["commit"], reports)),
    )
    expected = CASES[case]["expected"]
    if expected == "INPUT_REJECTED":
        if result.assembly is not None or not any(
            item.status == "REJECTED" for item in result.collections
        ):
            raise RuntimeError(f"{pack}/{case}: expected rejected input without an assembly")
        return {"actual": "INPUT_REJECTED", "records": 0, "collections": len(result.collections)}
    if result.assembly is None:
        raise RuntimeError(f"{pack}/{case}: complete reports did not produce an assembly")
    policy = load_config(POLICY_SOURCE)
    if not isinstance(policy, PolicyConfig):
        raise RuntimeError("Phase 53 policy source did not load as a policy config")
    evaluation = evaluate_policy(policy, result.assembly.bundle, evaluated_at=datetime.now(UTC))
    if evaluation.decision.value != expected:
        raise RuntimeError(
            f"{pack}/{case}: expected {expected}, observed {evaluation.decision.value}"
        )
    return {
        "actual": evaluation.decision.value,
        "collections": len(result.collections),
        "records": len(result.assembly.bundle.evidence),
        "rule_results": [
            {
                "actual": item.actual,
                "decision": item.decision.value,
                "expected": item.expected,
                "rule_id": item.rule_id,
            }
            for item in evaluation.rule_results
        ],
    }


def task_sheet() -> bytes:
    return (
        b"# Phase 53 timed assessment materials\n\n"
        b"Do not open the sibling `assessor` directory before submitting all timed answers.\n"
        b"These files are synthetic and do not prove that a test or scan ran.\n\n"
        b"For each assigned run, use the supplied policy and expected commit. Record:\n\n"
        b"1. PASS, FAIL, REVIEW, or INPUT REJECTED;\n"
        b"2. every blocking or missing rule with actual and expected values;\n"
        b"3. the source report/record used for each conclusion.\n\n"
        b"Neutral filenames are intentional. Inspect content to identify each report family.\n"
        b"Do not correct an answer after stopping the timer; record rework separately.\n"
    )


def prepare(destination: Path) -> dict[str, Any]:
    if destination.exists():
        raise FileExistsError(f"destination already exists: {destination}")
    participant = destination / "participant"
    assessor = destination / "assessor"
    participant.mkdir(parents=True)
    assessor.mkdir()
    policy = POLICY_SOURCE.read_bytes()
    (participant / "policy.yaml").write_bytes(policy)
    (participant / "TASK.md").write_bytes(task_sheet())

    input_manifest: dict[str, Any] = {
        "format": "forgegate.phase53-input-manifest.v1",
        "policy_sha256": sha256(policy),
        "packs": {},
    }
    answer_key: dict[str, Any] = {
        "format": "forgegate.phase53-answer-key.v1",
        "status": "IMPLEMENTATION_INDEPENDENT_ORACLE_AND_FORGEGATE_CROSS_CHECKED",
        "human_independent_review": "NOT_PERFORMED",
        "cases": {},
    }
    validation: dict[str, Any] = {
        "format": "forgegate.phase53-fixture-validation.v1",
        "validated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "results": {},
    }

    for pack, spec in PACKS.items():
        pack_root = participant / f"pack-{pack.lower()}"
        pack_root.mkdir()
        (pack_root / "expected-commit.txt").write_text(spec["commit"] + "\n", encoding="ascii")
        pack_manifest: dict[str, Any] = {"commit": spec["commit"], "cases": {}}
        for case, case_spec in CASES.items():
            run = RUN_BY_CASE[pack][case]
            case_root = pack_root / f"run-{run}"
            case_root.mkdir()
            reports = files_for(spec, case_spec["variant"])
            file_manifest: dict[str, Any] = {}
            for report_format, (name, content) in reports.items():
                (case_root / name).write_bytes(content)
                file_manifest[name] = {
                    "format": report_format,
                    "sha256": sha256(content),
                    "size_bytes": len(content),
                }
            pack_manifest["cases"][run] = {"files": file_manifest}
            key = f"{pack}/{run}"
            answer_key["cases"][key] = {
                "semantic_case": case,
                "expected": case_spec["expected"],
                "reasons": expected_reasons(spec, case_spec["variant"]),
                "values": {
                    "errors": 0,
                    "failures": 0,
                    "line_coverage_percent": 100,
                    "tests": spec["tests"],
                },
            }
            validation["results"][key] = validate_with_forgegate(pack, case, spec, reports)
        input_manifest["packs"][pack] = pack_manifest

    for case in CASES:
        totals = []
        counts = []
        for pack in PACKS:
            run = RUN_BY_CASE[pack][case]
            files = input_manifest["packs"][pack]["cases"][run]["files"]
            totals.append(sum(item["size_bytes"] for item in files.values()))
            counts.append(len(files))
        ratio = min(totals) / max(totals)
        if counts[0] != counts[1] or ratio < 0.8:
            raise RuntimeError(
                f"case {case}: unmatched A/B structure or byte size: {counts}, {totals}"
            )
        validation.setdefault("matching", {})[case] = {
            "file_counts": counts,
            "size_bytes": totals,
            "smaller_to_larger_ratio": round(ratio, 4),
        }

    order = []
    for index, case in enumerate(CASES, start=1):
        manual_pack = "A" if index % 2 else "B"
        forgegate_pack = "B" if index % 2 else "A"
        order.append(
            {
                "pair": index,
                "first": {
                    "method": "MANUAL",
                    "material": (
                        f"pack-{manual_pack.lower()}/run-{RUN_BY_CASE[manual_pack][case]}"
                    ),
                },
                "second": {
                    "method": "FORGEGATE",
                    "material": (
                        f"pack-{forgegate_pack.lower()}/run-{RUN_BY_CASE[forgegate_pack][case]}"
                    ),
                },
            }
        )
    (participant / "input-manifest.json").write_bytes(canonical_json(input_manifest))
    (participant / "run-order.json").write_bytes(canonical_json(order))
    answer_bytes = canonical_json(answer_key)
    (assessor / "answer-key.json").write_bytes(answer_bytes)
    validation["answer_key_sha256"] = sha256(answer_bytes)
    validation["input_manifest_sha256"] = sha256(canonical_json(input_manifest))
    (assessor / "validation.json").write_bytes(canonical_json(validation))
    receipt = {
        "format": "forgegate.phase53-preparation-receipt.v1",
        "answer_key_sha256": validation["answer_key_sha256"],
        "input_manifest_sha256": validation["input_manifest_sha256"],
        "packs": len(PACKS),
        "cases_per_pack": len(CASES),
        "forgegate_cross_checks": len(validation["results"]),
        "human_independent_review": "NOT_PERFORMED",
        "human_trials": "NOT_RUN",
    }
    (destination / "preparation-receipt.json").write_bytes(canonical_json(receipt))
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare no-overwrite Phase 53 A/B materials.")
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    try:
        receipt = prepare(args.destination.resolve())
    except (FileExistsError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 3
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
