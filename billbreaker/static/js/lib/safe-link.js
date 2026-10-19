// Outbound links are only shown for verified legislative and news sources.

const ALLOWED_HOSTS = [
  "congress.gov",
  "legiscan.com",
  "ap.org",
  "apnews.com",
  "news.google.com",
  "google.com",
  "senate.gov",
  "house.gov",
  "govinfo.gov",
];

export function isSafeExternalUrl(input) {
  try {
    const url = new URL(input);
    if (url.protocol !== "https:" && url.protocol !== "http:") return false;
    const host = url.hostname.toLowerCase();
    return ALLOWED_HOSTS.some((d) => host === d || host.endsWith("." + d));
  } catch {
    return false;
  }
}

export function hostOf(input) {
  try {
    return new URL(input).hostname.toLowerCase();
  } catch {
    return "";
  }
}
