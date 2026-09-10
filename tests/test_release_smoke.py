from __future__ import annotations

import importlib.util
import subprocess
import sys
from contextlib import nullcontext
from pathlib import Path
from types import ModuleType

import pytest


def _load_smoke(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    tools = Path(__file__).resolve().parents[1] / "tools"
    monkeypatch.syspath_prepend(str(tools))
    spec = importlib.util.spec_from_file_location(
        "forgegate_release_smoke", tools / "release_smoke.py"
    )
    assert spec is not None and spec.loader is not None
    smoke = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(smoke)
    return smoke


def test_release_smoke_unexpected_success_fails_the_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    smoke = _load_smoke(monkeypatch)

    with pytest.raises(SystemExit) as error:
        smoke.run([sys.executable, "-c", "pass"], cwd=tmp_path, expected_returncode=3)

    assert error.value.code not in (None, 0)


def test_release_smoke_resolves_temporary_directory_alias_before_building(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    smoke = _load_smoke(monkeypatch)
    fixture_root = tmp_path.resolve(strict=True)
    physical = fixture_root / "physical-temporary-directory"
    physical.mkdir()
    alias = fixture_root / "temporary-directory-alias"
    if sys.platform == "win32":
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-Command",
                "& { param($link, $target) "
                "New-Item -ItemType Junction -Path $link -Target $target | Out-Null }",
                str(alias),
                str(physical),
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
        assert result.returncode == 0, result.stderr
        assert alias.is_junction()
    else:
        alias.symlink_to(physical, target_is_directory=True)
        assert alias.is_symlink()

    def check_build_destination(destination: Path) -> None:
        assert destination == physical / "dist"
        assert destination.parent.is_dir()
        raise RuntimeError("canonical temporary root checked before build")

    monkeypatch.setattr(
        smoke.tempfile, "TemporaryDirectory", lambda **_kwargs: nullcontext(str(alias))
    )
    monkeypatch.setattr(smoke, "build_windows_delivery", check_build_destination)
    try:
        with pytest.raises(RuntimeError, match="canonical temporary root checked"):
            smoke.main()
    finally:
        # Remove only the verified alias entry, never the physical target directory.
        assert alias.parent == fixture_root
        if sys.platform == "win32":
            assert alias.is_junction()
            alias.rmdir()
        else:
            assert alias.is_symlink()
            alias.unlink()
        assert physical.is_dir()
