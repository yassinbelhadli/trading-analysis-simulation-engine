
# ICT Funded EA Pro Architecture

## Document Status

- Status: Architecture audit and Backend V2 proposal
- Scope: API layer, application services, repositories, dashboards, integrations, and operational boundaries
- Date: 2026-08-03
- Decision: Refactor in place; do not rewrite the trading engine or database model contract
- This document describes the current system before the migration starts
- Sprint 1 registry: `docs/api_docs.md`
- Sprint 1 report: `docs/backend_v2_sprint1_report.md`
- Sprint 2 report: `docs/backend_v2_sprint2_report.md`
- Sprint 3 report: `docs/backend_v2_sprint3_report.md`
- Sprint 4 report: `docs/backend_v2_stabilization_report.md`
- Foundation freeze: `docs/backend_v2_freeze.md`

## Executive Decision

The project should move toward a modular control plane without rewriting the trading core.

The migration must be:

1. Contract-preserving: existing client, admin, Telegram, MT4, and MT5 behavior remains available while a replacement is introduced.
2. Service-first: route handlers validate transport input and delegate; business rules live in application/domain services.
3. Repository-backed: database access is isolated behind repositories or query services.
4. Engine-protected: detection, scoring, risk, execution, runtime, and event behavior are treated as contracts.
5. Observable: every route migration has request, authorization, response, latency, and regression coverage.
6. Reversible: legacy adapters remain until all consumers are migrated and the replacement has passed a deprecation window.

This is not a second trading engine. It is a cleaner API and application boundary around the existing system.

## System Context

```text
Client Web          Admin Web          Future Owner Web
    |                   |                    |
    +------------ HTTP API / SSE -----------+
                         |
                 FastAPI control plane
                         |
        +----------------+----------------+
        |                |                |
   Application       Repositories     Integrations
    services          / queries       MT4/MT5, Telegram,
        |                |             email, news, billing
        +----------------+----------------+
                         |
                    PostgreSQL

Trading engine and background workers remain separate runtime components.
They communicate through explicit control/event contracts, not route logic.
```

## Current State

### Application Processes

The repository currently contains several possible processes:

- Main FastAPI application: `api/main.py`
- Next.js dashboard: `admin_dashboard/`
- Telegram bot: `telegram_bot/bot.py`
- Background/validation runner: `scripts/background_runner.py` and related launchers
- Separate MT4 bridge: `mt4_bridge/main.py`
- Trading engine components: `core_engine/engine_manager.py` and `core_engine/engine_runner.py`

The API starts database initialization and news workers. It does not reliably start the engine runner or account scanner. The Telegram bot and API can therefore observe different in-memory engine state.

The current `EventBus` is process-local. It is not a cross-process event broker. Realtime features must not assume that an event published by the engine is visible to a separately launched API or Telegram process.

### Main API Mounts

| Effective path | Source | Boundary | Current role |
|---|---|---|---|
| `/auth/*` | `api/routes/auth_router.py` | Public plus token-specific flows | Login, registration, verification, reset, sessions, 2FA |
| `/api/admin/*` | `api/routes/admin/bundle.py` and child routers | JWT and per-handler permissions | Current admin API |
| `/api/client/*` | `api/routes/client/*.py` | JWT only | Client dashboard and account operations |
| `/api/licenses/*` | `api/routes/licenses.py` | JWT only | Client license operations outside the client prefix |
| `/api/screenshots/*` | `api/routes/screenshots.py` | Signed request | Screenshot access |
| `/admin/*` | legacy admin routers in `api/routes/admin_*.py` | Static `X-Admin-Token` | Deprecated admin API |

The main application currently exposes 134 paths and 158 operations. The count is less important than the contract duplication: the new `/api/admin/*` API and legacy `/admin/*` API expose overlapping resources with different auth rules and response shapes.

### Current Admin API Modules

The current JWT admin bundle contains:

- Overview
- Users and clients
- Roles and permissions
- Licenses
- Plans, subscriptions, payments, and revenue
- Promotions
- News and broadcasts
- Tickets
- Audit logs
- System health and controls
- Trading overview, history, signals, risk, performance, engine, and snapshots
- Site settings

The legacy API separately exposes users, accounts, licenses, health, audit, and metrics. It should not receive new features.

### Current Client API Modules

Client routes are split across several files:

- `api/routes/client/dashboard.py`: dashboard, overview, profile, trades, license, subscription, settings, performance
- `api/routes/client/accounts.py`: add, rename, disconnect, reconnect, and remove accounts
- `api/routes/client/telegram.py`: Telegram status, connection, preferences, and test notification
- `api/routes/client/ea.py`: EA versions, update checks, and downloads
- `api/routes/licenses.py`: additional license list/bind/unbind operations

The client API is already separated by URL, but its handlers still contain SQL, validation, calculations, serialization, external calls, and transaction commits in the same modules.

### Current Route Registry

The following registry is the migration baseline. Paths are effective paths after `api/main.py` prefixes are applied. A pattern such as `{id}` represents a path parameter.

#### Auth and Public

| Effective path | Methods | Consumer | Decision |
|---|---|---|---|
| `/auth/login` | POST | Client and admin login pages | Keep contract; move workflow to `IdentityService` |
| `/auth/register` | POST | Client register page | Keep contract; move workflow to `IdentityService` |
| `/auth/refresh` | POST | Admin/client auth clients | Keep contract; unify transport implementation later |
| `/auth/logout`, `/auth/logout-all` | POST | Admin/client auth flows | Keep; require authenticated actor consistently |
| `/auth/me` | GET | Security page | Keep; typed identity read model |
| `/auth/change-password` | POST | Profile/security pages | Keep; move to identity service |
| `/auth/verify-email/send`, `/auth/verify-email/confirm` | POST | Verify-email flow | Keep; SMTP must be a readiness dependency |
| `/auth/forgot-password`, `/auth/reset-password` | POST | Client reset pages | Keep; move to identity service |
| `/auth/2fa/setup`, `/auth/2fa/enable`, `/auth/2fa/disable`, `/auth/2fa/verify` | POST | Admin security flow | Keep; staff policy remains separate from client auth |
| `/auth/sessions`, `/auth/sessions/{id}` | GET, DELETE | Admin security page | Keep; repository-backed session service |
| `/auth/check-permission` | POST | Permission checks | Keep only if frontend needs it; backend authorization remains authoritative |

#### Current JWT Admin API

| Source module | Effective endpoint groups | Main consumers | Decision |
|---|---|---|---|
| `admin/overview.py` | `GET /api/admin/overview` | `/dashboard` | Use as input to admin dashboard read model |
| `admin/users.py` | Users list/detail/create/update/suspend/activate/delete | `/dashboard/users`, legacy `/users` | Consolidate behind `UserService`; retain adapter first |
| `admin/clients.py` | `GET /api/admin/clients`, `GET /api/admin/clients/{id}` | `/dashboard/clients` | Keep as client-management read model |
| `admin/roles.py` | Roles, permissions, role assignment and CRUD | `/dashboard/roles`, users page | Move RBAC queries into authorization service |
| `admin/licenses.py` | License list/detail/create/update/activate/deactivate/unbind/reset/delete | `/dashboard/licenses`, legacy `/licenses` | Consolidate with `LicenseService`; no hard delete by default |
| `admin/billing.py` | Plans, subscriptions, payments, revenue analytics | subscriptions, billing, promotions, owner future | Split billing service from owner read models |
| `admin/promotions.py` | Promotion list/create/update/delete/toggle | `/dashboard/promotions` | Keep domain-owned; typed DTOs |
| `admin/news.py` | Engine status, news list/create/update/delete/broadcast | `/dashboard/news`, news workers, Telegram | Move to `NewsService`; fix broadcast integration before migration |
| `admin/tickets.py` | Ticket list/detail/update/escalate/ban | `/dashboard/tickets` | Move to `SupportService`; enforce permission server-side |
| `admin/audit.py` | Audit list and summary | dashboard/audit pages | Keep append-only query service and shared audit policy |
| `admin/settings.py` | Settings schema/read/update | admin settings, ThemeProvider | Keep masked responses; never return decrypted secrets |
| `admin/system_health.py` | Health, summary, engines, heartbeat, report, restart/stop/start controls | system page, topbar | Aggregate through `SystemHealthService`; define process ownership first |
| `admin/trading.py` | Trading overview, active/history/signals/risk/performance, engine/logs, controls, snapshot | trading pages | Move reads/commands to trading control plane; do not move engine rules here |

#### Current JWT Client API

| Source module | Effective endpoint groups | Main consumers | Decision |
|---|---|---|---|
| `client/dashboard.py` | `/api/client/dashboard`, `/overview`, `/profile`, `/trades`, `/license`, `/subscription`, `/settings`, `/performance` | All client dashboard pages | Split into client read models and domain services without changing client contracts first |
| `client/accounts.py` | `/api/client/accounts` list/add, `/{id}` rename/delete, `/{id}/disconnect`, `/{id}/reconnect` | Client accounts page, Telegram onboarding reuse | Route through `ClientAccountService` and centralized license invariants |
| `client/telegram.py` | `/api/client/telegram` status/connect/disconnect/preferences/test | Client Telegram page | Route through verified `TelegramService`; reject arbitrary chat IDs |
| `client/ea.py` | `/api/client/ea`, `/check-updates`, `/download/latest`, `/download/{build_id}` | Client download page | Route through `EADeliveryService`; artifact validity is a release gate |
| `licenses.py` | `/api/licenses/my`, `/bind`, `/unbind` | Client license flows and Telegram services | Make license domain canonical; keep client adapters for compatibility |

#### Supporting and Separate APIs

| Effective path | Source | Consumer | Decision |
|---|---|---|---|
| `/api/screenshots/{trade_id}/{type}` | `routes/screenshots.py` | Renderer/dashboard links | Keep signed access boundary; no JWT bypass |
| `/api/health/*` | `mt4_bridge` and health routes | Operations/bridge clients | Keep separate until bridge ownership is redesigned |
| `/admin/health/*`, `/admin/users/*`, `/admin/accounts/*`, `/admin/licenses/*`, `/admin/audit/*`, `/admin/metrics` | Legacy admin routers | Legacy frontend pages and scripts | No new features; compatibility adapter then deprecate |

#### Consumer Ownership

| Consumer | Allowed API owner | Current exceptions to remove |
|---|---|---|
| `app/client/**` | Client/auth clients | Raw verify-email fetch; direct generic fetch for trades/performance |
| `app/dashboard/**` | Admin/auth clients | Local license fetch helper; repeated legacy aliases |
| `app/users`, `app/audit`, `app/health`, `app/accounts`, `app/licenses` | Temporary legacy adapter | Migrate or retire after usage is measured |
| `telegram_bot/**` | Telegram, license, account, and engine services | Avoid route imports and duplicate binding logic |
| `core_engine/**` | Engine/runtime/event contracts | API may issue commands through a control port only |

No route is marked for immediate deletion. `consolidate` means move ownership behind a service and adapter first; `deprecate` means remove only after consumer evidence and contract tests.

### Authorization Boundaries

Current authorization has important gaps to resolve before production:

- `/api/client/*` checks for an active JWT but does not explicitly require a client role.
- `/api/licenses/*` has the same broad JWT boundary.
- `/api/admin/*` uses permission dependencies, but not every admin page has a matching frontend permission guard.
- `/admin/*` uses a static token and has no consistent user/actor context.
- Frontend guards currently check token presence before the API validates the token, role, or permission.
- The frontend has both current and legacy admin pages, so route ownership is unclear.

## Direct Database Access Inventory

The following route modules currently mix transport and persistence/business logic:

- `api/routes/auth_router.py`: identity, sessions, verification, reset, and 2FA
- `api/routes/client/dashboard.py`: trades, accounts, licenses, subscriptions, plans, settings, and calculations
- `api/routes/client/accounts.py`: account validation, MT connection, license checks, persistence, risk profile creation, and engine state
- `api/routes/client/telegram.py`: user mutation, preferences, audit, and commit
- `api/routes/client/ea.py`: build and license queries plus file delivery
- `api/routes/licenses.py`: license binding invariants and account mutation
- Most modules under `api/routes/admin/`
- Legacy modules under `api/routes/admin_*.py`

Existing persistence seams are available but incomplete:

- `database/repositories/user_repository.py`
- `database/repositories/account_repository.py`
- `database/repositories/license_repository.py`
- `database/repositories/scan_repository.py`
- `database/repositories/audit_repository.py`

Repositories are missing for trades, subscriptions, plans, news, tickets, and EA builds. Some existing repositories are also mixed with route-level business logic.

The transaction policy is inconsistent. `database/db.py` commits on normal session exit while many routes and services also commit explicitly. Backend V2 needs one clear unit-of-work policy.

## Frontend Architecture Audit

### Current Frontend Clients

- `admin_dashboard/lib/api.ts`: admin transport and typed wrappers, plus legacy aliases
- `admin_dashboard/lib/auth.ts`: admin authentication and token storage
- `admin_dashboard/lib/client-api.ts`: client domain wrappers
- `admin_dashboard/lib/client-auth.ts`: client authentication, token storage, and generic client fetch

Admin and client transports duplicate bearer handling, refresh, error parsing, and API URL resolution. The separate token namespaces are correct, but the transport implementation should be shared behind role-specific token providers.

There are also page-local fetch implementations:

- `app/dashboard/licenses/page.tsx` has its own admin fetch helper
- `app/client/verify-email/page.tsx` uses raw fetch
- `app/client/dashboard/trades/page.tsx` bypasses `getClientTrades`
- `app/client/dashboard/performance/page.tsx` bypasses `getClientPerformance`
- EA binary download has a separate raw fetch path

### Request Fan-out

The current dashboard is request-heavy because shared and page-level data are loaded independently.

Examples:

| Page | Page-owned initial requests | Shared/extra requests | Main issue |
|---|---:|---:|---|
| `/dashboard` | 2 | Topbar repeats overview | Duplicate overview read |
| `/dashboard/system` | 4 | Theme settings | Health data is split across calls |
| `/dashboard/licenses` | 3 | Theme settings | Licenses, plans, and users reload together after mutations |
| `/dashboard/users` | 2 | Theme settings | Users and roles are reloaded together for every mutation |
| `/client/dashboard` | 1 | ThemeProvider settings probe/fallback | Client can probe admin settings before client settings |
| `/client/dashboard/settings` | 1 | ThemeProvider reload after save | Duplicate client settings read |
| `/client/dashboard/accounts` | 1 | Refresh after mutations | Expected, but no shared client cache |

The target is not one giant response for every screen. The target is one purpose-built page read model per high-value dashboard, returning only the fields used by that screen.

### Frontend Access Boundaries

The target frontend rule is:

```text
Client pages -> client API client only
Admin pages  -> admin API client only
Owner pages  -> owner API client only
```

No client component should call `/api/admin/*`, `/admin/*`, or owner-only resources. No owner UI should infer access from a client response.

## Target Backend V2

### Canonical API Domains

These are target ownership domains, not an instruction to rename every URL in one release:

```text
/api/auth
/api/client
/api/admin
/api/owner
/api/trading
/api/telegram
/api/licenses
/api/billing
/api/news
/api/settings
/api/system
```

The first migration should establish ownership and service contracts while keeping existing routes as adapters. URL consolidation comes only after consumer inventory and contract tests are in place.

Recommended ownership:

| Domain | Owns | Does not own |
|---|---|---|
| Auth | identity, sessions, verification, 2FA | trading decisions |
| Client | client profile, client read models, client account actions | global admin data |
| Admin | operational management and support | owner-only global analytics |
| Owner | global business, revenue, system, and tenant analytics | individual client secrets |
| Trading | engine control-plane commands and read models | detection/risk implementation |
| Telegram | bot linking, notifications, bot-facing commands | arbitrary user mutations |
| Licenses | license lifecycle and binding invariants | payment gateway details |
| Billing | plans, subscriptions, payments, invoices | broker credentials |
| News | ingestion, calendar, impact state, broadcasts | account passwords |
| Settings | validated configuration and feature settings | decrypted secret responses |
| System | health, readiness, metrics, operational status | trading policy decisions |

### Layered Request Flow

```text
HTTP route / dependency
    -> request DTO and authorization
    -> application service / use case
    -> domain policy or integration port
    -> repository or query service
    -> response DTO / read model
```

Route handlers should contain only:

- HTTP method/path declaration
- authentication and permission dependencies
- Pydantic input/output models
- request-specific validation
- service invocation
- HTTP status mapping

Services should contain:

- business workflows
- transaction orchestration
- audit event decisions
- calls to repositories and integration ports
- domain invariant enforcement

Repositories/query services should contain:

- SQLAlchemy statements
- persistence mapping
- pagination and filtering primitives
- no HTTP-specific behavior

Integrations should contain:

- MT4/MT5 connector calls
- Telegram API calls
- SMTP/provider calls
- payment provider calls
- news provider calls

### Initial Service Boundaries

Create services only when a workflow is moved, not as empty abstractions:

- `IdentityService`: registration, verification, sessions, reset, 2FA
- `ClientAccountService`: add, validate, reconnect, disconnect, rename, removal policy
- `LicenseService`: activation, expiry, binding, unbinding, transfer lock, account linkage
- `SubscriptionService`: plan selection, renewal, cancellation, invoices
- `ClientDashboardQueryService`: client-specific read models
- `AdminDashboardQueryService`: operational admin read models
- `OwnerDashboardQueryService`: global owner read models
- `TradingQueryService`: trade and engine read models only
- `TradingControlService`: commands to the engine control plane, not direct detection logic
- `TelegramService`: verified linking and notification preferences
- `EADeliveryService`: build metadata, entitlement checks, artifact delivery
- `NewsService`: provider ingestion, normalized calendar, broadcast scheduling
- `SettingsService`: validation, masking, encryption, and scoped settings
- `SystemHealthService`: health snapshots and readiness state

### Repository and Query Plan

Add persistence seams by vertical:

- `TradeRepository` and `TradeQueryService`
- `SubscriptionRepository`
- `PlanRepository`
- `NewsRepository` for the authoritative store
- `TicketRepository`
- `EABuildRepository`
- RBAC query repositories for roles and permissions

Existing repositories should be reused and expanded rather than duplicated. The first candidate is the account/license workflow because it already has partial repository and service seams.

### Dashboard Aggregation

Introduce purpose-built aggregation endpoints after services exist:

- `GET /api/client/dashboard`: client home read model
- `GET /api/admin/dashboard`: operational admin read model
- `GET /api/owner/dashboard`: owner business/system read model

Each aggregator should:

- call independent query services concurrently where safe
- return only fields used by that page
- include a stable response schema
- expose a server-generated `generated_at`
- report partial read failures without leaking internal errors
- avoid exposing secrets or full database records

The aggregator is a read model, not a new place for business rules. Mutations remain in their domain services.

### Caching Policy

Use a cache interface so the first implementation can be local TTL or Redis without changing services.

| Data | Suggested TTL | Invalidation |
|---|---:|---|
| System health snapshot | 5 seconds | TTL; explicit refresh after control command |
| Engine status snapshot | 5 seconds | Engine event/control result |
| Plan catalog | 60 seconds | Plan mutation |
| Latest EA metadata | 60 seconds | Build publish |
| Public/site settings | 30 seconds | Settings mutation |
| Client dashboard read model | 2-5 seconds | Account/license/trade event or TTL |
| Owner revenue summary | 15-60 seconds | Billing event or TTL |

Do not cache passwords, tokens, broker credentials, or mutable risk decisions. A process-local cache is acceptable only while the API is single-process. Multi-process deployment requires a shared cache or explicit consistency rules.

### Realtime Policy

The current in-memory `EventBus` cannot provide cross-process realtime. Do not add a WebSocket route that reads only that singleton and call it production-ready.

Recommended sequence:

1. Define stable event names and payload schemas from the existing event types.
2. Add an outbox or shared event transport at the process boundary.
3. Publish engine, trade, risk, and health events to that transport.
4. Expose SSE for dashboard read-only updates first.
5. Use WebSocket only if bidirectional interaction is actually required.

Realtime must be additive. The database/read model remains the source for page refresh and recovery after reconnect.

## Engine Protection Boundary

The following are behavioral contracts and must not be rewritten as part of the API refactor:

- `core_engine/engine_manager.py`
- `core_engine/engine_runner.py`
- `core_engine/detection/`
- `core_engine/scoring/`
- `core_engine/filters/`
- `core_engine/risk/`
- `core_engine/execution/`
- `core_engine/mt_runtime.py`
- `core_engine/mt4_runtime.py`
- `core_engine/mt5_runtime.py`
- `telegram_bot/services/mt_connector.py`
- `telegram_bot/services/account_verification_service.py`
- `telegram_bot/services/license_binding_service.py`
- `core_engine/events/event_types.py` and `event_bus.py`
- database models and existing migration history

The API may call these through ports or existing services. It must not move trading decisions into route handlers, Telegram handlers, or dashboard aggregators.

Important current risks to solve outside the engine rewrite:

- API-local `EngineManager` state may not represent the background runner process.
- Engine runner task ownership and manager task ownership are not clearly unified.
- MT4 runtime expects write endpoints that the read-only bridge does not provide.
- Real execution and paper-trade read models are not clearly one durable source.
- News failure behavior must remain capital-protective; an API refactor must not make news checks fail open.

## Migration Plan

### Phase 0: Contract Freeze and Inventory

Deliverables:

- route registry with method, path, auth, consumer, response model, and deprecation status
- frontend consumer matrix
- OpenAPI snapshot
- baseline request/latency/error metrics
- contract tests for client, admin, Telegram, licenses, EA, and auth
- explicit list of legacy routes that must remain temporarily

Exit gate:

- every active frontend request maps to one documented backend contract
- no route is removed or renamed in this phase

### Phase A: Domain, SMTP, and Configuration

Deliverables:

- production domain and trusted CORS origins
- SMTP provider and verified sender
- environment-only secrets
- masked settings responses
- startup configuration validation
- Alembic migration policy instead of relying on `create_all` for production schema changes
- health/readiness checks for database, SMTP, Telegram, MT5/MT4 bridge, and storage

Exit gate:

- new client can register, receive verification, verify, log in, and reset a password
- no secret appears in API responses or logs

### Phase B: Backend Service and API Refactor

Order of verticals:

1. License and account lifecycle
2. Client dashboard read models
3. Identity/auth workflows
4. Subscription and billing
5. Admin operational resources
6. News and tickets

Rules:

- introduce a service behind the existing route first
- preserve response shape until the consumer migrates
- add repository/query seam before moving SQL
- service owns transaction and audit behavior
- use typed request/response schemas
- compare old and new results in tests before switching consumers

Exit gate:

- route handlers no longer contain the moved workflow
- contract and regression suites are green
- legacy adapter still passes during the deprecation window

### Phase C: Client Dashboard

Deliverables:

- client-only API client and typed DTOs
- client dashboard aggregator/read model
- role-aware ThemeProvider/settings loading
- shared client request/cache layer
- settings, account, license, Telegram, and EA clients with no page-local fetch helpers
- SSE only after the read model is stable

Exit gate:

- client frontend makes no admin or legacy admin requests
- dashboard initial load uses the intended bounded request count
- account/license invariants pass end-to-end tests

### Phase D: Admin Dashboard

Deliverables:

- one canonical admin frontend client
- current `/api/admin/*` routes become the only new API surface
- legacy pages migrate to current contracts or are explicitly retired
- admin dashboard aggregation for overview/system pages
- visibility-aware refresh and cache invalidation
- page permissions match backend permissions

Exit gate:

- no active admin page depends on `/admin/*`
- no page-local authenticated transport remains
- every privileged page has backend and frontend authorization coverage

### Phase E: Owner Dashboard

Deliverables:

- explicit owner role and permissions
- `/api/owner/*` API boundary
- owner dashboard read models for revenue, plans, licenses, health, signals, and system status
- tenant/client data minimization
- separate owner frontend route tree and client/admin API clients

Exit gate:

- a client token cannot access owner resources
- an admin without the owner permission cannot access owner resources
- owner metrics do not require the frontend to fan out into unrelated admin endpoints

### Phase F: Telegram and Realtime

Deliverables:

- verified Telegram `/start` linking flow
- one Telegram service for web and bot workflows
- shared event transport or outbox
- SSE/WebSocket gateway with reconnect and authorization
- event payload versioning

Exit gate:

- arbitrary `chat_id` cannot be linked
- notifications are scoped to the owning client/account
- reconnecting a dashboard cannot lose the source-of-truth state

### Phase G: Billing

Deliverables:

- billing service and payment provider adapter
- subscription state machine
- invoice/payment read models
- idempotency keys and webhook verification
- license entitlement synchronization

Exit gate:

- payment events are idempotent and auditable
- license activation/expiry follows one source of truth
- billing secrets never reach client or admin read models

### Phase H: Production

Deliverables:

- deployable API/frontend/worker topology
- shared cache/event transport where required
- database backup and migration runbook
- structured logs, metrics, tracing, and alerts
- rollback plan
- legacy route deprecation and removal plan
- production manual client journey

Exit gate:

- no unresolved critical security or capital-protection issue
- migration and rollback tested on a staging copy
- real MT4/MT5, Telegram, SMTP, billing, and email flows verified with non-production credentials

## First Implementation Slice

The first code slice should be deliberately small:

1. Add a route registry and API contract tests without changing behavior.
2. Create `LicenseService` around the existing license repository and binding rules.
3. Route client account/license binding through that service.
4. Add `ClientDashboardQueryService` for the existing dashboard response.
5. Add typed response models for those two flows.
6. Migrate only the client account and license frontend calls to the typed clients.
7. Measure request count and latency before adding cache.

Do not start with a global rename, a new owner dashboard, a WebSocket, or a rewrite of the engine. Those depend on contracts that are not yet frozen.

## Deprecation Rules

- No new feature goes into `/admin/*` legacy routes.
- No client frontend code may import admin API clients.
- No route is deleted until its consumers, logs, and contract tests show zero active use for the agreed window.
- Compatibility adapters must log deprecation usage without logging secrets.
- Response changes require a new typed contract or an explicit versioned field.
- Destructive operations require soft-delete or an explicit recovery policy; data must not be deleted automatically.

## Required Tests and Observability

Every migrated vertical needs:

- unit tests for service rules
- repository/query tests
- API authorization tests for client, admin, and owner roles
- response contract tests
- frontend consumer tests or typed compile coverage
- transaction rollback test
- audit event test
- latency and request-count baseline
- negative tests for invalid and unauthorized inputs

Trading-sensitive workflows additionally require:

- license expiry and transfer-lock tests
- daily loss and maximum drawdown regression tests
- news/spread/session filter regression tests
- MT4 and MT5 runtime compatibility tests
- no-trade-on-failure tests
- paper/live read-model consistency checks

## Open Decisions Before Coding

These decisions should be recorded before Phase B implementation:

- Is `/api` the permanent unversioned public contract, or should new contracts use `/api/v2`?
- Which process owns the engine control plane?
- Which event transport is acceptable for multi-process deployment?
- Is Redis available for shared cache/events, or is a database outbox preferred initially?
- Which billing provider and webhook model will be used?
- Which existing legacy admin pages must remain available during migration?
- What is the exact owner role model and tenant visibility policy?
- Which database migration tool and deployment gate are authoritative?

## Non-Goals

This document does not authorize:

- rewriting detection, scoring, risk, or execution logic
- replacing MT4/MT5 runtimes
- deleting legacy routes immediately
- changing database models without a migration plan
- adding realtime transport before cross-process event ownership is defined
- adding a generic 40-field response used by every dashboard
- moving business logic into Telegram or HTTP handlers
