from __future__ import annotations

import pytest

from forgegate.bounded_parsing import (
    StructureLimitError,
    enforce_json_structure_limits,
    enforce_xml_structure_limits,
    enforce_yaml_structure_limits,
)


def test_json_preflight_counts_structure_without_misreading_strings() -> None:
    enforce_json_structure_limits(b'{"text":"[[{}]]"}', max_nodes=3, max_depth=1)
    with pytest.raises(StructureLimitError, match="node"):
        enforce_json_structure_limits(b"[0,1]", max_nodes=2, max_depth=2)
    with pytest.raises(StructureLimitError, match="depth"):
        enforce_json_structure_limits(b"[[0]]", max_nodes=8, max_depth=1)


def test_xml_preflight_rejects_element_and_depth_excess() -> None:
    enforce_xml_structure_limits(b"<root><child /></root>", max_elements=2, max_depth=2)
    with pytest.raises(StructureLimitError, match="element"):
        enforce_xml_structure_limits(b"<root><child /></root>", max_elements=1, max_depth=2)
    with pytest.raises(StructureLimitError, match="depth"):
        enforce_xml_structure_limits(b"<root><child /></root>", max_elements=2, max_depth=1)


def test_yaml_preflight_rejects_node_and_depth_excess() -> None:
    enforce_yaml_structure_limits("root: [one, two]\n", max_nodes=5, max_depth=2)
    with pytest.raises(StructureLimitError, match="node"):
        enforce_yaml_structure_limits("root: [one, two]\n", max_nodes=4, max_depth=2)
    with pytest.raises(StructureLimitError, match="depth"):
        enforce_yaml_structure_limits("root: [[one]]\n", max_nodes=8, max_depth=2)


def test_preflights_defer_syntax_errors_to_authoritative_parsers() -> None:
    enforce_json_structure_limits(b'{"unterminated":', max_nodes=8, max_depth=4)
    enforce_xml_structure_limits(b"<unterminated>", max_elements=8, max_depth=4)
    enforce_yaml_structure_limits("[unterminated", max_nodes=8, max_depth=4)
