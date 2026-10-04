import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../static/js/ingestion.js", import.meta.url), "utf8");
const { prepareUpload, fileRun, MAX_FILE_BYTES } = await import(`data:text/javascript;base64,${Buffer.from(source).toString("base64")}`);
const file = (name, text) => ({ name, size: Buffer.byteLength(text), arrayBuffer: async () => Buffer.from(text) });

test("file preparation validates UTF-8, file type, JSON shape and size", async () => {
  const upload = await prepareUpload(file("sensor.json", '\uFEFF{"source_type":"IOT_TELEMETRY"}'));
  assert.equal(upload.kind, "json");
  assert.equal(upload.sourceType, "IOT_TELEMETRY");
  assert.equal(JSON.parse(upload.text).source_type, "IOT_TELEMETRY");
  const csv = await prepareUpload(file("health.CSV", "event_id,city\n" + "x".repeat(5000)));
  assert.equal(csv.kind, "csv");
  assert.equal(csv.preview.length, 4000);
  assert.equal(csv.truncated, true);
  await assert.rejects(prepareUpload(file("health.xlsx", "x")), /json or .csv/);
  await assert.rejects(prepareUpload(file("empty.csv", "")), /empty/);
  await assert.rejects(prepareUpload(file("bad.json", "{")), /invalid JSON/);
  await assert.rejects(prepareUpload(file("list.json", "[]")), /one ingestion event/);
  await assert.rejects(prepareUpload(file("unknown.json", '{"source_type":"UNKNOWN"}')), /source_type/);
  await assert.rejects(prepareUpload({ name: "large.csv", size: MAX_FILE_BYTES + 1 }), /5 MiB/);
  await assert.rejects(prepareUpload({ name: "bad.csv", size: 1, arrayBuffer: async () => new Uint8Array([255]) }), /UTF-8/);
});

const upload = { name: "health.csv", kind: "csv", sourceType: "PUBLIC_HEALTH", size: 10, preview: "example" };
const event = { event_id: "test", site_id: "site-c1-mondego", source_type: "PUBLIC_HEALTH", fhir: "UPLOADED", uploaded: 4, failed: 0, alert: null };

test("acceptance alone never marks a file as uploaded", () => {
  const built = fileRun(upload, { events: [{ ...event, fhir: "BUILT_NOT_SENT", uploaded: 0 }] });
  assert.equal(built.persisted, false);
  assert.equal(built.fhirOutcome, "BUILT_NOT_SENT");
  assert.equal(built.stages.at(-1).status, "warning");
  assert.equal(built.hasWrites, false);
  const accepted = fileRun(upload, { status: "ACCEPTED" });
  assert.equal(accepted.persisted, false);
  assert.equal(accepted.executionStatus, "failed");
  const success = fileRun(upload, { events: [event] });
  assert.equal(success.persisted, true);
  assert.equal(success.hasWrites, true);
});

test("partial batch errors retain successful events and failed counts", () => {
  const result = fileRun(upload, { detail: { events: [event, { ...event, event_id: "failed", fhir: "UPLOAD_FAILED", uploaded: 0, failed: 4 }] } }, true);
  assert.equal(result.executionStatus, "failed");
  assert.equal(result.persisted, false);
  assert.equal(result.hasWrites, true);
  assert.equal(result.events.length, 2);
  assert.equal(result.events[1].failed, 4);
  assert.equal(result.stages.at(-1).status, "failed");
  const conversion = fileRun(upload, { detail: { ...event, fhir: "CONVERSION_FAILED", uploaded: 0 } }, true);
  assert.equal(conversion.fhirOutcome, "CONVERSION_FAILED");
});
