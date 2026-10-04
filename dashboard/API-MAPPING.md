# Dashboard API and capability mapping

The browser uses one service layer in `static/js/api.js`. Mock and live adapters return dashboard-facing shapes so views do not import fixtures or fetch scattered endpoints.

## Existing OneAquaHealth routes

| Service method | Existing route | Classification | Error behavior |
|---|---|---|---|
| health | `GET /health` | Existing | Network/5xx shown as unavailable |
| gateway info | `GET /api/info` | Existing | Network/5xx shown as unavailable |
| overview | `GET /api/overview` | Existing, may require `oah-agent` and FHIR | 501/502/503 shown as unavailable; no mock fallback |
| station detail | `GET /api/sites/{site_id}` | Summarized observations and findings from tagged FHIR data | 404 when no observations; invalid site ids return 422 |
| run supplied sample | `POST /api/ingest-demo/{key}` | Existing, request-scoped | Validation and FHIR outcomes preserved |
| file JSON ingestion | `POST /ingest` via `POST /api/live/ingest` | One validated event object | 422 validation details; 500 conversion / 502 upload failure details retained |
| file CSV ingestion | `POST /ingest/public-health/csv` via `POST /api/live/ingest/public-health/csv` | Public-health batch grouped by event ID | Partial failures retain every event result |
| CSV template | `GET /ingest/public-health/csv/template` via the matching `/api/live` route | Download required CSV headers | Gateway failures shown without mock fallback |
| assistant | `POST /api/ask` with `{question, site_id?}` | Existing optional endpoint with station context | 501/502/503 shown as unavailable; no credentials in browser code |

The dashboard server exposes a narrow same-origin proxy under `/api/live/*`. Set `OAH_LIVE_BASE_URL` and open `/?mode=live`, or set `DASHBOARD_DEFAULT_MODE=live` (default `mock`). An explicit `?mode=` wins. Only allow-listed routes are proxied. Site ids match `[A-Za-z0-9.-]{1,64}`; the assistant proxy translates browser `siteId` to gateway `site_id` only for valid ids. `OAH_LIVE_TIMEOUT_SECONDS` defaults to 90 seconds for slow overview queries and assistant tool loops. `GET /api/live/overview?refresh=true` bypasses the gateway overview cache. Overview and station views only read already-uploaded FHIR data.

`GET /api/config` is a public, non-sensitive dashboard configuration route. It exposes the supported theme catalogue, validated `DASHBOARD_DEFAULT_THEME`, and validated `DASHBOARD_DEFAULT_MODE` as `defaultMode`; environment values such as service URLs and credentials are not returned.

File ingestion accepts raw JSON (`application/json`) or CSV (`text/csv` or
`application/csv`) rather than multipart form data. Fixed proxy routes forward
file bytes with their content type and preserve gateway status/JSON details.
Empty files return 422, unsupported content types return 415, and files larger
than 5 MiB return 413 before reaching the gateway. CSV template bytes download
as `public-health-template.csv`. The browser prepares a bounded preview and
retains per-event outcomes in session activity, not durable job storage.
Only `UPLOADED` with zero failures and positive uploaded counts confirms
persistence. HTTP ingestion invalidates gateway overview caches after reported
writes, including partial writes, and the browser refreshes Overview and clears
station evidence caches. Upload controls use the Data operator demo capability;
the live gateway remains anonymous as described above.

`GET /studio` serves the native dashboard with live Studio selected (an explicit
`?mode=` still wins). The **Surveillance** primary navigation item selects
the Studio page within the dashboard main content. Hash routes support direct
links, refresh, and browser Back/Forward. Studio state and DOM are retained
while other dashboard routes render. The Analyst persona can investigate in live mode;
these persona controls demonstrate intended capability, not production identity.

| Dashboard route | Gateway route | Response |
|---|---|---|
| `POST /api/live/studio/run` | `POST /api/officer/studio/run` | SSE bytes forwarded as available, with cleanup on completion/disconnect |
| `GET /api/live/studio/transcript/{session}` | `GET /api/officer/studio/report/{session}` | HTML transcript |
| `POST /api/live/studio/executive` | `POST /api/officer/studio/executive` | HTML executive report |
| `GET /api/live/studio/export/readings` | `GET /api/officer/export/readings.csv` | CSV |
| `GET /api/live/studio/export/surveillance` | `GET /api/officer/export/surveillance.csv` | CSV |
| `GET /api/live/studio/export/fhir` | `GET /api/officer/export/bundle.json` | FHIR collection Bundle |

Investigations accept `{question, siteId?}`. A validated station ID is appended
as context to the gateway question; omitting it requests a district-wide
investigation. Each question starts a fresh model run. Browser results survive
dashboard navigation, but not refresh. Gateway sessions expire
on restart. Stop aborts the browser request; upstream model work already in
progress may finish before the connection closes.

Exports accept validated `days` (1–365) and optional `site_id`; FHIR export
requires a station. Content types, bytes and attachment filenames are preserved.
Executive figures come from the chosen investigation, with SVG colors resolved
for standalone viewing. Only these fixed upstream paths are reachable through
this proxy. Upstream HTTP errors retain their status; connection failures return
502, and interruptions after streaming begins produce an SSE error event.

The chart module is shared with the standalone gateway Studio. Live Studio
reports and transcripts remain separate from the dashboard's mock report
lifecycle. The supplied-sample ingestion proxy still supports the India and
European sample keys.

## Mock-backed proposed routes

| Method and route | Purpose | Permission |
|---|---|---|
| `GET /api/mock/session` | Persona policy and capability flags | Any demo persona |
| `GET /api/mock/summary` | Scoped measures and station comparison | `dashboard.read` |
| `GET /api/mock/sites/{id}` | Station observations and findings | `dashboard.read` + site scope |
| `GET /api/mock/evidence/{id}` | Evidence details | `evidence.read` + site scope |
| `GET /api/mock/graph?siteId=` | Direct-reference relationship graph | `graph.read` + site scope |
| `POST /api/mock/assistant` | Deterministic evidence-linked sample answers | `assistant.ask` + site scope |
| `GET /api/mock/runs[/{id}]` | Stateful run history and stage detail | `ingestion.read` + site scope |
| `POST /api/mock/runs` | Start repeatable pipeline simulation | `ingestion.create` + site scope |
| `POST /api/mock/runs/{id}/retry` | Explicit successful retry of a failed demo run | `ingestion.retry` + site scope |
| `POST /api/mock/reset` | Restore seed runs and reports | `ingestion.create` |
| `GET/POST /api/mock/reports` | List or request a snapshot briefing | Viewer published scope / `report.create` |
| `GET /api/mock/reports/{id}/download/{html|json}` | Authorized real file bytes | Published viewer or `report.download` |

These endpoints are functional prototype contracts. Production work still requires durable job/report storage, backend identity and authorization, retained evidence with classification, graph/read APIs, audit events, and protected FHIR service credentials.
