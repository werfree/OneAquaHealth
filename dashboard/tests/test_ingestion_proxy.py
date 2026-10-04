import io
import json
import urllib.error
from pathlib import Path
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from dashboard import server
from oah_ingestion import app as gateway, web


class Upstream(io.BytesIO):
    status = 202


@pytest.fixture
def client():
    with TestClient(server.app) as instance:
        yield instance


@pytest.mark.parametrize("path,media,body", [
    ("/ingest", "application/json", b'{"source_type":"IOT_TELEMETRY"}'),
    ("/ingest/public-health/csv", "text/csv", b"event_id,city\r\nexample,coimbra\r\n"),
])
def test_upload_forwards_raw_bytes_and_preserves_acceptance(client, path, media, body):
    result = {"status": "ACCEPTED", "fhir": "BUILT_NOT_SENT", "uploaded": 0, "failed": 0}
    with mock.patch.object(server.urllib.request, "urlopen", return_value=Upstream(json.dumps(result).encode())) as upstream:
        response = client.post("/api/live" + path, content=body, headers={"Content-Type": media})
    assert response.status_code == 202
    assert response.json() == result
    request = upstream.call_args.args[0]
    assert request.full_url == server.LIVE_BASE_URL + path
    assert request.data == body
    assert request.get_header("Content-type") == media


@pytest.mark.parametrize("code,detail", [
    (422, [{"loc": ["body", "timestamp"], "msg": "Field required"}]),
    (502, {"status": "CSV_BATCH_PARTIALLY_FAILED", "events": [{"fhir": "UPLOADED", "uploaded": 3, "failed": 0}, {"fhir": "UPLOAD_FAILED", "uploaded": 0, "failed": 3}]}),
    (500, {"status": "FHIR_CONVERSION_FAILED", "fhir": "CONVERSION_FAILED"}),
])
def test_gateway_errors_keep_status_and_structured_details(client, code, detail):
    error = urllib.error.HTTPError("http://gateway", code, "failed", {}, io.BytesIO(json.dumps({"detail": detail}).encode()))
    with mock.patch.object(server.urllib.request, "urlopen", side_effect=error):
        response = client.post("/api/live/ingest", content=b"{}", headers={"Content-Type": "application/json"})
    assert response.status_code == code
    assert response.json() == {"detail": detail}


@pytest.mark.parametrize("body,media,code", [(b"{}", "multipart/form-data", 415), (b"", "application/json", 422), (b"x" * (server.MAX_INGEST_BYTES + 1), "application/json", 413)])
def test_invalid_or_oversized_upload_does_not_reach_gateway(client, body, media, code):
    with mock.patch.object(server.urllib.request, "urlopen") as upstream:
        response = client.post("/api/live/ingest", content=body, headers={"Content-Type": media})
    assert response.status_code == code
    upstream.assert_not_called()


def test_csv_template_is_a_download_and_gateway_outage_is_visible(client):
    template = b"event_id,city,site_id\r\n"
    with mock.patch.object(server.urllib.request, "urlopen", return_value=Upstream(template)) as upstream:
        response = client.get("/api/live/ingest/public-health/csv/template")
    assert response.content == template
    assert response.headers["content-type"].startswith("text/csv")
    assert 'filename="public-health-template.csv"' in response.headers["content-disposition"]
    assert upstream.call_args.args[0].full_url.endswith("/ingest/public-health/csv/template")
    with mock.patch.object(server.urllib.request, "urlopen", side_effect=urllib.error.URLError("connection refused")):
        response = client.post("/api/live/ingest", json={})
    assert response.status_code == 502
    assert "connection refused" in response.json()["detail"]


@pytest.mark.parametrize("filename,path,media,count", [
    ("sample_iot_telemetry_coimbra.json", "/ingest", "application/json", 1),
    ("sample_public_health.csv", "/ingest/public-health/csv", "text/csv", 2),
])
def test_dashboard_to_gateway_uses_real_validation_and_fhir_mapping(client, filename, path, media, count):
    demo = Path(__file__).resolve().parents[2] / "demo" / filename
    # Exercise both applications and the real pipeline without writing to public FHIR.
    with mock.patch.dict("os.environ", {"INGESTION_WORKERS_ENABLED": "false", "FHIR_UPLOAD_ENABLED": "false"}), TestClient(gateway.app) as gateway_client:
        def transport(request, **kwargs):
            response = gateway_client.post(path, content=request.data, headers={"Content-Type": request.get_header("Content-type")})
            result = Upstream(response.content)
            result.status = response.status_code
            return result

        with mock.patch.object(server.urllib.request, "urlopen", side_effect=transport):
            response = client.post("/api/live" + path, content=demo.read_bytes(), headers={"Content-Type": media})
    assert response.status_code == 202
    events = response.json().get("events", [response.json()])
    assert len(events) == count
    assert all(event["fhir"] == "BUILT_NOT_SENT" and event["resources"] and event["site_id"] for event in events)


def test_ingestion_invalidates_overview_after_partial_writes():
    payload = json.loads((Path(__file__).resolve().parents[2] / "demo/sample_iot_telemetry_coimbra.json").read_text())
    with mock.patch.dict("os.environ", {"INGESTION_WORKERS_ENABLED": "false"}), TestClient(gateway.app) as gateway_client, mock.patch.object(gateway, "process", return_value={"fhir": "UPLOAD_FAILED", "uploaded": 2, "failed": 1}), mock.patch.object(gateway, "invalidate_overview") as invalidate:
        response = gateway_client.post("/ingest", json=payload)
    assert response.status_code == 502
    invalidate.assert_called_once()
