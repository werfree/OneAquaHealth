export function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

export function formatDate(value, options = {}) {
  if (!value) return "Unavailable";
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return value;
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit", month: "short", year: "numeric", hour: options.dateOnly ? undefined : "2-digit",
    minute: options.dateOnly ? undefined : "2-digit", timeZone: "UTC", timeZoneName: options.dateOnly ? undefined : "short",
  }).format(date);
}

export function humanBytes(bytes) {
  if (!Number.isFinite(bytes)) return "—";
  if (bytes < 1024) return `${bytes} B`;
  return `${(bytes / 1024).toFixed(1)} KB`;
}

export function statusPill(value, label = null) {
  const normalized = String(value || "unknown").toLowerCase().replaceAll(" ", "-");
  return `<span class="status ${escapeHtml(normalized)}">${escapeHtml(label || String(value || "Unknown").replaceAll("_", " "))}</span>`;
}

export function valueDisplay(observation) {
  if (observation.value !== undefined && observation.value !== null) {
    return `${escapeHtml(observation.value)}${observation.unit ? ` <small>${escapeHtml(observation.unit)}</small>` : ""}`;
  }
  return escapeHtml(observation.codedValue || "Not available");
}

export function emptyState(title, text, action = "") {
  return `<div class="empty-state"><h3>${escapeHtml(title)}</h3><p>${escapeHtml(text)}</p>${action}</div>`;
}

export function errorState(error, context = "This view") {
  const message = error?.message || "An unexpected error occurred.";
  const guidance = {
    400: "The request was not valid.",
    401: "The session is no longer authorized.",
    403: "This capability is restricted.",
    404: "The requested record is unavailable in the current scope.",
    409: "The requested action conflicts with the current state.",
    422: "The submitted value did not pass validation.",
    501: "The backend does not implement this capability.",
    502: "The connected service is unavailable.",
    503: "The capability is temporarily unavailable.",
  }[error?.status] || (error?.status === 0 ? "The network request did not complete." : "");
  return `<div class="notice error"><strong>${escapeHtml(context)} is unavailable.</strong> ${escapeHtml(guidance)} ${escapeHtml(message)}</div>`;
}

export function jsonBlock(value) {
  return `<pre tabindex="0">${escapeHtml(JSON.stringify(value ?? null, null, 2))}</pre>`;
}

export function copyButton(label = "Copy JSON") {
  return `<button class="button small" type="button" data-copy-payload>${escapeHtml(label)}</button>`;
}

export function toast(message, kind = "info") {
  const root = document.querySelector("#toast-root");
  const item = document.createElement("div");
  item.className = `toast ${kind}`;
  item.textContent = message;
  root.append(item);
  window.setTimeout(() => item.remove(), 3600);
}

export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
