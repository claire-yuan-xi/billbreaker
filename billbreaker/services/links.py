"""Host allowlists for outbound links and the AP link resolver."""

from urllib.parse import urlparse

RESOLVE_HOSTS = ("apnews.com", "news.google.com", "google.com")

SOURCE_HOSTS = (
    "congress.gov",
    "legiscan.com",
    "ap.org",
    "apnews.com",
    "news.google.com",
    "google.com",
    "senate.gov",
    "house.gov",
    "govinfo.gov",
)


def _matches(host: str, allowed: tuple[str, ...]) -> bool:
    h = host.lower()
    return any(h == d or h.endswith("." + d) for d in allowed)


def is_allowed_resolve_host(host: str) -> bool:
    return _matches(host, RESOLVE_HOSTS)


def is_safe_external_url(url: str | None) -> bool:
    """True for http(s) links to a verified legislative or news source."""
    if not url:
        return False
    try:
        u = urlparse(url)
    except ValueError:
        return False
    if u.scheme not in ("http", "https") or not u.hostname:
        return False
    return _matches(u.hostname, SOURCE_HOSTS)


def host_of(url: str | None) -> str:
    try:
        return (urlparse(url or "").hostname or "").lower()
    except ValueError:
        return ""
