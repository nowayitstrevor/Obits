# Mystery Box Security Findings

Date: 2026-03-07
Scope: Passive, non-destructive external review only (no code changes, no database changes)
Analyst: GitHub Copilot

## Targets Reviewed

- `https://www.longshotroasters.com/mysterybox`
- `https://www.longshotroasters.com/mysterybox?t=pELv1lWugHU3vCwUBHKuPxGG`
- Exposed API origin found in page script: `https://coffee-production-9b09.up.railway.app`

## Executive Summary

- Public API access exists for the tokenized mystery session endpoint, which is expected by design.
- No direct public database browsing endpoint was found in tested paths.
- The primary risk is token URL leakage/replay from shared QR links (mitigated by your current single-use token consumption on submit).
- Infrastructure fingerprinting header `X-Powered-By: Express` is present and should be removed.

## Evidence Collected

### 1) Frontend code exposes API base and routes

Embedded script on `/mysterybox` includes:

- `const MYSTERY_API_BASE = "https://coffee-production-9b09.up.railway.app"`
- GET route: `/api/public/mysterybox/session?t=<token>`
- POST route: `/api/public/mysterybox/session/submit?t=<token>`

This is normal for browser apps, but confirms the endpoint contract is publicly discoverable.

### 2) Tokenized session endpoint behavior

Observed responses:

- `GET /api/public/mysterybox/session?t=<valid token>` -> `200` JSON
- `GET /api/public/mysterybox/session?t=<invalid token>` -> `404`
- `GET /api/public/mysterybox/session` (no token) -> `400`

Valid-token JSON response contained question metadata/options and session state (`ready`), not direct answer keys in tested response.

### 3) CORS behavior

For `GET /api/public/mysterybox/session?t=<valid token>`:

- Origin `https://www.longshotroasters.com` -> `Access-Control-Allow-Origin` set to that origin, `Access-Control-Allow-Credentials: true`
- Origin `https://evil.example` -> no ACAO header returned

This suggests browser cross-origin reads are restricted to your allowlisted origin.

### 4) Header/security posture

- `X-Powered-By: Express` present on API responses.
- API hosted behind Railway edge (`Server: railway-edge`, Railway request headers present).

### 5) Route probing notes

Several probed paths returned `200 text/html`, but hashes/content matched the same SPA fallback shell (not a confirmed admin/data API), including examples like:

- `/api/admin`
- `/api/docs`
- `/api/public/mysterybox/admin`
- `/api/public/mysterybox/debug`

Conclusion: these looked like frontend route fallbacks, not exposed admin endpoints.

## Findings and Severity

### Finding A: Bearer-style token in query string
Severity: Medium

Description:
- The session token in `?t=` functions like a bearer credential to load a mystery session.
- Any party possessing the full URL/token can call the public endpoint directly.

Impact:
- Unauthorized session access if token is leaked via sharing, logs, screenshots, browser history, or referrer exposure.

Current mitigation:
- Tokens are single-use and consumed on submit (as confirmed by stakeholder).

Recommended actions:
- Keep short token TTL and enforce expiration aggressively.
- Bind token to one claim path (first successful session initialization) if product flow allows.
- Consider reducing sensitive data returned before submit.

### Finding B: Token validity oracle via status codes
Severity: Low-Medium

Description:
- Distinct response codes (`400` missing, `404` invalid, `200` valid) reveal token validity state.

Impact:
- Makes automated token-state probing easier.

Recommended actions:
- Normalize external error responses (for example, a generic invalid/expired response body and consistent status strategy).
- Add endpoint-level rate limiting and anomaly monitoring.

### Finding C: Technology fingerprinting header
Severity: Low

Description:
- `X-Powered-By: Express` exposed publicly.

Impact:
- Minor intelligence leak useful for attacker reconnaissance.

Recommended actions:
- In Express app startup: `app.disable('x-powered-by')`.
- Optionally use Helmet to harden response headers baseline.

## Not Confirmed / Not Found

- No confirmed public endpoint that directly lists or dumps DB contents.
- No confirmed Swagger/OpenAPI/GraphQL public introspection endpoint in tested paths.
- No confirmed answer-key leakage in tested `session` response.

## Immediate Hardening Checklist

1. Disable `X-Powered-By` in the Express API.
2. Ensure strict token TTL + one-time consumption is enforced server-side.
3. Add rate limiting on:
   - `GET /api/public/mysterybox/session`
   - `POST /api/public/mysterybox/session/submit`
4. Normalize error responses for invalid/missing/expired tokens.
5. Confirm CORS allowlist remains exact (no wildcards with credentials).
6. Add structured audit logs for token validation and submit attempts.

## Verification Commands (PowerShell)

```powershell
# Valid token check
Invoke-WebRequest "https://coffee-production-9b09.up.railway.app/api/public/mysterybox/session?t=REPLACE_TOKEN" -UseBasicParsing

# Invalid token check
Invoke-WebRequest "https://coffee-production-9b09.up.railway.app/api/public/mysterybox/session?t=invalidtoken123" -UseBasicParsing

# Header check
Invoke-WebRequest "https://coffee-production-9b09.up.railway.app/api/public/mysterybox/session?t=REPLACE_TOKEN" -Method Head -UseBasicParsing | Select-Object -ExpandProperty Headers
```

## Notes for Follow-On Work in API Repo

When moving this file into the backend repo, add:

- exact server entrypoint file path where `app.disable('x-powered-by')` is applied,
- middleware order for CORS/rate-limit/helmet,
- tests for token expiry/reuse and response normalization.
