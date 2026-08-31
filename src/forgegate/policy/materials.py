from __future__ import annotations

import base64
import binascii
import hashlib
from typing import Any, Literal

import yaml
from pydantic import Field, model_validator

from forgegate.canonical import sha256_fingerprint
from forgegate.domain.models import (
    SLUG_PATTERN,
    ArtifactReference,
    PolicyConfig,
    StrictModel,
    canonical_release_track_name,
)

MAX_POLICY_BYTES = 1024 * 1024
MAX_POLICY_BASE64_CHARS = ((MAX_POLICY_BYTES + 2) // 3) * 4
POLICY_MEDIA_TYPES = frozenset(
    {
        "application/json",
        "application/yaml",
        "application/x-yaml",
        "text/yaml",
    }
)


class PolicyMaterial(StrictModel):
    """Exact policy bytes authorized by one immutable project profile."""

    schema_version: Literal["forgegate.policy-material.v1"] = "forgegate.policy-material.v1"
    material_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    project_id: str = Field(pattern=SLUG_PATTERN)
    project_profile_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    project_profile_version: int = Field(ge=1)
    release_track: str = Field(pattern=SLUG_PATTERN)
    artifact: ArtifactReference
    content_base64: str = Field(min_length=4, max_length=MAX_POLICY_BASE64_CHARS)
    policy: PolicyConfig
    policy_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def material_must_match_exact_bytes(self) -> PolicyMaterial:
        content = decode_policy_content(self.content_base64)
        if self.artifact.media_type not in POLICY_MEDIA_TYPES:
            raise ValueError("policy artifact media type is unsupported")
        _require_relative_policy_path(self.artifact.path_or_uri)
        if self.artifact.size_bytes != len(content):
            raise ValueError("policy artifact size does not match exact bytes")
        if self.artifact.sha256 != hashlib.sha256(content).hexdigest():
            raise ValueError("policy artifact SHA-256 does not match exact bytes")
        parsed = parse_policy_bytes(content)
        if parsed != self.policy:
            raise ValueError("embedded policy does not match exact policy bytes")
        expected_policy_fingerprint = sha256_fingerprint(self.policy.model_dump(mode="json"))
        if self.policy_fingerprint != expected_policy_fingerprint:
            raise ValueError("policy_fingerprint does not match the parsed policy")
        if self.policy.name != self.release_track:
            raise ValueError("policy name must match the canonical release track")
        identity = self.model_dump(mode="json", exclude={"schema_version", "material_id"})
        if self.material_id != sha256_fingerprint(identity):
            raise ValueError("material_id does not match policy material content")
        return self


def create_policy_material(
    *,
    project_id: str,
    project_profile_id: str,
    project_profile_version: int,
    release_track: str,
    artifact: ArtifactReference,
    content: bytes,
) -> PolicyMaterial:
    canonical_track = canonical_release_track_name(release_track)
    policy = parse_policy_bytes(content)
    values: dict[str, Any] = {
        "project_id": project_id,
        "project_profile_id": project_profile_id,
        "project_profile_version": project_profile_version,
        "release_track": canonical_track,
        "artifact": artifact.model_dump(mode="json"),
        "content_base64": base64.b64encode(content).decode("ascii"),
        "policy": policy.model_dump(mode="json"),
        "policy_fingerprint": sha256_fingerprint(policy.model_dump(mode="json")),
    }
    return PolicyMaterial(material_id=sha256_fingerprint(values), **values)


def decode_policy_content(value: str) -> bytes:
    try:
        content = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("content_base64 must be canonical base64") from exc
    if base64.b64encode(content).decode("ascii") != value:
        raise ValueError("content_base64 must be canonical base64")
    return content


def parse_policy_bytes(content: bytes) -> PolicyConfig:
    if len(content) > MAX_POLICY_BYTES:
        raise ValueError(f"policy material exceeds {MAX_POLICY_BYTES} byte limit")
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("policy material must be UTF-8") from exc
    try:
        raw = yaml.load(text, Loader=_UniqueKeySafeLoader)
    except yaml.YAMLError as exc:
        raise ValueError(f"cannot parse policy material: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError("policy material root must be a mapping")
    if raw.get("schema_version") != "forgegate.policy.v1":
        raise ValueError("policy material must contain forgegate.policy.v1")
    return PolicyConfig.model_validate(raw)


def policy_media_type(path: str) -> str:
    lowered = path.lower()
    if lowered.endswith(".json"):
        return "application/json"
    if lowered.endswith((".yaml", ".yml")):
        return "application/yaml"
    raise ValueError("policy path must end in .json, .yaml, or .yml")


def _require_relative_policy_path(value: str) -> None:
    normalized = value.replace("\\", "/")
    if normalized.startswith("/") or (
        len(normalized) >= 3 and normalized[0].isalpha() and normalized[1:3] == ":/"
    ):
        raise ValueError("policy artifact path must be relative")
    if any(part in {"", ".", ".."} for part in normalized.split("/")):
        raise ValueError("policy artifact path must be normalized without traversal")


class _UniqueKeySafeLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(
    loader: _UniqueKeySafeLoader,
    node: yaml.MappingNode,
    deep: bool = False,
) -> dict[object, object]:
    mapping: dict[object, object] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in mapping
        except TypeError as exc:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "found an unhashable key",
                key_node.start_mark,
            ) from exc
        if duplicate:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key: {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


__all__ = [
    "MAX_POLICY_BYTES",
    "POLICY_MEDIA_TYPES",
    "PolicyMaterial",
    "create_policy_material",
    "decode_policy_content",
    "parse_policy_bytes",
    "policy_media_type",
]
