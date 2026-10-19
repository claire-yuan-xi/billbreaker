// Formatting helpers for headlines and saved bills.

export function timeAgo(s) {
  if (!s) return "";
  const d = new Date(s);
  if (isNaN(d.getTime())) return "";
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 60) return `${Math.floor(diff)}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export function formatRelative(iso) {
  const t = new Date(iso).getTime();
  if (!Number.isFinite(t)) return "earlier";
  const diff = Math.max(0, (Date.now() - t) / 1000);
  const plural = (n, unit) => `${n} ${unit}${n === 1 ? "" : "s"} ago`;
  if (diff < 45) return "just now";
  if (diff < 90) return "a minute ago";
  if (diff < 3600) return plural(Math.round(diff / 60), "minute");
  if (diff < 5400) return "an hour ago";
  if (diff < 86400) return plural(Math.round(diff / 3600), "hour");
  if (diff < 172800) return "yesterday";
  if (diff < 7 * 86400) return `${Math.round(diff / 86400)} days ago`;
  if (diff < 30 * 86400) return plural(Math.round(diff / (7 * 86400)), "week");
  return plural(Math.round(diff / (30 * 86400)), "month");
}

export function cleanTitle(t) {
  return t.replace(/ - [^-]+$/, "");
}

// Feed links are decoded to apnews.com on the server; anything else goes through the resolver.
export function articleHref(link) {
  try {
    const host = new URL(link).hostname;
    if (host === "apnews.com" || host.endsWith(".apnews.com")) return link;
  } catch {
    // fall through to the resolver
  }
  return `/api/public/resolve?url=${encodeURIComponent(link)}`;
}

const TOPICS = [
  [/supreme court|justice|court|judge|ruling/i, "Courts"],
  [/senate|senator/i, "Senate"],
  [/\bhouse\b|speaker|representative/i, "House"],
  [/election|midterm|ballot|vote|campaign|primary/i, "Elections"],
  [/budget|tax|tariff|spending|shutdown|debt/i, "Money"],
  [/immigra|border|asylum|deport/i, "Immigration"],
  [/health|medicaid|medicare|abortion|drug/i, "Health"],
  [/school|education|student/i, "Education"],
  [/climate|energy|environment|oil|gas/i, "Environment"],
  [/governor|state|legislature|statehouse/i, "States"],
];

/** Rough topic tag from the headline, so cards are scannable at a glance. */
export function topicFor(title) {
  return TOPICS.find(([re]) => re.test(title))?.[1] ?? "Policy";
}

export function billHref(state, number) {
  const q = new URLSearchParams({ state, number });
  return `/bill?${q}`;
}
