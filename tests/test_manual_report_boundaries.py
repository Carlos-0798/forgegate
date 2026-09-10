"""Reproducibility and no-overwrite checks for manual browser boundary inputs."""

import subprocess
import sys
from pathlib import Path


def test_boundary_fixtures_are_exact_and_not_overwritten(tmp_path: Path) -> None:
    script = Path(__file__).resolve().parents[1] / "tools/manual_report_boundaries.py"
    output = tmp_path / "browser fixtures"
    command = [sys.executable, str(script), str(output)]
    first = subprocess.run(command, capture_output=True, check=False)
    assert first.returncode == 0
    summary = (output / "coverage-summary.xml").read_bytes()
    oversized = (output / "coverage-oversize.xml").read_bytes()
    assert summary == b'<coverage lines-covered="1" lines-valid="2"/>\n'
    assert len(oversized) == 1_048_577
    assert oversized == summary + b" " * (1_048_577 - len(summary))
    second = subprocess.run(command, capture_output=True, check=False)
    assert second.returncode != 0
    assert (output / "coverage-summary.xml").read_bytes() == summary
    assert (output / "coverage-oversize.xml").read_bytes() == oversized
