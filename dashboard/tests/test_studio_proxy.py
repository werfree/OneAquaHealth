import asyncio
import io
import json
import urllib.error
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from dashboard import server


class Upstream(io.BytesIO):
    status = 200

    def __init__(self, body, content_type="text/event-stream", disposition=None):
        super().__init__(body)
        self.headers = {"Content-Type": content_type}
        if disposition:
            self.headers["Content-Disposition"] = disposition


@pytest.fixture
def client():
    with TestClient(server.app) as instance:
        yield instance


def test_stream_forwards_station_context_and_closes_transport(client):
    upstream = Upstream(b'data: {"type":"start","session":"abc123"}\n\ndata: {"type":"done"}\n\n')
    with mock.patch.object(server.urllib.request, "urlopen", return_value=upstream) as request:
        response = client.post("/api/live/studio/run", json={"question": "Show trends", "siteId": "yam-ito"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["x-accel-buffering"] == "no"
    assert '"type":"done"' in response.text
    payload = json.loads(request.call_args.args[0].data)
    assert "Show trends" in payload["question"]
    assert "station yam-ito" in payload["question"]
    assert upstream.closed


def test_proxy_yields_first_chunk_without_reading_completion():
    upstream = mock.Mock()
    upstream.headers = {"Content-Type": "text/event-stream"}
    upstream.read1.side_effect = [b'data: {"type":"start"}\n\n', b'data: {"type":"done"}\n\n', b""]

    async def consume():
        with mock.patch.object(server, "studio_upstream", return_value=upstream):
            response = server.live_studio_run({"question": "Scan all stations"})
        first = await anext(response.body_iterator)
        assert b'"start"' in first
        assert upstream.read1.call_count == 1
        rest = [chunk async for chunk in response.body_iterator]
        assert b'"done"' in b"".join(rest)
        upstream.close.assert_called()

    asyncio.run(consume())


@pytest.mark.parametrize("payload", [{}, {"question": " "}, {"question": 12}, {"question": "a" * 4001}, {"question": "Scan", "siteId": "../bad"}])
def test_invalid_investigations_do_not_reach_gateway(client, payload):
    with mock.patch.object(server, "studio_upstream") as upstream:
        assert client.post("/api/live/studio/run", json=payload).status_code == 422
        upstream.assert_not_called()


def test_upstream_http_errors_and_connection_failures_are_visible(client):
    error = urllib.error.HTTPError("http://gateway", 404, "missing", {}, io.BytesIO(b'{"detail":"session expired"}'))
    with mock.patch.object(server.urllib.request, "urlopen", side_effect=error):
        result = client.get("/api/live/studio/transcript/abc123")
    assert result.status_code == 404
    assert result.json()["detail"] == "session expired"
    with mock.patch.object(server.urllib.request, "urlopen", side_effect=urllib.error.URLError("unavailable")):
        result = client.post("/api/live/studio/run", json={"question": "Scan"})
    assert result.status_code == 502
    assert "Start the ingestion gateway" in result.json()["detail"]


def test_non_stream_response_is_rejected_and_closed(client):
    upstream = Upstream(b"{}", "application/json")
    with mock.patch.object(server, "studio_upstream", return_value=upstream):
        result = client.post("/api/live/studio/run", json={"question": "Scan"})
    assert result.status_code == 502
    assert upstream.closed


def test_interrupted_stream_emits_error_and_releases_transport(client):
    upstream = mock.Mock()
    upstream.headers = {"Content-Type": "text/event-stream"}
    upstream.read1.side_effect = [b'data: {"type":"start"}\n\n', TimeoutError()]
    with mock.patch.object(server, "studio_upstream", return_value=upstream):
        response = client.post("/api/live/studio/run", json={"question": "Scan"})
    assert '"type":"error"' in response.text
    upstream.close.assert_called()


@pytest.mark.parametrize("kind,media,body", [
    ("readings", "text/csv", b"date,value\n2026-10-01,12\n"),
    ("surveillance", "text/csv", b"cases,population\n12,10000\n"),
    ("fhir", "application/fhir+json", b'{"resourceType":"Bundle"}'),
])
def test_exports_preserve_bytes_type_and_filename(client, kind, media, body):
    upstream = Upstream(body, media, 'attachment; filename="evidence.csv"')
    with mock.patch.object(server, "studio_upstream", return_value=upstream) as request:
        response = client.get(f"/api/live/studio/export/{kind}?days=28&site_id=yam-ito")
    assert response.content == body
    assert response.headers["content-type"] == media
    assert "evidence.csv" in response.headers["content-disposition"]
    path = request.call_args.args[0]
    assert "days=28" in path
    assert ("site_id=yam-ito" in path) is (kind != "surveillance")


def test_export_allowlist_and_parameters(client):
    with mock.patch.object(server, "studio_upstream") as upstream:
        assert client.get("/api/live/studio/export/unknown").status_code == 404
        assert client.get("/api/live/studio/export/fhir").status_code == 422
        assert client.get("/api/live/studio/export/readings?days=999").status_code == 422
        assert client.get("/api/live/studio/export/readings?site_id=../bad").status_code == 422
        upstream.assert_not_called()


def test_executive_report_passes_session_figures_and_html(client):
    payload = {"session": "abc123", "figures": [{"title": "Trend", "svg": "<svg/>"}]}
    with mock.patch.object(server, "studio_upstream", return_value=Upstream(b"<html>Report</html>", "text/html")) as upstream:
        result = client.post("/api/live/studio/executive", json=payload)
    assert result.status_code == 200
    assert result.headers["content-type"] == "text/html"
    assert b"Report" in result.content
    upstream.assert_called_once_with("studio/executive", payload)
    assert client.post("/api/live/studio/executive", json={"session": "../bad"}).status_code == 422
    assert client.post("/api/live/studio/executive", json={"session": "abc123", "figures": ["bad"]}).status_code == 422
