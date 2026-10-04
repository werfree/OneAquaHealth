import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../static/js/state.js", import.meta.url), "utf8");
const appSource = await readFile(new URL("../static/js/app.js", import.meta.url), "utf8");
let sequence = 0;

async function routes(pathname, hash) {
  globalThis.window = { location: { pathname, hash } };
  globalThis.document = { documentElement: { dataset: { theme: "aqua" } } };
  globalThis.sessionStorage = { getItem: () => null };
  return import(`data:text/javascript;base64,${Buffer.from(`${source}\n// ${sequence++}`).toString("base64")}`);
}

test("direct Studio and dashboard hashes select the correct page", async () => {
  for (const [pathname, hash, expected] of [
    ["/", "", "overview"], ["/studio", "", "studio"], ["/", "#studio", "studio"],
    ["/studio", "#overview", "overview"], ["/", "#ingestion", "ingestion"],
    ["/", "#reports", "reports"], ["/", "#unknown", "overview"],
  ]) assert.equal((await routes(pathname, hash)).state.route, expected);
});

test("browser history location can be resolved without resetting station state", async () => {
  const { state, setState, routeFromLocation } = await routes("/", "#studio");
  setState({ selectedSiteId: "yam-ito" });
  window.location.hash = "#overview";
  setState({ route: routeFromLocation() });
  assert.equal(state.route, "overview");
  assert.equal(state.selectedSiteId, "yam-ito");
});

test("dashboard renders the summary before waiting for selected-station data", () => {
  const bootstrap = appSource.slice(appSource.indexOf("async function bootstrap"), appSource.indexOf("async function loadSite"));
  const summaryReady = bootstrap.indexOf("setState({ session, summary, selectedSiteId, loading: false });");
  const progressiveRender = bootstrap.indexOf("render();", summaryReady);
  const stationLoad = bootstrap.indexOf("await loadSite(selectedSiteId, false);", summaryReady);
  assert.ok(summaryReady >= 0);
  assert.ok(progressiveRender > summaryReady);
  assert.ok(stationLoad > progressiveRender);
  assert.match(appSource, /current \? renderSiteWorkspace\(current\) : state\.error \? errorState\(state\.error, "Selected station"\)/);
});
