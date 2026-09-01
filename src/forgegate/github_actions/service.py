from __future__ import annotations

import html
import os
import re
import stat
from pathlib import Path

from forgegate.assurance import AssuranceBundle, VerifiedAssuranceBundle
from forgegate.canonical import sha256_fingerprint
from forgegate.domain.enums import Decision
from forgegate.github_actions.models import (
    FULL_COMMIT_PATTERN,
    RECOMMENDED_CONCLUSIONS,
    GitHubActionReport,
)

MAX_GITHUB_COMMAND_FILE_BYTES = 4 * 1024 * 1024
MAX_GITHUB_APPEND_BYTES = 64 * 1024
_SAFE_ERROR_CODE = re.compile(r"^[A-Z][A-Z0-9_]{1,127}$")
_EXIT_CODES = {
    Decision.PASS: 0,
    Decision.FAIL: 1,
    Decision.REVIEW: 2,
    Decision.ERROR: 3,
}


class GitHubActionGateError(RuntimeError):
    """Stable GitHub Actions bridge failure."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


def create_github_action_report(
    verified: VerifiedAssuranceBundle,
    *,
    expected_commit: str,
) -> GitHubActionReport:
    normalized_expected = expected_commit.strip().lower()
    if re.fullmatch(FULL_COMMIT_PATTERN, normalized_expected) is None:
        raise GitHubActionGateError(
            "GITHUB_EXPECTED_COMMIT_INVALID",
            "expected commit must be a complete lowercase or uppercase 40- or 64-hex object ID",
        )
    candidate = verified.bundle.attestation.candidate
    normalized_candidate = candidate.commit_sha.lower()
    if re.fullmatch(FULL_COMMIT_PATTERN, normalized_candidate) is None:
        raise GitHubActionGateError(
            "GITHUB_CANDIDATE_COMMIT_INCOMPLETE",
            "the assurance candidate must retain a complete 40- or 64-hex object ID",
        )
    if normalized_candidate != normalized_expected:
        raise GitHubActionGateError(
            "GITHUB_COMMIT_MISMATCH",
            "the assurance candidate commit does not match the expected CI commit",
        )
    evaluation = verified.bundle.attestation.policy_evaluation
    if evaluation is None:
        raise GitHubActionGateError(
            "GITHUB_EVALUATION_MISSING",
            "the verified assurance bundle does not contain a policy evaluation",
        )
    identity = {
        "status": "VALID",
        "integration": "github-actions",
        "bundle_id": verified.bundle.bundle_id,
        "manifest_id": verified.manifest.manifest_id,
        "project_id": candidate.project_id,
        "candidate_id": candidate.candidate_id,
        "candidate_commit": normalized_candidate,
        "expected_commit": normalized_expected,
        "commit_binding": "exact",
        "decision": evaluation.decision.value,
        "recommended_conclusion": RECOMMENDED_CONCLUSIONS[evaluation.decision],
        "assurance": verified.bundle.assurance,
        "verification_scope": verified.bundle.verification_scope,
        "source_artifact_bytes": verified.bundle.source_artifact_bytes,
    }
    return GitHubActionReport(
        report_id=sha256_fingerprint(identity),
        status="VALID",
        integration="github-actions",
        bundle_id=verified.bundle.bundle_id,
        manifest_id=verified.manifest.manifest_id,
        project_id=candidate.project_id,
        candidate_id=candidate.candidate_id,
        candidate_commit=normalized_candidate,
        expected_commit=normalized_expected,
        commit_binding="exact",
        decision=evaluation.decision,
        recommended_conclusion=RECOMMENDED_CONCLUSIONS[evaluation.decision],
        assurance=verified.bundle.assurance,
        verification_scope=verified.bundle.verification_scope,
        source_artifact_bytes=verified.bundle.source_artifact_bytes,
    )


def github_action_exit_code(decision: Decision) -> int:
    return _EXIT_CODES[decision]


def render_github_outputs(report: GitHubActionReport) -> str:
    values = (
        ("gate_status", report.status),
        ("decision", report.decision.value),
        ("recommended_conclusion", report.recommended_conclusion),
        ("report_id", report.report_id),
        ("bundle_id", report.bundle_id),
        ("candidate_id", report.candidate_id),
        ("project_id", report.project_id),
        ("candidate_commit", report.candidate_commit),
        ("assurance", report.assurance),
    )
    return "".join(f"{name}={value}\n" for name, value in values)


def render_github_error_outputs() -> str:
    return "gate_status=ERROR\ndecision=ERROR\nrecommended_conclusion=failure\n"


def render_github_step_summary(
    report: GitHubActionReport,
    bundle: AssuranceBundle,
) -> str:
    evaluation = bundle.attestation.policy_evaluation
    assert evaluation is not None
    lines = [
        "# ForgeGate release gate",
        "",
        f"**Decision: {report.decision.value}**",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Project | `{report.project_id}` |",
        f"| Candidate | `{report.candidate_id}` |",
        f"| Commit binding | `exact` — `{report.candidate_commit}` |",
        f"| Bundle | `{report.bundle_id}` |",
        f"| Assurance | `{report.assurance}` |",
        "",
        "## Rule results",
        "",
        "| Rule | Decision | Reason | Explanation |",
        "|---|---|---|---|",
    ]
    omitted = 0
    for index, result in enumerate(evaluation.rule_results):
        row = (
            f"| {_markdown_cell(result.rule_id)} | {result.decision.value} | "
            f"`{result.reason_code}` | {_markdown_cell(result.explanation)} |"
        )
        candidate = "\n".join((*lines, row, "")).encode("utf-8")
        if len(candidate) > MAX_GITHUB_APPEND_BYTES - 1024:
            omitted = len(evaluation.rule_results) - index
            break
        lines.append(row)
    if omitted:
        lines.extend(("", f"_{omitted} additional rule result(s) omitted by the summary limit._"))
    lines.extend(
        (
            "",
            "## Verification boundary",
            "",
            "- Verified exact portable-bundle members, canonical bytes, manifest hashes, "
            "document identities, and cross-document associations.",
            "- Matched the complete candidate commit exactly to the caller-supplied CI commit.",
            "- Did not rerun collectors or source artifacts, authenticate their producers, "
            "establish trusted time, or prove hardware, bench, field, or production behavior.",
            "- This bridge writes a GitHub Job Summary and outputs only; it does not call the "
            "GitHub Checks, Pull Requests, Issues, or Releases APIs.",
            "",
        )
    )
    rendered = "\n".join(lines)
    return rendered


def render_github_error_summary(code: str) -> str:
    safe_code = code if _SAFE_ERROR_CODE.fullmatch(code) else "GITHUB_GATE_ERROR"
    return "\n".join(
        (
            "# ForgeGate release gate",
            "",
            "**Decision: ERROR**",
            "",
            f"Gate error: `{safe_code}`",
            "",
            "No release decision was accepted. Inspect the failed step's sanitized error output.",
            "",
        )
    )


def append_github_file(path: Path, payload: str) -> None:
    encoded = payload.encode("utf-8")
    if not encoded or len(encoded) > MAX_GITHUB_APPEND_BYTES:
        raise GitHubActionGateError(
            "GITHUB_FILE_PAYLOAD_INVALID", "GitHub command-file append must be 1 to 65536 bytes"
        )
    requested = path.expanduser()
    if requested.is_symlink() or (requested.exists() and not requested.is_file()):
        raise GitHubActionGateError(
            "GITHUB_FILE_UNSAFE", "GitHub command-file path must be a non-symlink regular file"
        )
    try:
        parent = requested.parent.resolve(strict=True)
    except OSError as exc:
        raise GitHubActionGateError(
            "GITHUB_FILE_PARENT_INVALID", "GitHub command-file parent is unavailable"
        ) from exc
    if not parent.is_dir():
        raise GitHubActionGateError(
            "GITHUB_FILE_PARENT_INVALID", "GitHub command-file parent must be a directory"
        )
    target = parent / requested.name
    flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(target, flags, 0o600)
        with os.fdopen(descriptor, "ab") as stream:
            metadata = os.fstat(stream.fileno())
            if not stat.S_ISREG(metadata.st_mode):
                raise GitHubActionGateError(
                    "GITHUB_FILE_UNSAFE", "GitHub command-file target is not a regular file"
                )
            if metadata.st_size + len(encoded) > MAX_GITHUB_COMMAND_FILE_BYTES:
                raise GitHubActionGateError(
                    "GITHUB_FILE_TOO_LARGE", "GitHub command file would exceed the 4 MiB limit"
                )
            stream.write(encoded)
            stream.flush()
    except GitHubActionGateError:
        raise
    except OSError as exc:
        raise GitHubActionGateError(
            "GITHUB_FILE_IO", "cannot append the GitHub command file"
        ) from exc


def _markdown_cell(value: str) -> str:
    return (
        html.escape(value, quote=False).replace("|", "&#124;").replace("\r", " ").replace("\n", " ")
    )


__all__ = [
    "MAX_GITHUB_APPEND_BYTES",
    "MAX_GITHUB_COMMAND_FILE_BYTES",
    "GitHubActionGateError",
    "append_github_file",
    "create_github_action_report",
    "github_action_exit_code",
    "render_github_error_outputs",
    "render_github_error_summary",
    "render_github_outputs",
    "render_github_step_summary",
]
