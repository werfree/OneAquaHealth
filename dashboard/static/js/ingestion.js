export const MAX_FILE_BYTES = 5 * 1024 * 1024;

export async function prepareUpload(file) {
  if (!file || !/\.(json|csv)$/i.test(file.name)) throw new Error("Choose a .json or .csv file.");
  if (!file.size) throw new Error("The selected file is empty.");
  if (file.size > MAX_FILE_BYTES) throw new Error("File exceeds the 5 MiB upload limit.");
  let text;
  try { text = new TextDecoder("utf-8", { fatal: true }).decode(await file.arrayBuffer()); }
  catch { throw new Error("The file must be UTF-8 encoded."); }
  const kind = /\.json$/i.test(file.name) ? "json" : "csv";
  let sourceType = "PUBLIC_HEALTH";
  if (kind === "json") {
    let event;
    try { event = JSON.parse(text); } catch { throw new Error("The file contains invalid JSON."); }
    if (!event || Array.isArray(event) || typeof event !== "object") throw new Error("JSON must contain one ingestion event object.");
    if (!["IOT_TELEMETRY", "CITIZEN_SURVEY", "PUBLIC_HEALTH"].includes(event.source_type)) throw new Error("JSON source_type must be IOT_TELEMETRY, CITIZEN_SURVEY, or PUBLIC_HEALTH.");
    sourceType = event.source_type;
  }
  return { name: file.name, size: file.size, kind, sourceType, text, preview: text.slice(0, 4000), truncated: text.length > 4000 };
}

export function fileRun(upload, data, httpFailed = false) {
  const detail = data.detail || data;
  const events = detail.events || [detail];
  const persisted = events.length > 0 && events.every(event => event.fhir === "UPLOADED" && event.failed === 0 && event.uploaded > 0);
  const builtOnly = events.length > 0 && events.every(event => event.fhir === "BUILT_NOT_SENT");
  const failed = httpFailed || events.some(event => ["UPLOAD_FAILED", "CONVERSION_FAILED"].includes(event.fhir));
  const outcome = persisted ? "UPLOADED" : builtOnly ? "BUILT_NOT_SENT" : failed ? "UPLOAD_FAILED" : "UNKNOWN";
  return {
    id: `file-${Date.now()}`, sampleKey: upload.kind, sampleLabel: upload.name, sourceType: upload.sourceType,
    siteId: events[0]?.site_id, executionStatus: failed || outcome === "UNKNOWN" ? "failed" : "completed",
    fhirOutcome: events.some(event => event.fhir === "CONVERSION_FAILED") ? "CONVERSION_FAILED" : outcome,
    startedAt: new Date().toISOString(), progress: 100, events, persisted,
    hasWrites: events.some(event => event.uploaded > 0),
    stages: [
      { id: "received", name: "Received", status: "completed", summary: `${upload.name} · ${upload.kind.toUpperCase()}`, input: { filename: upload.name, bytes: upload.size, preview: upload.preview, truncated: upload.truncated } },
      { id: "validated", name: "Validated", status: "completed", summary: `${events.length} event(s) passed gateway validation`, output: events.map(event => ({ event_id: event.event_id, site_id: event.site_id, source_type: event.source_type })) },
      { id: "screened", name: "Screened", status: events.some(event => event.alert) ? "warning" : "completed", summary: "Gateway threshold screening results", output: events.map(event => ({ event_id: event.event_id, alert: event.alert })) },
      { id: "upsert", name: "FHIR outcome", status: persisted ? "completed" : builtOnly ? "warning" : "failed", summary: persisted ? "All event resources uploaded" : builtOnly ? "FHIR resources built; upload is disabled" : "Some resources were not confirmed uploaded", output: events,
        errors: failed ? ["Inspect each event's FHIR outcome and failed resource count. Successful events in a partial batch may already be persisted."] : [] },
    ],
  };
}
