# OneAquaHealth

OneAquaHealth validates environmental, citizen science, and public health data; maps events to OAH FHIR R4 resources; and uploads transaction Bundles to a FHIR server.

## Components

- `oah-pydantic-models/` contains the OAH logical models and FHIR resource mappers.
- `oah-ingestion/` runs the ingestion API, MQTT listener, RabbitMQ consumer, FHIR pipeline, and live dashboard.
- `oah-demo-publishers/` simulates external publishers for the three input channels.
- `oah-agent/` provides the FHIR data assistant and dataset briefing features.
- `docker-compose.yml` starts the local RabbitMQ broker.

## Install

From the repository root:

```powershell
python -m pip install -r requirements.txt
```

## Configure and start

Create a `.env` file in the repository root to override defaults. Example:

```dotenv
APP_PORT=8001
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USER=oah
RABBITMQ_PASSWORD=oah-local-dev
MQTT_CLIENT_ID=OAHIngest-my-laptop
FHIR_BASE_URL=https://hapi.fhir.org/baseR4
FHIR_UPLOAD_ENABLED=true
OAH_DATASET_TAG=oah-demo
```

`MQTT_CLIENT_ID` should be unique to this app installation and kept stable across restarts so the MQTT 5 session can resume. `MQTT_SESSION_EXPIRY_SECONDS` defaults to `86400`. `FHIR_BASE_URL` defaults to the shared HAPI sandbox shown above; use a server you control for isolated or sensitive data. Set `FHIR_UPLOAD_ENABLED=false` to build Bundles without uploading them. `OAH_DATASET_TAG` scopes the demo resources for querying.

Start RabbitMQ and the ingestion app:

```powershell
docker compose up -d rabbitmq
python -m oah_ingestion.app
```

The app starts the MQTT sensor listener, consumes citizen surveys from the durable `ingestion.citizen_surveys` queue, and serves the HTTP API. Defaults are `APP_HOST=0.0.0.0`, `APP_PORT=8000`, MQTT broker `broker.hivemq.com:1883`, and topic `oneaquahealth/sensors/+/+`.

Relevant environment variables:

- App: `APP_HOST`, `APP_PORT`, `LOG_LEVEL`
- MQTT: `MQTT_HOST`, `MQTT_PORT`, `MQTT_TOPIC`, `MQTT_USERNAME`, `MQTT_PASSWORD`, `MQTT_TLS`, `MQTT_CLIENT_ID`, `MQTT_DEMO_CLIENT_ID`, `MQTT_SESSION_EXPIRY_SECONDS`
- RabbitMQ: `RABBITMQ_HOST`, `RABBITMQ_PORT`, `RABBITMQ_VHOST`, `RABBITMQ_USER`, `RABBITMQ_PASSWORD`, `FHIR_RETRY_DELAY_SECONDS`
- FHIR: `FHIR_BASE_URL`, `FHIR_UPLOAD_ENABLED`, `OAH_DATASET_TAG`

## Send demo data

In another terminal, send one sample through each input channel:

```powershell
python -m oah_demo_publishers
```

The publisher sends sensor telemetry over MQTT, a citizen survey to RabbitMQ, and public-health data to `POST /ingest`. MQTT defaults to the public HiveMQ broker. Wait for the ingestion app's subscription log before publishing so the MQTT listener is ready.

For each event, the app validates and normalizes the input, screens for threshold alerts, maps it to OAH-profiled FHIR resources, and builds a transaction Bundle. If FHIR uploads are enabled, it sends the Bundle to `FHIR_BASE_URL`. The normalized envelope and upload outcome are logged.

The `/ingest` response is `202 Accepted` only when the event was processed successfully (or upload was intentionally disabled). It returns a `502` when the FHIR upload fails and a `500` when FHIR conversion fails. The demo publisher reports non-2xx HTTP responses as errors.

Delivery failure handling:

- **RabbitMQ:** failed uploads are nacked for redelivery after `FHIR_RETRY_DELAY_SECONDS` (default 5 seconds). Invalid messages are rejected without requeue.
- **MQTT:** failed uploads are left unacknowledged. MQTT 5 sessions use an expiry interval (default one day) so QoS 1 messages can be redelivered after a reconnect. Configure a stable, unique `MQTT_CLIENT_ID` for the app instance.
- **HTTP:** failed uploads return an error to the publisher, which can retry the request. The gateway assigns a fresh `event_id` to each attempt; replaying the same site, measurements, and observation timestamp maps to the same FHIR resource IDs.

The FHIR result is `UPLOADED` only when every transaction resource succeeds. Partial or missing transaction response entries count as failures and trigger the same delivery failure handling.

## Dashboard and API

Open `http://localhost:8000/` (or the configured `APP_PORT`) for the live dashboard.

- `GET /health` — process health.
- `POST /ingest` — accept a typed event envelope, including `PUBLIC_HEALTH`.
- `POST /api/ingest-demo/{key}` — run a bundled sample through validation, screening, mapping, and upload. Sample keys: `iot`, `survey`, `health`, `health-mondego`.
- `GET /api/overview` — summarize data on the FHIR server; requires the agent package and a reachable server.
- `POST /api/ask` — ask the assistant about FHIR data; requires `OPENAI_API_KEY`, the agent package, and a reachable server.

## Tests and model examples

Run the existing tests and model example builder with:

```powershell
python -m unittest discover -s oah-ingestion/tests -v
python -m unittest discover -s oah-pydantic-models/tests -v
python -m unittest discover -s oah-agent/tests -v
python oah-pydantic-models/examples/build_examples.py
```
