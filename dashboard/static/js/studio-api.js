import { ApiError } from "./api.js";

export async function studioRequest(path, { body, signal } = {}) {
  const response = await fetch(`/api/live/studio/${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body), signal,
  });
  if (!response.ok) {
    const details = await response.json().catch(() => ({}));
    throw new ApiError(typeof details.detail === "string" ? details.detail : `Studio request failed (${response.status})`, response.status, details);
  }
  return response;
}

// Parse frames across arbitrary transport chunks, including split UTF-8/CRLF.
export async function readStudioEvents(response, onEvent) {
  if (!response.body || !response.headers.get("content-type")?.includes("text/event-stream")) {
    throw new Error("The surveillance service returned an invalid stream.");
  }
  const reader = response.body.getReader(), decoder = new TextDecoder();
  let buffer = "";
  const dispatch = frame => {
    const data = frame.split(/\r?\n/).filter(line => line.startsWith("data:"))
      .map(line => line.slice(5).replace(/^ /, "")).join("\n");
    if (data) onEvent(JSON.parse(data));
  };
  try {
    while (true) {
      const { done, value } = await reader.read();
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true });
      let boundary;
      while ((boundary = /\r?\n\r?\n/.exec(buffer))) {
        dispatch(buffer.slice(0, boundary.index));
        buffer = buffer.slice(boundary.index + boundary[0].length);
      }
      if (done) { if (buffer.trim()) dispatch(buffer); break; }
    }
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}
