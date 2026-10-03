# OneAquaHealth

OneAquaHealth ingests environmental, citizen science, and public health data, maps events to OAH FHIR R4 resources, and uploads transaction Bundles to a FHIR server. The repository also contains a separate evidence dashboard with a stateful mock service and an optional live-gateway mode.

## Components

- `oah-pydantic-models/` contains the OAH logical models and FHIR resource mappers.
- `oah-ingestion/` runs the MQTT listener, RabbitMQ consumer, HTTP API, FHIR pipeline, and live ingestion dashboard.
- `oah-demo-publishers/` simulates external publishers for the three ingestion channels.
- `oah-agent/` provides the assistant and FHIR dataset briefing features.
- `dashboard/` contains the separate evidence dashboard, mock API, live-gateway adapter, themes, and report downloads.
- `docker-compose.yml` starts the local RabbitMQ broker.

## Install

From the repository root, install the ingestion and project packages:

```powershell
python -m pip install -r requirements.txt
```

To install and run the evidence dashboard, install the root project with its dashboard extras:

```powershell
python -m pip install -e ".[dev]"
```

## Configure and start ingestion

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
DASHBOARD_PORT=8090
OAH_LIVE_BASE_URL=http://127.0.0.1:8001
DASHBOARD_DEFAULT_THEME=aqua
```

`MQTT_CLIENT_ID` should be unique to this app instance and kept stable across restarts to resume its MQTT 5 session. If it is omitted, the listener generates an ID at startup; that generated ID cannot resume the prior process's session. `MQTT_SESSION_EXPIRY_SECONDS` defaults to `86400`. `FHIR_BASE_URL` defaults to the shared HAPI sandbox above; use a server you control for isolated or sensitive data. Set `FHIR_UPLOAD_ENABLED=false` to build Bundles without uploading them. `OAH_DATASET_TAG` scopes uploaded resources for querying.

Start RabbitMQ and then the ingestion application:

```powershell
docker compose up -d rabbitmq
python -m oah_ingestion.app
```

The app starts the MQTT sensor listener, consumes citizen surveys from the durable `ingestion.citizen_surveys` queue, and serves the HTTP API. Defaults are `APP_HOST=0.0.0.0`, `APP_PORT=8000`, MQTT broker `broker.hivemq.com:1883`, and topic `oneaquahealth/sensors/+/+`.

Relevant environment variables:

- App: `APP_HOST`, `APP_PORT`, `LOG_LEVEL`, `INGESTION_WORKERS_ENABLED` (default `true`; `false` skips MQTT/RabbitMQ workers while keeping the HTTP API available)
- MQTT: `MQTT_HOST`, `MQTT_PORT`, `MQTT_TOPIC`, `MQTT_USERNAME`, `MQTT_PASSWORD`, `MQTT_TLS`, `MQTT_CLIENT_ID`, `MQTT_DEMO_CLIENT_ID`, `MQTT_SESSION_EXPIRY_SECONDS`
- RabbitMQ: `RABBITMQ_HOST`, `RABBITMQ_PORT`, `RABBITMQ_VHOST`, `RABBITMQ_USER`, `RABBITMQ_PASSWORD`, `FHIR_RETRY_DELAY_SECONDS`
- FHIR: `FHIR_BASE_URL`, `FHIR_UPLOAD_ENABLED`, `OAH_DATASET_TAG`, `FHIR_MAX_SEARCH_RESULTS` (default `5000`, maximum resources collected across search pages), `FHIR_MAX_PAGES` (default `100`, page-loop bound), `FHIR_RETRIES` (default `3`, transport attempts with backoff)
- Briefings: `OVERVIEW_CACHE_SECONDS` (default `60`, per-process overview cache lifetime), `OAH_BRIEFING_WORKERS` (default `8`, concurrent site briefings)
- Evidence dashboard: `DASHBOARD_PORT`, `OAH_LIVE_BASE_URL`, `DASHBOARD_DEFAULT_THEME`, `OAH_LIVE_TIMEOUT_SECONDS` (default `90`, gateway proxy timeout), `DASHBOARD_DEFAULT_MODE` (`mock` by default, or `live`; an explicit `?mode=` overrides it)
- Deployment: `OAH_CITIES` (comma-separated allow-list; defaults include the European pilot and Delhi, Kanpur, Varanasi, Mumbai, Chennai, and Hyderabad), `OAH_SITES_FILE` (gazetteer override)
- Analyst: `OPENAI_API_KEY`, `OPENAI_MODEL` (default `gpt-4o`)

## Send demo data

In another terminal, send one sample through each ingestion channel:

```powershell
python -m oah_demo_publishers
```

The publisher sends sensor telemetry over MQTT, a citizen survey to RabbitMQ, and public-health data to `POST /ingest`. MQTT defaults to the public HiveMQ broker. Wait for the ingestion app's MQTT subscription log before publishing.

For each event, the app validates and normalizes the input, screens for threshold alerts, maps it to OAH-profiled FHIR resources, and builds a transaction Bundle. If uploads are enabled, it sends the Bundle to `FHIR_BASE_URL`. The normalized envelope and FHIR outcome are logged.

The HTTP `/ingest` endpoint returns `202 Accepted` when processing succeeds (or upload is intentionally disabled), `502` when FHIR upload fails, and `500` when FHIR conversion fails. The demo publisher reports non-2xx HTTP responses as errors.

Delivery failure handling:

- **RabbitMQ:** failed uploads are nacked for redelivery after `FHIR_RETRY_DELAY_SECONDS` (default 5 seconds). Invalid envelopes and FHIR conversion failures are rejected without requeue.
- **MQTT:** failed uploads are left unacknowledged. MQTT 5 sessions use an expiry interval (default one day), allowing QoS 1 messages to be redelivered after a reconnect when the app uses the same stable client ID.
- **HTTP:** failed uploads return an error to the publisher, which can retry the request. The gateway assigns a fresh `event_id` for each attempt; replaying the same site, measurements, and observation timestamp maps to the same FHIR resource IDs.

The FHIR result is `UPLOADED` only when every transaction resource succeeds. Partial or missing transaction response entries count as failures. `FHIR_UPLOAD_ENABLED=false` returns `BUILT_NOT_SENT` and intentionally skips upload.

## Ingestion dashboard and API

Open `http://localhost:8000/` (or the configured `APP_PORT`) for the live dashboard served by the ingestion app.

- `GET /health` — process health.
- `GET /api/info` — configured channel, FHIR, sample, and threshold information.
- `POST /ingest` — accept a typed event envelope, including `PUBLIC_HEALTH`.
- `POST /ingest/public-health/csv` — ingest one or more grouped `PUBLIC_HEALTH` events from long-form CSV (`Content-Type: text/csv`). Each row is one `risk_score` or `chemical_summary`; rows with the same `event_id` form one event. See `demo/sample_public_health.csv` for the required columns and format.
- `GET /ingest/public-health/csv/template` — download an empty CSV template for preparing a public-health batch.
- `POST /api/ingest-demo/{key}` — run a bundled JSON sample through validation, screening, mapping, and upload. `iot`, `survey`, and `health` now select the Indian examples; `health-kanpur` adds a Jajmau return. The European examples remain available as `iot-coimbra`, `iot-oslo`, `iot-benevento`, `survey-coimbra`, `survey-ghent`, `survey-toulouse`, `health-coimbra`, and `health-mondego`.
- `GET /api/overview` — summarize data on the FHIR server; requires the agent package and a reachable server. Cached for 60 seconds by default; `GET /api/overview?refresh=true` recomputes it.
- `GET /api/sites/{site_id}` — station briefing with summarized environmental and health observations; returns 404 when the tagged dataset has no observations for that site. Site ids match `[A-Za-z0-9.-]{1,64}`.
- `POST /api/ask` — ask the assistant about FHIR data with `{question, site_id?}`; the optional `site_id` adds station context. Requires `OPENAI_API_KEY`, the agent package, and a reachable server.

Upload the included health CSV from PowerShell with:

```powershell
curl.exe -X POST "http://localhost:8001/ingest/public-health/csv" `
  -H "Content-Type: text/csv" `
  --data-binary "@demo/sample_public_health.csv"
```

Download the blank template with:

```powershell
curl.exe -L "http://localhost:8001/ingest/public-health/csv/template" -o "public-health-template.csv"
```

The CSV endpoint validates the whole file before processing. Rows are grouped by `event_id`; the response reports the result for each grouped event. IoT and citizen-survey sample files remain JSON and use their existing MQTT and RabbitMQ channels (or the JSON `/ingest` route for direct API submissions).

## Evidence dashboard

The evidence dashboard is a separate application. Install it with `python -m pip install -e ".[dev]"`, then run:

```powershell
oah-dashboard
```

It opens at `http://localhost:8090` by default. It starts in mock mode with sample observations, findings, and run/report workflows. Its state survives browser refresh and resets when the dashboard server restarts. The dashboard theme selector remembers an explicit choice in that browser.

To connect it to the live ingestion gateway, set `OAH_LIVE_BASE_URL` in `.env` and open `http://localhost:8090/?mode=live`, or set `DASHBOARD_DEFAULT_MODE=live`. Live overview and station views only read FHIR, so already-uploaded data appears without ingestion. Set `INGESTION_WORKERS_ENABLED=false` for a gateway without MQTT/RabbitMQ listeners; the HTTP ingestion routes remain available. The allow-listed same-origin proxy also supports health/info, explicit supplied-sample execution, and the optional assistant. Live mode returns 501 for features without gateway endpoints, including durable run history/retry, evidence details, the relationships graph, and reports; these work in mock mode. See [dashboard/API-MAPPING.md](dashboard/API-MAPPING.md) for the boundary.

## Surveillance Studio

The gateway also serves the District Surveillance Officer Studio at
`http://localhost:8001/api/officer/panel` (use your configured `APP_PORT`).
The evidence dashboard also integrates Studio natively at
`http://localhost:8090/studio`. Choose **Surveillance** in the primary navigation
(**Studio** on mobile), or use the bot button to open the same dashboard page. Choose the current station or all stations, enter a question,
and watch tool activity, charts, and the answer arrive. Navigating away and returning keeps the current results; **Stop** interrupts the browser request,
and **New** clears the visible investigations. Each question starts a fresh
investigation rather than a conversation with model memory.

The Studio page follows all four dashboard themes and uses the dashboard's
origin for streaming and downloads. Executive reports download as HTML; open
the file and print to save as PDF. Figures are limited to the selected
investigation. Studio is available to the Analyst demo persona in live mode;
mock mode offers a link to the live workspace. Both the dashboard and gateway
must be running. The standalone gateway Studio remains available.

The Studio streams an investigation using server-sent events. The analyst can
choose data tools and charts: severity matrices, rankings, trends, scatter
plots, longitudinal river profiles, and exceedance persistence. Analyses are
computed in Python. Peak offsets are descriptive comparisons, not evidence of
causation. `OPENAI_API_KEY` is required for investigations and executive prose;
station data, analysis routes, and exports can be used without it.

| Gateway route | Purpose |
|---|---|
| `GET /api/officer/stations` | Station metadata, district, and reach |
| `GET /api/officer/wards?days=28` | Prioritized screening and change in notified cases |
| `GET /api/officer/trend?site_id=yam-ito&indicator=bod&days=28` | Chronological series and period comparison |
| `GET /api/officer/profile?river=Yamuna&indicator=faecal_coliform` | Readings along the river and steps between stations |
| `GET /api/officer/persistence?days=28` | Days exceeding the criterion and consecutive sampling runs |
| `GET /api/officer/offset?site_id=yam-ito&days=28` | Offset between water and notified-case peaks |
| `POST /api/officer/studio/run` with `{question}` | Stream tool calls, chart specifications, and an answer |
| `GET /api/officer/studio/report/{session}` | Download the investigation transcript as HTML |
| `POST /api/officer/studio/executive` with `{session, figures?}` | Executive HTML report with charts and print-to-PDF styling |
| `GET /api/officer/export/readings.csv?days=28` | Environmental readings and screening references |
| `GET /api/officer/export/surveillance.csv?days=28` | Case counts, rates, and population denominators |
| `GET /api/officer/export/bundle.json?site_id=yam-ito&days=28` | FHIR collection Bundle containing station observations |
| `GET /api/officer/report/facts?days=28` | Computed report facts without a model call |

Studio transcripts and sessions live in process memory and expire on restart.
The Studio's exports are separate from the evidence dashboard's mock report
lifecycle. Neither interface implements production authentication.

Public-health JSON envelopes additionally accept `disease_surveillance` lines
with `condition`, `cases`, `population_at_risk`, and optional rate and baseline.
Rates are derived per 100,000 when omitted. FHIR health observations retain the
cases, denominator, and baseline as components; existing risk-score envelopes
and the European CSV input continue to work.

Screening selects the station's city. Indian stations use the incoming CPCB
and IS 10500 reference rules; European stations retain the existing nitrate-as-N,
pH, and zinc conventions. The assistant's `get_thresholds(city=...)` tool uses
the same selection. These are prototype references, not enforcement limits.
New stations need a gazetteer entry to select a city reliably.

To generate the 28-day synthetic demonstration series without uploading it:

```bash
.venv/bin/python demo/generate_timeseries.py --days 28
```

To generate and upload all 192 events (168 water events and 24 weekly health
returns across six Indian stations), add `--ingest`, or run `./run-demo.sh seed`.
Seeding uses the root `.env` and runs the pipeline directly, so broker workers
are unnecessary. The data is synthetic. `?autorun=1` or Shift+D starts the
Studio's automatic demonstration.

## Tests and examples

Run the existing package tests and model example builder:

```powershell
python -m unittest discover -s oah-ingestion/tests -v
python -m unittest discover -s oah-pydantic-models/tests -v
python -m unittest discover -s oah-agent/tests -v
python -m pytest
node dashboard/tests/test_api.mjs
node dashboard/tests/test_studio_stream.mjs
node dashboard/tests/test_routes.mjs
python oah-pydantic-models/examples/build_examples.py
```

The root `pyproject.toml` configures pytest for `dashboard/tests`; install the dashboard extras first if pytest and httpx are not already installed. The JavaScript adapter checks use Node's built-in test runner with stubbed fetch responses and require no npm dependencies.
