"""Single-process gateway for IoT, citizen survey, and public health events."""

import csv
import io
import logging
import os
import threading
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response

from .csv_ingestion import CSV_TEMPLATE_COLUMNS, CsvIngestionError, parse_public_health_csv
from .envelope import IngestionEnvelope, envelope_as_message
from .pipeline import process
from .mqtt_worker import create_mqtt_client, mqtt_broker_address, mqtt_connect_options
from .rabbitmq_worker import consume_citizen_surveys
from .web import router as web_router

load_dotenv()

logger = logging.getLogger("OAH_Ingestion_App")


def ingestion_workers_enabled() -> bool:
    """`INGESTION_WORKERS_ENABLED=false` serves only the HTTP API and dashboard reads."""
    return os.getenv("INGESTION_WORKERS_ENABLED", "true").strip().lower() not in {"false", "0", "no"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not ingestion_workers_enabled():
        logger.info("Ingestion workers disabled; MQTT and RabbitMQ listeners not started")
        yield
        return
    client = create_mqtt_client()
    host, port = mqtt_broker_address()
    logger.info("Starting MQTT sensor listener for %s:%d", host, port)
    client.connect_async(host, port, keepalive=60, **mqtt_connect_options())
    client.loop_start()
    app.state.mqtt_client = client
    stop_event = threading.Event()
    rabbit_thread = threading.Thread(
        target=consume_citizen_surveys,
        args=(stop_event, process),
        name="citizen-survey-consumer",
        daemon=True,
    )
    rabbit_thread.start()
    app.state.rabbit_stop_event = stop_event
    app.state.rabbit_thread = rabbit_thread
    try:
        yield
    finally:
        stop_event.set()
        rabbit_thread.join(timeout=5)
        client.disconnect()
        client.loop_stop()


app = FastAPI(title="OneAquaHealth Ingestion", lifespan=lifespan)

# Live dashboard at "/" plus the /api/* routes it runs on.
app.include_router(web_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/ingest", status_code=202)
def ingest_event(envelope: IngestionEnvelope):
    """Validate, normalize and print one event for the downstream handoff."""
    message = envelope_as_message(envelope)
    result = process(envelope, message)
    if result.get("fhir") == "UPLOAD_FAILED":
        raise HTTPException(
            status_code=502,
            detail={"status": "FHIR_UPLOAD_FAILED", "event_id": str(message["event_id"]), **result},
        )
    if result.get("fhir") == "CONVERSION_FAILED":
        raise HTTPException(
            status_code=500,
            detail={"status": "FHIR_CONVERSION_FAILED", "event_id": str(message["event_id"]), **result},
        )
    logger.info("Normalized API event %s (%s)", message["event_id"], message["source_type"])
    return {
        "status": "ACCEPTED",
        "event_id": str(message["event_id"]),
        "source_type": message["source_type"],
        **result,
    }


@app.post("/ingest/public-health/csv", status_code=202)
async def ingest_public_health_csv(request: Request):
    """Validate a long-form CSV batch and ingest each grouped health event."""
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type not in {"text/csv", "application/csv"}:
        raise HTTPException(status_code=415, detail="Content-Type must be text/csv")

    try:
        text = (await request.body()).decode("utf-8-sig")
        envelopes = parse_public_health_csv(text)
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="CSV must be UTF-8 encoded") from exc
    except CsvIngestionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    results = []
    for envelope in envelopes:
        message = envelope_as_message(envelope)
        result = process(envelope, message)
        results.append({"event_id": message["event_id"], "source_type": "PUBLIC_HEALTH", **result})

    failed = [item for item in results if item.get("fhir") in {"UPLOAD_FAILED", "CONVERSION_FAILED"}]
    if any(item.get("fhir") == "CONVERSION_FAILED" for item in failed):
        status_code = 500
    elif failed:
        status_code = 502
    else:
        status_code = 202
    if status_code != 202:
        raise HTTPException(
            status_code=status_code,
            detail={"status": "CSV_BATCH_PARTIALLY_FAILED", "events": results},
        )
    return {"status": "ACCEPTED", "event_count": len(results), "events": results}


@app.get("/ingest/public-health/csv/template", include_in_schema=True)
def download_public_health_csv_template():
    """Download an empty CSV template for public-health batch ingestion."""
    output = io.StringIO(newline="")
    csv.writer(output, lineterminator="\r\n").writerow(CSV_TEMPLATE_COLUMNS)
    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="public-health-template.csv"'},
    )


def main():
    import uvicorn

    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s [%(levelname)s] %(message)s")
    # pika logs its whole connection handshake at INFO -- socket, transport,
    # AMQPConnector, workflow -- which buries the lines that confirm the app is
    # ready. Raise LOG_LEVEL_PIKA to debug broker problems.
    logging.getLogger("pika").setLevel(os.getenv("LOG_LEVEL_PIKA", "WARNING").upper())
    uvicorn.run(
        "oah_ingestion.app:app",
        host=os.getenv("APP_HOST", "0.0.0.0"),
        port=int(os.getenv("APP_PORT", "8000")),
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )


if __name__ == "__main__":
    main()
