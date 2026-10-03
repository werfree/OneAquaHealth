// Run with `node --test dashboard/tests/test_api.mjs`; no browser or network.
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../static/js/api.js", import.meta.url), "utf8");
let sequence = 0;

async function adapter({ search = "", pathname = "/", defaultMode = "mock", respond = () => ({}) } = {}) {
  globalThis.window = { location: { search, pathname } };
  globalThis.document = { documentElement: { dataset: { defaultMode } } };
  const calls = [];
  globalThis.fetch = async (path, options) => {
    calls.push({ path, ...options });
    return { ok: true, json: async () => respond(path) };
  };
  const module = await import(`data:text/javascript;base64,${Buffer.from(`${source}\n// test ${sequence++}`).toString("base64")}`);
  return { ...module, calls };
}

const station = {
  site_id: "site-c1-mondego", name: "Mondego C1", city: "coimbra",
  environmental_reading_count: 2, health_measure_count: 1,
  observed_at: "2026-10-01T10:00:00+00:00", co_location: true,
  environmental_observations: [
    { id: "nitrate-1", indicator: "nitrate", value: 14.2, unit: "mg/L", when: "2026-09-30T10:00:00+00:00" },
    { id: "survey-1", indicator: "waterAspect", coded_value: "foamy" },
  ],
  health_observations: [{ id: "risk-1", indicator: "risk", value: 0.8, unit: "{score} (HIGH)", cohort: "cohort-1", when: "2026-10-01T10:00:00+00:00" }],
  exceedances: [{ observation_id: "nitrate-1", indicator: "nitrate", value: 14.2, unit: "mg/L", threshold: 11.3, exceedance_factor: 1.26, basis: "screening basis" }],
  elevated_risks: [{ indicator: "risk", score: 0.8, interpretation: "HIGH", cohort: "cohort-1" }],
  caveat: "Association only, not causation.",
};

test("explicit mode overrides server default and mock stays the fallback", async () => {
  for (const [search, defaultMode, expected] of [
    ["", "live", "live"], ["?mode=mock", "live", "mock"],
    ["?mode=live", "mock", "live"], ["", undefined, "mock"], ["?mode=invalid", "live", "mock"],
  ]) {
    assert.equal((await adapter({ search, defaultMode })).apiMode, expected);
  }
});

test("live summary returns numeric metrics and rereads gateway cache", async () => {
  const { api, calls } = await adapter({ defaultMode: "live", respond: () => ({
    site_count: 1, briefings: [station], sites_with_exceedances: [station.site_id],
    sites_with_co_location: [station.site_id], dataset_tag: "test-tag", fhir_server: "https://fhir.test", generated_at: "now",
  }) });
  const summary = await api.summary("analyst");
  assert.deepEqual(summary.metrics, { sitesInScope: 1, loadedObservations: 3, screeningFindings: 1, coLocatedSites: 1 });
  assert.equal(summary.sites[0].city, "Coimbra");
  assert.equal(summary.sites[0].findingCount, 3);
  assert.equal(summary.sites[0].lastObservedAt, station.observed_at);
  assert.match(summary.scopeLabel, /test-tag.*https:\/\/fhir.test/);
  await api.summary("analyst");
  assert.equal(calls.length, 2);
});

test("live station maps observations, agency scores, screening basis and findings", async () => {
  const { api, calls } = await adapter({ defaultMode: "live", respond: () => station });
  const result = await api.site("analyst", station.site_id);
  assert.equal(calls[0].path, `/api/live/sites/${station.site_id}`);
  assert.equal(result.observations.length, 3);
  const [risk, nitrate, survey] = result.observations;
  assert.equal(risk.unit, "score");
  assert.equal(risk.interpretation, "Agency classification: HIGH");
  assert.equal(risk.resourceRef, "Observation/risk-1");
  assert.equal(nitrate.screeningReference, "screening basis");
  assert.match(nitrate.interpretation, /11.3/);
  assert.equal(survey.codedValue, "foamy");
  assert.equal(result.findings.length, result.site.findingCount);
  assert.equal(result.findings[1].type, "health-watch");
  assert.equal(result.findings[1].severity, "high");
  assert.match(result.findings[0].statement, /screening basis/);
  assert.equal(result.findings[2].caveat, station.caveat);
});

test("live ask sends station context, invalid evidence is rejected, and graph stays unavailable", async () => {
  const { api, calls, ApiError } = await adapter({ defaultMode: "live" });
  await api.ask("analyst", station.site_id, "What needs attention?");
  assert.equal(calls[0].path, "/api/live/ask");
  assert.deepEqual(JSON.parse(calls[0].body), { question: "What needs attention?", siteId: station.site_id });
  await assert.rejects(api.evidence("analyst", "unknown"), error => error instanceof ApiError && error.status === 404);
  await assert.rejects(api.graph(), error => error instanceof ApiError && error.status === 501);
});

test("native Studio defaults to live while explicit mock still wins", async () => {
  assert.equal((await adapter({ pathname: "/studio" })).apiMode, "live");
  assert.equal((await adapter({ pathname: "/studio", search: "?mode=mock" })).apiMode, "mock");
});

test("mock mode retains persona headers and station endpoint", async () => {
  const { api, calls } = await adapter({ search: "?mode=mock", defaultMode: "live" });
  await api.site("viewer", station.site_id);
  assert.equal(calls[0].path, `/api/mock/sites/${station.site_id}`);
  assert.equal(calls[0].headers["X-Demo-Role"], "viewer");
});
