// Abuse monitoring: loads recent rate-limit events with the admin token, which
// stays in this tab's sessionStorage only.

import { $, cloneTemplate, setText, slot, show } from "../lib/dom.js";
import { postJSON } from "../lib/api.js";

const KEY = "abuse-admin-token";
const REASON_STYLE = {
  limit_exceeded: "bg-destructive/15 text-destructive",
  store_error: "bg-amber-500/15 text-amber-700",
  near_limit: "bg-muted text-muted-foreground",
};

const form = $("[data-abuse-form]");
const input = $("[data-abuse-token]");
const button = $("[data-abuse-load]");
const errorBox = $("[data-abuse-error]");
const table = $("[data-abuse-table]");
const rows = $("[data-abuse-rows]");

function storeToken(value) {
  try {
    sessionStorage.setItem(KEY, value);
  } catch {
    // private mode: the token just won't persist
  }
}

function renderRow(e) {
  const row = cloneTemplate("tpl-abuse-row");
  setText(row, "ts", new Date(e.ts).toLocaleString());
  const reason = setText(row, "reason", e.reason);
  reason.className += ` ${REASON_STYLE[e.reason] || ""}`;
  setText(row, "identifier", e.identifier);
  setText(row, "endpoint", e.endpoint || "");
  setText(row, "count", e.count != null && e.limit_value != null ? `${e.count} / ${e.limit_value}` : "");
  setText(row, "window", e.window_seconds ? `${e.window_seconds}s` : "");
  slot(row, "identifier").title = e.identifier;
  return row;
}

async function load() {
  button.disabled = true;
  show(errorBox, false);
  try {
    const data = await postJSON("/api/admin/abuse-events", { token: input.value, limit: 200 });
    if (!data.ok) throw new Error(data.error);
    storeToken(input.value);
    rows.replaceChildren(...data.events.map(renderRow));
    if (!data.events.length) {
      const empty = document.createElement("tr");
      empty.innerHTML = '<td colspan="6" class="px-3 py-6 text-center text-muted-foreground">No events recorded.</td>';
      rows.replaceChildren(empty);
    }
    show(table, true);
  } catch (err) {
    errorBox.textContent = err.message || "Failed to load.";
    show(errorBox, true);
  } finally {
    button.disabled = input.value.length < 16;
  }
}

try {
  input.value = sessionStorage.getItem(KEY) || "";
} catch {
  // ignore
}
button.disabled = input.value.length < 16;
input.addEventListener("input", () => (button.disabled = input.value.length < 16));
form.addEventListener("submit", (event) => {
  event.preventDefault();
  load();
});
if (input.value.length >= 16) load();
