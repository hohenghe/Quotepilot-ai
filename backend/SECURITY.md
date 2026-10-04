# API abuse protection

Password hashes use Argon2id (19 MiB, two passes, one lane) with a fresh salt per
password. Existing salted HMAC-SHA256 hashes remain valid and are upgraded after
a successful password login or WeChat account binding. Password work runs in a
bounded thread pool path, so normal API requests do not perform password hashing.

The application applies process-local sliding-window limits before routing:
20 password login/bind requests, 10 registrations, 10 email/reset operations,
and 30 WeChat requests per IP per minute. It also caps all API requests at
`API_IP_RATE` (default 600/minute/IP) and blocks an identifier for five minutes
after ten failed password attempts. A limited request returns HTTP 429. These
limits protect a single worker; they are not shared between replicas or restarts.

For production DDoS protection, put `api.zhermai.com` behind an edge WAF/CDN,
apply rate rules to `/api/auth/*` and the expensive `/api/inquiries/analyze`
path, and prevent direct origin bypass. Verify the actual proxy network before
setting `TRUSTED_PROXY_CIDRS` to its CIDRs. With the setting empty, the TCP peer
is used and forwarding headers are ignored. The Procfile disables Uvicorn's own
proxy-header rewriting so the application can make that trust decision itself.
When adding more than one API replica, use an edge or shared rate-limit store;
the in-process counters alone are insufficient for distributed abuse.

Observe 429 rates and legitimate request volume before changing
`API_IP_RATE` or edge rules. The password hash parameters should also be
benchmarked on the deployed CPU and memory limit before increasing their cost.

## Browser human verification

Cloudflare Turnstile is available for web login, registration, password-recovery
requests, and anonymous inquiry analysis. Configure the widget's public site key
as `NEXT_PUBLIC_TURNSTILE_SITE_KEY` in Vercel, and its matching private key as
`TURNSTILE_SECRET_KEY` (or Cloudflare Spin's `TURNSTILE_SECRET`) in Northflank.
Set `TURNSTILE_ALLOWED_HOSTNAMES` (or `TURNSTILE_HOSTNAMES`) to the
comma-separated widget hostnames (for example `zhermai.com,www.zhermai.com`),
or leave it empty to derive them from allowed frontend origins.
Only enable the keys as a pair. Siteverify checks the token, action and hostname
before processing these requests; an unavailable verification service fails
closed. The widget is loaded only on affected web forms.
Cloudflare's public dummy key pair can be used in local development; the test
secret bypasses hostname/action checks only outside `ENV=production`.

The mini program shares the password endpoints and cannot render a browser
Turnstile widget. Those endpoints require a token for allowed browser origins
but still accept non-browser callers so the mini program works. Therefore,
scripts that omit or forge `Origin` can bypass the challenge on the shared
password endpoints. Keep the existing API rate limits and put the API behind
an edge WAF for stronger protection. Anonymous inquiry analysis has no mini
program caller and requires a valid token from every guest when enabled.
