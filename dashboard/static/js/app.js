import { api, apiMode, ApiError } from "./api.js";
import { state, setState, changeRole } from "./state.js";
import {
  copyButton, downloadBlob, emptyState, errorState, escapeHtml, formatDate,
  humanBytes, jsonBlock, statusPill, toast, valueDisplay,
} from "./components.js";

const routeContent = document.querySelector("#route-content");
const siteSelector = document.querySelector("#site-selector");
const personaSelector = document.querySelector("#persona-selector");
const modeIndicator = document.querySelector("#mode-indicator");
const themeSelector = document.querySelector("#theme-selector");
const browserThemeColor = document.querySelector("#browser-theme-color");
const embeddedThemeConfig = JSON.parse(document.querySelector("#theme-config").textContent);
let pollTimer = null;
let scopeRequestVersion = 0;
let siteRequestVersion = 0;
let graphRequestVersion = 0;
let routeRequestVersion = 0;
let runsRequestVersion = 0;
let reportsRequestVersion = 0;
let assistantRequestVersion = 0;

function clearPoll() {
  if (pollTimer) window.clearTimeout(pollTimer);
  pollTimer = null;
}

function schedulePoll(callback, delay = 900) {
  clearPoll();
  pollTimer = window.setTimeout(callback, delay);
}

function applyTheme(themeId, { persist = false } = {}) {
  const config = state.themeConfig;
  const theme = config?.themes.find(item => item.id === themeId);
  if (!theme) return;
  Object.entries(theme.tokens).forEach(([token, value]) => {
    document.documentElement.style.setProperty(`--${token}`, value);
  });
  state.theme = theme.id;
  document.documentElement.dataset.theme = theme.id;
  document.documentElement.style.colorScheme = theme.colorScheme;
  browserThemeColor?.setAttribute("content", theme.themeColor);
  themeSelector.value = theme.id;
  if (persist) localStorage.setItem("oah-theme", theme.id);
}

function syncChrome() {
  if (apiMode === "live") {
    personaSelector.innerHTML = `<option value="anonymous">Anonymous live caller</option>`;
    personaSelector.value = "anonymous";
    personaSelector.disabled = true;
  } else {
    personaSelector.value = state.role;
    personaSelector.disabled = false;
  }
  if (state.themeConfig) {
    themeSelector.innerHTML = state.themeConfig.themes.map(theme => `<option value="${escapeHtml(theme.id)}">${escapeHtml(theme.label)}${theme.id === state.themeConfig.defaultTheme ? " · Default" : ""}</option>`).join("");
    themeSelector.value = state.theme;
  }
  const modeLabel = apiMode === "mock"
    ? "Mock dataset"
    : state.session?.capabilities.hasServerAuthorization === false ? "Live adapter · anonymous" : "Live adapter";
  modeIndicator.innerHTML = `<span></span>${modeLabel}`;
  document.querySelectorAll("[data-route]").forEach(button => {
    const active = button.dataset.route === state.route;
    button.classList.toggle("is-active", active);
    if (active) button.setAttribute("aria-current", "page"); else button.removeAttribute("aria-current");
  });
  if (state.summary?.sites) {
    siteSelector.innerHTML = state.summary.sites.map(site => `<option value="${escapeHtml(site.id)}" ${site.id === state.selectedSiteId ? "selected" : ""}>${escapeHtml(site.shortName || site.name)}</option>`).join("");
    siteSelector.disabled = !state.summary.sites.length;
  } else {
    siteSelector.innerHTML = `<option>Loading stations…</option>`;
    siteSelector.disabled = true;
  }
}

async function bootstrap() {
  const requestVersion = ++scopeRequestVersion;
  const role = state.role;
  siteRequestVersion += 1;
  graphRequestVersion += 1;
  runsRequestVersion += 1;
  reportsRequestVersion += 1;
  assistantRequestVersion += 1;
  clearPoll();
  closeDrawer();
  setState({ loading: true, error: null });
  render();
  try {
    const [session, summary] = await Promise.all([api.session(role), api.summary(role)]);
    if (requestVersion !== scopeRequestVersion || role !== state.role) return;
    const selectedSiteId = summary.sites.some(site => site.id === state.selectedSiteId)
      ? state.selectedSiteId
      : summary.sites[0]?.id || null;
    setState({ session, summary, selectedSiteId, loading: false });
    if (selectedSiteId) await loadSite(selectedSiteId, false, requestVersion);
    if (requestVersion !== scopeRequestVersion || role !== state.role) return;
    if (state.route === "ingestion") await loadRuns();
    if (state.route === "reports") await loadReports();
  } catch (error) {
    if (requestVersion !== scopeRequestVersion || role !== state.role) return;
    setState({ loading: false, error });
  }
  render();
}

async function loadSite(siteId, shouldRender = true, expectedScopeVersion = scopeRequestVersion) {
  const requestVersion = ++siteRequestVersion;
  const role = state.role;
  graphRequestVersion += 1;
  assistantRequestVersion += 1;
  closeDrawer();
  setState({ selectedSiteId: siteId, site: null, siteError: null, graph: null, assistant: null, error: null });
  if (shouldRender) render();
  try {
    const site = await api.site(role, siteId);
    if (requestVersion !== siteRequestVersion || expectedScopeVersion !== scopeRequestVersion || role !== state.role || siteId !== state.selectedSiteId) return;
    setState({ site });
    if (state.selectedTab === "relationships" && state.session?.capabilities.canLoadGraph) await loadGraph(false);
  } catch (error) {
    if (requestVersion !== siteRequestVersion || expectedScopeVersion !== scopeRequestVersion || role !== state.role || siteId !== state.selectedSiteId) return;
    setState({ siteError: error });
  }
  if (shouldRender) render();
}

async function loadGraph(shouldRender = true) {
  if (!state.session?.capabilities.canLoadGraph || !state.selectedSiteId) return;
  const requestVersion = ++graphRequestVersion;
  const role = state.role;
  const siteId = state.selectedSiteId;
  try {
    const graph = await api.graph(role, siteId);
    if (requestVersion !== graphRequestVersion || role !== state.role || siteId !== state.selectedSiteId) return;
    setState({ graph });
  } catch (error) {
    if (requestVersion !== graphRequestVersion || role !== state.role || siteId !== state.selectedSiteId) return;
    setState({ graph: { error } });
  }
  if (shouldRender) render();
}

async function navigate(route) {
  routeRequestVersion += 1;
  clearPoll();
  setState({ route, error: null });
  if (route === "ingestion" && !state.runs) await loadRuns();
  if (route === "reports" && !state.reports) await loadReports();
  render();
  document.querySelector("#main-content")?.focus({ preventScroll: true });
}

function render() {
  syncChrome();
  if (state.loading && !state.summary) {
    routeContent.innerHTML = `<div class="loading"><span class="sr-only">Loading dashboard</span></div>`;
    return;
  }
  if (state.error && !state.summary) {
    routeContent.innerHTML = `<div class="route-header"><div><span class="eyebrow">Connection</span><h1>Dashboard unavailable</h1></div></div>${errorState(state.error, "Dashboard data")}`;
    return;
  }
  if (state.route === "overview") renderOverview();
  if (state.route === "ingestion") renderIngestion();
  if (state.route === "reports") renderReports();
}

function metricButton(key, label, value, note) {
  return `<button class="metric" type="button" data-metric="${key}"><span class="metric-label">${escapeHtml(label)}</span><span class="metric-value">${escapeHtml(value)}</span><span class="metric-note">${escapeHtml(note)}</span></button>`;
}

function renderOverview() {
  const summary = state.summary;
  const current = state.site;
  routeContent.innerHTML = `
    <header class="route-header">
      <div><span class="eyebrow">Cross-domain surveillance</span><h1>Station evidence overview</h1><p>Inspect environmental observations and population-health context through one FHIR-linked workspace.</p></div>
      <div class="route-actions">${statusPill(apiMode === "mock" ? "observed" : "running", apiMode === "mock" ? "Simulation active" : "Live gateway")}</div>
    </header>
    <section class="metric-strip" aria-label="Dataset summary">
      ${metricButton("sites", "Sites in scope", summary.metrics.sitesInScope, summary.scopeLabel)}
      ${metricButton("observations", "Loaded observations", summary.metrics.loadedObservations, "Environmental + health + survey")}
      ${metricButton("findings", "Screening findings", summary.metrics.screeningFindings, "Prototype rule flags")}
      ${metricButton("colocation", "Co-located sites", summary.metrics.coLocatedSites, "Association only")}
    </section>
    <div class="workspace-grid">
      <section class="panel station-table-panel" id="station-records">
        <div class="panel-head"><div><span class="eyebrow">Locations</span><h2>Station comparison</h2><p>${escapeHtml(summary.countNotice)}</p></div></div>
        <div class="panel-body flush"><div class="table-wrap"><table>
          <thead><tr><th>Station</th><th>Status</th><th>Records</th></tr></thead>
          <tbody>${summary.sites.map(site => `
            <tr class="station-row ${site.id === state.selectedSiteId ? "is-selected" : ""}" data-site-row="${escapeHtml(site.id)}" tabindex="0">
              <td><span class="station-name">${escapeHtml(site.shortName || site.name)}</span><span class="station-meta">${escapeHtml(site.city)} · ${site.lastObservedAt ? formatDate(site.lastObservedAt) : "No observation time"}</span></td>
              <td>${statusPill(site.status)}</td>
              <td class="number">${escapeHtml(site.observationCount)} obs.<br><span class="station-meta">${escapeHtml(site.findingCount)} findings</span></td>
            </tr>`).join("")}</tbody>
        </table></div></div>
      </section>
      <section class="panel" id="site-workspace">
        ${current ? renderSiteWorkspace(current) : state.siteError ? errorState(state.siteError, "Selected station") : summary.sites.length ? `<div class="loading"><span class="sr-only">Loading selected station</span></div>` : emptyState("No stations in scope", "The current response contains no stations to inspect.")}
      </section>
    </div>
    ${renderAssistant()}`;
}

function renderSiteWorkspace(data) {
  const { site, observations, findings, meta } = data;
  const environmental = observations.filter(item => item.kind === "environmental").length;
  const health = observations.filter(item => item.kind === "health" || item.kind === "health-summary").length;
  return `
    <div class="station-focus">
      <div class="station-focus-top"><div><span class="eyebrow">Selected Location</span><h2>${escapeHtml(site.name)}</h2><p>${escapeHtml(site.city)} · last source time ${formatDate(site.lastObservedAt)}</p></div>${statusPill(site.status)}</div>
      <div class="focus-summary"><span><strong>${environmental}</strong> environmental</span><span><strong>${health}</strong> health context</span><span><strong>${findings.length}</strong> findings</span><span class="coordinates"><strong>${site.latitude ?? "—"}, ${site.longitude ?? "—"}</strong> approximate coordinates</span></div>
    </div>
    <div class="local-tabs" role="tablist" aria-label="Station workspace">
      ${["context", "evidence", "relationships"].map(tab => `<button class="local-tab" type="button" role="tab" data-local-tab="${tab}" aria-selected="${state.selectedTab === tab}">${tab[0].toUpperCase() + tab.slice(1)}</button>`).join("")}
    </div>
    <div class="tab-panel" role="tabpanel">
      ${state.selectedTab === "context" ? renderContextTab(observations, findings, meta) : ""}
      ${state.selectedTab === "evidence" ? renderEvidenceTab(findings) : ""}
      ${state.selectedTab === "relationships" ? renderGraphTab() : ""}
    </div>`;
}

function renderContextTab(observations, findings, meta) {
  return `
    <div class="table-wrap"><table class="observation-table">
      <thead><tr><th>Observation</th><th>Value</th><th>Assessment context</th></tr></thead>
      <tbody>${observations.map(item => `<tr><td><span class="measure-name">${escapeHtml(item.indicator)}</span><span class="measure-meta">${escapeHtml(item.kind)} · ${formatDate(item.effectiveAt)}</span>${item.evaluationPeriod ? `<span class="measure-meta">Period ${escapeHtml(item.evaluationPeriod)}</span>` : ""}</td><td class="measure-value">${valueDisplay(item)}</td><td class="interpretation">${escapeHtml(item.interpretation)}${item.screeningReference ? `<br><strong>${escapeHtml(item.screeningReference)}</strong>` : ""}</td></tr>`).join("")}</tbody>
    </table></div>
    <div class="finding-list">${findings.length ? findings.map(finding => `
      <article class="finding-card ${escapeHtml(finding.severity)}">
        <div><span class="eyebrow">${escapeHtml(finding.type)}</span><h4>${escapeHtml(finding.title)}</h4><p>${escapeHtml(finding.statement)}</p>${finding.caveat ? `<p class="caveat">${escapeHtml(finding.caveat)}</p>` : ""}</div>
        ${finding.evidenceIds?.length ? `<button class="button small" type="button" data-show-finding-evidence="${escapeHtml(finding.id)}">View evidence</button>` : ""}
      </article>`).join("") : emptyState("No derived findings", "No threshold or cross-domain finding is present for this station.")}</div>
    <div class="notice neutral" style="margin-top:14px"><strong>Data-use note.</strong> ${escapeHtml(meta.screeningNotice)} ${escapeHtml(meta.coordinateNotice)}</div>`;
}

function renderEvidenceTab(findings) {
  if (!state.session?.capabilities.canReadEvidence) {
    return emptyState("Evidence details are restricted", `${state.session?.persona.label || "This persona"} can view scoped summaries but not raw evidence references.`);
  }
  const evidence = findings.flatMap(finding => (finding.evidenceIds || []).map(id => ({ id, finding: finding.title })));
  const unique = [...new Map(evidence.map(item => [item.id, item])).values()];
  return unique.length ? `<div class="evidence-list">${unique.map(item => `<button class="evidence-row" type="button" data-evidence-id="${escapeHtml(item.id)}"><span class="evidence-type">Evidence record</span><span><strong>${escapeHtml(item.id)}</strong><small>Supports ${escapeHtml(item.finding)}</small></span><span class="arrow" aria-hidden="true">→</span></button>`).join("")}</div>` : emptyState("No evidence references", "This station has no evidence-linked findings in the current scope.");
}

function renderGraphTab() {
  if (!state.session?.capabilities.canLoadGraph) {
    return emptyState("Relationship view unavailable", `${state.session?.persona.label || "This persona"} does not have graph access. Live mode also requires a future graph API.`);
  }
  if (!state.graph) return `<div class="loading"><span class="sr-only">Loading relationship graph</span></div>`;
  if (state.graph.error) return errorState(state.graph.error, "Relationship graph");
  const graph = state.graph;
  const nodeMap = new Map(graph.nodes.map(node => [node.id, node]));
  return `
    <div class="graph-toolbar" aria-label="Graph filters">
      <button class="graph-filter is-active" type="button" data-graph-filter="all">All records</button>
      <button class="graph-filter" type="button" data-graph-filter="Observation">Observations</button>
      <button class="graph-filter" type="button" data-graph-filter="Finding">Finding path</button>
      <button class="button small" type="button" data-graph-reset>Fit / reset</button>
    </div>
    <div class="graph-canvas" data-graph-canvas aria-label="Relationship graph for ${escapeHtml(state.site.site.name)}">
      <svg class="graph-lines" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true"><defs><marker id="arrowhead" markerWidth="5" markerHeight="5" refX="4" refY="2.5" orient="auto"><path class="graph-arrow" d="M0,0 L5,2.5 L0,5 z"></path></marker></defs>${graph.edges.map(edge => {
        const source = nodeMap.get(edge.source); const target = nodeMap.get(edge.target);
        return source && target ? `<line class="${edge.derived ? "derived" : ""}" x1="${source.x}" y1="${source.y}" x2="${target.x}" y2="${target.y}" marker-end="url(#arrowhead)" data-edge-source="${escapeHtml(edge.source)}" data-edge-target="${escapeHtml(edge.target)}"></line>` : "";
      }).join("")}</svg>
      ${graph.nodes.map(node => `<button class="graph-node" type="button" style="left:${node.x}%;top:${node.y}%" data-graph-node="${escapeHtml(node.id)}" data-type="${escapeHtml(node.type)}">${escapeHtml(node.label)}</button>`).join("")}
    </div>
    <div class="graph-legend"><span><i class="legend-dot location"></i>Location</span><span><i class="legend-dot"></i>FHIR record</span><span><i class="legend-dot finding"></i>Derived finding / edge</span></div>
    <ul class="relationship-list" aria-label="Textual relationship list">${graph.edges.map(edge => `<li><code>${escapeHtml(nodeMap.get(edge.source)?.label || edge.source)}</code> → <strong>${escapeHtml(edge.type)}</strong> → <code>${escapeHtml(nodeMap.get(edge.target)?.label || edge.target)}</code>${edge.derived ? " · derived" : ""}</li>`).join("")}</ul>`;
}

function renderAssistant() {
  const canAsk = state.session?.capabilities.canQueryAssistant && state.selectedSiteId;
  return `<section class="panel assistant-panel">
    <div class="panel-head"><div><span class="eyebrow">Observable assistance</span><h2>Ask about this site</h2><p>Answers cite returned records and expose tool/evidence steps—not hidden reasoning.</p></div>${canAsk ? statusPill("observed", apiMode === "mock" ? "Deterministic demo" : "Existing API") : statusPill("unavailable")}</div>
    ${canAsk ? `<div class="assistant-layout"><div class="assistant-main"><form id="assistant-form"><input id="assistant-question" name="question" maxlength="500" required aria-label="Question about selected site" placeholder="Ask about findings, evidence, or source timing"><button class="button primary" type="submit">Ask</button></form><div class="question-chips"><button class="question-chip" type="button" data-question="What needs attention at Mondego C1?">What needs attention?</button><button class="question-chip" type="button" data-question="What evidence supports the co-location finding?">Show supporting evidence</button><button class="question-chip" type="button" data-question="Are the environmental and health observations contemporaneous?">Are the source periods aligned?</button></div>${state.assistant ? `<div class="assistant-answer"><span class="eyebrow">Grounded response</span><p>${escapeHtml(state.assistant.answer)}</p></div>` : ""}</div><div class="trace-list"><span class="eyebrow">Execution trace</span>${state.assistant ? `<ol>${(state.assistant.trace || []).map(step => `<li><strong>${escapeHtml(step.label || step.tool || step.kind)}</strong><br>${escapeHtml(step.kind || "TOOL")} · ${escapeHtml(step.status || "completed")}</li>`).join("")}</ol><p class="station-meta">${escapeHtml(state.assistant.grounding?.notCovered || state.assistant.grounding?.not_covered || "Grounding checks are limited.")}</p>` : `<p style="margin-top:10px;color:var(--ink-3)">Run a suggested question to see evidence retrieval and grounding steps.</p>`}</div></div>` : emptyState("Assistant unavailable", "This persona cannot query scoped evidence, or the optional live assistant endpoint is unavailable.")}
  </section>`;
}

async function loadRuns() {
  const requestVersion = ++runsRequestVersion;
  const expectedScopeVersion = scopeRequestVersion;
  const expectedRouteVersion = routeRequestVersion;
  const role = state.role;
  clearPoll();
  try {
    const runs = await api.runs(role);
    if (requestVersion !== runsRequestVersion || expectedScopeVersion !== scopeRequestVersion || expectedRouteVersion !== routeRequestVersion || role !== state.role) return;
    const selectedRunId = runs.runs.some(run => run.id === state.selectedRunId) ? state.selectedRunId : runs.runs[0]?.id || null;
    setState({ runs, selectedRunId, error: null });
    if (!state.selectedSampleKey || !runs.samples.some(sample => sample.key === state.selectedSampleKey)) setState({ selectedSampleKey: runs.samples[0]?.key || null });
    if (runs.runs.some(run => run.executionStatus === "running") && state.route === "ingestion") schedulePoll(loadRuns);
  } catch (error) {
    if (requestVersion !== runsRequestVersion || expectedScopeVersion !== scopeRequestVersion || expectedRouteVersion !== routeRequestVersion || role !== state.role) return;
    setState({ runs: { error }, error: null });
  }
  render();
}

function selectedRun() {
  return state.runs?.runs?.find(run => run.id === state.selectedRunId) || null;
}

function renderIngestion() {
  const canTrack = state.session?.capabilities.canTrackRuns;
  const canStart = state.session?.capabilities.canStartRuns;
  const runsData = state.runs;
  routeContent.innerHTML = `
    <header class="route-header"><div><span class="eyebrow">Source to FHIR</span><h1>Ingestion workbench</h1><p>Run a supplied source sample, inspect each processing artifact, and keep screening findings distinct from processing failures.</p></div><div class="route-actions">${apiMode === "mock" && canStart ? `<button class="button" type="button" data-reset-demo>Reset demo state</button>` : ""}</div></header>
    ${!canTrack && apiMode === "mock" ? emptyState("Operational controls are restricted", `${state.session?.persona.label || "This persona"} does not have ingestion-run access. Switch to Data operator in the demo control to inspect payloads and run samples.`) : runsData?.error ? (apiMode === "live" && canStart ? renderLiveRunOnly(runsData.error) : errorState(runsData.error, "Ingestion history")) : !runsData ? `<div class="loading"><span class="sr-only">Loading ingestion workbench</span></div>` : renderIngestionWorkspace(runsData, canStart)}`;
}

function renderLiveRunOnly(error) {
  return `<div class="notice"><strong>Live history unavailable.</strong> ${escapeHtml(error.message)} The existing service can still execute request-scoped demo samples for Data operator.</div>`;
}

function renderIngestionWorkspace(data, canStart) {
  const run = selectedRun();
  const selectedSample = data.samples.find(sample => sample.key === state.selectedSampleKey) || data.samples[0];
  return `<div class="ingestion-layout">
    <div>
      <section class="panel"><div class="panel-head"><div><span class="eyebrow">Step 1</span><h2>Choose a source sample</h2><p>Supplied examples cover all three source types.</p></div></div><div class="panel-body"><div class="sample-list">${data.samples.map(sample => `<button class="sample-card ${sample.key === selectedSample?.key ? "is-selected" : ""}" type="button" data-sample-key="${escapeHtml(sample.key)}"><span><strong>${escapeHtml(sample.label || sample.channel || sample.key)}</strong><small>${escapeHtml(sample.description || sample.detail || "Supplied demo sample")}</small></span><span class="source-tag">${escapeHtml(sample.sourceType || sample.key)}</span></button>`).join("")}</div><div class="sample-action"><button class="button primary" type="button" data-start-run ${!canStart || !selectedSample ? "disabled" : ""}>${apiMode === "mock" ? "Start ingestion" : "Run live request"}</button></div>${!canStart ? `<div class="notice neutral" style="margin-top:12px">This persona may inspect summaries but cannot submit source samples.</div>` : ""}</div></section>
      <section class="panel run-list"><div class="panel-head"><div><span class="eyebrow">Recent activity</span><h2>Demo runs</h2><p>${escapeHtml(data.stateNotice)}</p></div></div><div class="table-wrap"><table><thead><tr><th>Run</th><th>Execution</th><th>FHIR outcome</th></tr></thead><tbody>${data.runs.length ? data.runs.map(item => `<tr class="run-row ${item.id === state.selectedRunId ? "is-selected" : ""}" data-run-id="${escapeHtml(item.id)}" tabindex="0"><td><span class="run-id">${escapeHtml(item.id)}</span><span class="station-meta">${escapeHtml(item.sampleLabel || item.sampleKey)} · attempt ${escapeHtml(item.attempt || 1)}</span>${item.retryOf ? `<span class="run-link">retry of ${escapeHtml(item.retryOf)}</span>` : ""}</td><td>${statusPill(item.executionStatus)}</td><td>${item.fhirOutcome ? statusPill(item.fhirOutcome) : `<span class="station-meta">Awaiting outcome</span>`}</td></tr>`).join("") : `<tr><td colspan="3">No durable live history is available.</td></tr>`}</tbody></table></div></section>
    </div>
    <section class="panel">${run ? renderPipeline(run) : emptyState("Select or start a run", "Stage inputs, outputs, warnings and transaction evidence will appear here.")}</section>
  </div>`;
}

function renderPipeline(run) {
  const stage = run.stages.find(item => item.id === state.selectedStageId) || run.stages[0];
  const payloadKeys = ["input", "output", "counts", "warnings", "errors"].filter(key => stage[key] !== undefined && (Array.isArray(stage[key]) ? stage[key].length : true));
  const activePayloadKey = stage._activePayload && payloadKeys.includes(stage._activePayload) ? stage._activePayload : payloadKeys[0];
  const retryAllowed = run.executionStatus === "failed" && state.session?.capabilities.canRetryRuns;
  return `<div class="pipeline-head"><div class="pipeline-head-row"><div><span class="eyebrow">Selected run</span><h2>${escapeHtml(run.sampleLabel || run.sampleKey)}</h2><p><span class="run-id">${escapeHtml(run.id)}</span> · ${escapeHtml(run.sourceType)} · started ${formatDate(run.startedAt)}</p></div><div>${statusPill(run.executionStatus)}</div></div><div class="progress-track" aria-label="${escapeHtml(run.progress)} percent complete"><span style="width:${Number(run.progress) || 0}%"></span></div>${retryAllowed ? `<button class="button danger small" style="margin-top:12px" type="button" data-retry-run="${escapeHtml(run.id)}">Retry failed run</button>` : ""}</div>
    <div class="pipeline-workspace"><div class="stage-list" role="tablist" aria-label="Pipeline stage">${run.stages.map((item, index) => `<button class="stage-button ${escapeHtml(item.status)}" type="button" role="tab" data-stage-id="${escapeHtml(item.id)}" aria-selected="${item.id === stage.id}"><span class="stage-index">${index + 1}</span><span><strong>${escapeHtml(item.name)}</strong><small>${escapeHtml(item.status)}</small></span></button>`).join("")}</div><div class="stage-detail"><span class="eyebrow">${escapeHtml(stage.status)}</span><h3>${escapeHtml(stage.name)}</h3><p>${escapeHtml(stage.summary)}</p>${stage.warnings?.length ? `<div class="notice"><strong>Screening / mapping warning.</strong> ${escapeHtml(stage.warnings.join(" "))}</div>` : ""}${stage.errors?.length ? `<div class="notice error"><strong>Processing failure.</strong> ${escapeHtml(stage.errors.join(" "))}</div>` : ""}${payloadKeys.length ? `<div class="payload-tabs" role="tablist">${payloadKeys.map(key => `<button class="payload-tab ${key === activePayloadKey ? "is-active" : ""}" type="button" data-payload-key="${key}">${key}</button>`).join("")}</div><div class="payload-head"><span>${escapeHtml(activePayloadKey)}</span>${copyButton()}</div>${jsonBlock(stage[activePayloadKey])}` : `<div class="notice neutral">No artifact is available for this pending stage.</div>`}</div></div>`;
}

async function startRun() {
  if (!state.selectedSampleKey) return;
  const expectedScopeVersion = scopeRequestVersion;
  const role = state.role;
  try {
    const run = await api.startRun(role, state.selectedSampleKey);
    if (expectedScopeVersion !== scopeRequestVersion || role !== state.role) return;
    if (apiMode === "live") {
      const existing = state.runs || { runs: [], samples: [], stateNotice: "Live request-scoped result" };
      existing.runs = [run, ...existing.runs];
      setState({ runs: existing, selectedRunId: run.id, selectedStageId: "received" });
      render();
    } else {
      setState({ selectedRunId: run.id, selectedStageId: "received" });
      await loadRuns();
    }
    toast("Ingestion started");
  } catch (error) { toast(error.message, "error"); }
}

async function retryRun(runId) {
  const expectedScopeVersion = scopeRequestVersion;
  const role = state.role;
  try {
    const run = await api.retryRun(role, runId);
    if (expectedScopeVersion !== scopeRequestVersion || role !== state.role) return;
    setState({ selectedRunId: run.id, selectedStageId: "received" });
    await loadRuns();
    toast(`Retry ${run.id} started`);
  } catch (error) { toast(error.message, "error"); }
}

async function loadReports() {
  const requestVersion = ++reportsRequestVersion;
  const expectedScopeVersion = scopeRequestVersion;
  const expectedRouteVersion = routeRequestVersion;
  const role = state.role;
  clearPoll();
  try {
    const reports = await api.reports(role);
    if (requestVersion !== reportsRequestVersion || expectedScopeVersion !== scopeRequestVersion || expectedRouteVersion !== routeRequestVersion || role !== state.role) return;
    const selectedReportId = reports.reports.some(report => report.id === state.selectedReportId) ? state.selectedReportId : reports.reports[0]?.id || null;
    const report = reports.reports.find(item => item.id === selectedReportId) || null;
    setState({ reports, selectedReportId, report, error: null });
    if (reports.reports.some(item => ["requested", "generating"].includes(item.status)) && state.route === "reports") schedulePoll(loadReports, 800);
  } catch (error) {
    if (requestVersion !== reportsRequestVersion || expectedScopeVersion !== scopeRequestVersion || expectedRouteVersion !== routeRequestVersion || role !== state.role) return;
    setState({ reports: { error }, report: null, error: null });
  }
  render();
}

function renderReports() {
  const data = state.reports;
  const canGenerate = state.session?.capabilities.canGenerateReports;
  routeContent.innerHTML = `
    <header class="route-header"><div><span class="eyebrow">Proposed capability · mock-backed</span><h1>Site One Health briefings</h1><p>Generate a fixed snapshot of scoped observations, findings, evidence references and interpretation limits.</p></div><div class="route-actions">${canGenerate ? `<button class="button primary" type="button" data-generate-report>Generate for current station</button>` : ""}</div></header>
    ${data?.error ? (data.error.status === 403 ? emptyState("Reports are not in this persona's scope", "Data operator focuses on ingestion operations. Viewer can access the published example; Analyst can generate draft briefings.") : errorState(data.error, "Reports")) : !data ? `<div class="loading"><span class="sr-only">Loading reports</span></div>` : renderReportsWorkspace(data)}`;
}

function renderReportsWorkspace(data) {
  return `<div class="reports-layout"><section class="panel"><div class="panel-head"><div><span class="eyebrow">Briefings</span><h2>Available reports</h2><p>Viewer sees only explicitly published demo records.</p></div></div><div class="report-list">${data.reports.length ? data.reports.map(report => `<button class="report-list-item ${report.id === state.selectedReportId ? "is-selected" : ""}" type="button" data-report-id="${escapeHtml(report.id)}"><strong>${escapeHtml(report.title)}</strong><span class="report-list-meta"><span>${escapeHtml(report.visibility)} · ${report.generatedAt ? formatDate(report.generatedAt) : "processing"}</span>${statusPill(report.status)}</span></button>`).join("") : emptyState("No reports in scope", "Generate a draft briefing from the selected station.")}</div></section><section class="panel">${state.report ? renderReportPreview(state.report) : emptyState("Select a briefing", "The report snapshot and download formats will appear here.")}</section></div>`;
}

function renderReportPreview(report) {
  if (report.status !== "generated" || !report.snapshot) {
    return `<div class="empty-state"><span class="eyebrow">${escapeHtml(report.status)}</span><h2>Building a consistent snapshot</h2><p>The mock service is capturing the observations and findings now. Existing snapshots will not change if the dashboard data changes later.</p><div class="progress-track" style="max-width:280px;margin:18px auto"><span style="width:${report.status === "generating" ? 65 : 22}%"></span></div></div>`;
  }
  const snapshot = report.snapshot;
  return `<article class="report-sheet"><span class="eyebrow">Site One Health Briefing</span><h2>${escapeHtml(snapshot.site.name)}</h2><p class="report-meta">Generated ${formatDate(snapshot.generatedAt)} · Environmental sample 30 Sep 2026 · Health period ${escapeHtml(snapshot.timeScope.healthEvaluationPeriod)}</p><div class="notice" style="margin-top:18px"><strong>Interpret carefully.</strong> Association only, not causation. Source periods are not contemporaneous.</div><h3>Source observations</h3><div class="table-wrap"><table><thead><tr><th>Measure</th><th>Value</th><th>Context</th></tr></thead><tbody>${snapshot.observations.map(item => `<tr><td>${escapeHtml(item.indicator)}</td><td class="number">${valueDisplay(item)}</td><td>${escapeHtml(item.interpretation)}</td></tr>`).join("")}</tbody></table></div><h3>Findings</h3><ul>${snapshot.findings.map(item => `<li><strong>${escapeHtml(item.title)}</strong> — ${escapeHtml(item.statement)}</li>`).join("")}</ul><h3>Limitations</h3><ul>${snapshot.limitations.map(item => `<li>${escapeHtml(item)}</li>`).join("")}</ul></article><div class="report-actions">${report.files.map(file => `<button class="button" type="button" data-download-report="${escapeHtml(file.format)}">Download ${escapeHtml(file.format.toUpperCase())} <span class="station-meta">${humanBytes(file.sizeBytes)}</span></button>`).join("")}<button class="button" type="button" data-print-report>Print / Save as PDF</button></div>`;
}

async function generateReport() {
  const expectedScopeVersion = scopeRequestVersion;
  const role = state.role;
  const siteId = state.selectedSiteId;
  try {
    const report = await api.createReport(role, siteId);
    if (expectedScopeVersion !== scopeRequestVersion || role !== state.role || siteId !== state.selectedSiteId) return;
    setState({ selectedReportId: report.id, report });
    toast("Briefing requested");
    await loadReports();
  } catch (error) { toast(error.message, "error"); }
}

async function selectReport(reportId) {
  const expectedScopeVersion = scopeRequestVersion;
  const role = state.role;
  try {
    const report = await api.report(role, reportId);
    if (expectedScopeVersion !== scopeRequestVersion || role !== state.role) return;
    setState({ selectedReportId: reportId, report });
    render();
  } catch (error) { toast(error.message, "error"); }
}

async function fetchReportFile(format, openForPrint = false) {
  if (!state.report) return;
  try {
    const response = await fetch(api.downloadUrl(state.report.id, format), { headers: { "X-Demo-Role": state.role } });
    if (!response.ok) {
      const detail = await response.json();
      throw new ApiError(detail.detail || "Download failed", response.status);
    }
    const blob = await response.blob();
    if (openForPrint) {
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank", "noopener,noreferrer");
      window.setTimeout(() => URL.revokeObjectURL(url), 60000);
    } else {
      const slug = state.report.siteId.replace("site-", "");
      downloadBlob(blob, `${slug}-one-health-briefing.${format}`);
    }
  } catch (error) { toast(error.message, "error"); }
}

async function showEvidence(evidenceId) {
  const expectedScopeVersion = scopeRequestVersion;
  const expectedSiteVersion = siteRequestVersion;
  const role = state.role;
  const siteId = state.selectedSiteId;
  openDrawer(`<div class="loading"><span class="sr-only">Loading evidence</span></div>`, "Evidence record", "Resolving scoped reference");
  try {
    const evidence = await api.evidence(role, evidenceId);
    if (expectedScopeVersion !== scopeRequestVersion || expectedSiteVersion !== siteRequestVersion || role !== state.role || siteId !== state.selectedSiteId) return;
    openDrawer(`<dl class="detail-grid">${Object.entries(evidence).map(([key, value]) => `<dt>${escapeHtml(key)}</dt><dd>${typeof value === "object" ? `<code>${escapeHtml(JSON.stringify(value))}</code>` : escapeHtml(value)}</dd>`).join("")}</dl>${evidence.basis ? `<div class="notice" style="margin-top:18px">${escapeHtml(evidence.basis)}</div>` : ""}`, evidence.label, evidence.type);
  } catch (error) {
    if (expectedScopeVersion !== scopeRequestVersion || expectedSiteVersion !== siteRequestVersion || role !== state.role || siteId !== state.selectedSiteId) return;
    openDrawer(errorState(error, "Evidence"), "Evidence unavailable", "Scope and permission check");
  }
}

function openNode(nodeId) {
  const node = state.graph?.nodes?.find(item => item.id === nodeId);
  if (!node) return;
  const edges = state.graph.edges.filter(edge => edge.source === node.id || edge.target === node.id);
  openDrawer(`<dl class="detail-grid"><dt>Reference</dt><dd><code>${escapeHtml(node.id)}</code></dd><dt>Record type</dt><dd>${escapeHtml(node.type)}</dd><dt>Site scope</dt><dd>${escapeHtml(node.siteId)}</dd><dt>Relationships</dt><dd>${edges.length}</dd></dl><h3 style="margin-top:24px">Connected records</h3><ul class="relationship-list">${edges.map(edge => `<li><strong>${escapeHtml(edge.type)}</strong><br><code>${escapeHtml(edge.source)} → ${escapeHtml(edge.target)}</code></li>`).join("")}</ul>`, node.label, "Relationship node");
}

function openDrawer(content, title, eyebrow = "Details") {
  const root = document.querySelector("#drawer-root");
  root.innerHTML = `<div class="drawer-backdrop" data-close-drawer><aside class="drawer" role="dialog" aria-modal="true" aria-labelledby="drawer-title"><div class="drawer-head"><div><span class="eyebrow">${escapeHtml(eyebrow)}</span><h2 id="drawer-title">${escapeHtml(title)}</h2></div><button class="icon-button" type="button" data-close-drawer aria-label="Close details">×</button></div><div class="drawer-body">${content}</div></aside></div>`;
  root.querySelector("[data-close-drawer]").focus();
}

function closeDrawer() { document.querySelector("#drawer-root").innerHTML = ""; }

function showAbout() {
  const targetMode = apiMode === "mock" ? "live" : "mock";
  const href = targetMode === "live" ? `${location.pathname}?mode=live` : location.pathname;
  openDrawer(`<p>This compact evidence workspace uses warm neutral surfaces, a muted water accent, and operational tables so station context stays primary.</p><div class="notice"><strong>Prototype boundaries.</strong> Role policy, durable run history, retry management, graph retrieval, and reports are functional mock-backed proposals—not capabilities discovered in the current backend.</div><h3 style="margin-top:24px">Connection mode</h3><p>The mock service is the complete demo. Live mode connects only features implemented by the existing gateway and shows missing capabilities as unavailable.</p><a class="button" href="${escapeHtml(href)}">Open ${escapeHtml(targetMode)} mode</a>`, "About this dashboard", "Design and data boundary");
}

function applyGraphFilter(type) {
  const canvas = document.querySelector("[data-graph-canvas]");
  if (!canvas || !state.graph) return;
  document.querySelectorAll("[data-graph-filter]").forEach(button => button.classList.toggle("is-active", button.dataset.graphFilter === type));
  const keep = new Set();
  state.graph.nodes.forEach(node => {
    if (type === "all" || node.type === type || (type === "Finding" && ["Observation", "Finding", "Location", "Group"].includes(node.type))) keep.add(node.id);
  });
  canvas.querySelectorAll("[data-graph-node]").forEach(node => { node.hidden = !keep.has(node.dataset.graphNode); });
  canvas.querySelectorAll("line[data-edge-source]").forEach(line => { line.style.display = keep.has(line.dataset.edgeSource) && keep.has(line.dataset.edgeTarget) ? "" : "none"; });
}

document.addEventListener("click", async event => {
  const route = event.target.closest("[data-route]");
  if (route) return navigate(route.dataset.route);
  if (event.target.closest("#about-demo")) return showAbout();
  const siteRow = event.target.closest("[data-site-row]");
  if (siteRow) return loadSite(siteRow.dataset.siteRow);
  const localTab = event.target.closest("[data-local-tab]");
  if (localTab) {
    setState({ selectedTab: localTab.dataset.localTab });
    if (state.selectedTab === "relationships" && !state.graph) await loadGraph(false);
    return render();
  }
  const metric = event.target.closest("[data-metric]");
  if (metric) {
    if (metric.dataset.metric === "sites") document.querySelector("#station-records")?.scrollIntoView({ behavior: "smooth", block: "start" });
    else if (metric.dataset.metric === "observations") { setState({ selectedTab: "context" }); render(); document.querySelector("#site-workspace")?.scrollIntoView({ behavior: "smooth" }); }
    else if (metric.dataset.metric === "findings" || metric.dataset.metric === "colocation") { setState({ selectedTab: "evidence" }); render(); document.querySelector("#site-workspace")?.scrollIntoView({ behavior: "smooth" }); }
    return;
  }
  const evidence = event.target.closest("[data-evidence-id]");
  if (evidence) return showEvidence(evidence.dataset.evidenceId);
  const findingEvidence = event.target.closest("[data-show-finding-evidence]");
  if (findingEvidence) { setState({ selectedTab: "evidence" }); return render(); }
  const question = event.target.closest("[data-question]");
  if (question) { const input = document.querySelector("#assistant-question"); if (input) { input.value = question.dataset.question; input.focus(); } return; }
  const sample = event.target.closest("[data-sample-key]");
  if (sample) { setState({ selectedSampleKey: sample.dataset.sampleKey }); return render(); }
  if (event.target.closest("[data-start-run]")) return startRun();
  const runRow = event.target.closest("[data-run-id]");
  if (runRow) { setState({ selectedRunId: runRow.dataset.runId, selectedStageId: "received" }); return render(); }
  const stageButton = event.target.closest("[data-stage-id]");
  if (stageButton) { setState({ selectedStageId: stageButton.dataset.stageId }); return render(); }
  const payloadButton = event.target.closest("[data-payload-key]");
  if (payloadButton) { const run = selectedRun(); const stage = run?.stages.find(item => item.id === state.selectedStageId); if (stage) stage._activePayload = payloadButton.dataset.payloadKey; return render(); }
  if (event.target.closest("[data-copy-payload]")) { const pre = event.target.closest(".stage-detail")?.querySelector("pre"); if (pre) { await navigator.clipboard.writeText(pre.textContent); toast("Payload copied"); } return; }
  const retry = event.target.closest("[data-retry-run]");
  if (retry) return retryRun(retry.dataset.retryRun);
  if (event.target.closest("[data-reset-demo]")) { try { await api.reset(state.role); await loadRuns(); toast("Demo state reset"); } catch (error) { toast(error.message, "error"); } return; }
  if (event.target.closest("[data-generate-report]")) return generateReport();
  const reportItem = event.target.closest("[data-report-id]");
  if (reportItem) return selectReport(reportItem.dataset.reportId);
  const download = event.target.closest("[data-download-report]");
  if (download) return fetchReportFile(download.dataset.downloadReport);
  if (event.target.closest("[data-print-report]")) return fetchReportFile("html", true);
  const graphFilter = event.target.closest("[data-graph-filter]");
  if (graphFilter) return applyGraphFilter(graphFilter.dataset.graphFilter);
  if (event.target.closest("[data-graph-reset]")) return applyGraphFilter("all");
  const graphNode = event.target.closest("[data-graph-node]");
  if (graphNode) return openNode(graphNode.dataset.graphNode);
  if (event.target.matches(".drawer-backdrop") || event.target.closest("button[data-close-drawer]")) return closeDrawer();
});

document.addEventListener("submit", async event => {
  if (event.target.id !== "assistant-form") return;
  event.preventDefault();
  const input = event.target.elements.question;
  const question = input.value.trim();
  if (!question) return;
  const requestVersion = ++assistantRequestVersion;
  const expectedScopeVersion = scopeRequestVersion;
  const role = state.role;
  const siteId = state.selectedSiteId;
  input.disabled = true;
  try {
    const assistant = await api.ask(role, siteId, question);
    if (requestVersion !== assistantRequestVersion || expectedScopeVersion !== scopeRequestVersion || role !== state.role || siteId !== state.selectedSiteId) return;
    setState({ assistant });
    render();
  } catch (error) {
    if (requestVersion !== assistantRequestVersion || expectedScopeVersion !== scopeRequestVersion || role !== state.role || siteId !== state.selectedSiteId) return;
    toast(error.message, "error");
    input.disabled = false;
  }
});

document.addEventListener("keydown", event => {
  if (event.key === "Escape") closeDrawer();
  const row = event.target.closest?.("[data-site-row], [data-run-id]");
  if (row && (event.key === "Enter" || event.key === " ")) { event.preventDefault(); row.click(); }
});

siteSelector.addEventListener("change", () => loadSite(siteSelector.value));
personaSelector.addEventListener("change", () => { changeRole(personaSelector.value); bootstrap(); });
themeSelector.addEventListener("change", () => { applyTheme(themeSelector.value, { persist: true }); toast(`${themeSelector.selectedOptions[0].text.replace(" · Default", "")} theme selected`); });
window.addEventListener("beforeunload", clearPoll);

const savedTheme = localStorage.getItem("oah-theme");
const initialTheme = embeddedThemeConfig.themes.some(theme => theme.id === savedTheme)
  ? savedTheme
  : embeddedThemeConfig.defaultTheme;
setState({ themeConfig: embeddedThemeConfig, theme: initialTheme });
applyTheme(initialTheme);
document.querySelector("#initial-theme-tokens")?.remove();
bootstrap();
