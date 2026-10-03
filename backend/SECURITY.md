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
