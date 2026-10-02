const MODE = new URLSearchParams(window.location.search).get("mode") === "live" ? "live" : "mock";

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

let liveOverview;

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
    city: item.city || "Pilot dataset",
    latitude: item.latitude,
    longitude: item.longitude,
    status: exceedances.length ? "attention" : risks.length ? "health-watch" : "observed",
    observationCount: Number(item.environmental_reading_count || 0) + Number(item.health_measure_count || 0),
    findingCount: exceedances.length + risks.length,
    lastObservedAt: item.observed_at || null,
    _source: item,
  };
}

async function getLiveOverview() {
  liveOverview = await request("/api/live/overview");
  return liveOverview;
}

const liveAdapter = {
  mode: "live",
  config: () => request("/api/config"),
  session: async role => liveSession(role),
  summary: async () => {
    const data = await getLiveOverview();
    const sites = (data.briefings || []).map(normalizeLiveSite);
    return {
      metrics: {
        sitesInScope: data.site_count ?? sites.length,
        loadedObservations: sites.reduce((total, site) => total + site.observationCount, 0),
        screeningFindings: data.sites_with_exceedances ?? sites.filter(site => site._source.exceedances?.length).length,
        coLocatedSites: data.sites_with_co_location ?? sites.filter(site => site._source.co_location).length,
      },
      sites,
      scopeLabel: "Current tagged FHIR response",
      countNotice: "The existing FHIR client may return only the first result page.",
    };
  },
  site: async (_role, siteId) => {
    const data = liveOverview || await getLiveOverview();
    const source = (data.briefings || []).find(item => (item.site_id || item.id) === siteId);
    if (!source) throw new ApiError("Site is not present in the live response", 404);
    const site = normalizeLiveSite(source);
    const observations = [
      ...(source.environmental_readings || []).map((item, index) => ({
        id: item.id || `live-env-${index}`, siteId, kind: "environmental", indicator: item.indicator || item.code || "Environmental measure",
        value: item.value, unit: item.unit, effectiveAt: item.when || item.effectiveDateTime, interpretation: item.interpretation || "Live FHIR record",
      })),
      ...(source.health_measures || []).map((item, index) => ({
        id: item.id || `live-health-${index}`, siteId, kind: "health", indicator: item.indicator || item.code || "Health measure",
        value: item.score ?? item.value, unit: item.unit || "score", effectiveAt: item.when || item.effectiveDateTime,
        evaluationPeriod: item.evaluation_period, interpretation: item.interpretation || "Agency classification",
      })),
    ];
    const findings = [
      ...(source.exceedances || []).map((item, index) => ({ id: `live-exceedance-${index}`, siteId, type: "threshold", severity: "high", title: `${item.indicator || "Measure"} screening flag`, statement: `${item.value} ${item.unit || ""} · ${item.threshold || item.basis || "prototype rule"}` })),
      ...(source.co_location ? [{ id: "live-colocation", siteId, type: "co-location", severity: "attention", title: "Cross-domain co-location", statement: "Environmental and elevated health records share this Location.", caveat: "Association only, not causation." }] : []),
    ];
    return { site, observations, findings, meta: { coordinateNotice: "Coordinates are approximate demo values.", screeningNotice: "Prototype screening rules only." } };
  },
  evidence: async () => { throw new ApiError("The live backend has no dashboard evidence endpoint", 501); },
  graph: async () => { throw new ApiError("The live backend has no graph endpoint", 501); },
  ask: (_role, _siteId, question) => request("/api/live/ask", { method: "POST", body: { question } }),
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
