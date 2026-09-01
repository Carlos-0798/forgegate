from __future__ import annotations

import hashlib
from typing import Literal

from pydantic import Field, model_validator

from forgegate.attestations import ReleaseAttestation
from forgegate.candidates import CandidateEvidenceBinding, ProfileBoundReleaseCandidate
from forgegate.canonical import sha256_fingerprint
from forgegate.domain.models import StrictModel, canonical_release_track_name
from forgegate.policy import PolicyMaterial
from forgegate.policy.models import ProfileAuthorizedPolicyEvaluation
from forgegate.projects import ProjectProfileDocument, profile_id

FINGERPRINT_PATTERN = r"^sha256:[0-9a-f]{64}$"
HEX_SHA256_PATTERN = r"^[0-9a-f]{64}$"


class AssuranceBundle(StrictModel):
    """Portable, self-validating projection of one completed release decision."""

    schema_version: Literal["forgegate.assurance-bundle.v1"] = "forgegate.assurance-bundle.v1"
    bundle_id: str = Field(pattern=FINGERPRINT_PATTERN)
    generator: Literal["forgegate"] = "forgegate"
    generator_version: str = Field(min_length=1, max_length=120)
    assurance: Literal["unsigned_local"] = "unsigned_local"
    verification_scope: Literal["retained_documents_and_embedded_policy_bytes"] = (
        "retained_documents_and_embedded_policy_bytes"
    )
    source_artifact_bytes: Literal["not_embedded"] = "not_embedded"
    project_profile: ProjectProfileDocument
    evidence_binding: CandidateEvidenceBinding
    policy_material: PolicyMaterial
    attestation: ReleaseAttestation

    @model_validator(mode="after")
    def bundle_must_be_cross_document_consistent(self) -> AssuranceBundle:
        candidate = self.attestation.candidate
        if not isinstance(candidate, ProfileBoundReleaseCandidate):
            raise ValueError("assurance bundle requires a profile-bound candidate")
        if (
            self.generator_version != self.attestation.generator_version
            or self.assurance != self.attestation.assurance
        ):
            raise ValueError("bundle generator metadata must match the attestation")
        if (
            self.project_profile.project_id != candidate.project_id
            or self.project_profile.profile_version != candidate.project_profile_version
            or profile_id(self.project_profile) != candidate.project_profile_id
        ):
            raise ValueError("project profile does not match the terminal candidate")
        if self.evidence_binding.candidate.candidate_id != candidate.candidate_id:
            raise ValueError("evidence binding does not match the terminal candidate")
        if (
            self.policy_material.project_id != candidate.project_id
            or self.policy_material.project_profile_id != candidate.project_profile_id
            or self.policy_material.project_profile_version != candidate.project_profile_version
            or self.policy_material.release_track != candidate.release_track
        ):
            raise ValueError("policy material does not match candidate profile authority")
        self._validate_profile_policy_path(candidate)
        evaluation = self.attestation.policy_evaluation
        if not isinstance(evaluation, ProfileAuthorizedPolicyEvaluation):
            raise ValueError("assurance bundle requires a profile-authorized policy evaluation")
        if (
            evaluation.policy_material_id != self.policy_material.material_id
            or evaluation.policy_artifact_sha256 != self.policy_material.artifact.sha256
            or evaluation.project_profile_id != candidate.project_profile_id
            or evaluation.project_profile_version != candidate.project_profile_version
            or evaluation.evidence_fingerprint
            != sha256_fingerprint(self.evidence_binding.assembly.bundle.model_dump(mode="json"))
        ):
            raise ValueError("evaluation does not match bundled policy material and evidence")
        identity = self.model_dump(mode="json", exclude={"schema_version", "bundle_id"})
        if self.bundle_id != sha256_fingerprint(identity):
            raise ValueError("bundle_id does not match assurance bundle content")
        return self

    def _validate_profile_policy_path(self, candidate: ProfileBoundReleaseCandidate) -> None:
        matches = [
            track
            for name, track in self.project_profile.config.release_tracks.items()
            if canonical_release_track_name(name) == candidate.release_track
        ]
        if len(matches) != 1:
            raise ValueError("candidate release track is not uniquely authorized by the profile")
        if matches[0].policy.replace("\\", "/") != self.policy_material.artifact.path_or_uri:
            raise ValueError("policy material path is not authorized by the bundled profile")


class AssuranceBundleFile(StrictModel):
    path: Literal["assurance-bundle.json", "README.md"]
    media_type: Literal["application/json", "text/markdown"]
    size_bytes: int = Field(ge=1)
    sha256: str = Field(pattern=HEX_SHA256_PATTERN)


class AssuranceBundleManifest(StrictModel):
    schema_version: Literal["forgegate.assurance-bundle-manifest.v1"] = (
        "forgegate.assurance-bundle-manifest.v1"
    )
    manifest_id: str = Field(pattern=FINGERPRINT_PATTERN)
    bundle_id: str = Field(pattern=FINGERPRINT_PATTERN)
    files: tuple[AssuranceBundleFile, AssuranceBundleFile] = Field(min_length=2, max_length=2)

    @model_validator(mode="after")
    def manifest_must_be_canonical(self) -> AssuranceBundleManifest:
        expected = ("README.md", "assurance-bundle.json")
        if tuple(item.path for item in self.files) != expected:
            raise ValueError("manifest files must use canonical path order")
        media_types = {item.path: item.media_type for item in self.files}
        if media_types != {
            "README.md": "text/markdown",
            "assurance-bundle.json": "application/json",
        }:
            raise ValueError("manifest file media types are invalid")
        identity = self.model_dump(mode="json", exclude={"schema_version", "manifest_id"})
        if self.manifest_id != sha256_fingerprint(identity):
            raise ValueError("manifest_id does not match manifest content")
        return self


def create_assurance_bundle(
    *,
    project_profile: ProjectProfileDocument,
    evidence_binding: CandidateEvidenceBinding,
    policy_material: PolicyMaterial,
    attestation: ReleaseAttestation,
) -> AssuranceBundle:
    identity = {
        "generator": "forgegate",
        "generator_version": attestation.generator_version,
        "assurance": attestation.assurance,
        "verification_scope": "retained_documents_and_embedded_policy_bytes",
        "source_artifact_bytes": "not_embedded",
        "project_profile": project_profile.model_dump(mode="json"),
        "evidence_binding": evidence_binding.model_dump(mode="json"),
        "policy_material": policy_material.model_dump(mode="json"),
        "attestation": attestation.model_dump(mode="json"),
    }
    return AssuranceBundle(
        bundle_id=sha256_fingerprint(identity),
        generator_version=attestation.generator_version,
        assurance="unsigned_local",
        verification_scope="retained_documents_and_embedded_policy_bytes",
        source_artifact_bytes="not_embedded",
        project_profile=project_profile,
        evidence_binding=evidence_binding,
        policy_material=policy_material,
        attestation=attestation,
    )


def create_assurance_manifest(
    bundle: AssuranceBundle,
    *,
    bundle_json: bytes,
    readme: bytes,
) -> AssuranceBundleManifest:
    files = (
        AssuranceBundleFile(
            path="README.md",
            media_type="text/markdown",
            size_bytes=len(readme),
            sha256=hashlib.sha256(readme).hexdigest(),
        ),
        AssuranceBundleFile(
            path="assurance-bundle.json",
            media_type="application/json",
            size_bytes=len(bundle_json),
            sha256=hashlib.sha256(bundle_json).hexdigest(),
        ),
    )
    identity = {
        "bundle_id": bundle.bundle_id,
        "files": [item.model_dump(mode="json") for item in files],
    }
    return AssuranceBundleManifest(
        manifest_id=sha256_fingerprint(identity),
        bundle_id=bundle.bundle_id,
        files=files,
    )


__all__ = [
    "AssuranceBundle",
    "AssuranceBundleFile",
    "AssuranceBundleManifest",
    "create_assurance_bundle",
    "create_assurance_manifest",
]
