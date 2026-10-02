# OneAquaHealth

OneAquaHealth validates environmental, citizen science, and public health data; maps each event to OAH FHIR R4 resources; and uploads the resulting transaction Bundle to a FHIR server.

## Components

- `oah-pydantic-models/` contains the OAH logical models and FHIR resource mappers.
- `oah-ingestion/` runs the ingestion API, MQTT listener, RabbitMQ consumer, FHIR mapping and upload pipeline, and live dashboard.
- `oah-demo-publishers/` simulates external publishers for the three input channels.
- `oah-agent/` provides the assistant and dataset briefing used by the dashboard's query and overview features.
- `docker-compose.yml` starts the local RabbitMQ broker.

## Install

From the repository root, install the project packages and dependencies:

```powershell
python -m pip install -r requirements.txt
```

## Configure and start

Create a `.env` file in the repository root if you need to override the defaults. For example:

```dotenv
APP_PORT=8001
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USER=oah
RABBITMQ_PASSWORD=oah-local-dev
FHIR_BASE_URL=https://hapi.fhir.org/baseR4
FHIR_UPLOAD_ENABLED=true
OAH_DATASET_TAG=oah-demo
```

`FHIR_BASE_URL` defaults to `https://hapi.fhir.org/baseR4`. Set `FHIR_UPLOAD_ENABLED=false` to validate and map data and build the FHIR Bundle without sending it. `OAH_DATASET_TAG` labels uploaded resources so demo data can be queried as a dataset. The public HAPI sandbox is shared; use a server you control for isolated or sensitive data.

Start RabbitMQ and then the ingestion application:

```powershell
docker compose up -d rabbitmq
python -m oah_ingestion.app
```

The app starts the MQTT sensor listener, consumes citizen survey messages from `ingestion.citizen_surveys`, and serves the HTTP API. Defaults are `APP_HOST=0.0.0.0`, `APP_PORT=8000`, MQTT broker `broker.hivemq.com:1883`, and topic `oneaquahealth/sensors/+/+`.

Relevant environment variables:

- App: `APP_HOST`, `APP_PORT`, `LOG_LEVEL`
- MQTT: `MQTT_HOST`, `MQTT_PORT`, `MQTT_TOPIC`, `MQTT_USERNAME`, `MQTT_PASSWORD`, `MQTT_TLS`, `MQTT_CLIENT_ID`, `MQTT_DEMO_CLIENT_ID`
- RabbitMQ: `RABBITMQ_HOST`, `RABBITMQ_PORT`, `RABBITMQ_VHOST`, `RABBITMQ_USER`, `RABBITMQ_PASSWORD`
- FHIR: `FHIR_BASE_URL`, `FHIR_UPLOAD_ENABLED`, `OAH_DATASET_TAG`

## Send demo data

In a second terminal, publish a sample to each input channel:

```powershell
python -m oah_demo_publishers
```

The publisher sends IoT telemetry over MQTT, a citizen survey to RabbitMQ, and a public health event to `POST /ingest`. It reads broker settings from `.env`; MQTT defaults to the public HiveMQ broker.

Each channel validates and normalizes its input, then calls the same pipeline:

1. Screen the event for configured risk thresholds.
2. Map it to OAH-profiled FHIR resources.
3. Build a FHIR transaction Bundle and, when uploads are enabled, POST it to `FHIR_BASE_URL`.

The pipeline prints the normalized envelope as a readable trace and logs the FHIR upload result. The HTTP response includes a `fhir` result such as `UPLOADED`, `UPLOAD_FAILED`, or `BUILT_NOT_SENT`; `202 Accepted` means the ingestion endpoint accepted the request, so check that result and the app logs to confirm the FHIR upload.

Current failure behavior: FHIR upload and conversion failures are logged/reported by the pipeline but do not raise back to the MQTT or RabbitMQ consumer. Those input messages are acknowledged after the attempt, so a failed upload is not automatically retried. The HTTP response reports the pipeline result, but there is no persistent retry queue for FHIR failures yet.

## Dashboard and API

Open `http://localhost:8000/` (or the configured `APP_PORT`) for the live dashboard. It includes sample-driven ingestion demonstrations and views for data on the configured FHIR server.

- `GET /health` — application health.
- `POST /ingest` — accept a complete typed event envelope, including `PUBLIC_HEALTH`.
- `POST /api/ingest-demo/{key}` — run a bundled demo sample through the actual validation, screening, mapping, and upload pipeline. Sample keys include `iot`, `survey`, `health`, and `health-mondego`.
- `GET /api/overview` — query the FHIR dataset and produce a cross-domain briefing; requires `oah-agent` (installed by `requirements.txt`) and a reachable FHIR server.
- `POST /api/ask` — ask the assistant about the FHIR dataset; requires `OPENAI_API_KEY`, the agent package, and a reachable FHIR server.

## Tests and model examples

Run the existing ingestion tests and build the model examples with:

```powershell
python -m unittest discover -s oah-ingestion/tests -v
python oah-pydantic-models/examples/build_examples.py
```
