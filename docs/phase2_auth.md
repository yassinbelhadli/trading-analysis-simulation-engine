# Phase 2.2 Authentication and Portal Boundary

## Status

- Phase: 2.2 Authentication and Portal Boundary
- Status: Audit and migration plan approved; implementation verified in `phase2_auth_implementation_report.md`
- Backend V2: frozen
- Website W1: foundation complete; W2 not started
- Owner API: not implemented
- Current domain/email infrastructure: recorded; no DNS or redirect changes made
- Implementation report: `docs/phase2_auth_implementation_report.md`
- This document does not authorize route, schema, token, or deployment changes

## Executive Finding

Authentication routes already exist and are covered by regression tests. Email delivery is not operational because the current SMTP configuration is incomplete.

The current registration path can therefore:

1. Create the user.
2. Create the verification token.
3. Attempt email delivery.
4. Return `verification_sent: false` when SMTP is unavailable.
5. Leave the user unable to complete the normal client journey until an email provider is configured or a safe test delivery path is used.

The next platform boundary must separate Website, Client, Admin, and future Owner portals without renaming or breaking the frozen API contracts.

## Current Authentication Architecture

### Backend Entry Point

Authentication routes are mounted at `/auth/*` by:

- `api/main.py`
- `api/routes/auth_router.py`

Current routes:

- `POST /auth/login`
- `POST /auth/register`
- `POST /auth/refresh`
- `POST /auth/logout`
- `POST /auth/logout-all`
- `GET /auth/me`
- `POST /auth/change-password`
- `POST /auth/verify-email/send`
- `POST /auth/verify-email/confirm`
- `POST /auth/forgot-password`
- `POST /auth/reset-password`
- `POST /auth/2fa/setup`
- `POST /auth/2fa/enable`
- `POST /auth/2fa/disable`
- `POST /auth/2fa/verify`
- `GET /auth/sessions`
- `DELETE /auth/sessions/{session_id}`
- `POST /auth/check-permission`

These paths are frozen. Phase 2.2 must not rename `/auth` to `/api/auth` without a separately approved compatibility plan.

### Identity and Token Storage

Backend sources:

- `security/jwt_handler.py`
- `security/dependencies.py`
- `security/access_control.py`
- `security/password.py`
- `security/totp.py`
- `database/models.py`

Current identity data:

- `users.email`
- `users.password_hash`
- `users.email_verified`
- `users.account_status`
- `users.role_id`
- `users.two_factor_enabled`
- encrypted `users.two_factor_secret`

Current token behavior:

- Access JWT contains user identity, expiry, token type, and role.
- Refresh token is returned to the client; only its hash is persisted in `login_sessions`.
- Refresh tokens rotate on refresh.
- Logout revokes the refresh session; existing access JWTs remain valid until expiry.
- Staff login may return a short-lived 2FA token before TOTP verification.

### Current Frontend Auth Clients

Admin:

- `admin_dashboard/lib/auth.ts`
- localStorage keys: `admin_at`, `admin_rt`, `admin_user`
- entry page: `admin_dashboard/app/login/page.tsx`
- staff redirect: `/dashboard`

Client:

- `admin_dashboard/lib/client-auth.ts`
- localStorage keys: `client_at`, `client_rt`, `client_user`
- entry page: `admin_dashboard/app/client/login/page.tsx`
- client redirect: `/client/dashboard`

Frontend guards:

- `admin_dashboard/components/auth/auth_guard.tsx`
- `admin_dashboard/components/auth/client_guard.tsx`
- `admin_dashboard/components/auth/permission_guard.tsx`

The frontend guards are UX guards based primarily on local token presence. Backend authorization remains authoritative.

## Current Email Delivery Architecture

### Central Email Service

The central service is:

`api/services/email_service.py`

It currently provides:

- `send_email`
- `send_verification_email`
- `send_password_reset_email`
- `send_welcome_email`
- `send_license_activated_email`
- `send_payment_success_email`
- `send_subscription_expiring_email`
- `send_subscription_expired_email`
- `notify_support_ticket`

Configuration sources, in precedence order:

1. `site_settings` email values when an authenticated service session is available.
2. Environment fallback values loaded by `api/main.py` and `email_service.py`.

The service returns a boolean result and logs a server-side warning/error. It does not raise a user-facing provider exception.

### Current Email Flow

```text
Auth route
  -> generate verification/reset code
  -> persist VerificationToken
  -> email_service.send_*_email()
       -> load site settings + env fallback
       -> check SMTP user/password
       -> connect with STARTTLS
       -> authenticate
       -> send message
  -> return boolean-derived user response
```

### Current Failure Reason

The current environment configuration was inspected without exposing secret values:

- `SMTP_HOST`: empty in the current configuration
- `SMTP_PORT`: `587`
- `SMTP_USER`: configured key exists
- `SMTP_PASS`: empty
- `SMTP_FROM`: configured key exists
- `FRONTEND_URL`: currently localhost
- `SUPPORT_EMAIL`: configured key exists
- `BILLING_EMAIL`: configured key exists

`send_email()` exits at its configuration guard when `smtp_user` or `smtp_pass` is missing:

```text
SMTP not configured - skipping email
```

Therefore the immediate failure is configuration/provider readiness, not a missing authentication route.

### Current User-Facing Behavior

Registration:

- `POST /auth/register` returns HTTP 200.
- Response includes `verification_sent: false` when delivery fails.
- Client register page shows a support fallback instead of claiming that an email was sent.

Unverified login:

- `POST /auth/login` creates a replacement verification code.
- If delivery fails, it returns HTTP 403 with a support message.

Verification resend:

- `POST /auth/verify-email/send` returns `Verification email queued (SMTP not configured)` when delivery fails.

Forgot password:

- `POST /auth/forgot-password` intentionally returns a generic response whether or not an email was delivered.
- The reset token is still persisted for test/admin-assisted flows.

This behavior is compatible with the current QA suite but cannot be considered a complete production client journey until a real non-production mailbox receives the message.

## Current Domain and Email Infrastructure

### Confirmed Current Facts

- Production domain: `ictfundedeapro.com`
- DNS provider: Namecheap BasicDNS
- Current email product: Namecheap Private Email / Expand Email candidate
- Mailbox capacity: 3 of 3 mailboxes currently in use
- Current domain redirect: `ictfundedeapro.com` -> `http://www.ictfundedeapro.com/`
- Deployment provider: not selected

No Namecheap credentials were requested, read, stored, or added to the repository. No DNS record or domain redirect was changed.

The current redirect uses HTTP. The production target should use HTTPS, but changing it is explicitly outside this audit and requires approval.

### Namecheap Private Email SMTP Requirements

The current candidate provider is compatible with the existing `email_service.py` STARTTLS implementation when configured on port 587.

| Setting | Required value/policy |
|---|---|
| SMTP host | `mail.privateemail.com` |
| SMTP TLS option | SSL on port `465`, or STARTTLS on port `587` |
| Current code path | `smtplib.SMTP`, `starttls()`, then `login()` |
| Username | Full mailbox email address |
| Password | Mailbox password from secret manager/environment only |
| Authentication | Required; SPA/secure password authentication disabled |
| From address | A verified mailbox/domain address |
| Reply-To | Approved support/reply mailbox policy |
| Timeout/retry | Must be defined before production enablement |

The current code uses `SMTP_USER`, not `SMTP_USERNAME`. Do not rename or add aliases until the environment naming decision is approved.

### IMAP/Inbound Requirements

IMAP is not needed for sending verification mail, but it is useful for mailbox-level delivery verification and future support workflows:

| Setting | Required value |
|---|---|
| IMAP host | `mail.privateemail.com` |
| IMAP SSL | Port `993` |
| IMAP STARTTLS | Port `143` |
| Username | Full mailbox email address |
| Password | Mailbox password from secret manager/environment only |

POP3 is optional and not required for backend email delivery.

### BasicDNS Requirements

For Namecheap BasicDNS, the current Private Email guidance lists these records:

| Type | Host | Candidate value | Priority/policy |
|---|---|---|---|
| MX | `@` | `mx1.privateemail.com` | `10` |
| MX | `@` | `mx2.privateemail.com` | `10` |
| TXT/SPF | `@` | `v=spf1 include:spf.privateemail.com ~all` | Consolidate with any existing SPF record |
| TXT/DKIM | Provider-generated host | Provider-generated value | `default._domainkey` or `privateemail._domainkey` depending on plan date |
| TXT/DMARC | `_dmarc` | Approved policy, initially monitor before enforcement | Must reference an approved reporting mailbox |

Optional provider records may include:

- CNAME `mail` -> `privateemail.com`
- CNAME `autodiscover` -> `privateemail.com`
- CNAME `autoconfig` -> `privateemail.com`
- SRV `_autodiscover._tcp` -> `privateemail.com` on port `443`

DNS safety rules:

- Do not publish these records yet.
- Verify existing MX/SPF records first to avoid conflicting providers.
- Maintain one consolidated SPF TXT record at `@`.
- Generate/copy the exact DKIM value from Namecheap; do not guess it.
- Verify the DKIM hostname variant for the actual subscription purchase date.
- Use staged DMARC monitoring before enforcement unless approved otherwise.
- Allow propagation and verify with external DNS tools before SMTP testing.

Public references:

- Namecheap BasicDNS Private Email records: `https://www.namecheap.com/support/knowledgebase/article.aspx/1338/2176/how-to-set-up-namecheap-private-email-dns-records-for-domains-on-namecheap-basicpremium-nameservers/`
- Namecheap Private Email client settings: `https://www.namecheap.com/support/knowledgebase/article.aspx/1179/2175/general-private-email-configuration-for-mail-clients-and-mobile-devices/`

### Mailbox Allocation

All 3 current mailboxes are reported as in use. Before assigning sender/reply addresses, decide:

- which mailbox sends verification/reset mail;
- which mailbox receives support replies;
- which mailbox is reserved for billing notifications;
- whether a dedicated service mailbox is required.

## Current Frontend Auth Flow

### Client Register

```text
app/current /client/register
  -> client-auth.register()
  -> POST /auth/register
  -> inspect verification_sent
  -> show success or SMTP support fallback
```

Source:

- `admin_dashboard/app/client/register/page.tsx`
- `admin_dashboard/lib/client-auth.ts`

### Client Verify Email

```text
/client/verify-email?code=...
  -> read code from query string
  -> POST /auth/verify-email/confirm
  -> redirect to /client/login
```

The page currently uses a raw `fetch()` call rather than the shared client transport. This is a documented consumer cleanup item, not a Phase 2.2 implementation change yet.

### Client Login

```text
/client/login
  -> POST /auth/login
  -> save client access/refresh tokens
  -> use backend redirect_to
  -> /client/dashboard
```

### Forgot/Reset Password

```text
/client/forgot-password
  -> POST /auth/forgot-password
  -> user receives reset code/link
  -> /client/reset-password
  -> POST /auth/reset-password
  -> /client/login
```

### Staff 2FA

```text
/login
  -> POST /auth/login
  -> if required: short-lived 2FA token
  -> POST /auth/2fa/verify
  -> save admin tokens
  -> /dashboard
```

2FA setup/enable/disable is staff-only. Client users do not currently have a client-facing 2FA UI.

## Target Portal Architecture

### Domain Mapping

The confirmed production target uses:

```text
www.ictfundedeapro.com
    Public Website

app.ictfundedeapro.com
    Client Portal

admin.ictfundedeapro.com
    Admin Portal

owner.ictfundedeapro.com
    Owner Portal

api.ictfundedeapro.com
    Central Backend API

hooks.ictfundedeapro.com
    Future provider webhooks

downloads.ictfundedeapro.com
    Future signed artifact delivery
```

Current DNS is managed through Namecheap BasicDNS. No DNS, redirect, deployment, or provider change is authorized by this audit.

Production URLs, email links, DNS, CORS, cookies, and security policies must use the confirmed domain only after the deployment phase is explicitly approved.

### Portal Responsibilities

| Portal | Responsibility | Allowed API boundary |
|---|---|---|
| Website | Public product/content pages | Public content contracts only |
| Client | Self-service account/license/subscription/EA/Telegram views | `/auth/*`, `/api/client/*`, owned license adapters |
| Admin | Operational staff workflows | `/auth/*`, `/api/admin/*`, permissioned resources |
| Owner | Future global business/platform governance | Future `/api/owner/*` only |
| API | Central auth and domain control plane | Private data/integrations through services |
| Hooks | Future signed provider callbacks | Future `/api/billing/webhooks/*` or dedicated hook boundary |
| Downloads | Future signed artifact delivery | Entitlement-gated download service |

The Client Portal must never call admin, legacy admin, or owner APIs. The Admin Portal must not be treated as the Owner Portal. No Owner API is created in Phase 2.2.

### Same Backend, Separate Applications

The portals share the central API and database but remain separate frontend boundaries:

```text
Website app       -> public routes/content
Client app        -> client auth + client API
Admin app         -> staff auth + admin API
Owner app         -> future owner auth + owner API
```

Separate applications do not justify duplicate authentication business logic. The backend auth service remains the single authority while each frontend owns its entry UX and permitted API client.

## Authentication Redirect Rules

### Current Local Development

- Client login: `http://localhost:3000/client/login`
- Client register: `http://localhost:3000/client/register`
- Client dashboard: `http://localhost:3000/client/dashboard`
- Admin login: `http://localhost:3000/login`
- Admin dashboard: `http://localhost:3000/dashboard`
- API: `http://127.0.0.1:8000`

### Target Production Rules

- Website login CTA -> `https://app.<canonical-domain>/client/login`
- Website register CTA -> `https://app.<canonical-domain>/client/register`
- Client successful login -> `https://app.<canonical-domain>/client/dashboard`
- Client failed/unverified login -> remain on Client Portal with safe message
- Admin login -> `https://admin.<canonical-domain>/dashboard`
- Admin 2FA challenge -> remain on Admin Portal until verified
- Owner login -> future `https://owner.<canonical-domain>/dashboard`
- API redirects are not used for browser page navigation; frontend portals own navigation

Existing `redirect_to` response values remain compatible during migration. The production URL mapping must be configured rather than hardcoded in route handlers.

## Authorization Rules

### Current

- Client routes generally require an active JWT but do not consistently enforce the client role.
- Admin routes require JWT plus handler permissions.
- Owner role exists as a wildcard but no owner API or owner visibility policy exists.
- Legacy admin routes require static `X-Admin-Token`.
- Frontend guards check token presence; backend authorization is authoritative.

### Target

- Client audience cannot access Admin or Owner resources.
- Admin audience cannot access Owner resources without explicit owner policy.
- Owner access uses explicit owner permissions, not an unbounded UI role shortcut.
- Legacy static-token routes are isolated and eventually retired through compatibility adapters.
- Cross-origin portal navigation never transfers tokens in URLs.
- Portal cookies/token storage, audience claims, CSRF policy, and logout behavior are approved before production.

No target authorization change is implemented in this audit.

## Required Environment Variables

### Current Email Service Names

The current code reads these names:

```env
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASS=
SMTP_FROM=
FRONTEND_URL=
SUPPORT_EMAIL=
BILLING_EMAIL=
```

The user proposal names `SMTP_USERNAME`; current implementation names it `SMTP_USER`. This naming decision must be resolved before configuration changes. Do not add a second alias silently.

### Target Portal URL Names

Target configuration should define, without values in source control:

```env
PUBLIC_WEBSITE_URL=
CLIENT_PORTAL_URL=
ADMIN_PORTAL_URL=
OWNER_PORTAL_URL=
API_PUBLIC_URL=
HOOKS_PUBLIC_URL=
DOWNLOADS_PUBLIC_URL=
```

The existing `FRONTEND_URL` is currently used to build verification/reset links. Phase 2.2 must define whether it becomes the Client Portal URL or is replaced by an explicit email-link setting through a compatibility-safe configuration migration.

### Existing Security Configuration

The current environment also contains JWT, encryption, database, Telegram, admin, and MT configuration. Values must remain environment/secret-manager inputs and must not be copied into documentation or source code.

## Email Provider Requirements

Before Auth is considered production-ready:

- select SMTP or a transactional email provider;
- configure host, port, username, password, sender, and reply-to policy;
- verify sender/domain ownership;
- configure SPF, DKIM, and DMARC;
- use TLS/STARTTLS according to provider requirements;
- add timeout/retry/observability policy without logging credentials or message bodies;
- test a real non-production mailbox;
- verify verification, reset, welcome, license, payment, expiry, and support-ticket templates;
- define bounce, suppression, and provider failure handling;
- keep user-facing errors safe and actionable;
- keep server logs diagnostic but secret-free.

Email delivery must remain centralized in the email service. Routes and frontend components must not open SMTP connections directly.

## Security Considerations

- Never log SMTP passwords, API keys, bot tokens, reset codes, verification codes, or broker credentials.
- Do not expose decrypted site settings in API responses.
- Do not put access/refresh tokens in query strings.
- Verification/reset query codes must be short-lived, single-use, and treated as secrets.
- Keep email enumeration behavior generic on forgot-password.
- Rate-limit login, register, verify, resend, reset, and 2FA flows.
- Require HTTPS for all production portal/API origins.
- Define trusted CORS origins per portal; no wildcard production CORS.
- Decide secure HTTP-only cookie versus browser token storage before production.
- Separate client/admin/owner token audiences before Owner launch.
- Add domain and sender alignment before users rely on email links.
- Keep email template variables escaped and prevent template HTML injection.
- Do not expose license keys in public Website content.

## Migration Plan

### Step 0: Approval and Domain Decision

- approve canonical domain spelling;
- approve portal subdomains;
- approve current env variable names versus target names;
- approve provider and sender policy;
- approve local/staging/prod origin mapping.

### Step 1: Provider Configuration Only

- configure SMTP/provider credentials through the deployment secret mechanism;
- configure sender and reply-to;
- verify DNS/authentication records;
- do not change route contracts;
- run a provider connectivity test without exposing credentials.

### Step 2: Email Flow Verification

Using the existing backend:

- register a new client;
- receive verification email;
- click/submit verification code;
- login to Client Portal;
- request password reset;
- receive reset email;
- reset password;
- verify staff 2FA flows and security notifications if enabled;
- verify failure fallback when provider is unavailable.

### Step 3: Portal Origin Configuration

- deploy existing Website foundation and existing portal applications behind separate origins;
- set portal URL configuration;
- make verification/reset links target Client Portal;
- configure trusted CORS and cookie/token policy;
- do not rename API routes.

### Step 4: Auth Consumer Integration

- integrate Website auth links/forms only after the provider and origin mapping pass;
- keep Client and Admin auth clients separate;
- preserve existing request/response shapes;
- test redirects and unauthorized cross-portal access;
- stop before Dashboard V2 or Owner work.

### Step 5: Production Gate

- real non-production mailbox test;
- domain/TLS/CORS test;
- client/admin portal separation test;
- refresh/logout/session revocation test;
- rate-limit and safe-error test;
- full existing regression suite;
- manual client and staff journeys;
- rollback of email configuration tested.

## Compatibility Requirements

- Do not delete or rename existing `/auth/*` routes.
- Do not change current response fields or status codes without an adapter and Golden Master.
- Keep `verification_sent` behavior compatible.
- Keep current safe fallback messages when SMTP is unavailable.
- Keep current refresh/logout/session behavior until a separately approved security migration.
- Keep current admin 2FA flow.
- Keep current Client/Admin frontend applications usable during portal origin migration.
- Do not change database schema in Phase 2.2 unless a separately approved migration is required.
- Do not modify Trading Engine, Detection, Risk, Execution, Simulation, Renderer, MT4/MT5, Telegram, Billing, Cache, or Realtime.

## QA and Exit Criteria

Phase 2.2 is complete only if:

### Email

- provider connectivity succeeds with non-production credentials;
- registration sends a real verification email;
- verification link/code works once and expires correctly;
- password reset email is received and reset works;
- welcome/license/payment/expiry/support templates are verified where enabled;
- provider failure returns a clear safe fallback;
- no secrets/codes appear in logs or responses.

### Authentication

- client register/login/logout/refresh;
- client verify email;
- client forgot/reset password;
- staff login and 2FA;
- session listing and revocation;
- invalid credentials and expired/revoked token behavior;
- rate limits;
- audit events;
- all existing QA suites remain green.

### Portals

- Website links to Client Portal correctly;
- Client Portal cannot access Admin/Owner resources;
- Admin Portal uses staff auth and permissions;
- Owner remains unavailable until its own contract is approved;
- redirect URLs match the canonical domain;
- CORS/origin/cookie behavior is verified.

### Reporting

The phase report must list:

- files changed;
- env/config changes without secret values;
- routes affected;
- provider test results;
- auth test results;
- portal-origin test results;
- compatibility verification;
- remaining security risks;
- explicit next-phase boundary.

## Explicit Out Of Scope

- Backend V2 architectural refactor
- new `/api/auth` route family
- Owner API or Owner Dashboard
- Dashboard V2
- Website W2 content pages
- Billing/payment provider implementation
- Telegram redesign or chat-link implementation
- Trading Engine/Detection/Risk/Execution changes
- MT4/MT5 changes
- Database schema redesign
- Cache, SSE, WebSocket, or event transport
- VPS/Docker/Nginx production implementation

## Stop Condition

Do not implement Phase 2.2 from this document yet. The audit and plan are complete. Wait for explicit approval after the domain, provider, environment naming, portal boundary, and security decisions are reviewed.
