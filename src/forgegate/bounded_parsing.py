from __future__ import annotations

from xml.parsers import expat

import yaml


class StructureLimitError(ValueError):
    """Raised before a parser materializes an over-complex document."""

    def __init__(self, kind: str, limit: int) -> None:
        self.kind = kind
        self.limit = limit
        super().__init__(f"document exceeds {limit} {kind} limit")


def enforce_json_structure_limits(content: bytes, *, max_nodes: int, max_depth: int) -> None:
    """Bound JSON tokens and container depth without constructing an object tree.

    The normal JSON decoder remains authoritative for syntax. Counting object keys
    as nodes is intentionally conservative and keeps this preflight independent of
    decoder allocation behavior.
    """

    _require_positive_limits(max_nodes, max_depth)
    nodes = 0
    depth = 0
    stack: list[int] = []
    index = 0
    length = len(content)
    whitespace = b" \t\r\n"
    delimiters = b"{}[],: \t\r\n"

    def observe_node() -> None:
        nonlocal nodes
        nodes += 1
        if nodes > max_nodes:
            raise StructureLimitError("node", max_nodes)

    while index < length:
        value = content[index]
        if value in whitespace:
            index += 1
            continue
        if value == 0x22:  # JSON string
            observe_node()
            index += 1
            while index < length:
                current = content[index]
                if current == 0x5C:  # escape; syntax is checked by json.loads
                    index += 2
                    continue
                index += 1
                if current == 0x22:
                    break
            continue
        if value in (0x7B, 0x5B):  # { or [
            observe_node()
            stack.append(value)
            depth += 1
            if depth > max_depth:
                raise StructureLimitError("depth", max_depth)
            index += 1
            continue
        if value in (0x7D, 0x5D):  # } or ]
            expected = 0x7B if value == 0x7D else 0x5B
            if stack and stack[-1] == expected:
                stack.pop()
                depth -= 1
            index += 1
            continue
        if value in (0x2C, 0x3A):  # comma or colon
            index += 1
            continue

        observe_node()
        index += 1
        while index < length and content[index] not in delimiters:
            index += 1


def enforce_xml_structure_limits(content: bytes, *, max_elements: int, max_depth: int) -> None:
    """Use Expat events to enforce XML limits before ElementTree construction."""

    _require_positive_limits(max_elements, max_depth)
    elements = 0
    depth = 0
    parser = expat.ParserCreate()

    def start_element(_: str, __: dict[str, str]) -> None:
        nonlocal elements, depth
        elements += 1
        if elements > max_elements:
            raise StructureLimitError("element", max_elements)
        depth += 1
        if depth > max_depth:
            raise StructureLimitError("depth", max_depth)

    def end_element(_: str) -> None:
        nonlocal depth
        depth -= 1

    parser.StartElementHandler = start_element
    parser.EndElementHandler = end_element
    try:
        for offset in range(0, len(content), 64 * 1024):
            parser.Parse(content[offset : offset + 64 * 1024], False)
        parser.Parse(b"", True)
    except StructureLimitError:
        raise
    except expat.ExpatError:
        # The format-specific ElementTree pass emits the established parse error.
        return


def enforce_yaml_structure_limits(text: str, *, max_nodes: int, max_depth: int) -> None:
    """Bound a YAML event stream before SafeLoader constructs Python objects."""

    _require_positive_limits(max_nodes, max_depth)
    nodes = 0
    depth = 0
    try:
        events = yaml.parse(text, Loader=yaml.SafeLoader)
        for event in events:
            if isinstance(event, (yaml.MappingStartEvent, yaml.SequenceStartEvent)):
                nodes += 1
                depth += 1
                if nodes > max_nodes:
                    raise StructureLimitError("node", max_nodes)
                if depth > max_depth:
                    raise StructureLimitError("depth", max_depth)
            elif isinstance(event, (yaml.MappingEndEvent, yaml.SequenceEndEvent)):
                depth -= 1
            elif isinstance(event, (yaml.ScalarEvent, yaml.AliasEvent)):
                nodes += 1
                if nodes > max_nodes:
                    raise StructureLimitError("node", max_nodes)
    except StructureLimitError:
        raise
    except yaml.YAMLError:
        # The construction pass retains the existing user-facing parse error.
        return


def _require_positive_limits(size_limit: int, depth_limit: int) -> None:
    if size_limit <= 0 or depth_limit <= 0:
        raise ValueError("structure limits must be positive")


__all__ = [
    "StructureLimitError",
    "enforce_json_structure_limits",
    "enforce_xml_structure_limits",
    "enforce_yaml_structure_limits",
]
