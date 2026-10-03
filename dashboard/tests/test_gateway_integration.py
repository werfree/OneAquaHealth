"""Exercise the combined HTTP routes with stubbed model and FHIR transports."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from oah_ingestion import app as gateway, officer, web
from oah_agent import studio

DEMO = Path(__file__).resolve().parents[2] / "demo"


@pytest.fixture
def client():
    web.invalidate_overview()
    with mock.patch.dict("os.environ", {"INGESTION_WORKERS_ENABLED": "false"}), mock.patch.object(gateway, "create_mqtt_client") as mqtt, mock.patch.object(gateway, "consume_citizen_surveys") as rabbit:
        with TestClient(gateway.app) as test_client:
            yield test_client
        mqtt.assert_not_called()
        rabbit.assert_not_called()
    web.invalidate_overview()


def test_both_interfaces_and_csv_template_are_available(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/").status_code == 200
    assert client.get("/api/officer/panel").status_code == 200
    charts = client.get("/api/officer/assets/studio-charts.js")
    assert charts.status_code == 200
    assert "createChartRenderer" in charts.text
    assert "Surveillance Studio" in client.get("/api/officer/panel").text
    assert client.get("/ingest/public-health/csv/template").status_code == 200
    assert client.get("/api/sites/bad%20id!").status_code == 422


def test_ingestion_failure_statuses_are_preserved(client):
    payload = json.loads((DEMO / "sample_iot_telemetry_coimbra.json").read_text())
    for outcome, code in (("UPLOAD_FAILED", 502), ("CONVERSION_FAILED", 500), ("UPLOADED", 202)):
        with mock.patch.object(gateway, "process", return_value={"fhir": outcome, "uploaded": 0, "failed": 1}):
            assert client.post("/ingest", json=payload).status_code == code


def test_european_csv_batch_still_ingests(client):
    with mock.patch.object(gateway, "process", return_value={"fhir": "UPLOADED", "uploaded": 1, "failed": 0}) as process:
        response = client.post("/ingest/public-health/csv", content=(DEMO / "sample_public_health.csv").read_bytes(), headers={"Content-Type": "text/csv"})
    assert response.status_code == 202
    assert response.json()["event_count"] == 2
    assert process.call_count == 2


def test_overview_and_station_routes_keep_original_contract(client):
    facts = {"site_count": 1, "briefings": [{"site_id": "site-c1-mondego"}]}
    station = {"site_id": "site-c1-mondego", "environmental_reading_count": 1, "health_measure_count": 0, "environmental_observations": [{"id": "obs-1"}], "health_observations": []}
    with mock.patch("oah_agent.briefing.dataset_briefing", return_value=facts) as briefing:
        assert client.get("/api/overview").json()["briefings"][0]["city"] == "coimbra"
        client.get("/api/overview")
        assert briefing.call_count == 1
        client.get("/api/overview?refresh=true")
        assert briefing.call_count == 2
    with mock.patch("oah_agent.briefing.site_briefing", return_value=station), mock.patch("oah_agent.tools.list_sites", return_value={"sites": []}):
        assert client.get("/api/sites/site-c1-mondego").json()["environmental_observations"] == [{"id": "obs-1"}]


def test_studio_streams_on_the_gateway(client):
    with mock.patch.object(studio, "run", return_value=iter(['data: {"type":"done","session":"test"}\n\n'])) as run:
        response = client.post("/api/officer/studio/run", json={"question": "Show the station trend"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert '"type":"done"' in response.text
    run.assert_called_once_with("Show the station trend")
    assert client.post("/api/officer/studio/run", json={"question": ""}).status_code == 422


def test_fhir_evidence_export_is_a_collection_bundle(client):
    observation = {"resourceType": "Observation", "id": "evidence-1"}
    with mock.patch.object(officer, "search", side_effect=[[observation], [], []]):
        response = client.get("/api/officer/export/bundle.json?site_id=yam-ito&days=28")
    assert response.status_code == 200
    assert response.json()["type"] == "collection"
    assert response.json()["entry"][0]["resource"] == observation
    assert response.headers["content-type"].startswith("application/fhir+json")


def test_surveillance_csv_preserves_cases_and_denominator(client):
    row = {"date": "2026-10-01", "site_id": "yam-ito", "cohort": "ward-delhi-central-riverside", "indicator": "acute_diarrhoeal_disease", "cases": 286, "population": 412000, "value": 69.42, "baseline": 26.66, "id": "health-1"}
    with mock.patch.object(officer, "_fetch", return_value=[row]):
        response = client.get("/api/officer/export/surveillance.csv?days=28")
    assert response.status_code == 200
    assert "population_at_risk" in response.text
    assert "286,412000,69.42,26.66" in response.text


def test_executive_report_and_transcript_use_completed_session(client):
    session = {"id": "test-session", "question": "What needs attention?", "model": "stub", "started_at": "2026-10-01T00:00:00Z", "transcript": [
        {"kind": "tool", "tool": "get_trend", "arguments": {}, "summary": "BOD is 11.84 mg/L", "urls": ["https://fhir.test/Observation"], "render": None},
        {"kind": "answer", "text": "BOD is 11.84 mg/L", "grounding": {"grounded": True, "figures_checked": 1, "source_figure_count": 1}},
    ], "grounding": {"grounded": True, "figures_checked": 1, "source_figure_count": 1}}
    model = mock.MagicMock()
    model.chat.completions.create.return_value = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({"situation": "BOD is 11.84 mg/L", "assessment": "Sampling is needed", "findings": [], "actions": [], "limitations": "Prototype screening only"})))])
    with mock.patch.object(studio, "session", return_value=session), mock.patch.object(studio, "_client", return_value=model):
        report = client.post("/api/officer/studio/executive", json={"session": "test-session", "figures": []})
        transcript = client.get("/api/officer/studio/report/test-session")
    assert report.status_code == 200
    assert "11.84" in report.text
    assert "text/html" in report.headers["content-type"]
    assert transcript.status_code == 200
    assert "https://fhir.test/Observation" in transcript.text
