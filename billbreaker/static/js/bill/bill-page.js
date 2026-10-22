import { postJSON } from "../lib/api.js";
import { saveRecent } from "../lib/recent.js";
import { wirePress } from "../lib/press.js";
import { readProfile } from "../lib/reader-profile.js";
import { cachedBadgeText } from "./cached-badge.js";
import { initPublish, initShareLink } from "./publish.js";
import { initReaderStrip } from "./reader-strip.js";
import { initSaveToggle } from "./save-toggle.js";
import { showSourceLink } from "./source-link.js";
import { runExplain } from "./stream.js";

const SOURCE_LABELS = { "congress.gov": "Congress.gov", govinfo: "GovInfo", openstates: "OpenStates" };
const SHARE_KEYS = {
  quick_take: "quick",
  winners_losers: "wl",
  citations: "citations",
  supporters_vs_critics: "sc",
  status_quo_diff: "sq",
};
const MIN_TEXT = 200;

/** The bill page: header from /api/bill-meta, then the streamed AI breakdown. */
export function initBillPage(page) {
  const params = new URLSearchParams(window.location.search);
  const state = params.get("state") || "US";
  const number = params.get("number") || "";
  const text = params.get("text") || "";
  const q = (sel) => page.querySelector(sel);
  const header = q("[data-bill-header]");
  const ai = q("[data-ai]");

  const model = { meta: null, title: null, sourceUrl: null, sections: {}, done: false, error: false };
  const title = () => model.title || model.meta?.id || `${state} ${number}`.trim() || "Bill";

  initReaderStrip(q("[data-reader-strip]"));
  const save = number ? initSaveToggle(q("[data-save-wrap]"), state, number, title) : null;
  if (number) initShareLink(q("[data-share-link]"));

  function renderHeader() {
    if (!model.meta && !model.title) return;
    header.classList.remove("hidden");
    q("[data-jurisdiction]").textContent = state === "US" ? "United States Federal" : state;
    q("[data-bill-id]").textContent = model.meta?.id || `${state} ${number}`.trim() || "pasted bill";
    q("[data-bill-title]").textContent = title();
    document.title = `BillBreaker | ${title()}`;
    showSourceLink(header, model.sourceUrl || model.meta?.sourceUrl || "");
    save?.refresh();
  }

  async function loadMeta() {
    q("[data-meta-error]").classList.add("hidden");
    try {
      model.meta = await postJSON("/api/bill-meta", { state, billNo: number, hasText: text.trim().length >= MIN_TEXT });
      const notice = q("[data-meta-notice]");
      if (model.meta.notice && !model.sections.quick_take) {
        notice.textContent = model.meta.notice;
        notice.classList.remove("hidden");
      }
      renderHeader();
    } catch {
      q("[data-meta-error]").classList.remove("hidden");
    }
  }
  q("[data-meta-retry]").addEventListener("click", loadMeta);
  q("[data-reload]").addEventListener("click", () => window.location.reload());

  let started = 0;
  let ticker = 0;

  // A big status box with a running seconds count, so it is obvious the AI is working.
  function setStatus(message) {
    const status = q("[data-ai-status]");
    const elapsed = q("[data-ai-elapsed]");
    status.classList.toggle("hidden", !message);
    status.classList.toggle("flex", !!message);
    q("[data-ai-status-text]").textContent = message || "";
    if (!message) {
      clearInterval(ticker);
      ticker = 0;
      return;
    }
    ai.classList.remove("hidden");
    if (!ticker) {
      started = Date.now();
      elapsed.textContent = "0s";
      ticker = setInterval(() => {
        elapsed.textContent = `${Math.round((Date.now() - started) / 1000)}s`;
      }, 1000);
    }
  }

  function showMeta(p) {
    if (typeof p.title === "string") model.title = p.title;
    if (typeof p.sourceUrl === "string") model.sourceUrl = p.sourceUrl;
    if (p.cached) {
      const badge = cachedBadgeText(p.cached_reason ?? null, p.cached_at ?? null);
      const label = q("[data-cached-label]");
      label.textContent = `· ${badge.label}`;
      label.classList.remove("hidden");
      if (badge.action) {
        q("[data-cached-text]").textContent = badge.action;
        q("[data-cached-action]").classList.replace("hidden", "flex");
      }
    }
    if (p.source) {
      const note = q("[data-source-note]");
      note.textContent =
        p.source === "web" ? "Looked up on the web" : `Text from ${SOURCE_LABELS[p.source] ?? p.source}`;
      note.classList.remove("hidden");
    }
    if (number && model.title) saveRecent({ state, number, title: model.title, ts: Date.now() });
    renderHeader();
  }

  function onEvent(event, payload) {
    if (event === "status") return setStatus(payload.message);
    if (event === "meta") return showMeta(payload);
    if (event === "error") {
      model.error = true;
      setStatus(null);
      const box = q("[data-ai-error]");
      box.textContent = payload.message || "AI error";
      box.classList.remove("hidden");
      ai.classList.remove("hidden");
      return;
    }
    if (event === "done") {
      model.done = true;
      setStatus(null);
      if (number && !model.error) initPublish(q("[data-publish-wrap]"), shareBody);
      return;
    }
    // Written for this reader from their answers, so it is never published with the rest.
    if (event === "for_you") {
      q('[data-block="for_you"]').innerHTML = payload.html;
      return;
    }
    if (event in SHARE_KEYS) {
      const { html, ...data } = payload;
      model.sections[event] = data;
      q(`[data-block="${event}"]`).innerHTML = html;
      q("[data-meta-notice]").classList.add("hidden");
      ai.classList.remove("hidden");
    }
  }

  function shareBody() {
    const payload = {};
    for (const [event, key] of Object.entries(SHARE_KEYS)) payload[key] = model.sections[event] ?? null;
    return {
      state,
      bill_no: number,
      title: title(),
      source_url: model.sourceUrl || model.meta?.sourceUrl || null,
      payload,
    };
  }

  wirePress(page);
  loadMeta();
  if (number || text.trim().length >= MIN_TEXT) {
    setStatus(number && text.trim().length < MIN_TEXT ? "Fetching the bill" : "Reading the bill");
    runExplain({ state, billNo: number, text, profile: readProfile() }, onEvent);
  }
}
