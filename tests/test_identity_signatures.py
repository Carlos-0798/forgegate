from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.rsa import generate_private_key
from pydantic import ValidationError
from typer.testing import CliRunner

from forgegate.application import (
    CandidateAdvanceCommand,
    CandidateApplication,
    CandidateAttestCommand,
    CandidateBindEvidenceCommand,
    CandidateCreateCommand,
    CandidateEvaluateCommand,
    ProjectRegisterCommand,
)
from forgegate.assembly import EvidenceBundleAssembly
from forgegate.assurance import AssuranceBundle, publish_assurance_bundle
from forgegate.canonical import sha256_fingerprint
from forgegate.cli import app
from forgegate.config import load_config
from forgegate.domain.enums import CandidateStatus
from forgegate.domain.models import ProjectConfig
from forgegate.identity import (
    AssuranceSignature,
    IdentityError,
    IdentityRole,
    IdentityStatus,
    SigningIdentity,
    TrustedIdentity,
    TrustStore,
    create_assurance_signature,
    create_trust_store,
    derive_signing_identity,
    load_ed25519_private_key,
    load_identity_document,
    publish_assurance_signature,
    render_assurance_signature_json,
    verify_assurance_signature,
)
from forgegate.identity import service as service_module

runner = CliRunner()
SIGNED_AT = datetime(2026, 8, 31, 23, 0, tzinfo=UTC)


def _completed_bundle(tmp_path: Path, repository_root: Path) -> AssuranceBundle:
    application = CandidateApplication.for_database(tmp_path / "identity.db")
    application.initialize()
    project = load_config(repository_root / "examples/sample-python-api/forgegate.yaml")
    assert isinstance(project, ProjectConfig)
    application.register_project(
        ProjectRegisterCommand(
            config=project,
            registered_at=datetime(2026, 8, 30, 11, 59, tzinfo=UTC),
        ),
        idempotency_key="project:identity",
    )
    candidate = application.create_candidate(
        CandidateCreateCommand(
            project_id="sample-api",
            version="1.2.0",
            commit_sha="a" * 40,
            source_branch="main",
            release_track="pull-request",
            created_at=datetime(2026, 8, 30, 12, 0, tzinfo=UTC),
        ),
        idempotency_key="candidate:identity",
    )
    application.advance_candidate(
        candidate.candidate_id,
        CandidateAdvanceCommand(
            to_status=CandidateStatus.COLLECTING,
            expected_revision=0,
            occurred_at=datetime(2026, 8, 30, 12, 1, tzinfo=UTC),
        ),
        idempotency_key="advance:identity:collecting",
    )
    assembly = load_config(repository_root / "tests/golden/evidence_bundle_assembly.json")
    assert isinstance(assembly, EvidenceBundleAssembly)
    application.bind_evidence(
        candidate.candidate_id,
        CandidateBindEvidenceCommand(
            assembly=assembly,
            bound_at=datetime(2026, 8, 30, 20, 31, tzinfo=UTC),
        ),
        idempotency_key="binding:identity",
    )
    for revision, status, occurred_at in (
        (1, CandidateStatus.READY, datetime(2026, 8, 30, 20, 32, tzinfo=UTC)),
        (2, CandidateStatus.EVALUATING, datetime(2026, 8, 30, 20, 33, tzinfo=UTC)),
    ):
        application.advance_candidate(
            candidate.candidate_id,
            CandidateAdvanceCommand(
                to_status=status,
                expected_revision=revision,
                occurred_at=occurred_at,
            ),
            idempotency_key=f"advance:identity:{status.value.lower()}",
        )
    material = application.materialize_policy(
        candidate.candidate_id,
        repository_root / "examples/sample-python-api",
    )
    application.evaluate_candidate(
        candidate.candidate_id,
        CandidateEvaluateCommand(
            policy_material=material,
            expected_revision=3,
            evaluated_at=datetime(2026, 8, 30, 21, 0, tzinfo=UTC),
        ),
        idempotency_key="evaluate:identity",
    )
    application.attest_candidate(
        candidate.candidate_id,
        CandidateAttestCommand(issued_at=datetime(2026, 8, 30, 22, 0, tzinfo=UTC)),
    )
    return application.get_assurance_bundle(candidate.candidate_id)


def _identity_context(
    bundle: AssuranceBundle,
) -> tuple[Ed25519PrivateKey, SigningIdentity, AssuranceSignature, TrustStore]:
    key = Ed25519PrivateKey.generate()
    identity = derive_signing_identity(key, display_name="sample-ci-producer")
    signature = create_assurance_signature(
        bundle,
        signer=identity,
        role=IdentityRole.PRODUCER,
        signed_at=SIGNED_AT,
        private_key=key,
    )
    trust_store = create_trust_store(
        (
            TrustedIdentity(
                identity=identity,
                roles=(IdentityRole.PRODUCER,),
                project_ids=("sample-api",),
            ),
        )
    )
    return key, identity, signature, trust_store


def _write_private_key(path: Path, key: Ed25519PrivateKey, *, encrypted: bool = False) -> None:
    encryption: serialization.KeySerializationEncryption = serialization.NoEncryption()
    if encrypted:
        encryption = serialization.BestAvailableEncryption(b"test-only-password")
    path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=encryption,
        )
    )


def _write_model(path: Path, model: SigningIdentity | TrustStore | AssuranceSignature) -> None:
    path.write_text(model.model_dump_json(indent=2) + "\n", encoding="utf-8")


def test_signature_authenticates_trusted_role_and_project(
    tmp_path: Path, repository_root: Path
) -> None:
    bundle = _completed_bundle(tmp_path, repository_root)
    key, identity, signature, trust_store = _identity_context(bundle)
    repeated = create_assurance_signature(
        bundle,
        signer=identity,
        role=IdentityRole.PRODUCER,
        signed_at=SIGNED_AT,
        private_key=key,
    )
    authenticated = verify_assurance_signature(bundle, signature, trust_store)

    assert signature == repeated
    assert AssuranceSignature.model_validate(signature.model_dump(mode="json")) == signature
    assert authenticated.project_id == "sample-api"
    assert authenticated.identity_id == identity.identity_id
    assert authenticated.role is IdentityRole.PRODUCER
    assert authenticated.trust_store_id == trust_store.trust_store_id


def test_signature_rejects_bundle_key_and_crypto_tampering(
    tmp_path: Path, repository_root: Path
) -> None:
    bundle = _completed_bundle(tmp_path, repository_root)
    _key, identity, signature, trust_store = _identity_context(bundle)
    wrong_key = Ed25519PrivateKey.generate()
    with pytest.raises(IdentityError, match="PRIVATE_KEY_MISMATCH"):
        create_assurance_signature(
            bundle,
            signer=identity,
            role=IdentityRole.PRODUCER,
            signed_at=SIGNED_AT,
            private_key=wrong_key,
        )

    detached = signature.model_copy(update={"bundle_sha256": "0" * 64})
    with pytest.raises(IdentityError, match="BUNDLE_MISMATCH"):
        verify_assurance_signature(bundle, detached, trust_store)

    raw = bytearray(base64.b64decode(signature.signature_base64))
    raw[-1] ^= 1
    altered = signature.model_copy(
        update={"signature_base64": base64.b64encode(raw).decode("ascii")}
    )
    with pytest.raises(IdentityError, match="SIGNATURE_INVALID"):
        verify_assurance_signature(bundle, altered, trust_store)


@pytest.mark.parametrize(
    ("kind", "message"),
    [
        ("unknown", "NOT_TRUSTED"),
        ("metadata", "TRUST_RECORD_MISMATCH"),
        ("revoked", "REVOKED"),
        ("role", "ROLE_DENIED"),
        ("project", "PROJECT_DENIED"),
    ],
)
def test_trust_store_fails_closed(
    tmp_path: Path,
    repository_root: Path,
    kind: str,
    message: str,
) -> None:
    bundle = _completed_bundle(tmp_path, repository_root)
    _key, identity, signature, _trust_store = _identity_context(bundle)
    trusted_identity = identity
    roles = (IdentityRole.PRODUCER,)
    projects = ("sample-api",)
    status = IdentityStatus.ACTIVE
    if kind == "unknown":
        trusted_identity = derive_signing_identity(
            Ed25519PrivateKey.generate(), display_name="other"
        )
    elif kind == "metadata":
        trusted_identity = identity.model_copy(update={"display_name": "unexpected-alias"})
    elif kind == "revoked":
        status = IdentityStatus.REVOKED
    elif kind == "role":
        roles = (IdentityRole.OPERATOR,)
    elif kind == "project":
        projects = ("other-project",)
    trust_store = create_trust_store(
        (
            TrustedIdentity(
                identity=trusted_identity,
                roles=roles,
                project_ids=projects,
                status=status,
            ),
        )
    )
    with pytest.raises(IdentityError, match=message):
        verify_assurance_signature(bundle, signature, trust_store)


def test_identity_models_reject_noncanonical_or_detached_content() -> None:
    key = Ed25519PrivateKey.generate()
    identity = derive_signing_identity(key, display_name="identity")
    with pytest.raises(ValidationError, match="identity_id"):
        identity.model_copy(update={"identity_id": "sha256:" + "0" * 64}).model_validate(
            identity.model_copy(update={"identity_id": "sha256:" + "0" * 64}).model_dump(
                mode="json"
            )
        )
    with pytest.raises(ValidationError, match="decoded length"):
        SigningIdentity(
            identity_id=identity.identity_id,
            display_name="identity",
            public_key_base64=identity.public_key_base64[:-1] + "A",
        )
    with pytest.raises(ValidationError, match="canonically ordered"):
        TrustedIdentity(
            identity=identity,
            roles=(IdentityRole.PRODUCER, IdentityRole.OPERATOR),
            project_ids=("sample-api",),
        )
    with pytest.raises(ValidationError, match="project IDs"):
        TrustedIdentity(
            identity=identity,
            roles=(IdentityRole.PRODUCER,),
            project_ids=("sample-api", "other-project"),
        )
    trusted = TrustedIdentity(
        identity=identity,
        roles=(IdentityRole.PRODUCER,),
        project_ids=("sample-api",),
    )
    trust = create_trust_store((trusted,))
    invalid_trust = trust.model_dump(mode="json")
    invalid_trust["trust_store_id"] = "sha256:" + "0" * 64
    with pytest.raises(ValidationError, match="trust_store_id"):
        TrustStore.model_validate(invalid_trust)
    with pytest.raises(ValidationError, match="unique, canonical"):
        TrustStore(
            trust_store_id=sha256_fingerprint(
                {"identities": [trusted.model_dump(mode="json")] * 2}
            ),
            identities=(trusted, trusted),
        )


def test_signature_model_rejects_time_base64_and_identity_drift(
    tmp_path: Path, repository_root: Path
) -> None:
    bundle = _completed_bundle(tmp_path, repository_root)
    _key, _identity, signature, _trust_store = _identity_context(bundle)
    values = signature.model_dump(mode="json")
    values["signed_at"] = "2026-08-31T23:00:00"
    with pytest.raises(ValidationError, match="UTC offset"):
        AssuranceSignature.model_validate(values)
    values = signature.model_dump(mode="json")
    values["signature_base64"] = signature.signature_base64[:-1] + "A"
    with pytest.raises(ValidationError, match="canonical base64"):
        AssuranceSignature.model_validate(values)
    invalid_signature = signature.model_dump(mode="json")
    invalid_signature["signature_id"] = "sha256:" + "0" * 64
    with pytest.raises(ValidationError, match="signature_id"):
        AssuranceSignature.model_validate(invalid_signature)


def test_private_key_loader_accepts_only_stable_unencrypted_ed25519(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    key_path = tmp_path / "key.pem"
    _write_private_key(key_path, Ed25519PrivateKey.generate())
    assert isinstance(load_ed25519_private_key(key_path), Ed25519PrivateKey)

    encrypted = tmp_path / "encrypted.pem"
    _write_private_key(encrypted, Ed25519PrivateKey.generate(), encrypted=True)
    with pytest.raises(IdentityError, match="unencrypted PKCS8"):
        load_ed25519_private_key(encrypted)
    rsa_path = tmp_path / "rsa.pem"
    rsa_path.write_bytes(
        generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    with pytest.raises(IdentityError, match="not Ed25519"):
        load_ed25519_private_key(rsa_path)
    empty = tmp_path / "empty.pem"
    empty.write_bytes(b"")
    with pytest.raises(IdentityError, match="invalid byte size"):
        load_ed25519_private_key(empty)
    large = tmp_path / "large.pem"
    large.write_bytes(b"x" * (service_module.MAX_PRIVATE_KEY_BYTES + 1))
    with pytest.raises(IdentityError, match="invalid byte size"):
        load_ed25519_private_key(large)
    with pytest.raises(IdentityError, match="regular file"):
        load_ed25519_private_key(tmp_path / "missing.pem")

    original_read = Path.read_bytes

    def changed_read(path: Path) -> bytes:
        payload = original_read(path)
        return payload + b" " if path == key_path else payload

    monkeypatch.setattr(Path, "read_bytes", changed_read)
    with pytest.raises(IdentityError, match="changed while reading"):
        load_ed25519_private_key(key_path)


@pytest.mark.parametrize(
    "payload",
    [
        b'{"schema_version":"forgegate.signing-identity.v1","schema_version":"duplicate"}',
        b'{"schema_version":"forgegate.signing-identity.v1","value":NaN}',
        b"\xff",
        b"[]",
        b'{"schema_version":"unknown.v1"}',
        b'{"schema_version":"forgegate.signing-identity.v1"}',
    ],
)
def test_identity_document_loader_rejects_untrusted_json(tmp_path: Path, payload: bytes) -> None:
    path = tmp_path / "identity.json"
    path.write_bytes(payload)
    with pytest.raises(IdentityError, match="IDENTITY_DOCUMENT_INVALID"):
        load_identity_document(path)


def test_identity_document_loader_is_bounded_and_detects_changed_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "oversized.json"
    path.write_bytes(b"x" * (service_module.MAX_IDENTITY_DOCUMENT_BYTES + 1))
    with pytest.raises(IdentityError, match="invalid byte size"):
        load_identity_document(path)
    with pytest.raises(IdentityError, match="regular file"):
        load_identity_document(tmp_path / "missing.json")

    key = Ed25519PrivateKey.generate()
    identity = derive_signing_identity(key, display_name="identity")
    _write_model(path, identity)
    original_read = Path.read_bytes

    def changed_read(candidate: Path) -> bytes:
        payload = original_read(candidate)
        return payload + b" " if candidate == path else payload

    monkeypatch.setattr(Path, "read_bytes", changed_read)
    with pytest.raises(IdentityError, match="changed while reading"):
        load_identity_document(path)


def test_signature_publication_is_content_addressed_and_fail_closed(
    tmp_path: Path, repository_root: Path
) -> None:
    bundle = _completed_bundle(tmp_path, repository_root)
    _key, _identity, signature, _trust_store = _identity_context(bundle)
    root = tmp_path / "signatures"
    first = publish_assurance_signature(signature, root)
    second = publish_assurance_signature(signature, root)

    assert first.replayed is False
    assert second.replayed is True
    assert first.path == second.path
    assert first.path.read_text(encoding="utf-8") == render_assurance_signature_json(signature)
    assert load_identity_document(first.path) == signature

    first.path.write_text("conflict", encoding="utf-8")
    with pytest.raises(IdentityError, match="OUTPUT_CONFLICT"):
        publish_assurance_signature(signature, root)
    occupied = tmp_path / "occupied"
    occupied.write_text("file", encoding="utf-8")
    with pytest.raises(IdentityError, match="OUTPUT_ROOT_INVALID"):
        publish_assurance_signature(signature, occupied)


def test_signature_publication_translates_io_and_concurrent_replay(
    tmp_path: Path,
    repository_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _completed_bundle(tmp_path, repository_root)
    _key, _identity, signature, _trust_store = _identity_context(bundle)
    root = tmp_path / "concurrent"
    root.mkdir()
    payload = render_assurance_signature_json(signature).encode("utf-8")
    original_replace = Path.replace

    def concurrent_replace(staging: Path, target: Path) -> Path:
        target.write_bytes(payload)
        raise OSError("concurrent writer")

    monkeypatch.setattr(Path, "replace", concurrent_replace)
    assert publish_assurance_signature(signature, root).replayed is True
    monkeypatch.setattr(Path, "replace", original_replace)

    def fail_mkstemp(*_args: Any, **_kwargs: Any) -> tuple[int, str]:
        raise OSError("staging denied")

    monkeypatch.setattr("forgegate.identity.publisher.tempfile.mkstemp", fail_mkstemp)
    with pytest.raises(IdentityError, match="cannot publish signature"):
        publish_assurance_signature(signature, tmp_path / "io-failure")


def test_signature_publication_rejects_symlink_signals_and_unreadable_replay(
    tmp_path: Path,
    repository_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _completed_bundle(tmp_path, repository_root)
    _key, _identity, signature, _trust_store = _identity_context(bundle)
    root = tmp_path / "signatures"
    published = publish_assurance_signature(signature, root)
    original_is_symlink = Path.is_symlink

    def report_target_symlink(path: Path) -> bool:
        return path == published.path or original_is_symlink(path)

    monkeypatch.setattr(Path, "is_symlink", report_target_symlink)
    with pytest.raises(IdentityError, match="unsafe symlink"):
        publish_assurance_signature(signature, root)
    monkeypatch.setattr(Path, "is_symlink", original_is_symlink)

    original_read = Path.read_bytes

    def fail_target_read(path: Path) -> bytes:
        if path == published.path:
            raise OSError("read denied")
        return original_read(path)

    monkeypatch.setattr(Path, "read_bytes", fail_target_read)
    with pytest.raises(IdentityError, match="cannot verify existing signature"):
        publish_assurance_signature(signature, root)


def test_identity_and_signature_cli_end_to_end(tmp_path: Path, repository_root: Path) -> None:
    bundle = _completed_bundle(tmp_path, repository_root)
    portable = publish_assurance_bundle(bundle, tmp_path / "portable")
    key_path = tmp_path / "producer-key.pem"
    _write_private_key(key_path, Ed25519PrivateKey.generate())

    derived = runner.invoke(
        app,
        ["identity", "derive", str(key_path), "--display-name", "sample-ci-producer"],
    )
    assert derived.exit_code == 0
    identity_path = tmp_path / "identity.json"
    identity_path.write_text(derived.stdout, encoding="utf-8")
    identity = load_identity_document(identity_path)
    assert isinstance(identity, SigningIdentity)

    trusted = runner.invoke(
        app,
        [
            "identity",
            "trust",
            str(identity_path),
            "--role",
            "producer",
            "--project",
            "sample-api",
        ],
    )
    assert trusted.exit_code == 0
    trust_path = tmp_path / "trust-store.json"
    trust_path.write_text(trusted.stdout, encoding="utf-8")

    command = [
        "sign-assurance",
        str(portable.directory),
        str(identity_path),
        str(key_path),
        "--role",
        "producer",
        "--signed-at",
        "2026-08-31T23:00:00Z",
        "--output-root",
        str(tmp_path / "signatures"),
    ]
    first = runner.invoke(app, command)
    second = runner.invoke(app, command)
    assert first.exit_code == second.exit_code == 0
    assert json.loads(first.stdout)["output_replayed"] is False
    signed = json.loads(second.stdout)
    assert signed["output_replayed"] is True

    verified = runner.invoke(
        app,
        [
            "verify-assurance-signature",
            str(portable.directory),
            signed["signature_path"],
            str(trust_path),
        ],
    )
    assert verified.exit_code == 0
    report = json.loads(verified.stdout)
    assert report["status"] == "AUTHENTICATED"
    assert report["role"] == "producer"
    assert report["project_id"] == "sample-api"
    assert report["trusted_time"] == "not_established"
    assert report["source_artifact_authentication"] == "not_established"


def test_identity_cli_rejects_wrong_document_types_and_bad_time(
    tmp_path: Path, repository_root: Path
) -> None:
    bundle = _completed_bundle(tmp_path, repository_root)
    portable = publish_assurance_bundle(bundle, tmp_path / "portable")
    key_path = tmp_path / "key.pem"
    key = Ed25519PrivateKey.generate()
    _write_private_key(key_path, key)
    identity = derive_signing_identity(key, display_name="identity")
    _write_model(tmp_path / "identity.json", identity)
    trust_store = create_trust_store(
        (
            TrustedIdentity(
                identity=identity,
                roles=(IdentityRole.PRODUCER,),
                project_ids=("sample-api",),
            ),
        )
    )
    _write_model(tmp_path / "trust.json", trust_store)

    wrong_trust_input = runner.invoke(
        app,
        [
            "identity",
            "trust",
            str(tmp_path / "trust.json"),
            "--role",
            "producer",
            "--project",
            "sample-api",
        ],
    )
    assert wrong_trust_input.exit_code == 3
    bad_time = runner.invoke(
        app,
        [
            "sign-assurance",
            str(portable.directory),
            str(tmp_path / "identity.json"),
            str(key_path),
            "--role",
            "producer",
            "--signed-at",
            "not-a-time",
            "--output-root",
            str(tmp_path / "signatures"),
        ],
    )
    assert bad_time.exit_code == 3

    _write_model(tmp_path / "signature-wrong.json", identity)
    wrong_signature = runner.invoke(
        app,
        [
            "verify-assurance-signature",
            str(portable.directory),
            str(tmp_path / "signature-wrong.json"),
            str(tmp_path / "trust.json"),
        ],
    )
    assert wrong_signature.exit_code == 3
