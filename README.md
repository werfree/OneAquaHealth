# OneAquaHealth

This repository contains the OAH Pydantic models and reusable ingestion components for the hackathon prototype.

## Layout

- `oah-pydantic-models/` contains the OAH logical data models based on the OAH FHIR Implementation Guide.
- `oah-ingestion/` validates the shared event envelope and all three stream payloads, consuming sensor telemetry from MQTT and citizen surveys from RabbitMQ while accepting public-health events over HTTP.
- `oah-demo-publishers/` is a separate runnable package that publishes demo samples over each of those channels.
- `oah-ingestion/src/oah_ingestion/app.py` is the single application entry point. It starts the MQTT sensor listener, RabbitMQ citizen survey consumer, and HTTP ingestion endpoint.
- `docker-compose.yml` starts the local RabbitMQ broker used by the ingestion components.

## Install and test

From this repository directory:

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s oah-ingestion/tests -v
python oah-pydantic-models/examples/build_examples.py
```

Start RabbitMQ, then run the single ingestion application:

```powershell
docker compose up -d rabbitmq
python -m oah_ingestion.app
```

Wait for the app log `Connected; subscribed to oneaquahealth/sensors/+/+` and `Consuming citizen surveys from ingestion.citizen_surveys` before starting the publishers.

The app loads environment variables from `.env`; `APP_HOST` defaults to `0.0.0.0` and `APP_PORT` defaults to `8000`. It starts listening for sensor telemetry on `oneaquahealth/sensors/+/+` at `broker.hivemq.com` by default and consumes citizen surveys from the durable RabbitMQ queue `ingestion.citizen_surveys`. Configure `MQTT_HOST`, `MQTT_PORT`, `MQTT_TOPIC`, `MQTT_USERNAME`, and `MQTT_PASSWORD` to use another MQTT broker. Configure `RABBITMQ_HOST`, `RABBITMQ_PORT`, `RABBITMQ_VHOST`, `RABBITMQ_USER`, and `RABBITMQ_PASSWORD` for RabbitMQ.

The HTTP `POST /ingest` endpoint accepts complete envelopes, including `PUBLIC_HEALTH`. The gateway validates the stream-specific payload, generates a fresh `event_id` and `received_at`, and prints the normalized generic envelope as JSON. MQTT sensor events and RabbitMQ citizen survey messages are normalized and printed in the same format. No downstream service is called yet.

Install and run the separate publisher package to send one sample through each input channel:

```powershell
python -m oah_demo_publishers
```

The publisher package sends IoT telemetry to MQTT, citizen survey JSON to `ingestion.citizen_surveys`, and public-health JSON to the ingestion API. It uses broker settings from `.env`; the MQTT demo uses public HiveMQ by default, so configure a broker you control for an isolated demo. The normalized JSON printed by the ingestion app is the current downstream handoff output; transformation and FHIR upload are not performed.
