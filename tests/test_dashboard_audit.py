from pathlib import Path

import pytest

from tests.test_dashboard import ORIGIN_HEADER, _activate, _candidate_payload, _dashboard_client


def test_dashboard_audit_pagination_filter_scope_and_read_only(
    tmp_path: Path, repository_root: Path
) -> None:
    with _dashboard_client(tmp_path, repository_root) as client:
        assert client.get("/app/api/audit-events?project_id=sample-api").status_code == 401
        activated = _activate(client)
        ids = []
        for index in range(27):
            created = client.post(
                "/app/api/candidates",
                headers={
                    **ORIGIN_HEADER,
                    "X-ForgeGate-CSRF": activated["csrf_token"],
                    "Idempotency-Key": f"audit:pagination:{index}",
                },
                json=_candidate_payload(version=f"audit-{index}"),
            )
            assert created.status_code == 201
            ids.append(created.json()["candidate_id"])
        url = "/app/api/audit-events?project_id=sample-api&limit=25"
        first = client.get(url)
        assert first.status_code == 200
        assert first.headers["Cache-Control"] == "no-store"
        assert first.json()["has_more"] is True
        cursor = first.json()["next_after_sequence"]
        second = client.get(f"{url}&after_sequence={cursor}").json()
        events = first.json()["events"] + second["events"]
        assert len(events) == 28  # One registration and 27 successful creations.
        assert len({event["sequence"] for event in events}) == 28
        assert second["has_more"] is False
        assert events[0]["actor"] is None
        assert events[1]["actor"]["display_name"] is not None
        filtered = client.get(f"{url}&candidate_id={ids[-1]}").json()
        assert len(filtered["events"]) == 1
        assert filtered["events"][0]["candidate_id"] == ids[-1]
        assert client.get("/app/api/audit-events?project_id=other-project").status_code == 403
        assert client.get(url, headers={"Origin": "https://example.invalid"}).status_code == 403
        assert client.get(f"{url}&candidate_id=cand-{'f' * 24}").json()["events"] == []
        assert client.get(url).json() == first.json()  # Reads append no release audit event.


@pytest.mark.parametrize(
    "query",
    [
        "project_id=INVALID",
        "project_id=sample-api&candidate_id=bad",
        "project_id=sample-api&after_sequence=-1",
        "project_id=sample-api&limit=201",
    ],
)
def test_dashboard_audit_rejects_malformed_filters(
    tmp_path: Path, repository_root: Path, query: str
) -> None:
    with _dashboard_client(tmp_path, repository_root) as client:
        _activate(client)
        response = client.get(f"/app/api/audit-events?{query}")
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "API_REQUEST_VALIDATION_FAILED"
