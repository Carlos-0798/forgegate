"""Generate synthetic browser boundary inputs in a new, isolated directory."""

from __future__ import annotations

import argparse
from pathlib import Path


def generate(output: Path) -> None:
    """Never overwrite an existing directory or touch a server or device."""
    output.mkdir(parents=True, exist_ok=False)
    summary = b'<coverage lines-covered="1" lines-valid="2"/>\n'
    (output / "coverage-summary.xml").write_bytes(summary)
    # Valid XML padded to exactly one byte beyond the browser's per-report cap.
    (output / "coverage-oversize.xml").write_bytes(
        summary + b" " * (1024 * 1024 + 1 - len(summary))
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="new synthetic fixture directory")
    args = parser.parse_args()
    generate(args.output)
    print("Created synthetic summary-only and 1,048,577-byte coverage fixtures.")


if __name__ == "__main__":
    main()
