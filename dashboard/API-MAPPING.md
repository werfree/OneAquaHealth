# Dashboard API and capability mapping

The browser uses one service layer in `static/js/api.js`. Mock and live adapters return dashboard-facing shapes so views do not import fixtures or fetch scattered endpoints.

## Existing OneAquaHealth routes

| Service method | Existing route | Classification | Error behavior |
|---|---|---|---|
| health | `GET /health` | Existing | Network/5xx shown as unavailable |
| gateway info | `GET /api/info` | Existing | Network/5xx shown as unavailable |
| overview | `GET /api/overview` | Existing, may require `oah-agent` and FHIR | 501/502/503 shown as unavailable; no mock fallback |
| run supplied sample | `POST /api/ingest-demo/{key}` | Existing, request-scoped | Validation and FHIR outcomes preserved |
| public ingress | `POST /ingest` | Existing; not called by this dashboard | A `202 ACCEPTED` is not treated as persisted success |
| assistant | `POST /api/ask` with `{question}` | Existing optional endpoint | 501/502/503 shown as unavailable; no credentials in browser code |

The dashboard server exposes a narrow same-origin proxy under `/api/live/*`. Set `OAH_LIVE_BASE_URL` and open `/?mode=live`. Only allow-listed routes are proxied.

The live browser contract is deliberately narrower than the upstream responses. `GET /api/live/session` returns the server-derived anonymous capability state, with `hasServerAuthorization: false`. The proxy removes broker/FHIR origins and other infrastructure fields from info, overview, and ingestion responses. Assistant traces retain observable FHIR path/query data but strip the configured service origin. Live summary arrays are normalized to numeric metrics, and request-scoped ingestion results use the same six-stage dashboard model as mock runs. `UPLOADED` is exposed as successful persistence only when the upstream failed-entry count is zero.

`GET /api/config` is a public, non-sensitive dashboard configuration route. It exposes the supported theme catalogue, each theme's complete presentation-token map, and the validated `DASHBOARD_DEFAULT_THEME`; environment values such as service URLs and credentials are not returned. The response is generated from `data/themes.json`, the same source used for the initial server-rendered theme.

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

## Live dashboard routes

| Method and route | Dashboard result | Classification |
|---|---|---|
| `GET /api/live/session` | Anonymous identity and server-derived capability flags; no production authorization claim | Unavailable authorization / existing gateway access |
| `GET /api/live/info` | Allow-listed sample metadata only | Existing |
| `GET /api/live/overview` | Sanitized FHIR-derived briefings normalized by the browser adapter | Existing and derived; first-page limitation |
| `POST /api/live/ingest-demo/{key}` | Sanitized request-scoped validation, screening, mapping, bundle, and FHIR outcome | Existing; not durable history |
| `POST /api/live/ask` | Answer, normalized observable trace, and numeric-grounding limitation | Existing optional capability |

Durable history/retry, scoped evidence, relationship graph retrieval, authenticated identity/site authorization, and reports remain unavailable in live mode. The corresponding prototype flows remain explicitly mock-backed.
