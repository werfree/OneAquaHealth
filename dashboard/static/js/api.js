// An explicit ?mode= wins; otherwise the server's DASHBOARD_DEFAULT_MODE.
const REQUESTED_MODE = new URLSearchParams(window.location.search).get("mode") || (window.location.pathname === "/studio" ? "live" : document.documentElement.dataset.defaultMode);
const MODE = REQUESTED_MODE === "live" ? "live" : "mock";

// Shared demo role policy. Personas demonstrate what each role is *intended* to
// see, so the policy must travel with the browser session in both mock and live
// mode — otherwise switching to live silently strips a role's intended views.
// Mock mode mirrors this policy in `dashboard/data/fixtures.json` and enforces
// it on the server; live mode is anonymous at the gateway and cannot enforce
// scope, so these flags express intended demo capability only.
export const ROLES = {
  viewer: {
    id: "user-viewer-01",
    label: "Viewer",
    description: "Published summaries and reports",
    permissions: ["dashboard.read", "report.download.published"],
    siteIds: ["site-c1-mondego"],
  },
  analyst: {
    id: "user-analyst-01",
    label: "Analyst",
    description: "Findings, evidence and briefings",
    permissions: ["dashboard.read", "evidence.read", "graph.read", "assistant.ask", "report.create", "report.download"],
    siteIds: ["site-c1-mondego", "site-coimbra-t1"],
  },
  operator: {
    id: "user-operator-01",
    label: "Data operator",
    description: "Assigned source runs and payloads",
    permissions: ["dashboard.read", "ingestion.read", "ingestion.create", "ingestion.retry", "raw.read"],
    siteIds: ["site-c1-mondego", "site-c6-casa-do-sal", "site-coimbra-t1"],
  },
};

// Live mode capability is the role's intended permission AND the gateway's current
// support. Read-only evidence is implemented by the dashboard for live mode, so
// Analyst keeps it; graph and proposed briefing features have no live route and
// therefore stay unavailable in live mode even for roles that may read them in mock.
const LIVE_CAPABILITY_SUPPORT = {
  canReadEvidence: true,
  canLoadGraph: false,
  canGenerateReports: false,
  canRetryRuns: false,
  canTrackRuns: false,
};

function capabilitySnapshot(persona, { live }) {
  const permissions = new Set(persona.permissions);
  const caps = {
    canQueryAssistant: permissions.has("assistant.ask"),
    canTrackRuns: permissions.has("ingestion.read"),
    canStartRuns: permissions.has("ingestion.create"),
    canRetryRuns: permissions.has("ingestion.retry"),
    canGenerateReports: permissions.has("report.create"),
    canLoadGraph: permissions.has("graph.read"),
    canReadEvidence: permissions.has("evidence.read"),
    hasServerAuthorization: !live,
  };
  if (live) {
    for (const [key, supported] of Object.entries(LIVE_CAPABILITY_SUPPORT)) {
      caps[key] = caps[key] && supported;
    }
  }
  return caps;
}

export class ApiError extends Error {
  constructor(message, status = 0, details = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.details = details;
  }
}

function errorMessage(details, status) {
  const detail = details?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map(item => `${(item.loc || []).join(".")}: ${item.msg || "Invalid value"}`).join("; ");
  return detail?.status || `Request failed (${status})`;
}

async function request(path, { method = "GET", body, rawBody, contentType = "application/json", role = "analyst", responseType = "json" } = {}) {
  const response = await fetch(path, {
    method,
    headers: {
      "Content-Type": contentType,
      "X-Demo-Role": role,
    },
    body: rawBody !== undefined ? rawBody : body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    let details;
    try { details = await response.json(); } catch { details = { detail: response.statusText }; }
    throw new ApiError(errorMessage(details, response.status), response.status, details);
  }
  if (responseType === "blob") return response.blob();
  return response.json();
}

const mockAdapter = {
  mode: "mock",
  config: () => request("/api/config"),
  session: role => request("/api/mock/session", { role }),
  summary: role => request("/api/mock/summary", { role }),
  site: (role, siteId) => request(`/api/mock/sites/${encodeURIComponent(siteId)}`, { role }),
  evidence: (role, evidenceId) => request(`/api/mock/evidence/${encodeURIComponent(evidenceId)}`, { role }),
  graph: (role, siteId) => request(`/api/mock/graph?siteId=${encodeURIComponent(siteId)}`, { role }),
  ask: (role, siteId, question) => request("/api/mock/assistant", { method: "POST", role, body: { siteId, question } }),
  runs: role => request("/api/mock/runs", { role }),
  run: (role, runId) => request(`/api/mock/runs/${encodeURIComponent(runId)}`, { role }),
  startRun: (role, sampleKey) => request("/api/mock/runs", { method: "POST", role, body: { sampleKey } }),
  retryRun: (role, runId) => request(`/api/mock/runs/${encodeURIComponent(runId)}/retry`, { method: "POST", role }),
  reset: role => request("/api/mock/reset", { method: "POST", role }),
  submitFile: async () => { throw new ApiError("File ingestion requires live mode", 501); },
  csvTemplate: async () => { throw new ApiError("CSV templates require live mode", 501); },
  reports: role => request("/api/mock/reports", { role }),
  report: (role, reportId) => request(`/api/mock/reports/${encodeURIComponent(reportId)}`, { role }),
  createReport: (role, siteId) => request("/api/mock/reports", { method: "POST", role, body: { siteId } }),
  downloadUrl: (reportId, format) => `/api/mock/reports/${encodeURIComponent(reportId)}/download/${format}`,
};

function liveSession(role) {
  const key = ROLES[role] ? role : "analyst";
  const profile = ROLES[key];
  const persona = { ...profile, key };
  return {
    persona,
    capabilities: capabilitySnapshot(persona, { live: true }),
    mode: "live",
    notices: [
      "Demo personas simulate a proposed policy; the live gateway itself is anonymous, so these controls show intended capability rather than enforcing access.",
      "Evidence references are read from already-uploaded FHIR data through the gateway's station endpoint.",
    ],
  };
}

function normalizeLiveSite(item) {
  const siteId = item.site_id || item.id;
  const exceedances = item.exceedances || [];
  const risks = item.elevated_risks || [];
  return {
    id: siteId,
    name: item.name || siteId,
    shortName: item.name || siteId,
    city: item.city ? item.city[0].toUpperCase() + item.city.slice(1) : "City not recorded",
    latitude: item.latitude,
    longitude: item.longitude,
    status: exceedances.length ? "attention" : risks.length ? "health-watch" : "observed",
    observationCount: Number(item.environmental_reading_count || 0) + Number(item.health_measure_count || 0),
    findingCount: exceedances.length + risks.length + (item.co_location ? 1 : 0),
    lastObservedAt: item.observed_at || null,
    _source: item,
  };
}

// Agency classifications are carried in unit text, e.g. "{score} (HIGH)".
function splitScoreUnit(unit) {
  const match = /^(.*?)\s*\((LOW|MODERATE|HIGH)\)\s*$/.exec(unit || "");
  return match ? { unit: match[1] === "{score}" ? "score" : match[1], level: match[2] } : { unit: unit === "{score}" ? "score" : unit, level: null };
}

function liveObservations(source, siteId) {
  const flagged = new Map((source.exceedances || []).map(item => [item.observation_id, item]));
  const environmental = (source.environmental_observations || []).map((item, index) => {
    const flag = flagged.get(item.id);
    return {
      id: item.id || `live-env-${index}`, resourceRef: item.id ? `Observation/${item.id}` : null, siteId, kind: "environmental",
      indicator: item.indicator || "Environmental measure", value: item.value, unit: item.unit, codedValue: item.coded_value,
      effectiveAt: item.when,
      interpretation: flag ? `Above prototype screening value ${flag.threshold}` : item.coded_value ? "Coded survey answer" : "No screening flag raised",
      screeningReference: flag?.basis,
    };
  });
  const health = (source.health_observations || []).map((item, index) => {
    const { unit, level } = splitScoreUnit(item.unit);
    return {
      id: item.id || `live-health-${index}`, resourceRef: item.id ? `Observation/${item.id}` : null, siteId, kind: "health",
      indicator: item.indicator || "Health measure", value: item.value, unit, effectiveAt: item.when,
      interpretation: level ? `Agency classification: ${level}` : "Agency classification not recorded",
      screeningReference: item.cohort ? `Cohort Group/${item.cohort}` : null,
    };
  });
  return [...environmental, ...health].sort((a, b) => String(b.effectiveAt || "").localeCompare(String(a.effectiveAt || "")));
}

// Stable, deterministic evidence reference ids so the Findings tab can link to a
// resolvable Evidence drawer in live mode. One env record (the flagged Observation)
// plus one rule record (the screening basis) per exceedance; one observation record
// per elevated risk and per cohort. Ids encode the station so the resolver can
// re-fetch that station's live payload without holding global state.
function liveEvidenceId(kind, index, siteId) {
  return `live-evidence-${kind}-${index}-${siteId}`;
}

function liveFindings(source, siteId) {
  const caveat = "Prototype screening reference, not a regulatory limit.";
  return [
    ...(source.exceedances || []).map((item, index) => ({
      id: `live-exceedance-${index}`, siteId, type: "threshold", severity: (item.exceedance_factor || 1) >= 2 ? "high" : "attention",
      title: `${item.indicator || "Measure"} above prototype screening value`,
      statement: `${item.value} ${item.unit || ""} against ${item.threshold}${item.exceedance_factor ? ` (${item.exceedance_factor}×)` : ""}. Basis: ${item.basis || "prototype rule"}.`,
      caveat,
      evidenceIds: [liveEvidenceId("exceedance", index, siteId), liveEvidenceId("rule", index, siteId)],
    })),
    ...(source.elevated_risks || []).map((item, index) => ({
      id: `live-risk-${index}`, siteId, type: "health-watch", severity: item.interpretation === "HIGH" ? "high" : "moderate",
      title: `${item.indicator || "Health measure"} classified ${item.interpretation}`,
      statement: `Score ${item.score}${item.cohort ? ` for cohort ${item.cohort}` : ""}, as classified by the reporting agency.`,
      evidenceIds: [liveEvidenceId("risk", index, siteId), ...(item.cohort ? [liveEvidenceId("cohort", index, siteId)] : [])],
    })),
    ...(source.co_location ? [{ id: "live-colocation", siteId, type: "co-location", severity: "attention", title: "Cross-domain co-location", statement: "An environmental screening flag and an elevated health classification share this Location.", caveat: source.caveat || "Association only, not causation.", evidenceIds: [], }] : []),
  ];
}

// The gateway has no evidence route, so live evidence is *derived* from the same
// already-uploaded station payload the views render. A tiny cache keyed by station
// lets the resolver avoid a re-fetch when the station is already in view; it falls
// back to a live GET when opened cold (e.g. a deep link). Evidence is never invented:
// every field below comes from the gateway's exceedance / risk / cohort records.
const liveStationCache = new Map();

async function liveStationSource(siteId) {
  if (!liveStationCache.has(siteId)) {
    liveStationCache.set(siteId, request(`/api/live/sites/${encodeURIComponent(siteId)}`));
  }
  return liveStationCache.get(siteId);
}

function liveEvidenceRecord(kind, index, source, siteId) {
  const fhirUrl = url => (url ? { resourceRef: url } : {});
  if (kind === "exceedance") {
    const item = (source.exceedances || [])[index];
    if (!item) return null;
    return {
      id: liveEvidenceId(kind, index, siteId), siteId, type: "FHIR_OBSERVATION",
      label: `${item.indicator || "Measure"} Observation`,
      ...fhirUrl(item.fhir_url),
      observationId: item.observation_id,
      display: `${item.value} ${item.unit || ""} · prototype screening value ${item.threshold}${item.exceedance_factor ? ` (${item.exceedance_factor}×)` : ""}`,
      basis: item.basis || null,
    };
  }
  if (kind === "rule") {
    const item = (source.exceedances || [])[index];
    if (!item) return null;
    return {
      id: liveEvidenceId(kind, index, siteId), siteId, type: "THRESHOLD_RULE",
      label: `${item.indicator || "Measure"} screening rule`,
      resourceRef: `threshold:${item.indicator || "measure"}`,
      display: `Above ${item.threshold} ${item.unit || ""}`.trim(),
      basis: item.basis || "Prototype screening rule; not a universal safety limit.",
    };
  }
  if (kind === "risk") {
    const item = (source.elevated_risks || [])[index];
    if (!item) return null;
    return {
      id: liveEvidenceId(kind, index, siteId), siteId, type: "FHIR_OBSERVATION",
      label: `${item.indicator || "Health measure"} Observation`,
      ...fhirUrl(item.fhir_url),
      observationId: item.observation_id,
      display: `Score ${item.score} · ${item.interpretation} agency classification`,
      basis: "Agency-reported classification exposed by the gateway, not computed by this dashboard.",
    };
  }
  if (kind === "cohort") {
    const cohortId = (source.elevated_risks || [])[index]?.cohort;
    const cohort = (source.cohorts || []).find(item => item.group_id === cohortId);
    if (!cohort) return null;
    const characteristics = cohort.characteristics || {};
    const described = [characteristics.sex, characteristics.ageRange].filter(Boolean).join(" · ");
    return {
      id: liveEvidenceId(kind, index, siteId), siteId, type: "FHIR_GROUP",
      label: cohort.name || cohort.group_id,
      ...fhirUrl(cohort.fhir_url),
      display: described ? `${described} · ${cohort.group_id}` : cohort.group_id,
      basis: "Population group attached to the source health Observation.",
    };
  }
  return null;
}

async function liveEvidence(_role, evidenceId) {
  const match = /^live-evidence-(exceedance|rule|risk|cohort)-(\d+)-(.+)$/.exec(evidenceId || "");
  if (!match) throw new ApiError("Unknown live evidence reference", 404);
  const [, kind, index, siteId] = match;
  const source = await liveStationSource(siteId);
  const record = liveEvidenceRecord(kind, Number(index), source, siteId);
  if (!record) throw new ApiError("Evidence is outside this station's current live records", 404);
  return record;
}

const liveAdapter = {
  mode: "live",
  config: () => request("/api/config"),
  session: async role => liveSession(role),
  summary: async (_role, refresh = false) => {
    const data = await request(`/api/live/overview${refresh ? "?refresh=true" : ""}`);
    const sites = (data.briefings || []).map(normalizeLiveSite);
    // The gateway reports lists of site ids, not counts.
    const countOf = value => Array.isArray(value) ? value.length : Number(value || 0);
    return {
      metrics: {
        sitesInScope: data.site_count ?? sites.length,
        loadedObservations: sites.reduce((total, site) => total + site.observationCount, 0),
        screeningFindings: sites.reduce((total, site) => total + (site._source.exceedances?.length || 0), 0),
        coLocatedSites: countOf(data.sites_with_co_location),
      },
      sites,
      scopeLabel: `Dataset tag ${data.dataset_tag || "oah-demo"} on ${data.fhir_server || "the FHIR server"}`,
      countNotice: data.generated_at ? `Computed from FHIR at ${data.generated_at}; cached briefly by the gateway.` : "Computed from the tagged FHIR dataset.",
    };
  },
  site: async (_role, siteId) => {
    const source = await liveStationSource(siteId);
    return {
      site: normalizeLiveSite(source),
      observations: liveObservations(source, siteId),
      findings: liveFindings(source, siteId),
      meta: { coordinateNotice: "Coordinates come from the FHIR Location or the demo gazetteer and may be approximate.", screeningNotice: "Prototype screening rules only." },
    };
  },
  evidence: liveEvidence,
  graph: async () => { throw new ApiError("The live backend has no graph endpoint", 501); },
  ask: (_role, siteId, question) => request("/api/live/ask", { method: "POST", body: { question, siteId } }),
  runs: async () => {
    const info = await request("/api/live/info");
    return { runs: [], samples: (info.samples || []).map(item => ({ ...item, label: item.channel, description: item.detail, sourceType: item.key })), stateNotice: "The live gateway exposes request-scoped results, not durable run history." };
  },
  run: async () => { throw new ApiError("The live backend does not persist run details", 501); },
  startRun: async (_role, sampleKey) => {
    const data = await request(`/api/live/ingest-demo/${encodeURIComponent(sampleKey)}`, { method: "POST" });
    return {
      id: `live-${Date.now()}`, sampleKey, sampleLabel: data.sample?.channel || sampleKey, sourceType: data.validated?.source_type || sampleKey,
      siteId: data.validated?.site_id, executionStatus: data.ok ? "completed" : "failed", fhirOutcome: data.upload?.fhir || "CONVERSION_FAILED",
      startedAt: new Date().toISOString(), progress: 100,
      stages: [
        { id: "received", name: "Received", status: "completed", summary: "Live request payload", input: data.raw },
        { id: "validated", name: "Validated", status: data.validated ? "completed" : "failed", summary: "Live Pydantic validation result", output: data.validated, errors: data.error ? [data.error] : [] },
        { id: "screened", name: "Screened", status: data.alert ? "warning" : "completed", summary: "Live threshold screening result", output: data.alert },
        { id: "mapped", name: "Mapped", status: data.observations ? "completed" : "pending", summary: "Live OAH-profiled FHIR sample", output: { profiles: data.profiles, observations: data.observations } },
        { id: "bundled", name: "Bundled", status: data.upload ? "completed" : "pending", summary: "Bundle is assembled within the current pipeline", output: { note: "Full bundle is not returned by the existing route." } },
        { id: "upsert", name: "Upsert outcome", status: data.upload?.fhir === "UPLOADED" && data.upload?.failed === 0 ? "completed" : "failed", summary: "Live FHIR transaction response", output: data.upload },
      ],
    };
  },
  submitFile: async (role, upload) => {
    try {
      return await request(upload.kind === "csv" ? "/api/live/ingest/public-health/csv" : "/api/live/ingest", {
        method: "POST", role, rawBody: upload.text, contentType: upload.kind === "csv" ? "text/csv" : "application/json",
      });
    } finally { liveStationCache.clear(); }
  },
  csvTemplate: () => request("/api/live/ingest/public-health/csv/template", { responseType: "blob" }),
  retryRun: async () => { throw new ApiError("The live backend has no retry endpoint", 501); },
  reset: async () => { throw new ApiError("The live backend has no reset endpoint", 501); },
  reports: async () => { throw new ApiError("Reports are a proposed capability and are unavailable in live mode", 501); },
  report: async () => { throw new ApiError("Reports are unavailable in live mode", 501); },
  createReport: async () => { throw new ApiError("Report generation is unavailable in live mode", 501); },
};

export const api = MODE === "live" ? liveAdapter : mockAdapter;
export const apiMode = MODE;
