# OneAquaHealth evidence dashboard

A compact vanilla HTML/CSS/JavaScript dashboard with a stateful FastAPI mock service. It tells one connected story: choose a station, inspect observations and findings, run an ingestion, inspect screening and FHIR stages, follow evidence relationships, and generate/download a Site One Health Briefing.

## Design direction and themes

The interface uses restrained operational layouts where station context and evidence tables take priority over generic statistic cards. The sidebar theme selector offers **Aqua**, **Aqua dark**, **White**, and **Dark**. `DASHBOARD_DEFAULT_THEME` in the repository-root `.env` selects the first featured theme; an explicit browser choice is retained locally for that browser. Semantic amber/red/green/blue remains reserved for attention, failures, completed work, and active processing. The relationship view is deliberately small and has a textual alternative.

## Set up and start

From the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/oah-dashboard
```

Copy `.env.example` to `.env` when starting from a fresh checkout. Open `http://127.0.0.1:8090`. The mock server owns run/report transitions; state survives browser refresh and resets when the server restarts. A Data operator can also use **Reset demo state**.

With the project dependencies installed, `python run.py` starts both the
gateway and dashboard using the root `.env` and `.venv`. Press Ctrl+C to stop
both. Use `python run.py --no-brokers` for HTTP ingestion and live Studio
without MQTT/RabbitMQ consumers, or add `--open` to open the browser.

For access from other devices on your LAN, set `DASHBOARD_HOST=0.0.0.0` in
the root `.env` and restart. Open `http://<your-computer-LAN-IP>:8090` from
the other device and allow that port through your private-network firewall
if necessary. The default host is `127.0.0.1` (this computer only).
`OAH_LIVE_BASE_URL` remains the server-side gateway address; it can stay on
loopback because browser requests use the dashboard's same-origin proxy.

Run tests with:

```bash
.venv/bin/python -m pytest
```

## Optional live mode

Start the existing OneAquaHealth gateway separately, set `OAH_LIVE_BASE_URL` in the root `.env` if it is not on port 8000, then open:

```text
http://127.0.0.1:8090/?mode=live
```

Live mode connects only the verified existing routes through the same-origin proxy. Overview, supplied-sample execution, and the optional assistant are connected. Durable run history, retry, authorization, graph, and the mock report lifecycle remain visibly unavailable because the existing backend does not implement them. It never treats `202 ACCEPTED` as proof of persistence; full upload success requires `fhir == "UPLOADED"` and zero failed entries.

See [API-MAPPING.md](API-MAPPING.md) for request/response ownership and future backend work.

## File ingestion

In live mode, choose **Ingestion**, select the **Data operator** persona,
and choose a UTF-8 `.json` or `.csv` file (maximum 5 MiB). Inspect the preview,
then click **Submit file**. JSON must contain one gateway ingestion envelope
with `source_type` set to `IOT_TELEMETRY`, `CITIZEN_SURVEY`, or `PUBLIC_HEALTH`.
CSV supports public-health risk scores and chemical summaries; use **Download
CSV template** for the required headers or `demo/sample_public_health.csv`
for populated examples. CSV rows with the same `event_id` form one event.

Validation errors appear beside the file selector. Processed files show each
event's FHIR outcome, uploaded/failed resource counts, and screening outputs.
Partial batch failures retain the successful events in the results; those
events may already be persisted. `BUILT_NOT_SENT` means uploads are disabled,
and is never shown as uploaded. Overview and station evidence refresh after
reported writes; a refresh failure does not discard file results.

Uploads and template downloads go through the dashboard's same-origin proxy,
so LAN browsers only need the dashboard port. No broker or OpenAI key is
required for HTTP file ingestion. Live results survive dashboard navigation
but reset on browser refresh or persona change; there is no durable job history.
File uploads are disabled in mock mode.

## Native Surveillance Studio

Open `http://127.0.0.1:8090/studio` with the gateway running and
`OPENAI_API_KEY` configured on the gateway. In live dashboard mode, the
**Surveillance** navigation item opens a full page in the dashboard,
just like Overview. Mobile navigation labels it **Studio**.
Choose **Current station** or **All stations**, ask a question, and inspect
streaming tool activity, charts, answers and screening references. The page
follows the selected theme and preserves results when navigating away and back.
**Stop** interrupts the request; **New** clears displayed results. Each question
starts a separate investigation; there is no model conversation memory.

Completed investigations expose transcripts, environmental/health CSV exports,
and a FHIR Bundle for station-scoped investigations. Executive reports download
as HTML with that investigation's SVG charts; open the file and print to PDF.
The Analyst demo persona can use Studio. Mock mode links to the live workspace.
Both Python services remain necessary; browser requests and downloads use the
dashboard origin. Standalone Studio remains at the gateway's `/api/officer/panel`.

Check the dashboard adapter and streaming parser with:

```bash
node dashboard/tests/test_api.mjs
node dashboard/tests/test_studio_stream.mjs
node dashboard/tests/test_routes.mjs
```


## Suggested 4-minute demo

1. On **Overview**, select Mondego C1 and point out nitrate/zinc screening flags alongside the separately timed health aggregate. Open **Evidence**, then **Relationships**; follow the co-location finding and repeat “association only, not causation.”
2. Switch the demo persona to **Data operator**, open **Ingestion**, choose IoT telemetry, and start a run. Inspect Received, Screened, Mapped, and Upsert outcome payloads. Open the seeded failed public-health run and retry it; the original failure remains visible.
3. Switch to **Analyst**, return to Overview, ask “What evidence supports the co-location finding?” and show the observable tool/evidence trace.
4. Open **Reports**, generate a station briefing, wait for the short lifecycle, preview it, and download HTML or JSON. Use **Print / Save as PDF** for a browser-generated PDF.
5. Switch to **Viewer** to show that only the published Mondego report and scoped station summary remain visible; direct evidence/graph requests are denied by the mock API.

## Capability boundary

- Connected to current code in live mode: health/info, FHIR-derived overview, four supplied sample replays, request-scoped validation/screening/mapping/upload result, and optional assistant answer/tool trace.
- Derived in the dashboard: scoped measures, station comparison, direct-reference graph assembly, and linked finding/evidence presentation.
- Simulated but functional: personas and site scope, durable-looking run history/progress/retry, report lifecycle, snapshot files, and deterministic sample assistant answers.
- Still needed for production: real authentication/authorization, durable run/evidence/report storage, audit logs, paging-safe aggregation, protected FHIR credentials, graph/read endpoints, file storage, and report publication workflow.

Coordinates are approximate demo values. Screening rules are prototype references, not universal safety limits. Chemical basis and units are preserved; missing data is never rendered as zero.
