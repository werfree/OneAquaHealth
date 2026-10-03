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

const LIVE_SOURCE_TYPES = {
  iot: "IOT_TELEMETRY",
  survey: "CITIZEN_SURVEY",
  health: "PUBLIC_HEALTH",
  "health-mondego": "PUBLIC_HEALTH",
};

function collectionCount(value, fallback) {
  if (Array.isArray(value)) return value.length;
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function normalizeTraceInput(step) {
  const input = step.input ?? step.arguments;
  const queries = step.fhir_urls || (step.fhir_url ? [step.fhir_url] : []);
  if (!queries.length) return input;
  return { ...(input === undefined ? {} : { arguments: input }), queries };
}

function normalizeLiveAssistant(data) {
  const grounding = data.grounding || {};
  return {
    question: data.question,
    answer: data.answer,
    trace: (data.trace || []).map(step => ({
      kind: step.kind || (step.fhir_urls || step.fhir_url ? "FHIR_QUERY" : "TOOL"),
      label: step.label || step.tool || "Assistant operation",
      status: step.status || "completed",
      input: normalizeTraceInput(step),
      evidenceRefs: step.evidenceRefs || [],
      grounded: step.grounded,
    })),
    grounding: {
      grounded: Boolean(grounding.grounded),
      unsupportedFigures: grounding.unsupportedFigures || grounding.unsupported_figures || [],
      notCovered: grounding.notCovered || grounding.not_covered || "Numeric grounding does not verify semantic correctness.",
    },
    model: data.model,
  };
}

function livePersistenceOutcome(upload) {
  const outcome = upload?.fhir || "CONVERSION_FAILED";
  if (!["UPLOADED", "BUILT_NOT_SENT", "UPLOAD_FAILED", "CONVERSION_FAILED"].includes(outcome)) return "CONVERSION_FAILED";
  if (outcome === "UPLOADED" && Number(upload?.failed || 0) !== 0) return "UPLOAD_FAILED";
  return outcome;
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
    findingCount: exceedances.length + risks.length + (item.co_location ? 1 : 0),
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
  session: () => request("/api/live/session"),
  summary: async () => {
    const data = await getLiveOverview();
    const sites = (data.briefings || []).map(normalizeLiveSite);
    return {
      metrics: {
        sitesInScope: collectionCount(data.site_count, sites.length),
        loadedObservations: sites.reduce((total, site) => total + site.observationCount, 0),
        screeningFindings: sites.reduce((total, site) => total + (site._source.exceedances || []).length, 0),
        coLocatedSites: collectionCount(data.sites_with_co_location, sites.filter(site => site._source.co_location).length),
      },
      sites,
      scopeLabel: "Current tagged FHIR response",
      countNotice: "Counts cover the current tagged FHIR response; no aggregate time window is supplied, and the existing client may return only the first result page.",
    };
  },
  site: async (_role, siteId) => {
    const data = liveOverview || await getLiveOverview();
    const source = (data.briefings || []).find(item => (item.site_id || item.id) === siteId);
    if (!source) throw new ApiError("Site is not present in the live response", 404);
    const site = normalizeLiveSite(source);
    const observations = [
      ...(source.exceedances || []).map((item, index) => ({
        id: item.observation_id || `live-env-${index}`, resourceRef: item.observation_id ? `Observation/${item.observation_id}` : undefined,
        siteId, kind: "environmental", indicator: item.indicator || "Environmental measure", value: item.value, unit: item.unit,
        interpretation: "Prototype screening finding", screeningReference: item.basis,
      })),
      ...(source.risks || source.elevated_risks || []).map((item, index) => ({
        id: item.observation_id || `live-health-${index}`, resourceRef: item.observation_id ? `Observation/${item.observation_id}` : undefined,
        siteId, kind: "health-summary", indicator: item.indicator || "Health measure", value: item.score, unit: "score",
        interpretation: item.interpretation ? `Agency classification: ${item.interpretation}` : "Agency-reported health context",
      })),
    ];
    const findings = [
      ...(source.exceedances || []).map((item, index) => ({ id: `live-exceedance-${index}`, siteId, type: "threshold", severity: "high", title: `${item.indicator || "Measure"} screening flag`, statement: `${item.value} ${item.unit || ""} · prototype threshold ${item.threshold ?? "not returned"}. ${item.basis || ""}`.trim() })),
      ...(source.elevated_risks || []).map((item, index) => ({ id: `live-health-risk-${index}`, siteId, type: "health", severity: "moderate", title: `${item.indicator || "Health measure"} context`, statement: `Agency classification ${item.interpretation || "not returned"}${item.score === undefined ? "" : ` at score ${item.score}`}.` })),
      ...(source.co_location ? [{ id: "live-colocation", siteId, type: "co-location", severity: "attention", title: "Cross-domain co-location", statement: "Environmental and elevated health records share this Location.", caveat: "Association only, not causation. The live overview does not return enough source timing to establish contemporaneity." }] : []),
    ];
    return { site, observations, findings, meta: {
      coordinateNotice: "Coordinates are approximate demo values.",
      screeningNotice: "Screening values are prototype triage rules, not universal safety limits. Live context includes returned exceedance and risk summaries; total record counts may be larger.",
    } };
  },
  evidence: async () => { throw new ApiError("The live backend has no dashboard evidence endpoint", 501); },
  graph: async () => { throw new ApiError("The live backend has no graph endpoint", 501); },
  ask: async (_role, _siteId, question) => normalizeLiveAssistant(await request("/api/live/ask", { method: "POST", body: { question } })),
  runs: async () => {
    const info = await request("/api/live/info");
    return { runs: [], samples: (info.samples || []).map(item => ({ ...item, label: item.channel, description: item.detail, sourceType: LIVE_SOURCE_TYPES[item.key] || item.key })), stateNotice: "Request-scoped results exist only in this browser session; the live gateway has no durable run history." };
  },
  run: async () => { throw new ApiError("The live backend does not persist run details", 501); },
  startRun: async (_role, sampleKey) => {
    const data = await request(`/api/live/ingest-demo/${encodeURIComponent(sampleKey)}`, { method: "POST" });
    const fhirOutcome = livePersistenceOutcome(data.upload);
    const validated = Boolean(data.validated);
    const persistenceConfirmed = fhirOutcome === "UPLOADED" && Number(data.upload?.failed || 0) === 0;
    const executionStatus = !validated || ["UPLOAD_FAILED", "CONVERSION_FAILED"].includes(fhirOutcome) ? "failed" : "completed";
    return {
      id: `live-${Date.now()}`, sampleKey, sampleLabel: data.sample?.channel || sampleKey, sourceType: data.validated?.source_type || LIVE_SOURCE_TYPES[sampleKey],
      siteId: data.validated?.site_id, executionStatus, fhirOutcome,
      startedAt: new Date().toISOString(), progress: 100,
      stages: [
        { id: "received", name: "Received", status: "completed", summary: "Live request payload; no trust decision has been made.", input: data.raw },
        { id: "validated", name: "Validated", status: validated ? "completed" : "failed", summary: "Live Pydantic validation result", output: data.validated, errors: data.error ? [data.error] : [] },
        { id: "screened", name: "Screened", status: !validated ? "pending" : data.alert ? "warning" : "completed", summary: !validated ? "Stage did not run." : "Prototype triage rules ran; findings are not pipeline failures.", output: validated ? data.alert : undefined },
        { id: "mapped", name: "Mapped", status: !validated ? "pending" : data.observations ? "completed" : "failed", summary: !validated ? "Stage did not run." : "Live OAH-profiled FHIR sample", output: validated ? { profiles: data.profiles, observations: data.observations } : undefined },
        { id: "bundled", name: "Bundled", status: !validated || !data.upload ? "pending" : "completed", summary: !validated ? "Stage did not run." : "Bundle was assembled within the request; the full bundle is not returned.", output: data.upload ? { note: "Full bundle is not returned by the existing route." } : undefined },
        { id: "upsert", name: "Upsert outcome", status: !validated || !data.upload ? "pending" : persistenceConfirmed ? "completed" : fhirOutcome === "BUILT_NOT_SENT" ? "warning" : "failed", summary: persistenceConfirmed ? "FHIR persistence confirmed: UPLOADED with zero failed entries." : "FHIR persistence was not confirmed.", output: data.upload, errors: ["UPLOAD_FAILED", "CONVERSION_FAILED"].includes(fhirOutcome) ? ["FHIR persistence failed."] : [] },
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
