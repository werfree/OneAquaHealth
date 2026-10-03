# Dashboard UI integration guide

**Audience:** frontend, backend, QA, and product teams  
**Last reviewed:** 3 October 2026  
**Implementation:** `dashboard/`  
**Purpose:** shared reference for replacing prototype adapters with production APIs without changing the dashboard's user-facing meaning

## 1. Scope and source of truth

This guide describes the dashboard that currently ships in `dashboard/static/` and the data it expects from `dashboard/server.py`. It combines the capability boundaries documented in:

- `docs/dashboard-data-capability-specification.md`
- `docs/dashboard-theme-runtime-impact-report.md`
- `dashboard/API-MAPPING.md`

Use the following labels consistently in requirements, tickets, API documentation, and the UI:

| Label | Meaning |
|---|---|
| **Existing** | Implemented by the current ingestion, FHIR, or assistant services. |
| **Derived** | Can be calculated from current FHIR data, subject to paging and data-quality limits. |
| **Mock-backed** | Works in the dashboard prototype but requires a new production service, policy, or durable store. |
| **Unavailable** | Must not be presented as operational until the backend capability exists. |

The most important integration rule is that an HTTP ingestion response of `ACCEPTED` is not proof of persistence. The UI may show a successful persistence outcome only when `fhir === "UPLOADED"` and `failed === 0`.

## 2. Runtime modes

The dashboard has two adapters with a shared UI-facing shape.

| Mode | URL | Data source | Intended use |
|---|---|---|---|
| Mock | `/` | Stateful dashboard fixture endpoints under `/api/mock/*` | Complete product demonstration, including proposed roles, runs, graph, evidence, and reports. |
| Live | `/?mode=live` | Same-origin allow-listed proxy under `/api/live/*` | Demonstrate only capabilities available from the existing OneAquaHealth gateway. |

The browser must call only the dashboard origin. Service URLs, FHIR credentials, and model-provider credentials remain server-side.

```text
Browser view
   │
   ├── mock adapter ──> /api/mock/* ──> in-process fixture/runtime state
   │
   └── live adapter ──> /api/live/* ──> allow-listed proxy ──> existing gateway/FHIR/assistant
```

Production integration should preserve the adapter boundary in `dashboard/static/js/api.js`: views consume dashboard models and must not parse raw FHIR Bundles or call multiple infrastructure services directly.

## 3. Information architecture

### 3.1 Global shell

| Region | UI | Behavior and integration requirement |
|---|---|---|
| Primary navigation | Overview, Ingestion, Reports | Client-side route state; no URL path routing is currently used. |
| Current station | Station selector in the top bar | Scope comes from the summary response. Changing it reloads site data and clears graph and assistant state. |
| Connection mode | Mock dataset or Live adapter indicator | Derived from the `mode=live` query parameter, not from API health. |
| Demo persona | Viewer, Analyst, Data operator | Mock policy demonstration only. A production UI must derive identity and capabilities from authenticated server claims. |
| Appearance | Five-theme selector | Independent of route, persona, station, runs, and reports. Stored locally as `oah-theme`. |
| About drawer | Prototype boundaries and mode switch | Must continue to disclose which features are mock-backed. |
| Detail drawer | Evidence and graph-node details | Modal side panel; opened from evidence rows and graph nodes. |
| Toast stack | Action success/failure feedback | Used for run, report, download, copy, and theme actions. |

### 3.2 Routes

| Route key | Screen title | Primary job | Capability status |
|---|---|---|---|
| `overview` | Station evidence overview | Compare sites and inspect environmental/public-health context. | Existing and derived; evidence/graph policy is mock-backed. |
| `ingestion` | Ingestion workbench | Start a sample, inspect stages and artifacts, retry a failure. | Request-scoped live sample is existing; history, progress, and retry are mock-backed. |
| `reports` | Site One Health briefings | Generate, preview, and download a fixed site snapshot. | Mock-backed; no live report service exists. |

## 4. Screen specifications

### 4.1 Overview

#### Summary strip

| Card | Field | Meaning | Interaction |
|---|---|---|---|
| Sites in scope | `metrics.sitesInScope` | Sites visible to the current scope. | Scrolls to station comparison. |
| Loaded observations | `metrics.loadedObservations` | Environmental, health, and survey records loaded into the read model. | Opens the Context tab. |
| Screening findings | `metrics.screeningFindings` | Prototype threshold findings, not all alerts or global incidents. | Opens the Evidence tab. |
| Co-located sites | `metrics.coLocatedSites` | Sites with environmental exceedance and elevated health context at the same `Location`. | Opens the Evidence tab. |

Counts must include a scope/time/paging qualifier. The current live FHIR client reads only its first result page, so live counts must not be labelled as global totals.

#### Station comparison

Each row shows station name, city, latest source time, status, observation count, and finding count. Selecting a row sets the global station and loads its workspace.

Supported status values are presentation labels, not clinical classifications:

| Status | UI meaning |
|---|---|
| `observed` | Records are present with no derived attention state. |
| `attention` | At least one environmental screening finding is present. |
| `health-watch` | Elevated health context is present without an environmental threshold finding. |

#### Station workspace: Context

The context table requires observations normalized to one of `environmental`, `survey`, `health`, or `health-summary`. It shows indicator, value/coded value, unit, effective time, optional evaluation period, interpretation, and optional screening reference.

Findings appear below the table. A co-location finding must always retain the caveat **association only, not causation**, and should disclose when source periods are not contemporaneous.

The footer must preserve the screening-rule and approximate-coordinate notices supplied by the backend.

#### Station workspace: Evidence

Evidence is shown only when `capabilities.canReadEvidence` is true. Findings supply `evidenceIds`; selecting an ID resolves the full evidence record and opens the detail drawer.

Backend requirements:

- Enforce evidence permission and site scope on the server.
- Return `404` for an out-of-scope record so its existence is not disclosed.
- Classify or redact sensitive source fields before returning them.
- Preserve the source resource reference, display value, provenance, and rule basis where applicable.

#### Station workspace: Relationships

The graph contains scoped nodes and direct edges assembled from FHIR references plus explicitly marked derived relationships. The UI supports all-record, Observation, and finding-path filters; selecting a node opens its connected-record details.

Every edge endpoint must be present in `nodes`. Derived nodes or edges must carry `derived: true`. A production response should also provide completeness/paging metadata; the current prototype uses fixed `x`/`y` coordinates for layout.

#### Site assistant

The assistant sends a question for the selected site and shows the answer alongside an observable execution trace. The trace may contain tool names, FHIR queries, evidence references, statuses, and grounding results. It must never expose private chain-of-thought.

The response must distinguish numeric grounding from semantic correctness. The existing grounding check verifies numeric literals only, so the limitation text is required in the UI.

### 4.2 Ingestion workbench

The mock workbench is visible to the Data operator persona. Live mode may execute supplied samples but cannot provide durable history.

#### User flow

1. Choose one of the allowed source samples.
2. Start ingestion.
3. Select a run from history.
4. Inspect one stage and its `input`, `output`, `counts`, `warnings`, or `errors` artifact.
5. Copy the displayed JSON if needed.
6. Retry only a terminal failed run.

#### Canonical stage order

| Order | ID | Label | Meaning |
|---|---|---|---|
| 1 | `received` | Received | The payload arrived; no trust decision has been made. |
| 2 | `validated` | Validated | Envelope/source/site/time validation completed. |
| 3 | `screened` | Screened | Deterministic prototype threshold rules ran. A finding is not a pipeline failure. |
| 4 | `mapped` | Mapped | Domain data became OAH-profiled FHIR R4 resources. |
| 5 | `bundled` | Bundled | Resources were de-duplicated and prepared as transaction PUTs. |
| 6 | `upsert` | Upsert outcome | FHIR transaction outcome was confirmed. |

Stage status values are `pending`, `running`, `completed`, `warning`, and `failed`. Run execution status and FHIR outcome are separate fields. For example, a completed pipeline may contain a mapping warning; `UPLOAD_FAILED` is not a completed persistence outcome.

The prototype polls run listings every 900 ms while any run is `running`. A production API should use explicit `Retry-After`/poll guidance or SSE after durable job events exist. Starting a duplicate active sample returns `409`; retrying a non-failed run also returns `409`.

### 4.3 Reports

Reports are explicitly labelled **Proposed capability · mock-backed**. Live mode must show them as unavailable until report metadata, snapshot storage, authorization, file storage, and download auditing exist.

#### User flow

1. The report list is scoped by persona and site access.
2. An Analyst requests a report for the globally selected station.
3. The UI displays `requested` and `generating` progress states.
4. A `generated` report shows an immutable snapshot of observations, findings, evidence, time scope, and limitations.
5. Authorized users download HTML or JSON; HTML may be opened for browser Print / Save as PDF.

The prototype polls reports every 800 ms while a report is `requested` or `generating`. Viewer access is limited to `visibility === "published"`; Data operator has no report access. Production services must enforce both rules server-side.

The UI currently recognizes `requested`, `generating`, `generated`, and `failed`. A later review workflow may add `review_required`, `approved`, `rejected`, and `archived`, but these states are not implemented.

## 5. Persona and capability contract

The persona selector demonstrates future authorization behavior; it is not authentication.

| Capability | Viewer | Analyst | Data operator |
|---|:---:|:---:|:---:|
| Read scoped dashboard | Yes | Yes | Yes |
| Read evidence detail | No | Yes | No |
| Load relationship graph | No | Yes | No |
| Ask assistant | No | Yes | No |
| Inspect/start/retry runs | No | No | Yes |
| Generate reports | No | Yes | No |
| Download reports | Published only | In-scope reports | No |

Current mock scoping:

- Viewer: Mondego C1 only.
- Analyst: Mondego C1 and Urban catchment T1.
- Data operator: all three demo sites.

Production rules:

- Replace `X-Demo-Role` with authenticated server identity and authorization.
- Return a server-derived session/capability response; never trust a role selected by the browser.
- Apply site/tenant scope on every read and mutation, including downloads.
- Hiding a control is a usability behavior, not an authorization boundary.

## 6. API-to-view mapping

### 6.1 Shared configuration

| UI consumer | Method and path | Required result |
|---|---|---|
| Theme bootstrap | `GET /api/config` | `{ defaultTheme, themes[] }`; public presentation data only. |

### 6.2 Mock/proposed dashboard contracts

| UI area | Method and path | Permission/capability | Notes |
|---|---|---|---|
| Session | `GET /api/mock/session` | Any demo persona | Persona, scope, capability flags, notices. |
| Summary | `GET /api/mock/summary` | `dashboard.read` | Metrics and scoped station rows. |
| Station workspace | `GET /api/mock/sites/{siteId}` | `dashboard.read` + site scope | Site, observations, findings, notices. |
| Evidence drawer | `GET /api/mock/evidence/{evidenceId}` | `evidence.read` + site scope | One evidence record. |
| Relationships | `GET /api/mock/graph?siteId=` | `graph.read` + site scope | Nodes, edges, completeness. |
| Assistant | `POST /api/mock/assistant` | `assistant.ask` + site scope | `{ siteId, question }` to answer/trace/grounding. |
| Run list | `GET /api/mock/runs` | `ingestion.read` | Runs, allowed samples, state notice. |
| Start run | `POST /api/mock/runs` | `ingestion.create` | Body `{ sampleKey }`; returns `202`. |
| Retry run | `POST /api/mock/runs/{runId}/retry` | `ingestion.retry` | Failed runs only; returns new run with `retryOf`. |
| Report list | `GET /api/mock/reports` | Persona report scope | Reports and recognized lifecycle. |
| Generate report | `POST /api/mock/reports` | `report.create` | Body `{ siteId }`; returns `202`. |
| Report detail | `GET /api/mock/reports/{reportId}` | Site and visibility scope | Includes snapshot/files when generated. |
| Download | `GET /api/mock/reports/{reportId}/download/{html|json}` | Download permission | Returns bytes and `Content-Disposition`. |

### 6.3 Existing live routes

| Dashboard proxy | Upstream route | UI use |
|---|---|---|
| `GET /api/live/info` | `GET /api/info` | Supplied sample catalogue for request-scoped ingestion. |
| `GET /api/live/overview` | `GET /api/overview` | Normalize FHIR-derived site briefing into summary and station shapes. |
| `POST /api/live/ingest-demo/{key}` | Same path | Run a supplied sample and construct a request-scoped six-stage result. |
| `POST /api/live/ask` | `POST /api/ask` | Ask the existing optional assistant. |

The live service has no session, durable run list/detail, retry, graph, evidence, or report endpoints. The UI must show an explicit unavailable state rather than silently substituting mock data.

## 7. Canonical frontend models

These camelCase models are the dashboard boundary. Backend implementations may use internal FHIR or snake_case models, but the adapter must normalize them before rendering.

```ts
type SiteStatus = "observed" | "attention" | "health-watch";
type ObservationKind = "environmental" | "survey" | "health" | "health-summary";
type StageStatus = "pending" | "running" | "completed" | "warning" | "failed";
type FhirOutcome = "UPLOADED" | "BUILT_NOT_SENT" | "UPLOAD_FAILED" | "CONVERSION_FAILED";

interface SessionResponse {
  persona: {
    key: string;
    id: string;
    label: string;
    description: string;
    permissions: string[];
    siteIds: string[];
  };
  capabilities: {
    canQueryAssistant: boolean;
    canTrackRuns: boolean;
    canStartRuns: boolean;
    canRetryRuns: boolean;
    canGenerateReports: boolean;
    canLoadGraph: boolean;
    canReadEvidence: boolean;
    hasServerAuthorization: boolean;
  };
  mode: "mock" | "live";
  notices: string[];
}

interface SummaryResponse {
  metrics: {
    sitesInScope: number;
    loadedObservations: number;
    screeningFindings: number;
    coLocatedSites: number;
  };
  sites: SiteSummary[];
  scopeLabel: string;
  countNotice: string;
}

interface SiteSummary {
  id: string;
  name: string;
  shortName?: string;
  city: string;
  latitude?: number;
  longitude?: number;
  status: SiteStatus;
  observationCount?: number; // Required in summary rows; omitted by current detail response.
  findingCount?: number;     // Required in summary rows; omitted by current detail response.
  lastObservedAt?: string;
}

interface ObservationView {
  id: string;
  resourceRef?: string;
  siteId: string;
  kind: ObservationKind;
  indicator: string;
  value?: number;
  codedValue?: string;
  unit?: string;
  effectiveAt?: string;
  evaluationPeriod?: string;
  interpretation: string;
  screeningReference?: string;
  source?: string;
  profile?: string;
}

interface FindingView {
  id: string;
  siteId: string;
  type: "threshold" | "co-location" | "health" | string;
  severity: "high" | "attention" | "moderate" | string;
  title: string;
  statement: string;
  caveat?: string;
  evidenceIds?: string[];
}

interface SiteResponse {
  site: SiteSummary;
  observations: ObservationView[];
  findings: FindingView[];
  meta: { screeningNotice: string; coordinateNotice: string };
}

interface PipelineStage {
  id: "received" | "validated" | "screened" | "mapped" | "bundled" | "upsert";
  name: string;
  status: StageStatus;
  summary: string;
  input?: unknown;
  output?: unknown;
  counts?: Record<string, number>;
  warnings?: string[];
  errors?: string[];
}

interface IngestionRun {
  id: string;
  sampleKey: string;
  sampleLabel: string;
  siteId: string;
  sourceType: "IOT_TELEMETRY" | "CITIZEN_SURVEY" | "PUBLIC_HEALTH";
  executionStatus: "running" | "completed" | "failed";
  fhirOutcome: FhirOutcome | null;
  startedAt: string;
  completedAt?: string;
  attempt: number;
  retryOf?: string;
  progress: number;
  stages: PipelineStage[];
}

interface GraphResponse {
  siteId: string;
  nodes: Array<{ id: string; siteId: string; type: string; label: string; x?: number; y?: number }>;
  edges: Array<{ id: string; source: string; target: string; type: string; derived?: boolean }>;
  complete: boolean;
  source: string;
}

interface EvidenceView {
  id: string;
  siteId: string;
  type: "FHIR_OBSERVATION" | "FHIR_GROUP" | "THRESHOLD_RULE" | string;
  label: string;
  resourceRef: string;
  display: string;
  basis?: string;
  observationId?: string;
}

interface AssistantResponse {
  question: string;
  answer: string;
  trace: Array<{
    kind: "TOOL" | "FHIR_QUERY" | "GROUNDING" | string;
    label: string;
    status: string;
    input?: unknown;
    evidenceRefs?: string[];
    grounded?: boolean;
  }>;
  grounding: {
    grounded: boolean;
    unsupportedFigures?: number[];
    unsupported_figures?: number[]; // Existing live API spelling.
    notCovered?: string;
    not_covered?: string;           // Existing live API spelling.
  };
  model: string;
}

interface ReportView {
  id: string;
  siteId: string;
  title: string;
  status: "requested" | "generating" | "generated" | "failed";
  visibility: "draft" | "published";
  ownerId: string;
  requestedAt: string;
  generatedAt?: string | null;
  files?: Array<{ format: "html" | "json"; mimeType: string; sizeBytes: number }>;
  snapshot?: {
    id: string;
    title: string;
    site: { id: string; name: string; city: string };
    timeScope: { latestEnvironmentalSample: string; healthEvaluationPeriod: string };
    generatedAt: string;
    observations: ObservationView[];
    findings: FindingView[];
    evidence: EvidenceView[];
    limitations: string[];
  };
}
```

The duplicate camelCase/snake_case grounding fields document the current adapter compatibility behavior. A production versioned contract should select one convention and normalize legacy responses in the adapter instead of spreading both forms through views.

## 8. UI state and refresh behavior

The client stores route, role, theme, selected site/tab/run/stage/sample/report, loaded resources, loading, and error state in one in-memory store.

| Event | State reset/reload |
|---|---|
| Persona change | Clear selected site/run/report and all scoped data, then reload session and summary. |
| Station change | Clear site, graph, and assistant result; load the new site; load graph only if its tab is active and permitted. |
| Route change | Stop the prior poll; lazy-load runs or reports when first opened. |
| Run start/retry | Select the returned run, reset selected stage to `received`, and poll while running. |
| Report request | Select the returned report and poll while requested/generating. |
| Theme change | Update semantic tokens and persist only the theme ID. Domain state must remain unchanged. |

Avoid stale-response races in a production frontend: attach request IDs or cancellation signals when persona or station changes, and discard responses that no longer match the active scope.

## 9. Loading, empty, error, and permission states

Every integration must support these states without relying on fixture data:

| State | Required behavior |
|---|---|
| Initial loading | Show a labelled loading indicator; do not render zero as a placeholder count. |
| Partial loading | Keep the shell and selected context visible while the local panel loads. |
| Empty collection | Explain what is absent and which action, if any, can create it. |
| `400`/`422` | Show the validation message near the initiated action. |
| `401` | Re-authenticate or show a session-expired state in production. |
| `403` | Show a capability-specific restricted state; do not retry automatically. |
| `404` | Treat scoped records as unavailable without revealing their existence. |
| `409` | Explain the state conflict, such as duplicate active run or invalid retry. |
| `501`/`502`/`503` | Show the feature as unavailable; never fall back to mock data in live mode. |
| Network failure | Preserve the current selection and offer a controlled retry. |

Errors from one optional panel, such as graph or assistant, must not erase already loaded station context.

## 10. Theme contract

Supported theme IDs are `oneaquahealth`, `aqua`, `aqua-dark`, `white`, and `dark`.

Precedence is:

1. Valid browser preference in `localStorage["oah-theme"]`.
2. Valid server `DASHBOARD_DEFAULT_THEME` exposed as `defaultTheme`.
3. Safe fallback `aqua`.

The initial HTML contains the validated default and token values to avoid a theme flash before JavaScript starts. Every theme must provide the same complete semantic-token set. Theme configuration is public presentation data only; `/api/config` must not expose environment values or secrets.

## 11. Responsive and accessibility behavior

| Breakpoint/behavior | Requirement |
|---|---|
| Above 1100 px | Two-column overview, ingestion, reports, and assistant layouts. |
| 1100 px and below | Primary workspaces stack into one column. |
| 780 px and below | Sidebar becomes a fixed bottom navigation; theme control remains available; pipeline stages scroll horizontally. |
| 480 px and below | Top bar wraps, metric notes hide, observation context column hides, forms and detail grids stack. |

Accessibility behavior already present and expected to remain:

- Skip link to main content.
- Native buttons/selects and keyboard activation for table-like selectable rows.
- `aria-current` for navigation and `aria-selected` for tabs.
- Textual relationship list in addition to the visual graph.
- Drawer dialog labelling and Escape-to-close behavior.
- Polite live regions for route content and toasts.
- Visible focus rings and reduced-motion support.
- Horizontal scrolling around tables instead of page overflow.

Production hardening should add focus trapping/restoration for the drawer, announce async completion more specifically, and test the complete keyboard order with real data lengths.

## 12. Backend integration priorities

| Priority | Backend deliverable | UI unlocked |
|---|---|---|
| P0 | Authenticated `/api/me` or session endpoint with permissions and site/tenant scope | Replace demo persona and `X-Demo-Role`. |
| P0 | Protected dashboard summary/site read model with paging and time-scope metadata | Reliable Overview counts and station context. |
| P0 | Service identity/credentials for FHIR behind the gateway | Prevent direct anonymous FHIR access. |
| P1 | Durable ingestion run, stage, artifact, timing, retry, and audit records | Real Ingestion history, progress, and retry. |
| P1 | Scoped evidence endpoint with redaction/classification | Real evidence drawer and finding traceability. |
| P1 | Graph/read endpoint with completeness metadata | Real Relationships tab. |
| P1 | Durable report snapshot, lifecycle, files, authorization, and download audit | Real Reports screen. |
| P2 | SSE or another event stream over durable run/report events | Replace short-interval polling. |
| P2 | Notifications and append-only audit query API | Operational attention and compliance views. |

## 13. Team ownership and handoff

### Backend team

- Publish versioned OpenAPI schemas matching the dashboard-facing models.
- Enforce identity, permission, tenant/site scope, and file access on every endpoint.
- Return scope, time range, paging, and completeness metadata with aggregate data.
- Keep ingestion execution status separate from FHIR persistence outcome.
- Persist only the operational artifacts approved by privacy/retention policy.
- Emit stable IDs and correlation IDs for runs, stages, reports, evidence, and audit events.

### UI team

- Keep all transport normalization inside the service adapter.
- Gate controls from server-provided capabilities while still handling server denials.
- Preserve the caveats for screening rules, approximate coordinates, co-location, and temporal mismatch.
- Never synthesize unavailable live data from fixtures.
- Render explicit loading, empty, restricted, failed, and unavailable states.
- Preserve semantic theme tokens and test all five themes at desktop and phone widths.

### Joint acceptance criteria

- Mock and live/production adapters satisfy the same documented view models.
- Switching persona/scope cannot leave prior-scope data visible.
- A run is shown as persisted only for `UPLOADED` with zero failures.
- Out-of-scope resource requests do not disclose record existence.
- Counts disclose their scope, time window, and pagination/completeness limitations.
- Assistant output includes observable trace and grounding limitations without hidden reasoning.
- Reports are immutable snapshots and downloads are authorized and auditable.
- Theme changes do not trigger or mutate domain requests.
- Core flows work by keyboard and at 390 × 844 without horizontal page overflow.

## 14. Relevant implementation files

| Concern | File |
|---|---|
| Page shell | `dashboard/static/index.html` |
| Route rendering and interactions | `dashboard/static/js/app.js` |
| Mock/live adapters | `dashboard/static/js/api.js` |
| Client state | `dashboard/static/js/state.js` |
| Shared rendering helpers | `dashboard/static/js/components.js` |
| Responsive and semantic-token styles | `dashboard/static/styles.css` |
| Mock API and live proxy | `dashboard/server.py` |
| Mock domain fixtures | `dashboard/data/fixtures.json` |
| Theme catalogue | `dashboard/data/themes.json` |
| Current endpoint summary | `dashboard/API-MAPPING.md` |
