from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from forgegate.artifacts import ArtifactError, ArtifactRegistry, RegisteredArtifact
from forgegate.collectors.base import CollectionResult

from .models import COLLECTION_RESULT_MEDIA_TYPE
from .service import LoadedCollectionResult

DEFAULT_MAX_JSON_NODES = 250_000
DEFAULT_MAX_JSON_DEPTH = 32


class CollectionResultLoadError(ValueError):
    def __init__(self, code: str, message: str, *, location: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.location = location


class CollectionResultLoader:
    def __init__(
        self,
        registry: ArtifactRegistry,
        *,
        max_nodes: int = DEFAULT_MAX_JSON_NODES,
        max_depth: int = DEFAULT_MAX_JSON_DEPTH,
    ) -> None:
        if min(max_nodes, max_depth) <= 0:
            raise ValueError("collection-result loader limits must be positive")
        self._registry = registry
        self._max_nodes = max_nodes
        self._max_depth = max_depth

    def load(self, source_path: str) -> LoadedCollectionResult:
        artifact = self._registry.register(
            source_path,
            media_type=COLLECTION_RESULT_MEDIA_TYPE,
        )
        root = _load_json(artifact)
        self._enforce_tree_limits(root)
        if not isinstance(root, dict):
            raise CollectionResultLoadError(
                "COLLECTION_RESULT_ROOT_INVALID",
                "collection result root must be an object",
                location="$",
            )
        try:
            result = CollectionResult.model_validate(root)
        except ValidationError as exc:
            error = exc.errors(include_url=False, include_input=False)[0]
            raise CollectionResultLoadError(
                "COLLECTION_RESULT_CONTRACT_INVALID",
                f"collection result violates its contract: {error['msg']}",
                location=_error_location(error.get("loc", ())),
            ) from exc
        for expected in result.artifacts:
            try:
                observed = self._registry.register(
                    expected.path_or_uri, media_type=expected.media_type
                ).reference
            except ArtifactError as exc:
                raise CollectionResultLoadError(
                    "COLLECTION_ARTIFACT_UNAVAILABLE",
                    f"cannot verify referenced artifact: {expected.path_or_uri}",
                    location=expected.path_or_uri,
                ) from exc
            if observed != expected:
                raise CollectionResultLoadError(
                    "COLLECTION_ARTIFACT_MISMATCH",
                    f"referenced artifact metadata does not match bytes: {expected.path_or_uri}",
                    location=expected.path_or_uri,
                )
        return LoadedCollectionResult(source=artifact.reference, result=result)

    def _enforce_tree_limits(self, root: Any) -> None:
        observed = 0
        stack: list[tuple[Any, int]] = [(root, 1)]
        while stack:
            value, depth = stack.pop()
            observed += 1
            if observed > self._max_nodes:
                raise CollectionResultLoadError(
                    "COLLECTION_RESULT_NODE_LIMIT",
                    f"collection result exceeds the {self._max_nodes} JSON node limit",
                )
            if depth > self._max_depth:
                raise CollectionResultLoadError(
                    "COLLECTION_RESULT_DEPTH_LIMIT",
                    f"collection result exceeds the {self._max_depth} JSON depth limit",
                )
            if isinstance(value, dict):
                stack.extend((item, depth + 1) for item in value.values())
            elif isinstance(value, list):
                stack.extend((item, depth + 1) for item in value)


def _load_json(artifact: RegisteredArtifact) -> Any:
    content = artifact.content
    if b"\x00" in content:
        raise CollectionResultLoadError(
            "COLLECTION_RESULT_UNSUPPORTED_ENCODING",
            "collection result must be UTF-8 and cannot contain NUL bytes",
        )
    try:
        text = content.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise CollectionResultLoadError(
            "COLLECTION_RESULT_UNSUPPORTED_ENCODING",
            "collection result must be UTF-8",
        ) from exc
    try:
        return json.loads(
            text,
            object_pairs_hook=_object_without_duplicates,
            parse_constant=_reject_json_constant,
        )
    except CollectionResultLoadError:
        raise
    except (json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise CollectionResultLoadError(
            "COLLECTION_RESULT_JSON_INVALID", f"invalid collection-result JSON: {exc}"
        ) from exc


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise CollectionResultLoadError(
                "COLLECTION_RESULT_DUPLICATE_KEY", f"duplicate JSON object key: {key}"
            )
        value[key] = item
    return value


def _reject_json_constant(value: str) -> Any:
    raise CollectionResultLoadError(
        "COLLECTION_RESULT_NUMBER_INVALID", f"non-finite JSON number: {value}"
    )


def _error_location(parts: Any) -> str:
    location = "$"
    for part in parts:
        location += f"[{part}]" if isinstance(part, int) else f".{part}"
    return location


__all__ = [
    "CollectionResultLoadError",
    "CollectionResultLoader",
]
