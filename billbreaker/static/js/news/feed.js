import { getJSON } from "../lib/api.js";

const POLL_MS = 60_000;

/**
 * Loads /api/news now and every minute after, calling onChange with
 * { items, loading, fetching, error } each time anything changes.
 */
export function startFeed(onChange) {
  const state = { items: [], loading: true, fetching: false, error: null };
  const emit = () => onChange({ ...state });

  async function load() {
    state.fetching = true;
    emit();
    for (let attempt = 0; attempt < 3; attempt++) {
      try {
        const data = await getJSON("/api/news");
        state.items = data.items ?? [];
        state.error = data.error ?? null;
        break;
      } catch {
        state.error = "Could not load live headlines";
      }
    }
    state.loading = false;
    state.fetching = false;
    emit();
  }

  load();
  setInterval(load, POLL_MS);
  return { refresh: load };
}

export function newestFirst(items) {
  return [...items].sort((a, b) => (Date.parse(b.pubDate) || 0) - (Date.parse(a.pubDate) || 0));
}

/** Headlines inside the time window, in the chosen order. */
export function filterHeadlines(items, sort, timeframe) {
  const now = Date.now();
  const cutoff = timeframe === "24h" ? now - 86_400_000 : timeframe === "week" ? now - 7 * 86_400_000 : 0;
  const kept = items.filter((it) => {
    if (!cutoff) return true;
    const t = new Date(it.pubDate).getTime();
    return !isNaN(t) && t >= cutoff;
  });
  kept.sort((a, b) => {
    const ta = new Date(a.pubDate).getTime() || 0;
    const tb = new Date(b.pubDate).getTime() || 0;
    return sort === "newest" ? tb - ta : ta - tb;
  });
  return kept;
}
