import { formatRelative } from "../lib/format.js";

/** Badge label and banner text for an analysis served from the cache. */
export function cachedBadgeText(reason, cachedAt) {
  const time = cachedAt ? ` from ${formatRelative(cachedAt)}` : "";
  const label = `Cached analysis${time}`;
  if (reason === "rate_limited") {
    return { label, action: "AI rate limit hit, showing your last successful analysis. Retry in a minute." };
  }
  if (reason === "ai_unavailable") {
    return { label, action: "AI is temporarily unavailable, showing your last successful analysis. Retry shortly." };
  }
  return { label, action: null };
}
