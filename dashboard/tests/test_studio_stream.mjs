import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

// Import just the parser; its ApiError import is exercised by the adapter tests.
const source = (await readFile(new URL("../static/js/studio-api.js", import.meta.url), "utf8"))
  .replace('import { ApiError } from "./api.js";', "class ApiError extends Error {}");
const { readStudioEvents, studioRequest } = await import(`data:text/javascript;base64,${Buffer.from(source).toString("base64")}`);

function response(bytes) {
  return new Response(new ReadableStream({ start(controller) { for (const chunk of bytes) controller.enqueue(chunk); controller.close(); } }), { headers: { "content-type": "text/event-stream" } });
}

test("SSE handles one-byte UTF-8 chunks, CRLF, comments, and trailing frame", async () => {
  const wire = ': heartbeat\r\n\r\ndata: {"type":"thinking","text":"Mondego → Yamuna"}\r\n\r\ndata: {"type":"done"}';
  const events = [];
  await readStudioEvents(response([...new TextEncoder().encode(wire)].map(byte => new Uint8Array([byte]))), event => events.push(event));
  assert.deepEqual(events, [{ type: "thinking", text: "Mondego → Yamuna" }, { type: "done" }]);
});

test("SSE dispatches an event before the next chunk is available", async () => {
  let send;
  const events = [];
  const stream = new ReadableStream({ start(controller) { send = controller; } });
  const reading = readStudioEvents(new Response(stream, { headers: { "content-type": "text/event-stream" } }), event => events.push(event));
  send.enqueue(new TextEncoder().encode('data: {"type":"start"}\n\n'));
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.deepEqual(events, [{ type: "start" }]);
  send.enqueue(new TextEncoder().encode('data: {"type":"done"}\n\n')); send.close();
  await reading;
  assert.equal(events[1].type, "done");
});

test("invalid stream types and malformed events fail visibly", async () => {
  await assert.rejects(readStudioEvents(new Response("{}"), () => {}), /invalid stream/);
  await assert.rejects(readStudioEvents(response([new TextEncoder().encode('data: bad-json\n\n')]), () => {}), SyntaxError);
});

test("Studio requests stay on the dashboard origin and propagate abort signals", async () => {
  const controller = new AbortController();
  globalThis.fetch = async (url, options) => {
    assert.equal(url, "/api/live/studio/run");
    assert.equal(options.signal, controller.signal);
    assert.deepEqual(JSON.parse(options.body), { question: "Scan", siteId: "yam-ito" });
    return new Response("", { status: 200 });
  };
  await studioRequest("run", { body: { question: "Scan", siteId: "yam-ito" }, signal: controller.signal });
  globalThis.fetch = async () => new Response('{"detail":"Gateway unavailable"}', { status: 502 });
  await assert.rejects(studioRequest("run", { body: { question: "Scan" } }), /Gateway unavailable/);
});
