# Dashboard integration implementation prompt

Use the following prompt when assigning the OneAquaHealth dashboard integration to an implementation agent or engineering team.

---

You are integrating the OneAquaHealth dashboard UI with its backend capabilities.

Before making changes, read these three documents completely and treat them as the authoritative integration context:

1. `docs/dashboard-theme-runtime-impact-report.md`
2. `docs/dashboard-data-capability-specification.md`
3. `docs/dashboard-ui-integration-guide.md`

Also inspect the current implementation before planning or editing:

- `dashboard/static/index.html`
- `dashboard/static/js/app.js`
- `dashboard/static/js/api.js`
- `dashboard/static/js/state.js`
- `dashboard/static/js/components.js`
- `dashboard/static/styles.css`
- `dashboard/server.py`
- `dashboard/data/fixtures.json`
- `dashboard/data/themes.json`
- `dashboard/API-MAPPING.md`

## Objective

Integrate the dashboard UI with the available OneAquaHealth backend features while preserving the existing dashboard-facing models, interaction behavior, accessibility, responsive layout, and five-theme system.

Replace mock-backed behavior only when a real backend capability and enforceable server contract exist. Features without production support must remain clearly identified as mock-backed or unavailable. Never silently substitute fixture data in live mode.

## Required approach

1. Audit the requested integration scope against the three source documents and current code.
2. Classify every affected feature as:
   - **Existing** — implemented by the current gateway, FHIR, ingestion, or assistant services.
   - **Derived** — safely calculable from current data with disclosed paging/time limitations.
   - **Mock-backed** — functional in the prototype but missing production APIs, persistence, identity, or policy.
   - **Unavailable** — not safe or truthful to expose as operational.
3. Identify contract gaps before editing. Do not invent backend behavior and present it as existing.
4. Keep transport and FHIR normalization inside the service adapter. UI views must consume dashboard-facing models rather than raw FHIR Bundles or infrastructure-specific payloads.
5. Make the smallest coherent implementation change that satisfies the requested scope.
6. Verify success, failure, empty, restricted, and unavailable states—not only the happy path.

## Non-negotiable integration rules

- An ingestion response with `status: "ACCEPTED"` is not proof of persistence.
- Show persistence success only when `fhir === "UPLOADED"` and `failed === 0`.
- Keep ingestion execution status separate from FHIR persistence outcome.
- Preserve the canonical stage order:
  `received → validated → screened → mapped → bundled → upsert`.
- Screening findings and mapping warnings are not pipeline failures.
- Preserve the statements that screening values are prototype triage rules and not universal safety limits.
- Preserve approximate-coordinate notices.
- Every co-location finding must retain **association only, not causation**.
- Disclose when environmental and health source periods are not contemporaneous.
- Do not expose chain-of-thought. Assistant traces may show tools, queries, evidence references, statuses, and grounding outcomes only.
- Do not expose service URLs, FHIR credentials, OpenAI credentials, or arbitrary environment values to the browser.
- Do not treat browser-hidden controls as authorization. Enforce permission and site/tenant scope on the server.
- Return scoped resources without leaking the existence of out-of-scope records.
- Never let a persona or station change leave data from the prior scope visible.

## UI areas to preserve

### Global shell

- Overview, Ingestion, and Reports navigation.
- Current-station selector.
- Connection-mode indicator.
- Server-derived persona/capability behavior.
- Appearance selector with `oneaquahealth`, `aqua`, `aqua-dark`, `white`, and `dark`.
- About and detail drawers.
- Action/error toasts.

### Overview

- Scoped metrics with explicit scope, time, and paging/completeness notices.
- Station comparison and selection.
- Context, Evidence, and Relationships tabs.
- Evidence-linked findings.
- Scoped assistant answers with observable trace and grounding limitations.

### Ingestion

- Source-sample selection.
- Run list and run detail where durable history exists.
- Stage status and artifact inspection.
- Separate warnings and failures.
- Retry only for terminal failed runs.
- Request-scoped live execution must not be described as durable history.

### Reports

- Keep the screen labelled as proposed/mock-backed until a production report service exists.
- Require durable immutable snapshots, lifecycle state, file storage, authorization, and download auditing before enabling production report actions.
- Viewer access must be limited to published reports; operators have no report access under the current proposed policy.

## API and model requirements

Preserve the dashboard boundary documented in `docs/dashboard-ui-integration-guide.md`, including:

- session/persona and capability flags;
- summary metrics and scoped site summaries;
- normalized site observations and findings;
- evidence records;
- graph nodes, edges, derived markers, and completeness metadata;
- assistant answer, trace, and grounding data;
- ingestion run, stage, progress, attempt, retry, and FHIR outcome fields;
- report lifecycle, snapshot, file, visibility, and limitation fields;
- public theme configuration.

If an upstream endpoint uses a different shape or naming convention, normalize it in `dashboard/static/js/api.js` or the server-side dashboard adapter. Do not spread compatibility branches across rendering functions.

If a contract must change:

1. Document the reason.
2. Version or explicitly migrate the contract.
3. Update frontend and backend together.
4. Add representative success and error examples.
5. Update the integration documentation in the same change.

## Authentication and authorization

The current `X-Demo-Role` behavior is a prototype only. For production integration:

- derive identity and permissions from authenticated server context;
- provide a protected session/current-user contract;
- enforce tenant/site scope on all reads, mutations, assistant calls, graph/evidence requests, reports, and downloads;
- use service credentials behind the gateway for FHIR access;
- reject unauthorized direct requests even when the UI hides the action.

If real authentication is outside the requested scope, retain and visibly label the demo policy. Do not imply it is secure production authorization.

## State, polling, and errors

- Preserve loaded parent context when an optional panel fails.
- Support initial loading, local loading, empty, restricted, validation-error, conflict, unavailable, and network-failure states.
- Handle `400/422`, `401`, `403`, `404`, `409`, and `501/502/503` intentionally.
- Cancel or discard stale requests after persona, site, or route changes.
- Use server-provided polling guidance where available.
- Do not add real-time progress claims until durable events exist. Prefer SSE only after job/report events are persisted.

## Theme and responsive requirements

- Keep theme state independent from domain state.
- Preserve the precedence: valid saved preference, valid server default, then `aqua` fallback.
- Store only the non-sensitive theme ID in browser storage.
- Apply the validated initial theme before application bootstrap to prevent a flash.
- Require a complete semantic-token map for every theme.
- Preserve the current responsive behaviors at 1100 px, 780 px, and 480 px.
- Verify at 390 × 844 with no horizontal page overflow.

## Accessibility requirements

- Preserve the skip link, native interactive elements, visible focus, keyboard row activation, tab states, textual graph alternative, live-region feedback, and reduced-motion behavior.
- Keep drawers correctly labelled and closable with Escape.
- Add focus trapping and focus restoration if drawer code is changed.
- Ensure asynchronous completion and errors are announced meaningfully.
- Do not communicate status by color alone.

## Expected deliverables

1. A short implementation plan mapping each change to **Existing**, **Derived**, **Mock-backed**, or **Unavailable** capability.
2. The frontend/backend implementation for the requested integration scope.
3. Updated or new API schemas and representative payloads where contracts change.
4. Automated tests for authorization/scope, adapters, success/failure states, and any state transitions introduced.
5. UI verification at desktop and mobile widths across relevant personas and modes.
6. Documentation updates describing:
   - implemented endpoints and fields;
   - remaining mock-backed features;
   - operational configuration;
   - known paging, privacy, evidence, and lifecycle limitations.
7. A final handoff listing changed files, verification results, assumptions, and unresolved backend dependencies.

## Acceptance criteria

- Mock and live/production adapters return the documented dashboard-facing models.
- No live screen silently uses fixture data.
- Role and site changes clear prior-scope data before loading the new scope.
- Server authorization matches every capability exposed by the UI.
- Out-of-scope resources are not disclosed.
- Counts include scope/time/paging or completeness context.
- Pipeline persistence status follows the FHIR outcome rule.
- Graph edges reference returned nodes and derived relationships are labelled.
- Assistant responses retain evidence/grounding limitations without exposing hidden reasoning.
- Report actions remain disabled/unavailable unless their production lifecycle and security dependencies exist.
- Theme changes do not trigger or mutate domain requests.
- All five themes remain legible.
- Core flows work with keyboard navigation and at 390 × 844.
- Relevant automated tests pass and `git diff --check` is clean.

## Final response format

Report the result using these headings:

1. **Implemented**
2. **API/contracts changed**
3. **Verification**
4. **Still mock-backed or unavailable**
5. **Assumptions and follow-up dependencies**

Do not claim completion for any feature that still depends on missing identity, persistence, authorization, evidence retention, graph, report, audit, or file-storage services.

---

