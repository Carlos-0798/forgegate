"""Opt-in operator/project-scoped jobs with explicitly confirmed report parsing."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Annotated

from fastapi import FastAPI, Header, Query, Request
from fastapi import Path as ApiPath
from pydantic import Field

from forgegate.api.auth import ApiAuthenticationError, ApiAuthenticator, ApiPrincipal
from forgegate.application import CandidateApplication
from forgegate.candidates.models import CANDIDATE_ID_PATTERN
from forgegate.canonical import sha256_fingerprint
from forgegate.collection_jobs import (
    CollectionJobRecord,
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
    jobs: list[CollectionJobRecord]
    next_after_job_id: str | None
    has_more: bool
    observed_at: datetime


class DashboardJobCommand(StrictModel):
    expected_revision: int = Field(ge=0, le=2)


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
    ) -> CollectionJobRecord:
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
        response_model=CollectionJobRecord,
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
    ) -> CollectionJobRecord:
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
        response_model=CollectionJobRecord,
        operation_id="runDashboardJob",
        include_in_schema=False,
    )
    def run_job(
        request: Request,
        job_id: Annotated[str, ApiPath(pattern=JOB_ID_PATTERN)],
        project_id: Annotated[str, Query(pattern=SLUG_PATTERN)],
        command: DashboardJobCommand,
        csrf: Annotated[str | None, Header(alias=DASHBOARD_CSRF_HEADER)] = None,
    ) -> CollectionJobRecord:
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
                )
            finally:
                execution_lock.release()

    @app.post(
        "/app/api/jobs/{job_id}/cancel",
        response_model=CollectionJobRecord,
        operation_id="cancelDashboardJob",
        include_in_schema=False,
    )
    def cancel_job(
        request: Request,
        job_id: Annotated[str, ApiPath(pattern=JOB_ID_PATTERN)],
        project_id: Annotated[str, Query(pattern=SLUG_PATTERN)],
        command: DashboardJobCommand,
        csrf: Annotated[str | None, Header(alias=DASHBOARD_CSRF_HEADER)] = None,
    ) -> CollectionJobRecord:
        return change_job(request, job_id, project_id, command, csrf, recover=False)

    @app.post(
        "/app/api/jobs/{job_id}/recover",
        response_model=CollectionJobRecord,
        operation_id="recoverDashboardJob",
        include_in_schema=False,
    )
    def recover_job(
        request: Request,
        job_id: Annotated[str, ApiPath(pattern=JOB_ID_PATTERN)],
        project_id: Annotated[str, Query(pattern=SLUG_PATTERN)],
        command: DashboardJobCommand,
        csrf: Annotated[str | None, Header(alias=DASHBOARD_CSRF_HEADER)] = None,
    ) -> CollectionJobRecord:
        return change_job(request, job_id, project_id, command, csrf, recover=True)
