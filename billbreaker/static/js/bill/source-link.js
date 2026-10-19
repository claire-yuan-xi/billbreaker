import { hostOf, isSafeExternalUrl } from "../lib/safe-link.js";

/** Shows the official source link, or a struck-through note when the host is not verified. */
export function showSourceLink(root, url) {
  const link = root.querySelector("[data-source-link]");
  const blocked = root.querySelector("[data-source-blocked]");
  if (!url) return;
  const safe = isSafeExternalUrl(url);
  link.classList.toggle("hidden", !safe);
  blocked.classList.toggle("hidden", safe);
  if (safe) {
    link.href = url;
    link.title = `Opens ${hostOf(url)} in a new tab`;
  } else {
    const host = hostOf(url);
    blocked.title = host
      ? `Link to ${host} blocked, host is not on the verified source allowlist.`
      : "Link blocked, invalid or unverified URL.";
  }
}
