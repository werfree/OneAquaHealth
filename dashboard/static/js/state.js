const listeners = new Set();

export function routeFromLocation() {
  const route = window.location.hash.slice(1);
  return ["overview", "ingestion", "reports", "studio"].includes(route)
    ? route : window.location.pathname === "/studio" ? "studio" : "overview";
}

export const state = {
  route: routeFromLocation(),
  role: sessionStorage.getItem("oah-demo-role") || "analyst",
  theme: document.documentElement.dataset.theme || "aqua",
  themeConfig: null,
  selectedSiteId: null,
  selectedTab: "context",
  selectedRunId: null,
  selectedStageId: "received",
  selectedSampleKey: "iot",
  selectedReportId: null,
  session: null,
  summary: null,
  site: null,
  graph: null,
  runs: null,
  reports: null,
  report: null,
  assistant: null,
  loading: true,
  error: null,
};

export function setState(patch) {
  Object.assign(state, patch);
  listeners.forEach(listener => listener(state));
}

export function subscribe(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function changeRole(role) {
  sessionStorage.setItem("oah-demo-role", role);
  setState({
    role,
    selectedSiteId: null,
    selectedRunId: null,
    selectedReportId: null,
    selectedTab: "context",
    session: null,
    summary: null,
    site: null,
    graph: null,
    runs: null,
    reports: null,
    report: null,
    assistant: null,
    loading: true,
    error: null,
  });
}
