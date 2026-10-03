# OneAquaHealth evidence dashboard

A compact vanilla HTML/CSS/JavaScript dashboard with a stateful FastAPI mock service. It tells one connected story: choose a station, inspect observations and findings, run an ingestion, inspect screening and FHIR stages, follow evidence relationships, and generate/download a Site One Health Briefing.

## Design direction and themes

The interface uses restrained operational layouts where station context and evidence tables take priority over generic statistic cards. The sidebar selector offers **OneAquaHealth**, **Aqua**, **Aqua dark**, **White**, and **Dark**. The OneAquaHealth preset follows the public project's blue, cyan, white, and navy visual language; White is deliberately achromatic, including status and graph data colors.

All theme metadata and CSS custom-property values live in [`data/themes.json`](data/themes.json). Each theme must provide the same complete token map, so adding or changing a theme does not require editing component CSS or JavaScript. The server validates the catalogue, injects the selected default before first paint, and exposes the same data through `GET /api/config`. `DASHBOARD_DEFAULT_THEME` in the repository-root `.env` selects the featured theme; an explicit browser choice is retained locally for that browser.

## Set up and start

From the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/oah-dashboard
```

Copy `.env.example` to `.env` when starting from a fresh checkout. Open `http://127.0.0.1:8090`. The mock server owns run/report transitions; state survives browser refresh and resets when the server restarts. A Data operator can also use **Reset demo state**.

Run tests with:

```bash
.venv/bin/python -m pytest
```

## Optional live mode

Start the existing OneAquaHealth gateway separately, set `OAH_LIVE_BASE_URL` in the root `.env` if it is not on port 8000, then open:

```text
http://127.0.0.1:8090/?mode=live
```

Live mode connects only the verified existing routes through the same-origin proxy. Overview, supplied-sample execution, and the optional assistant are connected. Durable run history, retry, authorization, evidence, graph, and reports remain visibly unavailable because the existing backend does not implement them. It never treats `202 ACCEPTED` as proof of persistence; full upload success requires `fhir == "UPLOADED"` and zero failed entries.

The live session is reported as an anonymous, server-derived capability state; the demo persona selector is disabled in this mode. Proxy responses expose only dashboard-required data: broker/FHIR origins are removed, while assistant FHIR traces retain origin-free path/query evidence. Live overview counts describe the current tagged response and may be incomplete because the existing FHIR client reads only its first page.

See [API-MAPPING.md](API-MAPPING.md) for request/response ownership and future backend work.

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
