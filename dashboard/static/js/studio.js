import { apiMode } from "./api.js";
import { state, subscribe } from "./state.js";
import { escapeHtml as esc, downloadBlob, toast } from "./components.js";
import { createChartRenderer } from "./studio-charts.js";
import { readStudioEvents, studioRequest } from "./studio-api.js";

const md = text => esc(text).split(/\n{2,}/).map(block => `<p>${block
  .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replaceAll("\n", "<br>")}</p>`).join("");

export function initStudio() {
  const root = document.querySelector("#studio-root");
  root.innerHTML = `<section class="studio-shell" id="surveillance-studio" aria-labelledby="studio-title">
    <header class="studio-head"><h1 id="studio-title">Surveillance Studio</h1>
      <div class="studio-actions"><button class="button small" type="button" data-studio-new>New</button>
      </div></header>
    <div class="studio-scope"><label for="studio-scope">Investigate</label><select id="studio-scope"><option value="station">Current station</option><option value="all">All stations</option></select>
      <span id="studio-station"></span></div>
    <div class="studio-notice" id="studio-notice"></div>
    <div class="studio-feed" tabindex="0" aria-label="Investigation results">
      <div class="studio-welcome"><span aria-hidden="true">✦</span><h3>What do you want to investigate?</h3><p>Explore water quality and population health together. Answers show retrieved evidence, charts, and screening references.</p><p>Each question starts a new investigation. Results stay here while you navigate.</p></div>
    </div>
    <form class="studio-composer"><label class="sr-only" for="studio-question">Investigation question</label>
      <textarea id="studio-question" maxlength="4000" rows="2" placeholder="What needs attention at this station?" required></textarea>
      <div class="studio-controls">
      <div class="studio-prompt-chips"><button type="button" class="question-chip" data-studio-prompt="What needs attention? Show the evidence and screening criteria.">What needs attention?</button>
      <button type="button" class="question-chip" data-studio-prompt="Show water quality and disease notification trends over the last 28 days.">Show trends</button>
      <button type="button" class="question-chip" data-studio-prompt="Show a severity matrix and rank the wards requiring attention." data-studio-all>Compare wards</button>
      <button type="button" class="question-chip" data-studio-prompt="Show whether faecal coliform exceedances are persistent over 28 days." data-studio-all>Persistence</button></div>
      <span class="studio-status" data-state="ready" aria-live="polite">Live</span><button class="button small" type="button" data-studio-stop hidden>Stop</button><button class="button primary" type="submit">Investigate</button></div>
    </form><div class="studio-tooltip" aria-hidden="true"></div></section>`;
  const feed = root.querySelector(".studio-feed");
  const question = root.querySelector("textarea"), scope = root.querySelector("select");
  const form = root.querySelector("form"), status = root.querySelector(".studio-status");
  const tip = root.querySelector(".studio-tooltip");
  const setStatus = (stateName, label) => { status.dataset.state = stateName; status.textContent = label; };
  let controller = null, previousRole = state.role;
  const allowed = () => apiMode === "live" && state.role === "analyst";
  const add = (target, html) => {
    const container = document.createElement("div"); container.innerHTML = html;
    const node = container.firstElementChild; target.append(node);
    feed.scrollTop = feed.scrollHeight; return node;
  };
  function sync() {
    const site = state.summary?.sites?.find(item => item.id === state.selectedSiteId);
    root.querySelector("#studio-station").textContent = scope.value === "all" ? "District-wide comparison" : site?.name || state.selectedSiteId || "Select a station";
    root.querySelector("#studio-notice").innerHTML = apiMode !== "live"
      ? '<span>Studio investigates live FHIR data.</span> <a href="/studio">Open live Studio</a>'
      : state.role !== "analyst" ? "Switch to the Analyst persona to investigate." : "";
    const disabled = !allowed() || Boolean(controller) || (scope.value === "station" && !state.selectedSiteId);
    question.disabled = !allowed();
    form.querySelector('[type="submit"]').disabled = disabled;
    root.querySelectorAll("[data-studio-prompt]").forEach(button => { button.disabled = disabled; });
    root.querySelector("[data-studio-new]").disabled = Boolean(controller);
    root.querySelector("[data-studio-stop]").hidden = !controller;
  }
  async function run() {
    if (!allowed() || controller || !question.value.trim()) return;
    const text = question.value.trim(), siteId = scope.value === "station" ? state.selectedSiteId : null;
    if (scope.value === "station" && !siteId) return;
    const runNode = document.createElement("section"); runNode.className = "studio-run";
    const stationName = root.querySelector("#studio-station").textContent;
    feed.querySelector(".studio-welcome")?.remove(); feed.append(runNode);
    add(runNode, `<div class="studio-ask"><small>${esc(stationName)}</small><p>${esc(text)}</p></div>`);
    const activity = add(runNode, '<div class="studio-working">Starting investigation…</div>');
    const draw = createChartRenderer({ add: html => add(runNode, html), tip });
    question.value = ""; controller = new AbortController(); setStatus("running", "Investigating"); sync();
    let session = null, finished = false;
    try {
      const response = await studioRequest("run", { body: { question: text, siteId }, signal: controller.signal });
      await readStudioEvents(response, event => {
        if (event.type === "start") { session = event.session; runNode.dataset.session = session; }
        if (event.type === "thinking") add(runNode, `<div class="studio-thinking">${md(event.text)}</div>`);
        if (event.type === "tool_start") activity.textContent = `Retrieving evidence: ${event.tool}`;
        if (event.type === "tool_done") {
          const urls = (event.urls || []).filter(url => /^https?:\/\//i.test(url));
          add(runNode, `<details class="studio-tool"><summary>${esc(event.tool)} <span>${esc(event.summary || "Completed")}</span></summary>
            <pre>${esc(JSON.stringify(event.arguments || {}, null, 2))}</pre>${urls.map(url => `<a href="${esc(url)}" target="_blank" rel="noopener">FHIR evidence ↗</a>`).join(" ")}</details>`);
        }
        if (event.type === "render") draw(event.spec);
        if (event.type === "answer") {
          const grounding = event.grounding || {};
          const label = grounding.grounded && grounding.figures_checked > 0 ? `${grounding.figures_checked} figures verified`
            : grounding.grounded ? "No figures to verify" : "Some figures could not be verified";
          add(runNode, `<div class="studio-answer">${md(event.text)}<div class="studio-grounding">${esc(label)}<p>${esc(grounding.not_covered || "")}</p></div></div>`);
        }
        if (event.type === "error") { finished = true; throw new Error(event.message || "Investigation failed"); }
        if (event.type === "done") {
          finished = true;
          if (!session) throw new Error("The investigation did not return a report session.");
          const params = new URLSearchParams({ days: "28" }); if (siteId) params.set("site_id", siteId);
          add(runNode, `<div class="studio-downloads"><button type="button" class="button small" data-studio-executive>Executive report</button>
            <a class="button small" href="/api/live/studio/transcript/${encodeURIComponent(session)}" target="_blank" rel="noopener">Transcript ↗</a>
            <a class="button small" href="/api/live/studio/export/readings?${params}">Readings CSV</a>
            <a class="button small" href="/api/live/studio/export/surveillance?days=90">Health CSV</a>
            ${siteId ? `<a class="button small" href="/api/live/studio/export/fhir?${params}">FHIR Bundle</a>` : ""}</div>`);
        }
      });
      if (!finished) throw new Error("The investigation ended before completion. Please retry.");
      setStatus("complete", "Live");
    } catch (error) {
      const message = error.name === "AbortError" ? "Investigation stopped. You can start another question." : error.message;
      add(runNode, `<div class="notice error">${esc(message)}</div>`);
      setStatus("error", "Error");
    } finally {
      activity.remove(); controller = null; sync();
      if (state.route === "studio" && !question.disabled) question.focus();
    }
  }
  async function executive(button) {
    const runNode = button.closest(".studio-run"), session = runNode.dataset.session;
    button.disabled = true; button.textContent = "Preparing report…";
    const figures = [...runNode.querySelectorAll(".viz")].flatMap(chart => {
      const svg = chart.querySelector("svg"); if (!svg) return [];
      const clone = svg.cloneNode(true), originals = [svg, ...svg.querySelectorAll("*")];
      [clone, ...clone.querySelectorAll("*")].forEach((node, i) => {
        const style = getComputedStyle(originals[i]);
        for (const property of ["fill", "stroke", "stroke-width", "font-size", "font-family", "font-weight", "stroke-dasharray"]) {
          node.style.setProperty(property, style.getPropertyValue(property));
          if (node.getAttribute(property)?.includes("var(")) node.removeAttribute(property);
        }
      });
      return [{ title: chart.querySelector(".viz-t")?.textContent, caption: chart.querySelector(".viz-c")?.textContent, svg: clone.outerHTML }];
    });
    try {
      const response = await studioRequest("executive", { body: { session, figures } });
      downloadBlob(await response.blob(), `surveillance-report-${session}.html`);
      toast("Report downloaded. Open it and print to save as PDF.");
    } catch (error) { toast(error.message, "error"); }
    finally { button.disabled = false; button.textContent = "Executive report"; }
  }
  root.addEventListener("click", event => {
    if (event.target.closest("[data-studio-stop]")) controller?.abort();
    if (event.target.closest("[data-studio-new]") && !controller) { feed.replaceChildren(); setStatus("ready", "Live"); question.focus(); }
    const prompt = event.target.closest("[data-studio-prompt]");
    if (prompt) { if (prompt.hasAttribute("data-studio-all")) scope.value = "all"; question.value = prompt.dataset.studioPrompt; sync(); question.focus(); }
    const report = event.target.closest("[data-studio-executive]"); if (report) executive(report);
  });
  form.addEventListener("submit", event => { event.preventDefault(); run(); });
  question.addEventListener("keydown", event => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); run(); } });
  scope.addEventListener("change", sync);
  subscribe(() => {
    if (previousRole !== state.role) { controller?.abort(); feed.replaceChildren(); previousRole = state.role; }
    if (state.route !== "studio") tip.classList.remove("on");
    sync();
  });
  sync();
}
