"""Reviewed Dashboard job parsing, exact export, and candidate evidence handoff."""

import secrets
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Annotated, Literal

from fastapi import FastAPI, Header, Query, Request, Response
from fastapi import Path as ApiPath
from pydantic import Field, field_validator

from forgegate.api.auth import ApiAuthenticationError, ApiAuthenticator, ApiPrincipal
from forgegate.application import CandidateApplication, CandidateBindEvidenceCommand
from forgegate.assembly import EvidenceBundleAssembly
from forgegate.candidates import CandidateEvidenceBinding
from forgegate.candidates.models import CANDIDATE_ID_PATTERN, FINGERPRINT_PATTERN
from forgegate.canonical import canonical_json, sha256_fingerprint
from forgegate.collection_jobs import (
    MAX_JOB_REVISION,
    CollectionJobRecordLike,
    CollectionJobRequest,
    CollectionJobReview,
    CollectionJobStore,
    JobError,
)
from forgegate.dashboard.routes import (
    DASHBOARD_CSRF_HEADER,
    DASHBOARD_SESSION_COOKIE,
    _require_same_origin,
)
from forgegate.dashboard.sessions import DashboardSessionManager
from forgegate.domain.models import SLUG_PATTERN, StrictModel

JOB_ID_PATTERN = r"^job-[0-9a-f]{32}$"


class DashboardJobPage(StrictModel):
    enabled: bool
    project_id: str
    jobs: list[CollectionJobRecordLike]
    next_after_job_id: str | None
    has_more: bool
    observed_at: datetime


class DashboardJobCommand(StrictModel):
    expected_revision: int = Field(ge=0, le=MAX_JOB_REVISION)


class DashboardJobAssemblyCommand(StrictModel):
    expected_job_revision: int = Field(ge=0, le=MAX_JOB_REVISION)
    expected_result_fingerprint: str = Field(pattern=FINGERPRINT_PATTERN)
    expected_assembly_id: str = Field(pattern=FINGERPRINT_PATTERN)


class DashboardJobBindEvidenceCommand(DashboardJobAssemblyCommand):
    expected_candidate_revision: int = Field(ge=0)
    expected_candidate_fingerprint: str = Field(pattern=FINGERPRINT_PATTERN)
    bound_at: datetime

    @field_validator("bound_at")
    @classmethod
    def bound_at_must_include_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("bound_at must include a UTC offset")
        return value


class DashboardJobEvidenceBindingResult(StrictModel):
    schema_version: Literal["forgegate.dashboard-job-evidence-binding.v1"] = (
        "forgegate.dashboard-job-evidence-binding.v1"
    )
    job_id: str = Field(pattern=JOB_ID_PATTERN)
    result_fingerprint: str = Field(pattern=FINGERPRINT_PATTERN)
    assembly_id: str = Field(pattern=FINGERPRINT_PATTERN)
    assembly_fingerprint: str = Field(pattern=FINGERPRINT_PATTERN)
    binding: CandidateEvidenceBinding
    candidate_transition: Literal["NOT_PERFORMED"] = "NOT_PERFORMED"
    policy_decision: Literal["NOT_PERFORMED"] = "NOT_PERFORMED"
    source_artifact_bytes: Literal["not_embedded"] = "not_embedded"


@contextmanager
def _job_errors() -> Iterator[None]:
    try:
        yield
    except JobError as exc:
        code = str(exc)
        status = 404 if code == "JOB_NOT_FOUND" else 409
        if code in {
            "JOB_STORE_CORRUPT",
            "JOB_STORE_IO_FAILED",
            "JOB_STORE_PATH_INVALID",
            "JOB_STORE_VERSION_INVALID",
            "JOB_STORE_MIGRATION_REQUIRED",
        }:
            status = 503
        raise ApiAuthenticationError(
            code,
            "Job operation unavailable; refresh authoritative state before retrying.",
            status_code=status,
        ) from exc


def install_job_routes(
    app: FastAPI,
    *,
    application: CandidateApplication,
    authenticator: ApiAuthenticator,
    manager: DashboardSessionManager,
    store_path: Path | None,
) -> None:
    store = None if store_path is None else CollectionJobStore(store_path)
    execution_lock = Lock()  # One foreground HTTP parser per app instance, not a worker pool.
    execution_owner_id = "executor-" + secrets.token_hex(16)
    if store is not None:
        store.require_dashboard_store()  # No creation or migration during startup.

    def authorize(
        request: Request, project_id: str, *, write: bool = False, csrf: str | None = None
    ) -> ApiPrincipal:
        _require_same_origin(request, required=write)
        session, principal = manager.session(request.cookies.get(DASHBOARD_SESSION_COOKIE))
        request.state.authenticated_principal = principal
        if write:
            manager.require_csrf(session, csrf)
        authenticator.require_project(principal, project_id, write=write, audit=True)
        return principal

    def configured() -> CollectionJobStore:
        if store is None:
            raise ApiAuthenticationError(
                "DASHBOARD_JOBS_DISABLED",
                "No job store is configured for this service.",
                status_code=503,
            )
        store.require_dashboard_store()
        return store

    def review_for_project(
        job_store: CollectionJobStore, job_id: str, project_id: str
    ) -> CollectionJobReview:
        review = job_store.review(job_id, project_id=project_id)
        # A configured queue must not expose foreign candidates from another candidate DB.
        candidate = application.get_candidate(review.record.candidate_id)
        if candidate.project_id != project_id:
            raise JobError("JOB_NOT_FOUND")
        return review

    def bindable_assembly(
        job_store: CollectionJobStore,
        job_id: str,
        project_id: str,
        command: DashboardJobAssemblyCommand,
    ) -> tuple[CollectionJobRecordLike, EvidenceBundleAssembly, str]:
        review = review_for_project(job_store, job_id, project_id)
        record = review.record
        if record.state != "SUCCEEDED" or review.result is None or review.result.assembly is None:
            raise JobError("JOB_RESULT_NOT_BINDABLE")
        if record.revision != command.expected_job_revision:
            raise JobError("JOB_STATE_CONFLICT")
        assembly = review.result.assembly
        assembly_fingerprint = sha256_fingerprint(assembly.model_dump(mode="json"))
        if (
            record.result_fingerprint != command.expected_result_fingerprint
            or assembly.assembly_id != command.expected_assembly_id
        ):
            raise JobError("JOB_RESULT_IDENTITY_CONFLICT")
        return record, assembly, assembly_fingerprint

    @app.get(
        "/app/api/jobs",
        response_model=DashboardJobPage,
        operation_id="listDashboardJobs",
        include_in_schema=False,
    )
    def list_jobs(
        request: Request,
        project_id: Annotated[str, Query(pattern=SLUG_PATTERN)],
        after_job_id: Annotated[str | None, Query(pattern=JOB_ID_PATTERN)] = None,
        candidate_id: Annotated[str | None, Query(pattern=CANDIDATE_ID_PATTERN)] = None,
        limit: Annotated[int, Query(ge=1, le=25)] = 25,
    ) -> DashboardJobPage:
        authorize(request, project_id)
        visible = []
        with _job_errors():
            if store is not None:
                configured()
                # Phase 34 hard-caps the entire store at 100 jobs. Filter before paging.
                for record in store.list_jobs(after=after_job_id or "", limit=100):
                    if record.project_id == project_id and (
                        candidate_id is None or record.candidate_id == candidate_id
                    ):
                        review_for_project(store, record.job_id, project_id)
                        visible.append(record)
        page = visible[:limit]
        return DashboardJobPage(
            enabled=store is not None,
            project_id=project_id,
            jobs=page,
            next_after_job_id=page[-1].job_id if page else None,
            has_more=len(visible) > limit,
            observed_at=datetime.now(UTC),
        )

    @app.get(
        "/app/api/jobs/{job_id}",
        response_model=CollectionJobReview,
        operation_id="reviewDashboardJob",
        include_in_schema=False,
    )
    def show_job(
        request: Request,
        job_id: Annotated[str, ApiPath(pattern=JOB_ID_PATTERN)],
        project_id: Annotated[str, Query(pattern=SLUG_PATTERN)],
    ) -> CollectionJobReview:
        authorize(request, project_id)
        with _job_errors():
            return review_for_project(configured(), job_id, project_id)

    def change_job(
        request: Request,
        job_id: str,
        project_id: str,
        command: DashboardJobCommand,
        csrf: str | None,
        *,
        recover: bool,
    ) -> CollectionJobRecordLike:
        principal = authorize(request, project_id, write=True, csrf=csrf)
        with _job_errors():
            job_store = configured()
            review_for_project(job_store, job_id, project_id)
            operation = job_store.recover if recover else job_store.cancel
            return operation(
                job_id,
                command.expected_revision,
                actor=principal.audit_actor(),
                project_id=project_id,
            )

    @app.post(
        "/app/api/jobs",
        response_model=CollectionJobRecordLike,
        operation_id="submitDashboardJob",
        include_in_schema=False,
    )
    def submit_job(
        request: Request,
        project_id: Annotated[str, Query(pattern=SLUG_PATTERN)],
        command: CollectionJobRequest,
        idempotency_key: Annotated[
            str,
            Header(
                alias="Idempotency-Key",
                min_length=1,
                max_length=128,
                pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$",
            ),
        ],
        csrf: Annotated[str | None, Header(alias=DASHBOARD_CSRF_HEADER)] = None,
    ) -> CollectionJobRecordLike:
        principal = authorize(request, project_id, write=True, csrf=csrf)
        candidate = application.get_candidate(command.candidate_id)
        if candidate.project_id != project_id:
            raise ApiAuthenticationError(
                "JOB_NOT_FOUND", "Job candidate not found.", status_code=404
            )
        # Isolate keys across identities/projects and from CLI callers; do not expose raw keys.
        key = "dashboard:" + sha256_fingerprint(
            {
                "identity": principal.audit_actor().identity_id,
                "project": project_id,
                "key": idempotency_key,
            }
        ).removeprefix("sha256:")
        with _job_errors():
            return configured().submit(
                command, application, key=key, actor=principal.audit_actor(), project_id=project_id
            )

    @app.post(
        "/app/api/jobs/{job_id}/run",
        response_model=CollectionJobRecordLike,
        operation_id="runDashboardJob",
        include_in_schema=False,
    )
    def run_job(
        request: Request,
        job_id: Annotated[str, ApiPath(pattern=JOB_ID_PATTERN)],
        project_id: Annotated[str, Query(pattern=SLUG_PATTERN)],
        command: DashboardJobCommand,
        csrf: Annotated[str | None, Header(alias=DASHBOARD_CSRF_HEADER)] = None,
    ) -> CollectionJobRecordLike:
        principal = authorize(request, project_id, write=True, csrf=csrf)
        with _job_errors():
            job_store = configured()
            review_for_project(job_store, job_id, project_id)
            if not execution_lock.acquire(blocking=False):
                raise ApiAuthenticationError(
                    "DASHBOARD_JOB_RUN_BUSY",
                    "Another report parser is active. Inspect jobs and retry manually later.",
                    status_code=429,
                )
            try:
                return job_store.run(
                    job_id,
                    command.expected_revision,
                    application,
                    actor=principal.audit_actor(),
                    project_id=project_id,
                    execution_owner_id=execution_owner_id,
                )
            finally:
                execution_lock.release()

    @app.post(
        "/app/api/jobs/{job_id}/assembly-export",
        response_class=Response,
        operation_id="exportDashboardJobAssembly",
        include_in_schema=False,
        responses={
            200: {
                "description": "Exact canonical evidence assembly JSON",
                "content": {
                    "application/vnd.forgegate.evidence-bundle-assembly+json": {
                        "schema": {"type": "string", "format": "binary"}
                    }
                },
            }
        },
    )
    def export_job_assembly(
        request: Request,
        job_id: Annotated[str, ApiPath(pattern=JOB_ID_PATTERN)],
        project_id: Annotated[str, Query(pattern=SLUG_PATTERN)],
        command: DashboardJobAssemblyCommand,
        csrf: Annotated[str | None, Header(alias=DASHBOARD_CSRF_HEADER)] = None,
    ) -> Response:
        authorize(request, project_id, write=True, csrf=csrf)
        with _job_errors():
            _record, assembly, assembly_fingerprint = bindable_assembly(
                configured(), job_id, project_id, command
            )
        content = canonical_json(assembly.model_dump(mode="json")).encode("utf-8")
        filename = f"evidence-assembly-{assembly.assembly_id.removeprefix('sha256:')}.json"
        return Response(
            content=content,
            media_type="application/vnd.forgegate.evidence-bundle-assembly+json",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-ForgeGate-Job-Result": command.expected_result_fingerprint,
                "X-ForgeGate-Assembly": assembly.assembly_id,
                "X-ForgeGate-Assembly-Fingerprint": assembly_fingerprint,
            },
        )

    @app.post(
        "/app/api/jobs/{job_id}/bind-evidence",
        response_model=DashboardJobEvidenceBindingResult,
        operation_id="bindDashboardJobEvidence",
        include_in_schema=False,
    )
    def bind_job_evidence(
        request: Request,
        job_id: Annotated[str, ApiPath(pattern=JOB_ID_PATTERN)],
        project_id: Annotated[str, Query(pattern=SLUG_PATTERN)],
        command: DashboardJobBindEvidenceCommand,
        idempotency_key: Annotated[
            str,
            Header(
                alias="Idempotency-Key",
                min_length=1,
                max_length=128,
                pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$",
            ),
        ],
        csrf: Annotated[str | None, Header(alias=DASHBOARD_CSRF_HEADER)] = None,
    ) -> DashboardJobEvidenceBindingResult:
        principal = authorize(request, project_id, write=True, csrf=csrf)
        with _job_errors():
            record, assembly, assembly_fingerprint = bindable_assembly(
                configured(), job_id, project_id, command
            )
            candidate = application.get_candidate(record.candidate_id)
            candidate_fingerprint = sha256_fingerprint(candidate.model_dump(mode="json"))
            if (
                candidate.revision != command.expected_candidate_revision
                or candidate_fingerprint != command.expected_candidate_fingerprint
                or candidate_fingerprint != record.candidate_fingerprint
            ):
                raise JobError("JOB_CANDIDATE_CONFLICT")
        key = "dashboard-job-bind:" + sha256_fingerprint(
            {
                "identity": principal.audit_actor().identity_id,
                "project": project_id,
                "job": job_id,
                "key": idempotency_key,
            }
        ).removeprefix("sha256:")
        binding = application.bind_evidence(
            record.candidate_id,
            CandidateBindEvidenceCommand(assembly=assembly, bound_at=command.bound_at),
            idempotency_key=key,
            actor=principal.audit_actor(),
        )
        return DashboardJobEvidenceBindingResult(
            job_id=job_id,
            result_fingerprint=command.expected_result_fingerprint,
            assembly_id=assembly.assembly_id,
            assembly_fingerprint=assembly_fingerprint,
            binding=binding,
        )

    @app.post(
        "/app/api/jobs/{job_id}/cancel",
        response_model=CollectionJobRecordLike,
        operation_id="cancelDashboardJob",
        include_in_schema=False,
    )
    def cancel_job(
        request: Request,
        job_id: Annotated[str, ApiPath(pattern=JOB_ID_PATTERN)],
        project_id: Annotated[str, Query(pattern=SLUG_PATTERN)],
        command: DashboardJobCommand,
        csrf: Annotated[str | None, Header(alias=DASHBOARD_CSRF_HEADER)] = None,
    ) -> CollectionJobRecordLike:
        return change_job(request, job_id, project_id, command, csrf, recover=False)

    @app.post(
        "/app/api/jobs/{job_id}/recover",
        response_model=CollectionJobRecordLike,
        operation_id="recoverDashboardJob",
        include_in_schema=False,
    )
    def recover_job(
        request: Request,
        job_id: Annotated[str, ApiPath(pattern=JOB_ID_PATTERN)],
        project_id: Annotated[str, Query(pattern=SLUG_PATTERN)],
        command: DashboardJobCommand,
        csrf: Annotated[str | None, Header(alias=DASHBOARD_CSRF_HEADER)] = None,
    ) -> CollectionJobRecordLike:
        return change_job(request, job_id, project_id, command, csrf, recover=True)
