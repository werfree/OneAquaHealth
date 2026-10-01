"""Single-process gateway for IoT, citizen survey, and public health events."""

import logging
import os
import threading
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Response

from .envelope import IngestionEnvelope, envelope_as_message
from .pipeline import print_generic_event, process
from .mqtt_worker import create_mqtt_client, mqtt_broker_address
from .rabbitmq_worker import consume_citizen_surveys

load_dotenv()

logger = logging.getLogger("OAH_Ingestion_App")


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = create_mqtt_client()
    host, port = mqtt_broker_address()
    logger.info("Starting MQTT sensor listener for %s:%d", host, port)
    client.connect_async(host, port, keepalive=60)
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


@app.get("/")
def index():
    """What this gateway is and where its data goes.

    Without this, opening the app in a browser answers 404, which reads as a
    broken service rather than an API with no root resource.
    """
    from .fhir_client import base_url, upload_enabled
    from .mqtt_worker import mqtt_broker_address
    from .pipeline import dataset_tag
    from .rabbitmq import CITIZEN_SURVEY_QUEUE

    mqtt_host, mqtt_port = mqtt_broker_address()
    return {
        "service": "OneAquaHealth ingestion gateway",
        "channels": {
            "mqtt": f"{mqtt_host}:{mqtt_port} -> {os.getenv('MQTT_TOPIC', 'oneaquahealth/sensors/+/+')}",
            "rabbitmq": f"{os.getenv('RABBITMQ_HOST', 'localhost')} -> {CITIZEN_SURVEY_QUEUE}",
            "http": "POST /ingest",
        },
        "fhir": {
            "server": base_url(),
            "upload_enabled": upload_enabled(),
            "dataset_tag": dataset_tag(),
        },
        "endpoints": ["GET /", "GET /health", "POST /ingest", "GET /docs"],
    }


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    # Browsers request this on every visit; answering 404 clutters the log a
    # demo is being recorded from.
    return Response(status_code=204)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/ingest", status_code=202)
def ingest_event(envelope: IngestionEnvelope):
    """Validate, normalize and print one event for the downstream handoff."""
    message = envelope_as_message(envelope)
    result = process(envelope, message)
    logger.info("Normalized API event %s (%s)", message["event_id"], message["source_type"])
    return {
        "status": "ACCEPTED",
        "event_id": str(message["event_id"]),
        "source_type": message["source_type"],
        **result,
    }


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
