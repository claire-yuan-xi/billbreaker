# Abuse monitoring

The site has no accounts, so abuse is caught with per-IP rate limits stored in
SQLite (`billbreaker/services/rate_limit.py`). This page covers the alerting
and the admin page layered on top.

## Always on

- Per-IP limits on AI calls and publishing. They fail closed: if the store
  errors, the request is blocked, so an outage cannot be used to skip throttling.
- Structured logs. Every `near_limit`, `limit_exceeded` and `exception` event is
  one JSON line prefixed `[abuse]`.
- The same events are stored in the `abuse_events` table for the admin page.

## Settings

| Variable                  | Default | Purpose                                                  |
| ------------------------- | ------- | -------------------------------------------------------- |
| `ABUSE_ALERT_WEBHOOK_URL` | unset   | HTTPS URL to POST alerts to (Slack or Discord compatible) |
| `ABUSE_ALERT_THRESHOLD`   | `5`     | Incidents per identifier per hour before alerting         |
| `ABUSE_ALERT_COOLDOWN_S`  | `3600`  | Minimum seconds between alerts for the same identifier    |
| `ABUSE_ADMIN_TOKEN`       | unset   | Token for `/admin/abuse` (at least 16 characters)         |

A missing or non-https webhook turns alerts off; limits, logs and stored events
keep working. Without `ABUSE_ADMIN_TOKEN`, `/admin/abuse` says the token is not
configured.

## Webhook delivery

`maybe_alert()` calls `post_with_retry()` in `billbreaker/services/abuse.py`:
three attempts with exponential backoff and jitter, a 4 second timeout each,
retries only on 5xx, 408 and 429, and it never raises.

## Admin page

`/admin/abuse` shows the last 200 events. Paste the token into the page; it is
kept in `sessionStorage` for that tab only. The page is marked `noindex`.

## Tests

`tests/test_abuse_alert.py` covers threshold gating, the per-identifier
cooldown, the https-only webhook rule and the token check.
