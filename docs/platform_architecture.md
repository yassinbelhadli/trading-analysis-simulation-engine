# ICT Funded EA Pro Platform Architecture

## Document Status

- Status: Platform architecture baseline
- Backend V2 Foundation: approved and frozen
- Scope: website, portals, API domains, authentication, permissions, billing, Telegram, engine, and infrastructure
- Date: 2026-08-03
- This document is a platform reference, not an implementation authorization
- Existing means currently implemented
- Partial means code exists but the production contract or wiring is incomplete
- Future means absent, explicitly deferred, or requires a new approved phase
- Phase 2.1 Website specification: `docs/phase2_website.md`
- Phase 2.2 Auth/portal audit: `docs/phase2_auth.md`
- Phase 2.2 implementation report: `docs/phase2_auth_implementation_report.md`

## Architecture Principle

The platform is built around the frozen Backend V2 control plane. New platform surfaces must consume the existing contracts instead of reopening the backend architecture.

```text
Public Website       Client Portal       Admin Portal       Owner Portal
       |                  |                  |                  |
       +------------------+------------------+------------------+
                          |
                   Edge / HTTPS / WAF
                          |
                    FastAPI API
                          |
              Frozen Backend V2 contracts
                          |
                  Services and repositories
                          |
                       PostgreSQL

Private workers and trading infrastructure stay behind the API boundary:

Billing worker   Telegram worker   News worker   Engine worker   MT4/MT5
       \              |                |              |           /
        +-------------+----------------+--------------+----------+
                              |
                    DB / outbox / private integrations
```

The browser never talks directly to PostgreSQL, MT4, MT5, Telegram, Redis, or private workers.

## Platform Domains

| Domain | Current state | Target responsibility | Public surface |
|---|---|---|---|
| Website | W1 foundation exists; public content future | Marketing, pricing, features, FAQ, docs, legal, public auth entry | `www` |
| Client Portal | Existing in shared Next app | Client self-service, accounts, license, subscription, EA, Telegram settings, analytics | `app` |
| Admin Portal | Existing in shared Next app | Operations, support, users, licenses, system, trading monitoring | `admin` |
| Owner Portal | Future | Global business, revenue, tenants, platform governance | `owner` |
| Auth | Existing | Identity, sessions, verification, password reset, staff 2FA | `/auth` |
| Client API | Existing/frozen | Client-scoped read and lifecycle operations | `/api/client` |
| Admin API | Existing/frozen | Permissioned operational administration | `/api/admin` |
| Owner API | Future | Owner-only global read/control contracts | `/api/owner` |
| License Domain | Partial | Entitlement, activation, expiry, account binding | `/api/licenses` plus adapters |
| Billing Domain | Future/partial models | Checkout, payments, invoices, refunds, entitlements | `/api/billing` |
| Telegram Domain | Existing/partial | Verified linking, notifications, bot workflows | `/api/telegram` future plus bot worker |
| Trading Domain | Existing engine, partial control plane | Read models, commands, risk state, execution state | `/api/trading` future; current admin paths preserved |
| News Domain | Existing/partial | Calendar, impact state, ingestion, broadcasts | `/api/news` future; current admin paths preserved |
| Settings Domain | Existing/partial | Scoped settings, masking, encrypted secrets | `/api/settings` future; current admin settings preserved |
| System Domain | Existing/partial | Readiness, health, metrics, operational status | `/api/system` future; current health paths preserved |
| Infrastructure | Local/development | Edge, TLS, workers, storage, backups, monitoring | Private/public deployment topology |

## Existing Repository Map

### Existing Website/Public Surface

The Website foundation app now exists under `website/`, but it contains only the W1 shell/component preview. Public marketing content is not implemented yet. Existing public browser routes are authentication and utility pages inside `admin_dashboard`:

- `/login`
- `/client/login`
- `/client/register`
- `/client/forgot-password`
- `/client/reset-password`
- `/client/verify-email`
- `/forbidden`

The future Website is a separate platform domain. It must not be implemented by adding marketing sections into the frozen dashboard layouts.

### Existing Client Portal

Current source:

- `admin_dashboard/app/client/`
- `admin_dashboard/lib/client-api.ts`
- `admin_dashboard/lib/client-auth.ts`
- `admin_dashboard/components/auth/client_guard.tsx`

Current client responsibilities:

- client home dashboard
- MT4/MT5 account lifecycle
- license view
- subscription view
- EA metadata/download
- Telegram preferences
- profile/password
- settings
- trades and performance

The current Client Portal is a route tree inside the shared Next app. The future Client Dashboard V2 is a UX redesign consuming frozen API contracts, not a backend refactor.

### Existing Admin Portal

Current source:

- `admin_dashboard/app/dashboard/`
- `admin_dashboard/lib/api.ts`
- `admin_dashboard/lib/auth.ts`
- `admin_dashboard/components/auth/auth_guard.tsx`
- `admin_dashboard/components/auth/permission_guard.tsx`

Current admin responsibilities:

- users and clients
- roles and permissions
- licenses
- subscriptions/plans/payments
- promotions
- audit
- tickets
- news
- system health
- trading monitor and controls
- security and settings

The existing `/dashboard/admin` page is not an Owner Portal. It is an owner-like revenue page under the admin route tree and must not be treated as the final owner boundary.

### Existing Engine and Workers

Current components:

- FastAPI: `api/main.py`
- Telegram bot: `telegram_bot/bot.py`
- Engine manager: `core_engine/engine_manager.py`
- Engine runner: `core_engine/engine_runner.py`
- Account scanner: `core_engine/scanner.py`
- MT5 runtime: `core_engine/mt5_runtime.py`
- MT4 runtime: `core_engine/mt4_runtime.py`
- MT4 bridge: `mt4_bridge/main.py`
- Background runner: `scripts/background_runner.py`
- News worker: `news_engine/` and API startup news tasks
- Renderer: `renderer_bridge/` and `renderer_v2/`

These are platform components, but they are not owned by browser portals. The browser sends authorized commands to the API; only the approved control plane may communicate with private workers.

## Target Domain Layout

### Public Website

```text
Website
  -> public content/read API
  -> public plan catalog
  -> public documentation/content source
  -> auth entry links
  -> checkout entry point when Billing is approved
```

The Website must not read private admin settings, client data, engine state, or database rows directly.

### Client Portal

```text
Client Portal
  -> /auth/*
  -> /api/client/*
  -> /api/licenses/* through client-safe adapters
  -> /api/billing/* for the client's own subscription when approved
  -> verified Telegram linking flow when approved
```

The Client Portal must never call:

- `/api/admin/*`
- `/admin/*`
- `/api/owner/*`
- engine/runtime ports
- PostgreSQL

### Admin Portal

```text
Admin Portal
  -> /auth/* for staff login and 2FA
  -> /api/admin/*
  -> operational system/trading read models
  -> support and client management
```

The Admin Portal is for operational staff. It is not automatically the owner surface. Revenue, global tenant visibility, secrets, and platform governance require a separate owner policy.

### Owner Portal

```text
Owner Portal
  -> /auth/* with owner-scoped audience/policy
  -> /api/owner/* after owner contract approval
  -> global business and platform read models
```

This domain is future. No Owner API, tenant model, visibility policy, owner DTO, or owner frontend exists today. It must not be created as a route alias to `/api/admin/*`.

## API Communication Rules

### Frozen Existing Contracts

The following remain the current stable contracts:

- `/auth/*`
- `/api/client/*`
- `/api/admin/*`
- `/api/licenses/*`
- `/api/screenshots/*`
- legacy `/admin/*` compatibility surface

Registry:

- `docs/api_docs.md`

Backend V2 reports:

- `docs/backend_v2_sprint1_report.md`
- `docs/backend_v2_sprint2_report.md`
- `docs/backend_v2_sprint3_report.md`
- `docs/backend_v2_stabilization_report.md`

### Future API Ownership

These are ownership domains, not immediate route changes:

```text
/api/auth
/api/public
/api/client
/api/admin
/api/owner
/api/licenses
/api/billing
/api/telegram
/api/trading
/api/news
/api/settings
/api/system
```

Every future endpoint must declare:

- domain owner
- consumer surface
- authentication boundary
- permission
- request DTO
- response DTO
- audit requirement
- idempotency requirement for mutations
- compatibility strategy

## Communication Flows

### Website Visitor

```text
Browser
  -> www.ictfundedeapro.com
  -> public content and plan catalog
  -> /auth/register or /client/login
  -> api.ictfundedeapro.com/auth/*
```

The Website does not create licenses or subscriptions directly. Checkout and entitlement creation go through the approved Billing service.

### Client Login and Dashboard

```text
Client Browser
  -> app.ictfundedeapro.com/client/login
  -> api.ictfundedeapro.com/auth/login
  -> client access/refresh session
  -> api.ictfundedeapro.com/api/client/*
       -> Service
       -> Repository / DTO
       -> PostgreSQL
```

The current browser token implementation is frozen for Backend V2. A future security phase may move tokens to secure HTTP-only cookies, but that is not part of this architecture document's implementation scope.

### Client Account Connection

```text
Client Browser
  -> POST /api/client/accounts
  -> ClientAccountService
  -> LicenseService
  -> MTConnector
  -> MT5Runtime or MT4Runtime
  -> AccountRepository / ScanRepository
  -> PostgreSQL
  -> Engine control request after the existing commit boundary
```

The browser never receives broker passwords back. Passwords are encrypted before persistence and are not part of DTO responses.

### Admin Operations

```text
Admin Browser
  -> admin.ictfundedeapro.com
  -> /auth/login + optional 2FA
  -> /api/admin/*
       -> permission dependency
       -> application service
       -> repository/query service
       -> PostgreSQL or approved health/control integration
```

Admin controls must not directly call MT5 terminals from the browser. Engine controls require a future process-safe control-plane contract because the current `EngineManager` is process-local.

### Owner Operations

```text
Owner Browser
  -> owner.ictfundedeapro.com
  -> owner-scoped auth policy
  -> /api/owner/*
       -> owner read models
       -> billing/license/system repositories
       -> redacted global analytics
```

This flow is intentionally future and requires owner visibility decisions first.

### Billing Webhook

```text
Payment Provider
  -> hooks.ictfundedeapro.com (future)
  -> webhook signature verification
  -> BillingService
  -> idempotency record
  -> Subscription/Payment/Invoice repositories
  -> License entitlement service
  -> outbox/event transport
  -> client read model and notifications
```

No provider, webhook, payment tables, or idempotency contract exists today.

### Telegram Notification

```text
Engine / News / Billing event
  -> durable event transport (future)
  -> Telegram worker
  -> verified chat/user mapping
  -> Telegram Bot API
```

Current implementation uses a process-local EventBus and a polling bot. It is not a cross-process production event architecture.

### Trading Engine

```text
Engine Worker on private Windows host
  -> MT5 terminal or private MT4 bridge
  -> market data
  -> detection/scoring
  -> risk/execution guard
  -> execution or paper trading
  -> PostgreSQL read model
  -> durable events (future)
```

The Engine is the capital-protection boundary. No portal or future service may move detection, scoring, risk, or execution rules into HTTP handlers.

## Authentication Model

### Current Model

| Surface | Current entry | Current token store | Backend boundary |
|---|---|---|---|
| Client | `/client/login`, `/auth/login` | `client_at`, `client_rt`, `client_user` in browser storage | Active JWT; client role enforcement incomplete |
| Admin | `/login`, `/auth/login`, optional 2FA | `admin_at`, `admin_rt`, `admin_user` in browser storage | JWT plus permission dependencies |
| Owner | No route | None | No implementation |
| Legacy admin | Legacy pages | Expected static token | `X-Admin-Token` |
| Screenshots | Signed URL | HMAC query signature | Signature and expiry |
| Telegram | Bot token | Telegram process | Separate bot process |
| MT4 bridge | Local EA | None | Private/local only; currently unauthenticated |

### Target Surface Separation

Before Owner production launch, token/audience separation must be approved:

- client audience cannot call admin/owner resources;
- admin audience cannot call owner resources without explicit owner permission;
- owner audience has explicit owner claims and tenant visibility;
- legacy static-token routes are removed or isolated behind an internal compatibility boundary;
- frontend guards remain UX only; backend authorization remains authoritative.

This is a future security/platform phase, not a modification to frozen Backend V2.

## Permission Model

### Current Roles

- `owner`: wildcard bypass; not a complete owner platform contract
- `admin`: broad operational access
- `support`: support/client/account/trade reads
- `risk_manager`: risk/account/trade reads
- `analyst`: analytics/trade/account reads
- `billing`: billing/subscription access
- `notification_mgr`: email/Telegram notification access
- `client`: self, trades, subscriptions, support access

Source: `security/access_control.py`.

### Target Permission Domains

```text
public.read
client.self.read
client.self.update
client.accounts.read
client.accounts.manage
client.trades.read
client.subscription.read
client.billing.manage
client.telegram.manage

admin.overview.read
admin.clients.read
admin.clients.manage
admin.licenses.read
admin.licenses.manage
admin.billing.read
admin.billing.manage
admin.support.read
admin.support.manage
admin.news.manage
admin.system.read
admin.engine.control
admin.trading.read

owner.platform.read
owner.revenue.read
owner.tenants.read
owner.settings.manage
owner.emergency.control
```

The owner permission set is future. Do not replace the current wildcard with these permissions until the owner policy is approved and tested.

## Domain Ownership and Data Rules

| Data | Source of truth | Allowed writers | Portal visibility |
|---|---|---|---|
| User identity | PostgreSQL `users` | Auth/identity service | Self; staff by permission; owner by policy |
| Login sessions | PostgreSQL `login_sessions` | Auth service | Self/security staff by policy |
| Licenses | PostgreSQL `licenses` plus LicenseService | License/Billing workflows | Client own; admin permission; owner policy |
| Accounts | PostgreSQL `trading_accounts` | ClientAccountService, approved Telegram workflow | Client own; admin operations; owner policy |
| Risk profiles | PostgreSQL `risk_profiles` | Account/engine risk workflows | Client scoped summary; risk staff; owner policy |
| Paper trades | PostgreSQL `paper_trades` | Engine/paper-trading lifecycle | Client own; trading staff; owner policy |
| Real execution state | MT4/MT5 runtime plus durable read model | Engine worker only | Read-only portal views |
| Audit events | PostgreSQL `audit_logs` | Services/workers through audit policy | Scoped by permission |
| Subscription/payment | Future dedicated billing tables | Billing service/webhooks | Client own; billing/admin/owner policy |
| News events | CSV/DB currently; future authoritative store | News worker/admin service | Public calendar subset; admin/full engine |
| EA artifacts | Object/file storage currently | Release service | Signed entitlement-based download |
| Secrets | Environment/secret manager target | Deployment/config process | Never in DTOs or client responses |

No portal may write another portal's scoped data by bypassing its service boundary.

## Deployment Topology

### Target Subdomains

Confirmed production domain: `ictfundedeapro.com`. DNS is currently managed through Namecheap BasicDNS. Production deployment and DNS changes remain unapproved.

| Hostname | Target | Public? |
|---|---|---|
| `www.ictfundedeapro.com` | Public Website | Yes |
| `app.ictfundedeapro.com` | Client Portal | Yes |
| `admin.ictfundedeapro.com` | Admin Portal | Yes, staff access policy |
| `owner.ictfundedeapro.com` | Owner Portal | Yes, owner access policy |
| `api.ictfundedeapro.com` | FastAPI API | Yes through edge only |
| `hooks.ictfundedeapro.com` | Billing/provider webhooks, future | Yes through signed webhook endpoints |
| `downloads.ictfundedeapro.com` | Signed object-storage downloads, future | Signed URLs only |

Current email infrastructure context:

- Namecheap Private Email / Expand Email is the current provider candidate.
- All 3 available mailboxes are currently reported as in use.
- The current domain redirect is `ictfundedeapro.com` -> `http://www.ictfundedeapro.com/`.
- No Namecheap credentials are stored or requested.
- No DNS records or redirects may be changed until explicitly approved.
- SMTP/IMAP/DNS requirements are documented in `docs/phase2_auth.md`.

Never expose publicly:

- PostgreSQL
- Redis
- MT4 bridge
- MT5 terminal
- engine worker control ports
- internal render/news/Telegram workers

No separate `telegram.` or `mt4.` public subdomain is required. Telegram polling has no inbound web surface; MT4 must remain private.

### Target Process Topology

```text
Public Internet
    |
    v
Cloudflare/WAF + Nginx/Caddy :443
    |
    +--> www site process
    +--> client Next.js process
    +--> admin Next.js process
    +--> owner Next.js process
    +--> FastAPI process :8000
    +--> signed webhook handlers

Private network
    +--> PostgreSQL :5432
    +--> Redis/outbox :6379 (future)
    +--> Telegram worker (one instance)
    +--> News worker (one instance)
    +--> Billing scheduler/worker (future)
    +--> Render worker
    +--> Windows trading host
          +--> EngineRunner
          +--> AccountScanner
          +--> MT5 terminal(s)
          +--> MT4 bridge :9100 loopback/private
```

### Process Ownership

| Process | Owns |
|---|---|
| Edge proxy | TLS, routing, WAF, rate limits |
| Website | Public content only |
| Client Portal | Client UX only |
| Admin Portal | Staff UX only |
| Owner Portal | Owner UX only |
| FastAPI | Auth, API contracts, service calls, read/control plane |
| Engine worker | Engine state, risk/execution lifecycle, MT4/MT5 sessions |
| Telegram worker | Telegram polling/webhook and notification delivery |
| News worker | Provider ingestion and normalized news state |
| Billing worker | Webhooks, subscriptions, invoices, entitlement events |
| PostgreSQL | Durable source of truth |
| Redis/outbox | Future shared events, cache, locks, rate limiting |
| Object storage | EA files, screenshots, charts |

The current local process topology is not yet this topology. It must be implemented only in the Production phase after the contracts and operational requirements are approved.

## File and Package Structure

### Current Repository Structure

```text
api/                 FastAPI app, routes, services, schemas
website/             W1 public Website foundation app
admin_dashboard/     Shared Next.js client/admin app
core_engine/          Detection, scoring, risk, execution, runtimes
database/             Models, DB session, repositories, migrations
telegram_bot/         Telegram handlers and services
news_engine/          News providers, filters, repositories
renderer_bridge/      Telegram/chart rendering
mt4_bridge/           Local MT4 bridge
license_system/       Legacy license helpers
billing/              Future/empty billing modules
scripts/              QA, launchers, background tools
storage/              EA artifacts and local output
logs/                 Local health/engine files
docs/                 Architecture and phase reports
```

### Target Logical Structure

This is a logical ownership map, not an instruction to move files during the freeze:

```text
platform/
  website/                 Public marketing/docs app
  client_portal/            Client UX app
  admin_portal/             Staff UX app
  owner_portal/             Owner UX app
  api/
    routes/                 Thin HTTP adapters
    services/               Use cases and read orchestration
    repositories/           Domain persistence/query boundaries
    schemas/                Request/response DTOs
    integrations/           SMTP, payment, Telegram, news, storage ports
    auth/                   Authentication and authorization policy
  workers/
    engine/                 Engine process adapter only
    telegram/               Telegram delivery worker
    news/                   News ingestion worker
    billing/                Billing/webhook worker
    scheduler/              Expiry/report/backup jobs
  engine/                   Existing frozen trading core boundary
  infrastructure/
    docker/                 Images and compose definitions
    proxy/                  Nginx/Caddy/Cloudflare configuration
    observability/          Logs, metrics, alerts, dashboards
    migrations/             Deployment migration gates
  docs/
```

The existing Backend V2 Foundation remains the authority for API/service/repository/DTO boundaries. A future physical move requires a separate approved phase and compatibility plan.

## Infrastructure Requirements

### Required Before Production

- canonical domain and DNS
- TLS certificates and HTTPS-only redirects
- trusted CORS origins
- secret manager/environment injection
- non-empty pinned Python dependency manifest
- pinned Node dependency/build runtime
- production FastAPI runner without `reload=True`
- supervised worker processes
- PostgreSQL private networking
- backup/PITR and restore test
- Alembic migration baseline for every model table
- object storage and signed-download policy
- log redaction/retention/rotation
- liveness/readiness endpoints
- rate limiting at edge and API
- monitoring and alerting
- rollback procedure

### Trading Host Requirements

- Windows host for MT5 terminal support
- one explicit engine-worker owner
- one account-scanner owner
- private MT4 bridge per terminal
- no public MT5/MT4 credentials
- capital-protection gates tested fail-closed
- news/spread/risk failures cannot silently allow real trades
- broker/runtime health visible through a durable control/read model

### Storage Rules

- PostgreSQL for durable application state
- object storage for EA builds, screenshots, and charts
- Redis/outbox only after a shared event/cache contract is approved
- local files are not authoritative production state
- health JSON files are diagnostics, not source of truth

## Platform Roadmap

### Phase 1: Backend V2 Foundation

Status: **Done and frozen**

- route registry
- service/repository boundaries
- DTOs and aggregators for approved slices
- compatibility adapters
- Golden Masters and regression discipline

### Phase 2: Website

Scope:

- landing page
- pricing
- features
- FAQ
- contact
- documentation
- legal pages
- public auth entry points
- SEO, sitemap, robots, analytics consent

Constraint: consume public/frozen API contracts; do not reopen Backend V2 architecture.

### Phase 3: Client Dashboard V2

Scope:

- new UX/UI
- responsive client navigation
- onboarding experience
- account/license/subscription presentation
- clear entitlement and support states

Constraint: same APIs first. Any API gap becomes a separately approved bug/contract change.

### Phase 4: Admin Dashboard V2

Scope:

- operations UX
- support workflows
- users/clients/licenses
- system/trading monitoring
- staff permission UX

Constraint: Admin Portal must not silently become Owner Portal.

### Phase 5: Owner Dashboard

Prerequisites:

- owner role definition
- tenant/workspace model decision
- owner visibility matrix
- owner-only permissions
- revenue/payment data policy
- owner API and DTO contracts
- audit and emergency-control policy

### Phase 6: Billing

Scope:

- provider selection
- checkout
- webhook verification
- subscriptions
- invoices
- taxes/currency
- coupons
- refunds
- idempotency
- license entitlement synchronization

### Phase 7: Telegram

Scope:

- verified `/start` link flow
- web/bot service convergence
- notification preferences
- event transport
- delivery retries and observability

### Phase 8: Production

Scope:

- VPS/cloud topology
- domain/DNS/Cloudflare
- Docker or supervised services
- Nginx/Caddy/HTTPS
- SMTP
- PostgreSQL migrations/backups
- monitoring/alerts
- private trading host
- production manual client test
- rollback and incident runbooks

## Open Platform Decisions

These decisions must be approved before the relevant phase, not guessed during implementation:

1. Canonical domain: `ictfundedeapro.com`, `ictfunded.com`, or another verified domain.
2. Separate Next.js deployments versus one repository with independently deployed applications.
3. Owner definition: global platform owner versus tenant/workspace owner.
4. Tenant model: single global tenant versus organizations/workspaces.
5. Owner visibility and emergency-control permissions.
6. Payment provider: Stripe, Paddle, or another provider.
7. Billing tax/currency/invoice requirements.
8. Redis versus database outbox for cross-process events.
9. SSE versus WebSocket for future realtime.
10. Secure cookie/token migration strategy.
11. Hosting split between API/dashboards and Windows MT5 trading host.
12. MT4 live execution acceptance criteria.
13. Database migration baseline and production deployment gate.
14. Object storage provider and retention policy.

## Frozen Foundation Rule

Backend V2 Foundation is frozen. No architectural refactor, new domain layer, route consolidation, owner API, billing architecture, cache architecture, or realtime architecture may be added until the next platform phase is explicitly approved.

Only focused bug fixes are allowed during the freeze. A bug fix must preserve frozen contracts, include a regression test, and avoid introducing a new architectural boundary.
