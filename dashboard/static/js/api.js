// An explicit ?mode= wins; otherwise the server's DASHBOARD_DEFAULT_MODE.
const REQUESTED_MODE = new URLSearchParams(window.location.search).get("mode") || document.documentElement.dataset.defaultMode;
const MODE = REQUESTED_MODE === "live" ? "live" : "mock";

export class ApiError extends Error {
  constructor(message, status = 0, details = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.details = details;
  }
}

async function request(path, { method = "GET", body, role = "analyst", responseType = "json" } = {}) {
  const response = await fetch(path, {
    method,
    headers: {
      "Content-Type": "application/json",
      "X-Demo-Role": role,
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    let details;
    try { details = await response.json(); } catch { details = { detail: response.statusText }; }
    throw new ApiError(details.detail || `Request failed (${response.status})`, response.status, details);
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
  reports: role => request("/api/mock/reports", { role }),
  report: (role, reportId) => request(`/api/mock/reports/${encodeURIComponent(reportId)}`, { role }),
  createReport: (role, siteId) => request("/api/mock/reports", { method: "POST", role, body: { siteId } }),
  downloadUrl: (reportId, format) => `/api/mock/reports/${encodeURIComponent(reportId)}/download/${format}`,
};

function liveSession(role) {
  return {
    persona: {
      key: role,
      id: "anonymous-live-caller",
      label: role === "operator" ? "Data operator" : role[0].toUpperCase() + role.slice(1),
      description: "UI-only demo persona; live backend is anonymous",
      permissions: ["dashboard.read"],
      siteIds: [],
    },
    capabilities: {
      canQueryAssistant: true,
      canTrackRuns: false,
      canStartRuns: role === "operator",
      canRetryRuns: false,
      canGenerateReports: false,
      canLoadGraph: false,
      canReadEvidence: false,
      hasServerAuthorization: false,
    },
    mode: "live",
    notices: ["The existing live gateway is anonymous; persona controls do not secure it."],
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

function liveFindings(source, siteId) {
  const caveat = "Prototype screening reference, not a regulatory limit.";
  return [
    ...(source.exceedances || []).map((item, index) => ({
      id: `live-exceedance-${index}`, siteId, type: "threshold", severity: (item.exceedance_factor || 1) >= 2 ? "high" : "attention",
      title: `${item.indicator || "Measure"} above prototype screening value`,
      statement: `${item.value} ${item.unit || ""} against ${item.threshold}${item.exceedance_factor ? ` (${item.exceedance_factor}×)` : ""}. Basis: ${item.basis || "prototype rule"}.`,
      caveat,
    })),
    ...(source.elevated_risks || []).map((item, index) => ({
      id: `live-risk-${index}`, siteId, type: "health-watch", severity: item.interpretation === "HIGH" ? "high" : "moderate",
      title: `${item.indicator || "Health measure"} classified ${item.interpretation}`,
      statement: `Score ${item.score}${item.cohort ? ` for cohort ${item.cohort}` : ""}, as classified by the reporting agency.`,
    })),
    ...(source.co_location ? [{ id: "live-colocation", siteId, type: "co-location", severity: "attention", title: "Cross-domain co-location", statement: "An environmental screening flag and an elevated health classification share this Location.", caveat: source.caveat || "Association only, not causation." }] : []),
  ];
}

const liveAdapter = {
  mode: "live",
  config: () => request("/api/config"),
  session: async role => liveSession(role),
  summary: async () => {
    const data = await request("/api/live/overview");
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
    const source = await request(`/api/live/sites/${encodeURIComponent(siteId)}`);
    return {
      site: normalizeLiveSite(source),
      observations: liveObservations(source, siteId),
      findings: liveFindings(source, siteId),
      meta: { coordinateNotice: "Coordinates come from the FHIR Location or the demo gazetteer and may be approximate.", screeningNotice: "Prototype screening rules only." },
    };
  },
  evidence: async () => { throw new ApiError("The live backend has no dashboard evidence endpoint", 501); },
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
  retryRun: async () => { throw new ApiError("The live backend has no retry endpoint", 501); },
  reset: async () => { throw new ApiError("The live backend has no reset endpoint", 501); },
  reports: async () => { throw new ApiError("Reports are a proposed capability and are unavailable in live mode", 501); },
  report: async () => { throw new ApiError("Reports are unavailable in live mode", 501); },
  createReport: async () => { throw new ApiError("Report generation is unavailable in live mode", 501); },
};

export const api = MODE === "live" ? liveAdapter : mockAdapter;
export const apiMode = MODE;
