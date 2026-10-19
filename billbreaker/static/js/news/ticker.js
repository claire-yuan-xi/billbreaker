import { cloneTemplate, setText, show, slot } from "../lib/dom.js";
import { articleHref, cleanTitle, timeAgo } from "../lib/format.js";

/** The scrolling headline bar at the very top of the page. */
export function renderTicker(root, items, loading) {
  const status = root.querySelector("[data-ticker-status]");
  const live = root.querySelector("[data-ticker-live]");
  const ready = !loading && items.length > 0;
  show(status, !ready);
  live.classList.toggle("hidden", !ready);
  live.classList.toggle("flex", ready);
  if (!ready) {
    status.textContent = loading ? "loading live headlines" : "live headlines unavailable";
    return;
  }
  // Two copies back to back so the marquee loops without a gap; the copy is hidden from readers.
  const loop = [...items, ...items].map((it, i) => {
    const a = cloneTemplate("tpl-ticker-item");
    slot(a, "link").href = articleHref(it.link);
    setText(a, "time", timeAgo(it.pubDate));
    setText(a, "title", cleanTitle(it.title));
    if (i >= items.length) {
      a.tabIndex = -1;
      a.setAttribute("aria-hidden", "true");
    }
    return a;
  });
  root.querySelector("[data-ticker-track]").replaceChildren(...loop);
}
