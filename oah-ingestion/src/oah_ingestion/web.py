"""The live dashboard and the API behind it.

Served from the ingestion app itself, so the demo needs no second process, no
build step, no account and no network beyond the FHIR server. Opening
http://localhost:8000 gives you the whole system.

Every route here answers with what actually happened rather than a canned
fixture: `/api/ingest-demo` runs a real envelope through validation, screening,
FHIR conversion and upload, and returns each stage; `/api/ask` runs the real
assistant and returns its tool trace and grounding verdict alongside the
answer. That is what lets the page explain itself -- the UI is showing the
pipeline's own output, not a description of it.

The assistant is imported lazily. `oah-agent` depends on `oah-ingestion`, so
importing it at module scope would be circular, and the gateway must stay
usable when the agent package is not installed.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from pydantic import TypeAdapter

from .alerts import assess
from .envelope import IngestionEnvelope, envelope_as_message
from .fhir_adapter import envelope_to_fhir
from .fhir_client import base_url
from .pipeline import dataset_tag, process
from .sites import registry
from .thresholds import as_reference

logger = logging.getLogger("OAH_Web")
router = APIRouter()

STATIC = Path(__file__).resolve().parent / "static"
DEMO = Path(__file__).resolve().parents[3] / "demo"
ENVELOPE = TypeAdapter(IngestionEnvelope)

SAMPLES = {
    "iot": ("sample_iot_telemetry.json", "CPCB telemetry", "Yamuna at ITO Bridge: coliform with statistics, BOD, DO"),
    "iot-oslo": ("sample_iot_telemetry_oslo.json", "IoT telemetry", "Oslo Akerselva sensor readings"),
    "iot-benevento": ("sample_iot_telemetry_benevento.json", "IoT telemetry", "Benevento Calore sensor readings"),
    "survey": ("sample_citizen_survey.json", "Citizen survey", "Ganga Prahari volunteer at Assi Ghat, Varanasi"),
    "survey-ghent": ("sample_citizen_survey_ghent.json", "Citizen survey", "StreamKeepers volunteer at the Leie in Ghent"),
    "survey-toulouse": ("sample_citizen_survey_toulouse.json", "Citizen survey", "StreamKeepers volunteer at the Garonne in Toulouse"),
    "health": ("sample_public_health.json", "IDSP return", "Central Delhi riverside ward, week ending 2 Oct"),
    "health-kanpur": ("sample_public_health_kanpur.json", "IDSP return", "Jajmau ward, Kanpur Nagar"),
}


@router.get("/", include_in_schema=False)
def dashboard():
    page = STATIC / "dashboard.html"
    if not page.is_file():
        raise HTTPException(status_code=404, detail="dashboard.html is missing from the static directory")
    return FileResponse(page, media_type="text/html")


@router.get("/api/info")
def info():
    """What this gateway is and where its data goes."""

    import os

    from .mqtt_worker import mqtt_broker_address
    from .rabbitmq import CITIZEN_SURVEY_QUEUE

    mqtt_host, mqtt_port = mqtt_broker_address()
    return {
        "service": "OneAquaHealth ingestion gateway",
        "channels": {
            "mqtt": f"{mqtt_host}:{mqtt_port} -> {os.getenv('MQTT_TOPIC', 'oneaquahealth/sensors/+/+')}",
            "rabbitmq": f"{os.getenv('RABBITMQ_HOST', 'localhost')} -> {CITIZEN_SURVEY_QUEUE}",
            "http": ["POST /ingest (JSON)", "POST /ingest/public-health/csv (CSV batch)"],
        },
        "fhir": {"server": base_url(), "dataset_tag": dataset_tag()},
        "samples": [{"key": k, "channel": v[1], "detail": v[2]} for k, v in SAMPLES.items()],
        "thresholds": as_reference(),
    }


@router.post("/api/ingest-demo/{key}")
def ingest_demo(key: str):
    """Run one demo sample through the whole pipeline, returning every stage.

    This is what makes the dashboard a live demo rather than a screenshot: the
    four stages it displays are this response, produced by the same code path a
    real MQTT or RabbitMQ message takes.
    """

    if key not in SAMPLES:
        raise HTTPException(status_code=404, detail=f"unknown sample {key!r}; try one of {sorted(SAMPLES)}")

    filename = SAMPLES[key][0]
    raw = json.loads((DEMO / filename).read_text(encoding="utf-8"))

    try:
        envelope = ENVELOPE.validate_python(raw)
    except Exception as exc:
        return {"stage": "validation", "ok": False, "error": str(exc)[:600]}

    alert = assess(envelope)
    resources = envelope_to_fhir(envelope)
    result = process(envelope, envelope_as_message(envelope))

    observations = [r.model_dump(exclude_none=True) for r in resources if r.resourceType == "Observation"]
    return {
        "ok": result.get("fhir") not in {"UPLOAD_FAILED", "CONVERSION_FAILED"},
        "sample": {"key": key, "file": filename, "channel": SAMPLES[key][1], "detail": SAMPLES[key][2]},
        "raw": raw,
        "validated": json.loads(envelope.model_dump_json()),
        "alert": alert,
        "observations": observations[:4],
        "profiles": sorted({o["meta"]["profile"][0].rsplit("/", 1)[-1] for o in observations}),
        "upload": {k: v for k, v in result.items() if k != "alert"},
        "fhir_server": base_url(),
    }


@router.get("/api/overview")
def overview():
    """Current state of the dataset on the FHIR server, with the cross-domain join."""

    try:
        from oah_agent.briefing import dataset_briefing
    except ImportError:
        raise HTTPException(status_code=501, detail="oah-agent is not installed; overview needs its query tools")

    facts = dataset_briefing(dataset_tag=dataset_tag())
    gazetteer = registry()
    for briefing in facts["briefings"]:
        site = gazetteer.get(briefing["site_id"])
        briefing["name"] = site.name if site else briefing["site_id"]
        briefing["latitude"] = site.latitude if site else None
        briefing["longitude"] = site.longitude if site else None
    facts["fhir_server"] = base_url()
    facts["dataset_tag"] = dataset_tag()
    return facts


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=500)


@router.post("/api/ask")
def ask(body: Question):
    """Put a question to the assistant and return its answer, trace and verdict."""

    try:
        from oah_agent.assistant import ask as run
    except ImportError:
        raise HTTPException(status_code=501, detail="oah-agent is not installed")

    try:
        result = run(body.question)
    except RuntimeError as exc:  # missing OPENAI_API_KEY, most likely
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.exception("Assistant failed")
        raise HTTPException(status_code=502, detail=f"{type(exc).__name__}: {exc}")

    return {
        "question": body.question,
        "answer": result["answer"],
        "trace": result["trace"],
        "grounding": result["grounding"],
        "model": result["model"],
    }
