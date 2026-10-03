import json
import copy
from unittest import mock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from dashboard import server

from dashboard.server import (
    FIXTURE,
    download_report,
    get_evidence,
    get_config,
    get_graph,
    get_site,
    get_summary,
    index,
    list_reports,
    resolve_default_theme,
    retry_run,
    start_run,
)


@pytest.fixture(autouse=True)
def isolated_runtime():
    """Run/report checks should work even when the user clears demo history."""
    previous = copy.deepcopy(server.runtime)
    server.runtime["runs"] = [{
        "id": "run-003", "sampleKey": "health", "siteId": "site-coimbra-t1",
        "sourceType": "PUBLIC_HEALTH", "executionStatus": "failed", "fhirOutcome": "UPLOAD_FAILED",
        "startedAt": "2026-09-30T10:20:00Z", "attempt": 1, "error": "FHIR transaction service unavailable",
    }]
    server.runtime["reports"] = [{
        "id": "report-001", "siteId": "site-c1-mondego", "title": "Mondego C1 briefing",
        "status": "generated", "visibility": "published", "ownerId": "user-analyst-01",
        "requestedAt": "2026-10-02T09:59:55Z", "generatedAt": "2026-10-02T10:00:00Z",
        "snapshotObservationIds": [item["id"] for item in FIXTURE["observations"] if item["siteId"] == "site-c1-mondego"],
        "snapshotFindingIds": [item["id"] for item in FIXTURE["findings"] if item["siteId"] == "site-c1-mondego"],
    }]
    yield
    server.runtime.clear()
    server.runtime.update(previous)


def test_fixture_references_resolve():
    observation_ids = {item["id"] for item in FIXTURE["observations"]}
    finding_ids = {item["id"] for item in FIXTURE["findings"]}
    evidence_ids = {item["id"] for item in FIXTURE["evidence"]}
    site_ids = {item["id"] for item in FIXTURE["sites"]}
    node_ids = {item["id"] for item in FIXTURE["graph"]["nodes"]}

    assert all(item["siteId"] in site_ids for item in FIXTURE["observations"])
    assert all(item["siteId"] in site_ids for item in FIXTURE["findings"])
    assert all(set(item.get("evidenceIds", [])) <= evidence_ids for item in FIXTURE["findings"])
    assert all(set(site["observationIds"]) <= observation_ids for site in FIXTURE["sites"])
    assert all(set(site["findingIds"]) <= finding_ids for site in FIXTURE["sites"])
    assert all(edge["source"] in node_ids and edge["target"] in node_ids for edge in FIXTURE["graph"]["edges"])


def test_theme_configuration_is_validated_and_applied_before_paint():
    config = get_config()
    assert config["defaultTheme"] in {theme["id"] for theme in config["themes"]}
    assert [theme["id"] for theme in config["themes"]] == ["aqua", "aqua-dark", "white", "dark"]
    assert resolve_default_theme("dark") == "dark"
    assert resolve_default_theme("not-a-theme") == "aqua"
    page = index().body.decode("utf-8")
    assert f'data-theme="{config["defaultTheme"]}"' in page
    assert "__DEFAULT_THEME__" not in page
    assert config["defaultMode"] in {"mock", "live"}
    assert f'data-default-mode="{config["defaultMode"]}"' in page
    assert "__DEFAULT_MODE__" not in page


def test_viewer_scope_and_evidence_permission_are_enforced():
    summary = get_summary("viewer")
    assert [site["id"] for site in summary["sites"]] == ["site-c1-mondego"]

    with pytest.raises(HTTPException) as denied_site:
        get_site("site-coimbra-t1", "viewer")
    assert denied_site.value.status_code == 404

    with pytest.raises(HTTPException) as denied_evidence:
        get_evidence("evidence-nitrate-observation", "viewer")
    assert denied_evidence.value.status_code == 403


def test_operator_can_start_and_retry_runs_but_not_read_reports():
    started = start_run({"sampleKey": "iot"}, "operator")
    assert started["executionStatus"] == "running"
    assert len(started["stages"]) == 6

    retry = retry_run("run-003", "operator")
    assert retry["retryOf"] == "run-003"
    assert retry["attempt"] == 2

    with pytest.raises(HTTPException) as reports:
        list_reports("operator")
    assert reports.value.status_code == 403


def test_published_report_downloads_are_real_html_and_json_bytes():
    listing = list_reports("viewer")
    report = listing["reports"][0]
    assert report["visibility"] == "published"
    assert {item["format"] for item in report["files"]} == {"html", "json"}

    html_response = download_report("report-001", "html", "viewer")
    assert html_response.media_type == "text/html"
    assert b"Association only, not causation" in html_response.body
    expected_size = next(item["sizeBytes"] for item in report["files"] if item["format"] == "html")
    assert len(html_response.body) == expected_size

    json_response = download_report("report-001", "json", "viewer")
    assert json.loads(json_response.body)["site"]["id"] == "site-c1-mondego"


def test_graph_is_scoped_and_direct_unauthorized_requests_fail():
    graph = get_graph("site-c1-mondego", "analyst")
    node_ids = {node["id"] for node in graph["nodes"]}
    assert all(edge["source"] in node_ids and edge["target"] in node_ids for edge in graph["edges"])

    with pytest.raises(HTTPException) as viewer_graph:
        get_graph("site-c1-mondego", "viewer")
    assert viewer_graph.value.status_code == 403


class FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return b'{"ok": true}'


def test_live_site_proxies_with_configured_timeout():
    with mock.patch.object(server, "LIVE_TIMEOUT_SECONDS", 42.0), mock.patch("urllib.request.urlopen", return_value=FakeResponse()) as request:
        result = server.live_site("site-c1-mondego")
    assert json.loads(result.body) == {"ok": True}
    assert request.call_args.args[0].full_url == f"{server.LIVE_BASE_URL}/api/sites/site-c1-mondego"
    assert request.call_args.kwargs["timeout"] == 42.0


def test_live_ask_only_forwards_valid_site_context():
    for site_id in ("site-c1-mondego", "../../etc/passwd", "bad id!", "x" * 65, None):
        with mock.patch("urllib.request.urlopen", return_value=FakeResponse()) as request:
            server.live_ask({"question": "What needs attention?", "siteId": site_id})
        payload = json.loads(request.call_args.args[0].data)
        assert payload["question"] == "What needs attention?"
        if site_id == "site-c1-mondego":
            assert payload["site_id"] == site_id
        else:
            assert "site_id" not in payload


def test_live_site_rejects_invalid_path_ids():
    with TestClient(server.app) as client, mock.patch.object(server, "proxy_live") as proxy:
        assert client.get("/api/live/sites/bad%20id!").status_code == 422
        assert client.get("/api/live/sites/" + "x" * 65).status_code == 422
    proxy.assert_not_called()


def test_live_overview_forwards_refresh():
    with mock.patch.object(server, "proxy_live") as proxy:
        server.live_overview(refresh=True)
        proxy.assert_called_once_with("/api/overview?refresh=true")


def test_studio_serves_native_dashboard():
    response = server.studio()
    assert response.status_code == 200
    assert b'id="studio-root"' in response.body
    assert b'data-route="studio"' in response.body
    assert response.body.index(b'id="studio-root"') < response.body.index(b'</main>')


def test_all_gateway_samples_can_be_proxied():
    from oah_ingestion.web import SAMPLES

    with mock.patch.object(server, "proxy_live") as proxy:
        for key in SAMPLES:
            server.live_ingest_demo(key)
            proxy.assert_called_with(f"/api/ingest-demo/{key}", method="POST")
