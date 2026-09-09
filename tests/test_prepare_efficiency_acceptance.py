from __future__ import annotations

import json
import subprocess
import sys


def test_prepare_matched_blinded_inputs_and_refuse_overwrite(tmp_path, repository_root):
    destination = tmp_path / "phase53"
    command = [
        sys.executable,
        str(repository_root / "tools/prepare_efficiency_acceptance.py"),
        str(destination),
    ]
    first = subprocess.run(
        command, cwd=repository_root, check=False, capture_output=True, text=True
    )
    assert first.returncode == 0, first.stdout + first.stderr
    receipt = json.loads(first.stdout)
    assert receipt == json.loads((destination / "preparation-receipt.json").read_text())
    assert receipt["packs"] == 2
    assert receipt["cases_per_pack"] == 6
    assert receipt["forgegate_cross_checks"] == 12
    assert receipt["human_independent_review"] == "NOT_PERFORMED"
    assert receipt["human_trials"] == "NOT_RUN"

    participant = destination / "participant"
    assert not (participant / "answer-key.json").exists()
    order = json.loads((participant / "run-order.json").read_text())
    assert [item["pair"] for item in order] == [1, 2, 3, 4, 5, 6]
    assert all("case" not in item for item in order)
    assert {item["first"]["method"] for item in order} == {"MANUAL"}
    assert {item["second"]["method"] for item in order} == {"FORGEGATE"}
    assert len({item["first"]["material"] for item in order}) == 6
    assert len({item["second"]["material"] for item in order}) == 6
    answer_key = json.loads((destination / "assessor/answer-key.json").read_text())
    assert {item["semantic_case"] for item in answer_key["cases"].values()} == {
        "01",
        "02",
        "03",
        "04",
        "05",
        "06",
    }
    validation = json.loads((destination / "assessor/validation.json").read_text())
    assert {item["actual"] for item in validation["results"].values()} == {
        "PASS",
        "FAIL",
        "REVIEW",
        "INPUT_REJECTED",
    }
    assert all(item["smaller_to_larger_ratio"] >= 0.8 for item in validation["matching"].values())

    second = subprocess.run(
        command, cwd=repository_root, check=False, capture_output=True, text=True
    )
    assert second.returncode == 3
    assert "destination already exists" in second.stdout
