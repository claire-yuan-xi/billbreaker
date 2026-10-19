// Runs the AI breakdown: server-sent events first, one JSON call as the fallback.

const SECTIONS = ["quick_take", "winners_losers", "citations", "supporters_vs_critics", "status_quo_diff"];
const STALL_MS = 150_000;

/**
 * Calls handlers.on(event, payload) for status, meta, each section, error and done.
 * Each section payload carries its data plus rendered html.
 */
export async function runExplain(request, on) {
  // Some proxies buffer SSE until the end. Only give up after the server itself would have,
  // so a slow analysis is not run twice.
  const ctrl = new AbortController();
  let gotAny = false;
  const stall = setTimeout(() => !gotAny && ctrl.abort(), STALL_MS);
  try {
    const res = await fetch("/api/explain-bill", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
      signal: ctrl.signal,
    });
    if (!res.ok || !res.body) {
      clearTimeout(stall);
      return runJson(request, on, `HTTP ${res.status}`);
    }
    const retry = await readEvents(res.body, (event, payload) => {
      gotAny = true;
      on(event, payload);
    });
    clearTimeout(stall);
    if (retry) await runJson(request, on, "retrying");
  } catch (e) {
    clearTimeout(stall);
    const reason = e instanceof Error ? e.message : "Network error";
    if (!gotAny) await runJson(request, on, reason);
    else on("error", { message: reason });
  }
}

/** Parses an SSE body. Returns true when the server asks for the JSON fallback. */
async function readEvents(body, emit) {
  const reader = body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  let event = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) return false;
    buf += dec.decode(value, { stream: true });
    let nl;
    while ((nl = buf.indexOf("\n")) !== -1) {
      const line = buf.slice(0, nl).replace(/\r$/, "");
      buf = buf.slice(nl + 1);
      if (line === "") event = "";
      else if (line.startsWith("event: ")) event = line.slice(7).trim();
      else if (line.startsWith("data: ")) {
        let payload;
        try {
          payload = JSON.parse(line.slice(6));
        } catch {
          continue;
        }
        if (event === "error" && payload.fallback === "json") return true;
        emit(event, payload);
      }
    }
  }
}

/** One non-streamed call, used when streaming fails. */
async function runJson(request, on, reason) {
  on("status", { message: "Retrying without streaming" });
  try {
    const res = await fetch("/api/explain-bill", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...request, mode: "json" }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      on("error", { message: body.error || `Analysis failed (${res.status}). ${reason}` });
      return;
    }
    const payload = await res.json();
    on("meta", payload);
    for (const key of SECTIONS) {
      if (payload[key]) on(key, { ...payload[key], html: payload.html?.[key] ?? "" });
    }
    on("done", {});
  } catch (e) {
    on("error", { message: e instanceof Error ? e.message : reason });
  }
}
