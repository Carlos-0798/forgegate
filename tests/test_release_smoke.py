from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


def test_release_smoke_unexpected_success_fails_the_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tools = Path(__file__).resolve().parents[1] / "tools"
    monkeypatch.syspath_prepend(str(tools))
    spec = importlib.util.spec_from_file_location(
        "forgegate_release_smoke", tools / "release_smoke.py"
    )
    assert spec is not None and spec.loader is not None
    smoke = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(smoke)

    with pytest.raises(SystemExit) as error:
        smoke.run([sys.executable, "-c", "pass"], cwd=tmp_path, expected_returncode=3)

    assert error.value.code not in (None, 0)
