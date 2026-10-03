# Dashboard Data & Capability Specification

**Scope:** implementation-led reverse engineering of OneAquaHealth as checked on 2026-10-02. This is a data and capability handoff for a later dashboard-design process; it intentionally contains no visual design guidance.

## 1. Executive summary

OneAquaHealth is a small, single-process Python prototype that accepts three One Health data streams, validates and screens them, transforms them into OAH-profiled FHIR R4 resources, and upserts those resources into a configurable FHIR server. A FastAPI application also serves a simple live demonstration page and optionally calls an OpenAI tool-using assistant over the same FHIR data.

The future dashboard can immediately demonstrate real ingestion, FHIR resource inspection, threshold alerts, site/cohort relationships, cross-domain co-location, and assistant tool traces. It cannot yet truthfully show durable jobs, progress, user identity, authorization, reports/downloads, persisted audit history, notifications, or a server-side relationship graph. Those require backend work.

Classification used throughout:

- **EXISTING** — directly implemented.
- **DERIVED** — calculable from existing data, usually by querying/aggregating FHIR resources.
- **RECOMMENDED** — needs new API, storage, instrumentation, or policy.

## 2. System mental model

```text
MQTT telemetry ─┐
RabbitMQ survey ├─> validate/normalize ─> screen thresholds ─> OAH→FHIR map
HTTP health ────┘                                      │                 │
                                                       └─> in-process alert callback
                                                                         │
                                              transaction Bundle PUT ──> FHIR R4 server
                                                                         │
FastAPI demo UI <── REST endpoints <── FHIR query tools <── assistant / deterministic briefing
```

The FHIR server is the only durable application data store identified in the implementation. RabbitMQ is a durable input queue; MQTT is an external message stream. The process retains no event, job, alert, user, report, or audit database after a request/consumer callback ends.

## 3. Architecture relevant to the dashboard

| Boundary | Input | Processing | Output/storage | Dashboard consumer | Classification |
|---|---|---|---|---|---|
| FastAPI gateway | HTTP `POST /ingest` envelope | Pydantic validation; normalize; pipeline | 202 response plus FHIR transaction | pipeline demo | EXISTING |
| MQTT worker | `oneaquahealth/sensors/{city}/{site_id}` JSON | topic/payload agreement; filters invalid individual readings; pipeline | FHIR transaction; QoS ack | operational feed only | EXISTING |
| RabbitMQ worker | `ingestion.citizen_surveys` JSON | Pydantic validation; pipeline; ack/nack | FHIR transaction; durable broker queue | operational feed only | EXISTING |
| Pipeline | discriminated envelope | screen; map; tag; bundle; upload | logs + configured FHIR server | demo endpoint result | EXISTING |
| FHIR server | transaction Bundle / search | external FHIR R4 persistence and query | `Location`, `Specimen`, `Observation`, `Group`, provenance resources | overview, assistant | EXISTING, external |
| Agent | question | OpenAI function-tool loop; FHIR lookups; numeric grounding check | response only; conversation memory is in-process | `/api/ask` | EXISTING when key/server available |

Primary implementation: `oah-ingestion/src/oah_ingestion/app.py`, `pipeline.py`, `fhir_adapter.py`, `fhir_client.py`, and `oah-agent/src/oah_agent/{assistant,tools,briefing,grounding}.py`.

## 4. Major subsystem catalogue

| Subsystem | Responsibility | Key implementation |
|---|---|---|
| OAH logical models | Type-safe OAH logical entities | `oah-pydantic-models/src/oah_models/` |
| Envelope validation | Discriminated stream validation, UUID/time metadata | `oah-ingestion/.../envelope.py` |
| Input adapters | MQTT topic verification, RabbitMQ consume/ack, HTTP handling | `sensor.py`, `mqtt_worker.py`, `rabbitmq_worker.py`, `app.py` |
| Threshold screening | Deterministic screening against nitrate, pH, zinc rules | `thresholds.py`, `alerts.py` |
| FHIR adapter | Convert the three envelopes into profiled FHIR resources | `fhir_adapter.py` |
| FHIR persistence/query | Bundle construction, idempotent PUT, first-page FHIR searches | `oah_models/fhir/bundle.py`, `fhir_client.py` |
| Site gazetteer | Demo site name and position lookup | `sites.py`, `demo/sites.json` |
| Assistant/briefing | Typed data retrieval, co-location computation, model narrative, numeric grounding | `oah-agent/src/oah_agent/` |
| Current demo UI | Calls the above APIs and displays their live results | `oah-ingestion/.../static/dashboard.html` |

No ORM/repository layer, relational database, graph database, worker orchestration framework, report engine, identity provider, authorization middleware, WebSocket/SSE server, or notification service is present.

## 5. Domain entity catalogue

| Entity | Purpose and salient fields | Storage / lifecycle / consumers | Classification |
|---|---|---|---|
| `IoTEnvelope` | `event_id`, city, site, timestamp, received_at, device ID, 1–500 measurements | ephemeral request/message object; mapped to FHIR | EXISTING |
| `CitizenSurveyEnvelope` | event metadata; app/volunteer ID; coordinates; coded observations; optional photo URLs | ephemeral; mapped to FHIR | EXISTING |
| `PublicHealthEnvelope` | agency, evaluation period, cohort, 0–1 risk score, chemical summaries | ephemeral; mapped to FHIR | EXISTING |
| Measurement | parameter, unit, value, optional min/max/avg | nested envelope; scalar or component Observation | EXISTING |
| Threshold rule | nitrate > 11.3 mg/L; pH outside 6.5–9.0; zinc > .0078 mg/L; stated basis | Python dictionary, deployment-local | EXISTING |
| Alert | site/city/observed time, `LOW|MODERATE|HIGH`, exceedances, elevated risks, caveat | returned/logged/callback only; not persisted | EXISTING ephemeral |
| Site / FHIR `Location` | site ID/name, optional WGS84 position | demo gazetteer and FHIR server | EXISTING |
| FHIR `Observation` | profile, final status, code, site subject, time, scalar/coded/component value; optional cohort/device/performer | FHIR server; queried by overview/agent | EXISTING |
| FHIR `Specimen` | sampling site, collection time/collector | FHIR server; environmental mapping | EXISTING |
| FHIR `Device` | sensor ID/name/type/location | FHIR server; telemetry provenance | EXISTING |
| FHIR `Practitioner` | citizen volunteer ID/name | FHIR server; survey provenance | EXISTING |
| FHIR `Organization` | health agency | FHIR server; public-health provenance | EXISTING |
| FHIR `Group` | demographic cohort: age range, gender, location reference | FHIR server; health Observation `focus` | EXISTING |
| `Library` / dataset | logical model supports metadata, records and versioning | mapper exists but ingestion does not create it | EXISTING model; unused flow |
| Briefing | per-site environmental readings, health measures, threshold findings, co-location and caveat | computed response only | DERIVED |
| Execution trace | assistant tool name, arguments, FHIR URLs | `/api/ask` response only | EXISTING, assistant only |
| Ingestion job, report, audit event, user/role/permission, notification | dashboard concepts requested but absent | none | RECOMMENDED |

Source-specific statuses: FHIR `Observation.status` defaults to `final`; FHIR `Library.status` defaults to `draft`; `RiskScore.interpretation` is `LOW|MODERATE|HIGH`. There is no ingestion-job enum.

## 6. Entity relationship model

```text
IoTEnvelope ──contains──> Measurement ──maps_to──> Observation
IoTEnvelope ──identifies──> Device ──located_at──> Location
CitizenSurveyEnvelope ──contains──> SurveyObservation ──maps_to──> Observation
CitizenSurveyEnvelope ──identifies──> Practitioner ──performs──> Observation
CitizenSurveyEnvelope ──links_photo──> Binary URL (reference only)
PublicHealthEnvelope ──defines──> Group ──focus_of──> health Observation
PublicHealthEnvelope ──identifies──> Organization ──performs──> Observation
All Observations ──subject/site──> Location
Environmental Observation ──uses──> Specimen
All mapped resources ──tagged_with──> dataset tag
Observation ──screened_by──> ThresholdRule (derived; only matching indicators)
Site briefing ──joins──> environmental Observation + health Observation at Location
```

Cardinality: one telemetry measurement yields one Observation plus shared Location/Specimen and a Device; one survey answer yields one Observation plus shared Location/Specimen and a Practitioner; one public-health risk score yields one health Observation, while a public-health envelope yields one Group and Organization. Bundle de-duplication collapses same `(resourceType,id)` resources, and transaction PUTs make identical replays idempotent.

## 7. Lifecycle and state models

### Existing event handling

```text
HTTP: RECEIVED → VALIDATED → SCREENED → MAPPED → [BUILT_NOT_SENT | UPLOADED | UPLOAD_FAILED | CONVERSION_FAILED]
MQTT: RECEIVED → topic/payload validation → accepted/rejected → same pipeline → QoS acknowledgement
RabbitMQ: RECEIVED → validated → same pipeline → ACK
                                         └──────── invalid/exception → NACK(requeue=false)
```

`ACCEPTED` is only the HTTP endpoint's response status; it does not mean the FHIR upload succeeded. The actual terminal `fhir` values are listed above. No retry state or persisted transition record exists. RabbitMQ reconnects after a connection failure; MQTT relies on the client loop. Upload failure is deliberately swallowed to avoid endless broker redelivery (`pipeline.py`).

### Existing alert behavior

`assess()` yields no alert, or an alert with severity `HIGH` for environmental threshold exceedance and the highest supplied `MODERATE|HIGH` public-health interpretation otherwise. Subscribers are in-memory callbacks; a subscriber failure is logged and ignored.

## 8. Ingestion pipeline

| Seq | Stage ID / name | Input → output | Existing fields usable by UI | Status data |
|---|---|---|---|---|
| 1 | `received` | raw channel payload → envelope candidate | raw JSON; channel; transport topic/queue only in logs for workers | DERIVED start time from receipt |
| 2 | `validated` | candidate → discriminated Pydantic envelope | validated envelope, validation exception | EXISTING result, not persisted |
| 3 | `screened` | envelope → optional alert | threshold basis, exceeding values, elevated health risk | EXISTING, transient |
| 4 | `mapped` | envelope → FHIR resource objects | profiled resources, resource-type counts | EXISTING, transient |
| 5 | `bundled` | resources → deduplicated transaction Bundle | resource list/count, PUT URLs | DERIVED; bundle not returned by normal API |
| 6 | `persisted` | Bundle → FHIR transaction result | `UPLOADED`, succeeded/failed entry count | EXISTING summary only |

The existing `/api/ingest-demo/{key}` returns raw input, validated form, alert, up to four Observations, profile names, and upload summary. It does not currently return timestamps, durations, full bundle, each resource, per-stage state, progress, retry count, or raw data after the request ends.

## 9. Pipeline stages and data

| Desired pipeline field | Availability |
|---|---|
| stage ID/name, raw input, validated output, alert, selected Observations, FHIR result | EXISTING for demo endpoint / request scope |
| source type, event ID, event and gateway receipt time | EXISTING in envelope/normalization |
| FHIR resource counts, uploaded/failed count | EXISTING |
| bundle payload, all generated artifacts | DERIVED in-process; not API-exposed or persisted |
| stage start/end/duration, progress, accepted/rejected/warning counts, retry metadata | RECOMMENDED |
| pipeline/job identifier stable across transports | RECOMMENDED; do not use regenerated gateway `event_id` as a source id |

## 10. Pipeline visualization data

The truthful current visual sequence is **Received → Validated → Screened → Mapped → Upsert attempted**. “Persisted” must depend on `fhir == "UPLOADED"` and `failed == 0`; “Accepted” must not be rendered as successful persistence. A recommended `PipelineStage` contract is in section 38.

## 11. Raw/intermediate/final payloads

- **Raw:** available only in the immediate HTTP/demo/request path and broker message; HTTP demo returns it. No raw-event retention.
- **Normalized:** `envelope_as_message()` assigns a new gateway `event_id` and `received_at`, prints it to logs; it is not stored.
- **Validated:** Pydantic envelope available while handling the message; demo endpoint returns it.
- **Screened:** alert object is returned/logged/callback only.
- **Mapped:** Python FHIR resource models and Bundle exist only during `process()`; demo exposes a subset of Observations.
- **Final:** FHIR transaction resources persist externally, subject to server behavior.

Representative existing raw telemetry is `demo/sample_iot_telemetry.json`: site `site-c1-mondego`, device `ESP32-SENS-COIMBRA-01`, pH 7.4, nitrate 14.2 with min/max/avg, and zinc 0.05. The mapped nitrate becomes an `observation-with-component-oah` Observation with `value`, `average`, `minimum`, and `maximum` components.

## 12. Execution/explainability trace

The system must not present private model reasoning. Observable execution can be shown as follows:

| Trace class | Current payload | Classification |
|---|---|---|
| Ingestion | request raw/validated/alert/mapped/upload summary for demo | EXISTING but transient |
| Threshold decision | rule basis, value, threshold/band, exceedance factor | EXISTING |
| FHIR persistence | server base URL, resource summary, succeeded/failed counts | EXISTING |
| Assistant | tool name, JSON arguments, one or more constructed FHIR search URLs | EXISTING at `/api/ask` |
| Grounding | Boolean, counts, unsupported figures, limitation statement | EXISTING |
| OpenAI model ID | returned by `/api/ask` | EXISTING |
| prompt ID/version, token usage, latency, model provider response ID, retrieved resource IDs, error/retry timeline | RECOMMENDED |

Recommended consumer-safe trace: `ExecutionTrace { id, subjectType, subjectId, startedAt, completedAt, outcome, steps[] }`; each step captures `kind`, `title`, `status`, `timestamp`, `durationMs`, `inputRef`, `outputRef`, `evidenceRefs`, `error`, and redacted metadata—never chain-of-thought.

## 13. Evidence model

No generic Evidence resource/model is stored. The best available evidence chain is derived:

```text
briefing finding → Observation id + FHIR search URL → profile/code/value/time/site/cohort → source provenance (Device / Practitioner / Organization) → source envelope only if retained externally
```

Threshold rules are evidence for the screening classification only; their Python source/basis is available, but no rule version is persisted with each alert. Recommended evidence fields: ID, type (`FHIR_OBSERVATION`, `THRESHOLD_RULE`, `SOURCE_EVENT`, `COHORT`, `FHIR_QUERY`), resource reference, display value, captured-at time, provenance, immutable snapshot/hash, and access classification.

## 14. Analysis/finding model

There is no durable `Analysis` or `Finding`. `site_briefing()` derives:

- environmental threshold exceedances, carrying indicator, value, unit, threshold/basis, factor, and source Observation ID;
- health risk entries, carrying indicator, score, agency interpretation, cohort, and Observation ID;
- `co_location` when the same site has both an exceedance and an elevated health risk.

The computation explicitly declares this as association only, not causation. The future dashboard should retain that caveat with any derived finding.

## 15. Report model

There is **no report-generation feature**. No domain object, endpoint, template, review/approval state, file artifact, or storage path exists. `DataSetOah → Library` is dataset metadata mapping, not a report model.

## 16. Report-generation lifecycle

No existing lifecycle. Recommended: `REQUESTED → GENERATING → GENERATED → REVIEW_REQUIRED → APPROVED|REJECTED → ARCHIVED`, with a separate `FAILED` and retry policy. This must be implemented before presenting report functionality as real.

## 17. Report download/file model

No download endpoint or report file is implemented. The only file-like reference in the current domain is optional citizen-survey `photo_urls`, mapped to `Location.extension` documentation references; it does not imply uploads, authorization, expiry, or download auditability.

## 18. Graph model

FHIR references and the derived site briefing provide a real relationship substrate; no graph is stored or queried as a graph. A dashboard may assemble a local graph from FHIR search responses, but relationship completeness is constrained by endpoint/query pagination and missing provenance/event lineage.

## 19. Graph node catalogue

| Node type | ID | Label/metadata | Origin |
|---|---|---|---|
| Site | `Location/{id}` | name, position, city from gazetteer | FHIR + local demo data |
| Environmental Observation | `Observation/{id}` | code, quantity/coded value, effective time, profile, status | FHIR |
| Health Observation | `Observation/{id}` | risk score, interpretation embedded in unit, time | FHIR |
| Cohort | `Group/{id}` | name, age range, gender, location | FHIR |
| Device | `Device/{id}` | identifier/name/type | FHIR |
| Volunteer | `Practitioner/{id}` | identifier/name | FHIR |
| Agency | `Organization/{id}` | name | FHIR |
| Specimen | `Specimen/{id}` | collection date/collector | FHIR |
| Threshold rule | `threshold:{indicator}` | rule, basis, version/hash recommended | Python; derived |
| Alert / finding | generated ID | severity, exceedances, caveat | derived/transient |

## 20. Graph edge catalogue

| Edge | Source → target | Cardinality / origin |
|---|---|---|
| `OBSERVED_AT` | Observation → Location | many:1, `subject` |
| `DESCRIBES` | health Observation → Group | many:1, `focus` |
| `MEASURED_BY` | telemetry Observation → Device | many:1, `device` |
| `PERFORMED_BY` | survey/health Observation → Practitioner/Organization | many:many, `performer` |
| `USES_SPECIMEN` | environmental Observation → Specimen | many:1, `specimen` |
| `COLLECTED_AT` | Specimen → Location | many:1, `subject` |
| `LOCATED_AT` | Device → Location | many:1, `location` |
| `DEFINES_LOCATION` | Group → Location | many:1, group characteristic reference |
| `SCREENED_BY` | Observation → Threshold rule | derived when matching indicator/rule |
| `SUPPORTS` | Observation/threshold → derived finding | derived |

Useful assembled queries: neighbours of a site; its observations by profile/date/code; cohort behind a health measure; provenance for an Observation; threshold evidence supporting an alert; all observations that support a co-location. Path-finding beyond these direct references is RECOMMENDED in a graph/read model.

## 21. Available metrics

| Metric | Meaning / formula | Source | Class |
|---|---|---|---|
| site count | tagged `Location` count | FHIR search | DERIVED |
| environmental/health reading count | tagged profiled Observation count | FHIR search | DERIVED |
| site environmental/health count | results from `get_site_profile` | FHIR | DERIVED |
| threshold exceedance count | `evaluate_many` over environmental summaries | FHIR + threshold table | DERIVED |
| sites with elevated risk/co-location | briefing predicates per site | FHIR + threshold table | DERIVED |
| upload success/failed resources | current transaction response counts | `process()` response/log | EXISTING transient |
| alert count | count of emitted `assess()` results | only while instrumented in process | DERIVED transient |

Job totals, active jobs, throughput, duration, retries, queue depth, model tokens, report/download counts, and request latency are not reliable without instrumentation.

## 22. Metric formulas

- `exceedanceRate = screenedEnvironmentalObservationsWithExceedance / screenedEnvironmentalObservations` — **DERIVED** only after explicitly defining denominator and data time range.
- `coLocatedSiteCount = count(site where exceedances.length > 0 && elevated_risks.length > 0)` — **DERIVED**.
- `uploadEntrySuccessRate = uploaded / (uploaded + failed)` — **EXISTING** per transaction, not historical.
- `nitrateExceedanceFactor = value / 11.3`, `zincExceedanceFactor = value / .0078` — **EXISTING** alert payload where exceeded.

## 23. Time-series opportunities

| Series | Timestamp | Aggregation | Class / caveat |
|---|---|---|---|
| readings by site/indicator | `Observation.effectiveDateTime` | hour/day/week | DERIVED; FHIR search currently fetches first page only |
| health risk score | health Observation effective time | day/month/evaluation period | DERIVED |
| screening exceedances | source Observation effective time | day/week | DERIVED |
| event receipt latency | `received_at - timestamp` | distribution/day | EXISTING only during raw event handling; not stored |
| ingestion stage duration, throughput, failures/retries | stage event times | minute/hour/day | RECOMMENDED |

## 24. Authentication model

There is no authentication implementation. All FastAPI routes are anonymous; FHIR calls contain no Authorization header; the assistant checks only `OPENAI_API_KEY` server configuration. The current page therefore has no current-user API or user identity.

## 25. Authorization model

There are no roles, permissions, scopes, claims, tenant boundaries, ownership checks, data masking, or action guards in repository code. Dataset tags scope searches functionally (`meta.tag`) but are not authorization. Treat the public/default FHIR server configuration as unsuitable for sensitive production data.

## 26. Existing user roles

Only one effective role exists: **anonymous caller with unrestricted access to exposed app endpoints**. Infrastructure credentials (RabbitMQ/MQTT/FHIR/OpenAI) are service configuration, not user roles.

## 27. Permission matrix

| Capability | Anonymous caller today | Required future policy |
|---|---|---|
| View dashboard/info/overview | allowed | viewer permission + tenant/site scope |
| Submit HTTP ingestion | allowed | ingest permission + source scope |
| Replay bundled sample | allowed | demo operator permission |
| Ask assistant | allowed if server has API key | analyst permission + data scope |
| FHIR resource mutation | gateway's configured server access | service identity; user authorization enforced at gateway |
| Reports/downloads/admin/audit | nonexistent | new permissions |

## 28. Role-based visibility matrix

**Existing:** no restricted visibility; all current UI/API information is equally reachable. **Recommended minimum policy**, not an inferred current role design:

| Proposed role | Sites/readings | raw payload/provenance | ingestion control | reports | audit/config |
|---|---|---|---|---|---|
| Viewer | authorized site summaries | no raw identifiers by default | no | approved only | no |
| Analyst | authorized data/evidence | redacted raw data | no | generate draft | own activity |
| Data operator | assigned source/site events | full operational payload | submit/retry/cancel | no | own operations |
| Health reviewer | approved health aggregates | restricted evidence | no | review/approve | review trail |
| Administrator | policy-scoped | policy-scoped | configure sources/rules | administer | full audit |

## 29. Role-based action matrix

The preceding action matrix is RECOMMENDED. Existing code offers only anonymous HTTP ingestion, demo replay, FHIR-derived reads, and assistant questions. “Retry”, “cancel”, “approve”, “reject”, “configure”, “administer”, and all report actions are absent.

## 30. User actions

| Action | Existing service/API | Inputs/result/failure | Class |
|---|---|---|---|
| Ingest public-health event | `POST /ingest` | valid envelope → status/event ID/FHIR summary; 422 validation or FHIR failure summary | EXISTING |
| Publish telemetry/survey | MQTT/RabbitMQ publishers | channel-valid payload → asynchronous pipeline; broker errors | EXISTING integration |
| Replay included demo | `POST /api/ingest-demo/{key}` | one of `iot`, `survey`, `health`, `health-mondego` → stage data | EXISTING |
| Inspect dataset overview | `GET /api/overview` | agent package + FHIR availability → briefing | EXISTING |
| Ask data question | `POST /api/ask` | question → answer, tool trace, grounding; API key/FHIR/model failures | EXISTING |
| Search FHIR / inspect a cohort | typed agent tools / direct FHIR service | profile/code/site filters | EXISTING internal capability |
| Retry/cancel an ingestion, acknowledge alert, generate/download/approve report | none | n/a | RECOMMENDED |

## 31. API inventory

| Method | Endpoint | Purpose | Request/response | Permission | Status |
|---|---|---|---|---|---|
| GET | `/health` | liveness | `{status:"ok"}` | none | EXISTING |
| POST | `/ingest` | validated public ingress | discriminated envelope → `ACCEPTED`, event ID, source type, FHIR summary, alert | none | EXISTING |
| GET | `/` | current static demo | HTML | none | EXISTING |
| GET | `/api/info` | service/config/sample/threshold description | gateway, channels, FHIR tag, samples, rules | none | EXISTING |
| POST | `/api/ingest-demo/{key}` | run demo sample through pipeline | stage-rich response | none | EXISTING |
| GET | `/api/overview` | FHIR-derived cross-domain briefing | site briefing aggregate | none | EXISTING; may return 501 |
| POST | `/api/ask` | assistant | `{question}` → answer/trace/grounding/model | none | EXISTING; may return 501/503/502 |
| GET/POST | configured FHIR base | search/transaction | FHIR R4 resource/Bundle | external-server policy, no local header | EXISTING integration |

There are no GraphQL, WebSocket, SSE, report, file, audit, auth, or job APIs.

## 32. Recommended aggregation APIs

These are not implemented. Prefer a protected dashboard read model rather than exposing raw FHIR server queries to a browser.

```text
GET  /api/me
GET  /api/dashboard/summary?scope=&from=&to=
GET  /api/ingestions?status=&source=&site=&from=&to=
GET  /api/ingestions/{id}
GET  /api/ingestions/{id}/timeline
GET  /api/observations/{id}/evidence
GET  /api/sites/{id}/graph?depth=2
POST /api/reports
GET  /api/reports/{id}
GET  /api/reports/{id}/download
GET  /api/audit-events
```

## 33. Real-time capabilities

MQTT and RabbitMQ are real-time ingestion transports, but no browser push mechanism is implemented. Alert handlers are in-memory callbacks, so they can be wired to a future publisher but currently only log. The natural current strategy is **polling** short-lived APIs for the prototype; introduce SSE for per-job/alert events once durable job/event records exist. Do not claim live browser progress today.

## 34. Search/filter/sort dimensions

| Entity | Existing/derived dimensions | Gaps |
|---|---|---|
| FHIR Observation | profile/kind, code, site (`subject`), dataset tag; client-side min/max value; effective time in result | date pagination/sorting semantics and server-side broad filtering not wrapped |
| Site | FHIR Location ID/name/position; city via local gazetteer | city is not a FHIR attribute in this implementation |
| Cohort | group ID/name; age range/gender/location characteristics | no API listing/filtering cohorts |
| Alert | severity, site, indicator, time only in-process | no persistence/search |
| Ingestion/report/audit/user | none | RECOMMENDED |

## 35. Drill-down information by entity

| Entity | Information currently obtainable | Class |
|---|---|---|
| Ingestion demo | raw, validated, alert, sample Observations/profiles, FHIR aggregate | EXISTING transient |
| FHIR Observation | ID/profile/status/code/value/components/site/time/cohort/device/performer/specimen | EXISTING from FHIR |
| Site | name/position; environmental + health summaries; cohort IDs; briefing co-location | DERIVED |
| Cohort | age range, sex, location reference | EXISTING from FHIR `Group` |
| Device/volunteer/agency | resource identity and relevant references | EXISTING FHIR resources, no wrapped endpoint |
| Alert | affected readings/risk, basis, caveat | EXISTING transient |
| Assistant response | answer, tool trace, grounding verdict | EXISTING transient |
| Report/audit/job/user | none | RECOMMENDED |

## 36. Audit/event model

Existing logs and responses disclose some operational facts but are not an audit trail: normalized event printout, FHIR upload summary, validation errors, alert log, and assistant response trace. They lack stable IDs, durable storage, actors, before/after state, resource linkage, correlation IDs, and querying.

Recommended append-only event schema:

```ts
type AuditEvent = {
  id: string; occurredAt: string; type: string; severity: "INFO"|"WARNING"|"ERROR";
  actor?: { id: string; type: "USER"|"SERVICE" }; resource: { type: string; id: string };
  correlationId?: string; before?: unknown; after?: unknown; message?: string; metadata?: Record<string, unknown>;
};
```

## 37. Notification candidates

| Candidate | Current source | Class |
|---|---|---|
| ingestion conversion/upload failure | pipeline result/log | EXISTING signal, no delivery |
| threshold or elevated health alert | alert object/log/callback | EXISTING signal, no durable delivery |
| invalid MQTT/RabbitMQ payload | worker log | EXISTING signal, no delivery |
| assistant grounding failure | response verdict | EXISTING signal, no delivery |
| report approval/download, retry exhausted, authorization violation | none | RECOMMENDED |

## 38. Frontend TypeScript models

These are consumer models; `Existing` fields map directly, while stage/job/report/auth structures are recommended adapters.

```ts
type SourceType = "IOT_TELEMETRY" | "CITIZEN_SURVEY" | "PUBLIC_HEALTH";
type PipelineOutcome = "UPLOADED" | "BUILT_NOT_SENT" | "UPLOAD_FAILED" | "CONVERSION_FAILED";
type StageStatus = "PENDING" | "RUNNING" | "COMPLETED" | "WARNING" | "FAILED";

interface ObservationSummary { id: string; indicator: string; site?: string; when?: string;
  value?: number; unit?: string; coded_value?: string;
  statistics?: Array<{stat: string; value?: number}>; cohort?: string; }
interface Alert { severity: "LOW"|"MODERATE"|"HIGH"; site_id: string; city: string; observed_at: string;
  exceedances: Array<{indicator:string; value:number; unit:string; threshold:string|number; exceedance_factor?:number; basis:string}>;
  elevated_risks: Array<{indicator:string; score:number; interpretation:"MODERATE"|"HIGH"}>; caveat:string; }
interface PipelineStage { id:string; name:string; status:StageStatus; startedAt?:string; completedAt?:string;
  input?:unknown; output?:unknown; counts?:Record<string,number>; warnings?:string[]; errors?:string[]; }
interface IngestionDetail { id:string; sourceType:SourceType; status:PipelineOutcome; raw?:unknown; normalized?:unknown;
  stages:PipelineStage[]; alert?:Alert; artifacts?: Array<{type:string; id:string}>; } // RECOMMENDED persistence
interface ExecutionStep { id:string; kind:"TOOL"|"FHIR_QUERY"|"SCREEN"|"MAP"|"UPLOAD";
  label:string; status:StageStatus; fhirUrls?:string[]; metadata?:Record<string,unknown>; }
interface ExecutionTrace { id:string; subjectId:string; model?:string; steps:ExecutionStep[];
  grounding?: {grounded:boolean; unsupported_figures:number[]; not_covered:string}; } // assistant fields EXISTING
interface GraphNode { id:string; type:string; label:string; status?:string; metadata:Record<string,unknown>; }
interface GraphEdge { id:string; source:string; target:string; type:string; metadata?:Record<string,unknown>; }
interface ReportFile { id:string; name:string; mimeType:string; sizeBytes:number; url?:string; } // RECOMMENDED
```

The adapter separates FHIR’s resource shape from dashboard lists, hides transport details, and gives proposed operational concepts a clear non-FHIR lifecycle without pretending they exist today.

## 39. Complete interconnected mock dataset

The following is a **RECOMMENDED front-end fixture**, deliberately linked to actual source types, FHIR IDs, threshold rules, profile vocabulary, and current demo values. `ingestion-*`, findings, reports, downloads, users, audit events, and notifications are proposed—not existing persisted records.

```json
{
  "currentUser": {"id":"user-analyst-01","displayName":"Maya Costa","role":"ANALYST","permissions":["dashboard.read","evidence.read","assistant.ask","report.create"],"scope":{"cities":["coimbra"],"sites":["site-c1-mondego","site-coimbra-t1"]}},
  "users": [
    {"id":"user-viewer-01","role":"VIEWER","permissions":["dashboard.read"],"scope":{"sites":["site-c1-mondego"]}},
    {"id":"user-operator-01","role":"DATA_OPERATOR","permissions":["ingestion.create","ingestion.retry","raw.read"],"scope":{"cities":["coimbra"]}},
    {"id":"user-reviewer-01","role":"HEALTH_REVIEWER","permissions":["dashboard.read","evidence.read","report.review"],"scope":{"sites":["site-c1-mondego","site-coimbra-t1"]}}
  ],
  "sites": [
    {"id":"site-c1-mondego","name":"Mondego river station C1","city":"coimbra","latitude":40.2111,"longitude":-8.4291},
    {"id":"site-c6-casa-do-sal","name":"Casa do Sal stream reach C6","city":"coimbra","latitude":40.2194,"longitude":-8.4377},
    {"id":"site-coimbra-t1","name":"Coimbra urban catchment T1","city":"coimbra","latitude":40.2033,"longitude":-8.4103}
  ],
  "ingestions": [
    {"id":"ingestion-001","scenario":"SUCCESS_WITH_EVIDENCE","sourceType":"IOT_TELEMETRY","siteId":"site-c1-mondego","status":"UPLOADED","eventAt":"2026-09-30T10:00:00Z","alertId":"alert-001","artifactIds":["Observation/nitrate-site-c1-mondego-1759226400-1","Observation/zinc_dissolved-site-c1-mondego-1759226400-2"]},
    {"id":"ingestion-002","scenario":"IN_PROGRESS","sourceType":"CITIZEN_SURVEY","siteId":"site-c6-casa-do-sal","status":"RUNNING","eventAt":"2026-10-02T09:15:00Z"},
    {"id":"ingestion-003","scenario":"WARNING","sourceType":"IOT_TELEMETRY","siteId":"site-c1-mondego","status":"UPLOADED_WITH_WARNING","eventAt":"2026-10-02T09:20:00Z","warnings":["Unknown unit 'ppm' retained as free text; no UCUM code assigned."]},
    {"id":"ingestion-004","scenario":"FAILURE","sourceType":"PUBLIC_HEALTH","siteId":"site-c1-mondego","status":"UPLOAD_FAILED","eventAt":"2026-10-02T09:25:00Z","error":"FHIR transaction unavailable"},
    {"id":"ingestion-005","scenario":"RETRY_SUCCESS","sourceType":"PUBLIC_HEALTH","siteId":"site-c1-mondego","status":"UPLOADED","eventAt":"2026-10-02T09:30:00Z","retryOf":"ingestion-004","attempt":2}
  ],
  "alerts": [{"id":"alert-001","ingestionId":"ingestion-001","severity":"HIGH","siteId":"site-c1-mondego","exceedanceEvidenceIds":["evidence-001","evidence-002"]}],
  "analysis": {"id":"analysis-001","siteId":"site-c1-mondego","sourceIngestionIds":["ingestion-001","ingestion-005"],"type":"SITE_CO_LOCATION","status":"COMPLETED","findingIds":["finding-001","finding-002"]},
  "findings": [
    {"id":"finding-001","type":"THRESHOLD_EXCEEDANCE","severity":"HIGH","indicator":"nitrate","value":14.2,"unit":"mg/L","threshold":11.3,"factor":1.26,"evidenceIds":["evidence-001","evidence-002"]},
    {"id":"finding-002","type":"CO_LOCATION","severity":"WARNING","siteId":"site-c1-mondego","statement":"Environmental exceedance and elevated health risk are co-located; association only, not causation.","evidenceIds":["evidence-001","evidence-003","evidence-004"]}
  ],
  "evidence": [
    {"id":"evidence-001","type":"FHIR_OBSERVATION","resourceRef":"Observation/nitrate-site-c1-mondego-1759226400-1","value":14.2,"unit":"mg/L","observedAt":"2026-09-30T10:00:00Z"},
    {"id":"evidence-002","type":"THRESHOLD_RULE","indicator":"nitrate","rule":"above 11.3 mg/L","basis":"EU Drinking Water Directive 50 mg/L as NO3 ~= 11.3 mg/L as NO3-N; screening value only"},
    {"id":"evidence-003","type":"FHIR_OBSERVATION","resourceRef":"Observation/overall_health_risk_score-site-c1-mondego-1759190400-r3","value":0.534,"interpretation":"HIGH","cohortRef":"Group/group-mondego-riverside-residents"},
    {"id":"evidence-004","type":"FHIR_GROUP","resourceRef":"Group/group-mondego-riverside-residents","ageRange":"18-74","gender":"all","locationRef":"Location/site-c1-mondego"}
  ],
  "report": {"id":"report-001","analysisId":"analysis-001","status":"GENERATED","version":1,"generatedAt":"2026-10-02T10:00:00Z","fileId":"report-file-001","ownerId":"user-analyst-01"},
  "reportFile": {"id":"report-file-001","reportId":"report-001","filename":"mondego-one-health-briefing-2026-10-02.pdf","format":"PDF","mimeType":"application/pdf","sizeBytes":248136,"downloadCount":1,"lastDownloadedAt":"2026-10-02T10:10:00Z"},
  "graph": {"nodes":[{"id":"Location/site-c1-mondego","type":"SITE"},{"id":"Observation/nitrate-site-c1-mondego-1759226400-1","type":"ENVIRONMENTAL_OBSERVATION"},{"id":"Group/group-mondego-riverside-residents","type":"COHORT"},{"id":"Observation/overall_health_risk_score-site-c1-mondego-1759190400-r3","type":"HEALTH_OBSERVATION"},{"id":"finding-002","type":"FINDING"}],"edges":[{"id":"edge-1","source":"Observation/nitrate-site-c1-mondego-1759226400-1","target":"Location/site-c1-mondego","type":"OBSERVED_AT"},{"id":"edge-2","source":"Observation/overall_health_risk_score-site-c1-mondego-1759190400-r3","target":"Location/site-c1-mondego","type":"OBSERVED_AT"},{"id":"edge-3","source":"Observation/overall_health_risk_score-site-c1-mondego-1759190400-r3","target":"Group/group-mondego-riverside-residents","type":"DESCRIBES"},{"id":"edge-4","source":"finding-002","target":"Observation/nitrate-site-c1-mondego-1759226400-1","type":"SUPPORTED_BY"},{"id":"edge-5","source":"finding-002","target":"Observation/overall_health_risk_score-site-c1-mondego-1759190400-r3","type":"SUPPORTED_BY"}]},
  "auditEvents": [{"id":"audit-001","type":"INGESTION_COMPLETED","occurredAt":"2026-09-30T10:00:04Z","resource":{"type":"INGESTION","id":"ingestion-001"},"actor":{"type":"SERVICE","id":"oah-ingestion"}},{"id":"audit-002","type":"REPORT_DOWNLOADED","occurredAt":"2026-10-02T10:10:00Z","resource":{"type":"REPORT_FILE","id":"report-file-001"},"actor":{"type":"USER","id":"user-viewer-01"}}]
}
```

## 40. Mock pipeline simulation

All timings below are demo-only; the current service exposes no real stage duration.

| Scenario | Replay transitions |
|---|---|
| Successful `ingestion-001` | 0s Received → 1s Validated → 2s Screened (alert) → 3s Mapped → 4s Bundled → 5s Uploaded |
| In-progress `ingestion-002` | 0s Received → 1s Validated → 2s Screened → hold at 35% Mapping; later complete or fail |
| Warning `ingestion-003` | same success path; Mapping completes with warning count 1 |
| Failure `ingestion-004` | Received → Validated → Screened → Mapped → Upload failed at 5s |
| Retry `ingestion-005` | prior failure shown; 0s retry requested → 1s Mapping → 3s Uploaded, `attempt=2` |
| Report | Requested → Generating (0–4s) → Generated (5s); download increments a mock counter |

Replay events should be `stage.started`, `stage.completed`, `stage.warning`, `stage.failed`, `ingestion.retry_requested`, `report.generated`, and `report.downloaded`, tied to the fixture IDs above.

## 41. Representative JSON payloads

Existing endpoint examples:

```json
{"question":"Where does nitrate exceed the screening value?"}
```

```json
{"status":"ACCEPTED","event_id":"<gateway-generated UUID>","source_type":"PUBLIC_HEALTH","fhir":"UPLOADED","resources":{"Group":1,"Location":1,"Observation":5,"Organization":1,"Specimen":1},"uploaded":9,"failed":0,"alert":{"severity":"HIGH","site_id":"site-c1-mondego"}}
```

```json
{"question":"...","answer":"...","trace":[{"tool":"get_site_profile","arguments":"{\"site_id\":\"site-c1-mondego\"}","fhir_urls":["https://.../Observation?..."]}],"grounding":{"grounded":true,"unsupported_figures":[],"not_covered":"Checks numeric literals only..."},"model":"gpt-4o"}
```

Recommended dashboard payloads are the `currentUser`, `ingestions`, `analysis`, `findings`, `evidence`, `report`, `reportFile`, `graph`, and `auditEvents` objects in section 39. The existing dashboard summary is derivable from `/api/overview`; its current shape is `{site_count, sites_with_exceedances, sites_with_elevated_risk, sites_with_co_location, briefings[]}`.

## 42. Existing capabilities

- Multi-channel ingestion from MQTT, RabbitMQ, and HTTP.
- Strict discriminated envelope validation and pilot-city/time constraints.
- Sensor topic/payload matching and partial invalid-measurement filtering.
- Deterministic threshold screening with stated prototype bases.
- OAH logical model to FHIR resource conversion and tagged, idempotent FHIR transaction upsert.
- FHIR site/environment/health/cohort data retrieval; source provenance resources.
- Derived cross-domain co-location briefing with explicit non-causality caveat.
- Assistant typed-tool trace and numeric grounding verdict.
- Four real demo samples and an existing live demo page.

## 43. Derived capabilities

- Site-level metrics, counts, threshold findings, and environmental/health co-location.
- FHIR-reference graph assembly and evidence navigation.
- Time series from Observation effective timestamps, subject to scalable paging/query APIs.
- Per-transaction upload success ratio and receipt latency only at execution time.
- Dashboard-facing summaries by safely aggregating FHIR searches server-side.

## 44. Missing capabilities/data

| Missing information | Why useful | Capture location / backend change | Complexity |
|---|---|---|---|
| durable ingestion/job record and stages | history, progress, filtering, retries | persist before/after every pipeline stage | Medium |
| stage timing/counts/artifact refs | pipeline visualization and operational metrics | instrumentation in `process()`/workers | Medium |
| source event retention + hash | raw payload/evidence/provenance | secure object store + metadata table | Medium |
| actor/identity/roles/scopes | safe role-aware dashboard | IdP middleware and authorization service | High |
| FHIR credentials/tenant enforcement | protect health data | protected gateway/service identity | High |
| audit/event store | explainability and compliance | append-only store from routes/workers/actions | Medium |
| notifications | attention signals | durable event publisher + delivery preferences | Medium |
| reports/files/download logging | requested report workflow | generator, object storage, metadata/API | High |
| graph/read model | relationship exploration at scale | project FHIR/events into graph or API read model | Medium |
| model/token/latency/prompt-version telemetry | safe AI observability | assistant instrumentation, redaction policy | Medium |
| pagination/date querying | trustworthy metrics and timelines | robust FHIR traversal/read API | Medium |

## 45. Recommended backend enhancements

1. Add a protected persistence/read-model service for `Ingestion`, `PipelineStage`, artifact references, and append-only audit events; emit stage events from all transports.
2. Put authentication, tenant/site data scope, role permissions, and service-to-FHIR credentials ahead of every dashboard endpoint.
3. Retain raw source payloads securely with retention/classification rules; keep FHIR references and hashes in evidence records.
4. Add server-side dashboard aggregation, FHIR pagination/date queries, and graph/evidence endpoints.
5. Add report generation/file metadata/download authorization only after role/audit infrastructure exists.
6. Instrument assistant and pipeline latency/errors; show observable tool/evidence trace, never private reasoning.

## 46. Features available for the first dashboard demo

Immediately: live replay of the four source samples; validation/screening/FHIR mapping/upload outcome; raw/validated/FHIR sample inspection; source threshold/caveat display; overview of currently tagged FHIR dataset; site/cohort/environment/health relationship view; derived co-location; assistant answer with typed-tool trace and grounding verdict.

With only frontend/server aggregation: FHIR-backed lists, filters, maps, time series, observation/cohort detail, direct-reference graph, and summary metrics—provided the demo dataset is small and queries are safely proxied.

Not honest to demonstrate as production-existing: user-specific UI, data restriction, durable runs/history/progress/retries, reports/downloads, audit history, push notifications, queued job monitoring, or durable graphs.

## 47. Open questions / uncertainties found in the repository

- The configured FHIR server is external and may enforce behavior, security, retention, paging, and referential constraints not represented in this repository.
- `docs/plan.md` describes roadmap aspirations (including a correlation dashboard and natural-language-to-FHIR translation) that do not precisely match the shipped implementation: the UI is static HTML/JS, and the assistant deliberately uses typed tools rather than allowing the model to compose FHIR URLs.
- `sample_iot_telemetry_mqtt.json` is transport payload shape, while HTTP/demo telemetry uses the complete envelope; this distinction should become explicit in an ingestion contract.
- Gateway normalization replaces supplied event ID/received time with fresh values, so original producer ID/time provenance is not retained in the normalized message.
- Current FHIR client returns only the first search page; global counts and time series can be incomplete at scale.
- Uploaded resources have deterministic IDs and transaction PUT semantics, but it remains an integration question whether the configured FHIR server permits client-assigned IDs and how conflicts/version history are managed.
- The demo gazetteer explicitly labels locations as approximate demo values; they must not be treated as authoritative locations.
- Alert callbacks are in-memory and no callback is registered by the application, so “real-time alerts” currently means logged/returned signals, not user notification delivery.
- No privacy, consent, retention, classification, data-quality governance, or regulatory acceptance model is implemented; this is especially material for public-health data.

## Verification

Source review covered routes, workers, validation, models, FHIR resources/mappers/bundling, threshold logic, assistant/tool/grounding flow, static UI, demo fixtures, documentation, and tests. The repository test suites passed with project source paths configured: 23 ingestion tests, 26 agent tests, and 7 model/FHIR tests.
