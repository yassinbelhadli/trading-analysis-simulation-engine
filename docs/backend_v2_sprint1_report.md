# Backend V2 Sprint 1 Report

## Status

- Sprint: Backend V2 Foundation, Sprint 1
- Status: Documentation and static inventory complete
- Runtime implementation: none
- API behavior changes: none
- Database schema changes: none
- Frontend changes: none
- Trading Engine, Detection, Risk, Execution, Simulation, Renderer, MT4, MT5, and Telegram changes: none

## Scope

Sprint 1 was limited to:

- route registry
- API contract inventory
- dependency graph
- duplicate/overlapping route report
- direct route-to-database access report
- initial service/repository boundary report
- architecture and migration notes

The complete route registry is in [`api_docs.md`](api_docs.md). The broader target architecture is in [`architecture.md`](architecture.md).

## Evidence Snapshot

The main FastAPI application was imported and its OpenAPI document was inspected without starting application lifespan events.

```text
Main API paths:      133
Main API operations: 157
```

The separate MT4 bridge is not included in those numbers. Its routes are listed in `docs/api_docs.md`.

The inventory includes routes that are currently empty or not mounted as well as routes that are mounted. Empty route modules are not treated as active API contracts.

## Dependency Graph

### Runtime Graph

```text
Next.js client/admin pages
    |
    +--> frontend auth/domain clients
    |       |
    |       +--> HTTP requests and binary downloads
    |
    +--> FastAPI routes and auth dependencies
            |
            +--> direct SQLAlchemy queries and mutations (current state)
            |
            +--> partial repositories
            |       +--> users
            |       +--> accounts
            |       +--> licenses
            |       +--> scans
            |       +--> audit
            |
            +--> partial API services
            |       +--> health
            |       +--> admin overview
            |       +--> settings
            |       +--> email/news/rate limiting
            |
            +--> external integrations
            |       +--> MT4/MT5 runtime and connector
            |       +--> Telegram
            |       +--> SMTP
            |       +--> news providers
            |       +--> EA artifact storage
            |
            +--> PostgreSQL and stored application state

Telegram bot --------------------+
    |                             |
    +--> Telegram services -------+--> repositories / direct DB
    +--> MT connector ------------+--> MT4/MT5 runtime
    +--> AlertService ------------+--> process-local EventBus

Background runner --------------------> engine runner / news / health loops
                                          |
                                          +--> process-local EngineManager
                                          +--> process-local EventBus
                                          +--> MT4/MT5 runtime

Separate MT4 bridge <-------------------> local MT4 EA
```

### Target Request Graph

```text
Route + auth dependency
    -> typed request DTO
    -> application service / use case
    -> domain policy or integration port
    -> repository or query service
    -> typed response DTO / read model
```

The target graph is a migration direction. It is not implemented in Sprint 1.

### Important Process Boundary Finding

`core_engine.events.event_bus.EventBus` is process-local. The API, Telegram bot, and background runner cannot rely on it for cross-process delivery. Any future realtime or engine-control implementation needs an explicit process boundary, outbox, queue, or shared event transport. Sprint 1 does not introduce one.

## Duplicate and Overlapping Route Report

| Domain | Current contracts | Consumers | Risk | Migration decision |
|---|---|---|---|---|
| Admin users | `/api/admin/users/*` and `/admin/users/*` | Current and legacy admin pages | Different auth and response behavior | Make JWT admin route canonical; keep legacy adapter until unused |
| Admin accounts | `/api/client/accounts/*` for client and `/admin/accounts/*` for legacy admin | Client and legacy admin pages | Different lifecycle and destructive behavior | Centralize account service; preserve role-specific routes |
| Admin licenses | `/api/admin/licenses/*` and `/admin/licenses/*` | Current and legacy admin pages | Binding/expiry invariants can diverge | One license service; adapters preserve both paths temporarily |
| Client licenses | `/api/client/license` and `/api/licenses/my` | Client dashboard and license services | Two read shapes and separate binding domain | Make license domain canonical; keep client read adapter |
| License binding | `/api/licenses/bind`, `/api/licenses/unbind`, admin bind/unbind, Telegram binding | Client, admin, Telegram | Multiple mutation paths can update different fields | Centralize invariants before any route consolidation |
| Health | `/api/admin/system-health/*`, `/admin/health/*`, bridge `/health`, bridge `/api/health/*` | Admin pages, bridge, operations | Process-local and different payloads | Separate system health from bridge health; aggregate later |
| Audit | `/api/admin/audit-logs*` and `/admin/audit/*` | Current and legacy pages | Different filters/shapes and actor context | One audit query service; legacy adapter |
| Admin dashboard reads | `/api/admin/overview` plus separate health, audit, plans, users, licenses, revenue calls | Dashboard pages/topbar | Request fan-out and duplicate reads | Add purpose-built read model after service contracts exist |
| Client dashboard reads | `/api/client/dashboard` and `/api/client/overview` | Client dashboard and overview consumers | Overlapping calculated fields | Keep contracts; compare and eventually define one read model |
| Admin auth transport | `lib/api.ts`, `lib/auth.ts`, page-local license fetch | Admin pages | Duplicate token refresh/error handling | Shared transport core with separate token namespace |
| Client auth transport | `lib/client-api.ts`, `lib/client-auth.ts`, raw page fetches | Client pages | Duplicate transport and bypassed typed wrappers | Migrate consumers to domain clients later |
| Trading snapshot | Backend `/api/admin/trade/{id}/snapshot`; frontend reference `/api/admin/trading/trade/{id}/snapshot` | Trading replay page | Endpoint mismatch | Add adapter or fix consumer only after contract approval |
| Legacy account removal | Backend `POST /admin/accounts/{id}/remove`; frontend attempts `DELETE /admin/accounts/{id}` | Legacy accounts page | Method/path mismatch | Document and test adapter before deprecation |
| MT4 commands | Runtime expects order-write paths; bridge exposes data upload/read paths | MT4 runtime and bridge | Live execution contract mismatch | No change in Sprint 1; verify in a dedicated MT4 phase |

No duplicate route was deleted or renamed in this sprint.

## Direct Database Access Report

### Route Modules With Mixed Responsibilities

| Route module | Direct data touched | Logic mixed into route | Missing boundary |
|---|---|---|---|
| `api/routes/auth_router.py` | Users, sessions, verification tokens, roles | Registration, verification, reset, 2FA, session policy | `IdentityService`, session repository, verification repository |
| `api/routes/client/dashboard.py` | Trades, accounts, licenses, subscriptions, plans, audits, users | Calculations, preference validation, read-model shaping, mutations | Query services, `SubscriptionRepository`, `TradeRepository`, `PlanRepository` |
| `api/routes/client/accounts.py` | Accounts, licenses, scans, risk profiles | Input validation, MT connection, license limits, encryption, engine state | `ClientAccountService`, account/license policy, repositories |
| `api/routes/client/telegram.py` | User preferences and Telegram identity | Chat linking, preferences, audit, commit | `TelegramService`, verified-link policy |
| `api/routes/client/ea.py` | EA builds and licenses | Entitlement checks, file selection, response delivery | `EABuildRepository`, `EADeliveryService` |
| `api/routes/licenses.py` | Licenses and trading accounts | Bind/unbind invariants and audit | `LicenseService`, license/account repositories |
| `api/routes/admin/*.py` | Users, licenses, billing, news, tickets, audit, health, trades | Validation, SQL, calculations, commands, response shaping | Domain services and query services by vertical |
| `api/routes/admin_*.py` | Legacy users, accounts, licenses, audit, metrics, health | Static-token policy, direct SQL, destructive operations | Compatibility adapters over canonical services |

### Existing Persistence Seams

Already present and reusable:

- `database/repositories/user_repository.py`
- `database/repositories/account_repository.py`
- `database/repositories/license_repository.py`
- `database/repositories/scan_repository.py`
- `database/repositories/audit_repository.py`

Missing or not clearly established:

- trades and paper-trade queries
- subscriptions and plans
- payments/invoices
- news events and normalized calendar
- support tickets
- EA builds/artifacts
- RBAC query and policy access

### Transaction Finding

`database/db.py` commits on normal session exit, while many routes/services commit explicitly. This is a migration risk because a service extraction can accidentally change atomicity. No transaction behavior was changed in Sprint 1. A unit-of-work decision is required before Sprint 2 moves mutations.

## Initial Service Boundary Report

This is a boundary proposal only. No service implementation was added in Sprint 1.

| Candidate | First genuine consumers | Existing seams | First migration target |
|---|---|---|---|
| `IdentityService` | Auth routes, admin/client auth flows | `UserRepository`, session models, email service | Registration and verification workflow |
| `LicenseService` | Client license routes, admin license routes, Telegram binding | `LicenseRepository`, `AccountRepository`, binding service | Binding/activation/expiry invariants |
| `ClientAccountService` | Client accounts route, Telegram onboarding | `AccountRepository`, `ScanRepository`, `MTConnector`, `AccountManager` | Add/reconnect/disconnect lifecycle |
| `ClientDashboardQueryService` | Client dashboard and overview pages | Existing dashboard SQL, trade/account/license models | Read-only client home model |
| `AdminDashboardQueryService` | Admin overview/topbar/system pages | Admin overview/health services and audit repository | Bounded admin read model |
| `OwnerDashboardQueryService` | Future owner dashboard only | Billing, license, system, analytics queries | Define after owner policy is approved |
| `SubscriptionService` | Client subscription and admin billing | Subscription/plan models; no complete repository | State transitions and idempotency |
| `TradingQueryService` | Admin trading pages and client performance | PaperTrade queries, analytics service | Read-only query boundary; no engine rewrite |
| `TradingControlService` | Admin health/trading control routes | EngineManager and process boundary | Define command contract before implementation |
| `TelegramService` | Client Telegram routes and bot services | UserRepository, Telegram services | Verified chat linking and notifications |
| `EADeliveryService` | Client download page and license checks | EABuild model and storage | Entitlement and artifact metadata |
| `NewsService` | Admin news routes, startup worker, Telegram broadcast | News engine repositories and broadcast service | Choose authoritative store before moving SQL |
| `SettingsService` | Admin settings and ThemeProvider | `api/services/site_settings.py` | Masking and scoped settings reads |
| `SystemHealthService` | Admin system page and operational checks | `admin_health_service.py`, health monitor | Snapshot/read model; no process control yet |

### Abstraction Rule

No interface, base class, factory, or generic helper should be introduced only because it might be useful later. An abstraction is justified only when at least two existing modules genuinely require the same behavior or when an external boundary requires a stable port.

One consumer stays simple. Two or more real consumers can share a carefully scoped abstraction. The first implementation should remain concrete until the second consumer is identified.

## Migration Notes

| Sprint 1 change | Files | Runtime impact | Compatibility impact |
|---|---|---|---|
| Current architecture documentation | `docs/architecture.md` | None | None |
| Complete API registry | `docs/api_docs.md` | None | None |
| Sprint 1 report | `docs/backend_v2_sprint1_report.md` | None | None |

No route, response, schema, dependency, import, engine component, frontend file, or runtime configuration was changed by Sprint 1.

## Verification and Exit Criteria

Required regression commands:

```text
python scripts/_qa_client_sprint1.py
python scripts/_qa_client_sprint2.py
python scripts/_qa_auth_full.py
python scripts/_qa_wizard.py
```

Additional static verification:

- OpenAPI snapshot contains 133 paths and 157 operations.
- Route registry covers public/auth, current admin, client, license, signed, legacy, and separate bridge boundaries.
- Direct database access and missing repository seams are documented.
- Duplicate routes and known consumer mismatches are documented.
- No runtime implementation was changed.

Regression results:

| Suite | Result |
|---|---|
| `scripts/_qa_client_sprint1.py` | 54/54 PASS |
| `scripts/_qa_client_sprint2.py` | 62/62 PASS |
| `scripts/_qa_auth_full.py` | 22/22 PASS |
| `scripts/_qa_wizard.py` | 13/13 PASS |
| `admin_dashboard`: `npx tsc --noEmit` | PASS |
| `admin_dashboard`: `npm run build` | PASS |

Non-blocking existing warnings observed during verification:

- Starlette/httpx TestClient deprecation warning.
- Expected missing `ADMIN_TOKEN` warning in QA configuration.
- Expected SMTP-not-configured messages in email tests.
- A performance-page inspection warning was logged by the QA harness while the suite still completed with `13/13 PASS`.

Sprint 1 is complete only after the regression commands pass. After that, stop and wait for approval before Sprint 2.

## Remaining Technical Debt

This sprint intentionally did not fix:

- duplicate admin route generations
- role enforcement gaps on client routes
- license invariant divergence
- direct SQL in handlers
- inconsistent transaction ownership
- process-local engine and event state
- MT4 bridge write-contract mismatch
- EA artifact validity
- SMTP configuration
- cache or realtime transport

These are migration inputs, not Sprint 1 implementation tasks.
