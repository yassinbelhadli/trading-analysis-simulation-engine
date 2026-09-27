# API Contract Inventory

## Snapshot

- Application: `api/main.py`
- Snapshot date: 2026-08-03
- Main API paths: 134
- Main API operations: 158
- Source: static `app.openapi()` inspection; no application code was changed
- Contract status values used below: `canonical`, `compatibility`, `duplicate`, `separate`

This is the current-state registry for Backend V2 Sprint 1. It is not a permission change, route rename, or implementation proposal.

## Authentication Matrix

| Boundary | Current rule | Consumer |
|---|---|---|
| `/auth/*` | Endpoint-specific public, short-lived token, or JWT behavior | Login, register, reset, security pages |
| `/api/admin/*` | JWT plus per-handler permission dependency | Current admin dashboard |
| `/api/client/*` | Active JWT; explicit client-role enforcement is not consistent | Client dashboard |
| `/api/licenses/*` | Active JWT; shared license boundary | Client web and Telegram services |
| `/api/screenshots/*` | Signed request | Renderer and dashboard links |
| `/admin/*` | Static `X-Admin-Token` dependency | Legacy admin pages/scripts |
| MT4 bridge | No authentication in the bridge app | Local MT4 bridge clients |

Response models are not uniformly declared. Many handlers return untyped dictionaries or lists. The frontend contract sources are currently `admin_dashboard/lib/api.ts`, `admin_dashboard/lib/client-api.ts`, `admin_dashboard/lib/auth.ts`, and `admin_dashboard/lib/client-auth.ts`, plus several page-local fetch helpers.

## Public and Authentication Routes

Consumer: client and admin authentication pages, security pages, and auth clients.

| Method | Path | Contract status | Notes |
|---|---|---|---|
| POST | `/auth/login` | canonical | Returns access/refresh tokens and user data |
| POST | `/auth/register` | canonical | Registration and verification-email attempt |
| POST | `/auth/refresh` | canonical | Refreshes an access token |
| POST | `/auth/logout` | canonical | Session logout |
| POST | `/auth/logout-all` | canonical | Revokes user sessions |
| GET | `/auth/me` | canonical | Current authenticated identity |
| POST | `/auth/change-password` | canonical | Password change |
| POST | `/auth/verify-email/send` | canonical | Sends/resends verification code |
| POST | `/auth/verify-email/confirm` | canonical | Confirms verification code |
| POST | `/auth/forgot-password` | canonical | Starts password reset |
| POST | `/auth/reset-password` | canonical | Completes password reset |
| POST | `/auth/2fa/setup` | canonical | Staff 2FA setup |
| POST | `/auth/2fa/enable` | canonical | Staff 2FA enable |
| POST | `/auth/2fa/disable` | canonical | Staff 2FA disable |
| POST | `/auth/2fa/verify` | canonical | Short-lived 2FA verification |
| GET | `/auth/sessions` | canonical | Lists sessions |
| DELETE | `/auth/sessions/{session_id}` | canonical | Revokes one session |
| POST | `/auth/check-permission` | canonical | Permission check endpoint |

Source: `api/routes/auth_router.py`.

## Current JWT Admin Routes

Consumer: `admin_dashboard/app/dashboard/**` through `admin_dashboard/lib/api.ts` and `admin_dashboard/lib/auth.ts`.

Authentication: JWT plus handler-level permission checks.

### Overview, Users, Clients, Roles

| Method | Path | Source | Contract status |
|---|---|---|---|
| GET | `/api/admin/overview` | `admin/overview.py` | canonical |
| GET | `/api/admin/users` | `admin/users.py` | canonical |
| GET | `/api/admin/users/{user_id}` | `admin/users.py` | canonical |
| PATCH | `/api/admin/users/{user_id}` | `admin/users.py` | canonical |
| POST | `/api/admin/users` | `admin/users.py` | canonical |
| POST | `/api/admin/users/{user_id}/suspend` | `admin/users.py` | canonical |
| POST | `/api/admin/users/{user_id}/activate` | `admin/users.py` | canonical |
| DELETE | `/api/admin/users/{user_id}` | `admin/users.py` | destructive; review |
| GET | `/api/admin/clients` | `admin/clients.py` | canonical |
| GET | `/api/admin/clients/{client_id}` | `admin/clients.py` | canonical |
| GET | `/api/admin/roles` | `admin/roles.py` | canonical |
| GET | `/api/admin/roles/{role_id}` | `admin/roles.py` | canonical |
| POST | `/api/admin/roles` | `admin/roles.py` | canonical |
| PATCH | `/api/admin/roles/{role_id}` | `admin/roles.py` | canonical |
| DELETE | `/api/admin/roles/{role_id}` | `admin/roles.py` | destructive; review |
| GET | `/api/admin/permissions` | `admin/roles.py` | canonical |
| POST | `/api/admin/roles/assign` | `admin/roles.py` | canonical |

### Licenses and Billing

| Method | Path | Source | Contract status |
|---|---|---|---|
| GET | `/api/admin/licenses` | `admin/licenses.py` | duplicate domain |
| GET | `/api/admin/licenses/{license_id}` | `admin/licenses.py` | duplicate domain |
| POST | `/api/admin/licenses` | `admin/licenses.py` | duplicate domain |
| PATCH | `/api/admin/licenses/{license_id}` | `admin/licenses.py` | duplicate domain |
| POST | `/api/admin/licenses/{license_id}/activate` | `admin/licenses.py` | duplicate domain |
| POST | `/api/admin/licenses/{license_id}/deactivate` | `admin/licenses.py` | duplicate domain |
| POST | `/api/admin/licenses/{license_id}/unbind` | `admin/licenses.py` | duplicate domain |
| POST | `/api/admin/licenses/{license_id}/reset` | `admin/licenses.py` | duplicate domain |
| DELETE | `/api/admin/licenses/{license_id}` | `admin/licenses.py` | destructive; review |
| GET | `/api/admin/plans` | `admin/billing.py` | billing catalog |
| PUT | `/api/admin/plans/{plan_id}` | `admin/billing.py` | billing catalog |
| POST | `/api/admin/plans/restore-defaults` | `admin/billing.py` | billing catalog |
| GET | `/api/admin/subscriptions` | `admin/billing.py` | billing |
| PATCH | `/api/admin/subscriptions/{sub_id}` | `admin/billing.py` | billing |
| POST | `/api/admin/subscriptions/{sub_id}/cancel` | `admin/billing.py` | billing |
| GET | `/api/admin/payments` | `admin/billing.py` | billing |
| GET | `/api/admin/analytics/revenue` | `admin/billing.py` | owner candidate |

### News, Promotions, Tickets, Audit, and Settings

| Method | Path | Source | Contract status |
|---|---|---|---|
| GET | `/api/admin/news/engine-status` | `admin/news.py` | news |
| GET | `/api/admin/news` | `admin/news.py` | news |
| POST | `/api/admin/news` | `admin/news.py` | news |
| PATCH | `/api/admin/news/{news_id}` | `admin/news.py` | news |
| DELETE | `/api/admin/news/{news_id}` | `admin/news.py` | destructive; review |
| POST | `/api/admin/news/{news_id}/broadcast` | `admin/news.py` | news/Telegram integration |
| GET | `/api/admin/promotions` | `admin/promotions.py` | billing candidate |
| POST | `/api/admin/promotions` | `admin/promotions.py` | billing candidate |
| PUT | `/api/admin/promotions/{promo_id}` | `admin/promotions.py` | billing candidate |
| DELETE | `/api/admin/promotions/{promo_id}` | `admin/promotions.py` | destructive; review |
| POST | `/api/admin/promotions/{promo_id}/toggle` | `admin/promotions.py` | billing candidate |
| GET | `/api/admin/tickets` | `admin/tickets.py` | support |
| GET | `/api/admin/tickets/{ticket_id}` | `admin/tickets.py` | support |
| PATCH | `/api/admin/tickets/{ticket_id}` | `admin/tickets.py` | support |
| POST | `/api/admin/tickets/{ticket_id}/escalate` | `admin/tickets.py` | support |
| POST | `/api/admin/tickets/{ticket_id}/ban` | `admin/tickets.py` | security-sensitive |
| GET | `/api/admin/audit-logs` | `admin/audit.py` | audit |
| GET | `/api/admin/audit-logs/summary` | `admin/audit.py` | audit |
| GET | `/api/admin/settings/schema` | `admin/settings.py` | settings |
| GET | `/api/admin/settings` | `admin/settings.py` | settings |
| PUT | `/api/admin/settings` | `admin/settings.py` | settings; secret response review |

### System Health and Trading

| Method | Path | Source | Contract status |
|---|---|---|---|
| GET | `/api/admin/system-health` | `admin/system_health.py` | system |
| GET | `/api/admin/system-health/summary` | `admin/system_health.py` | system |
| GET | `/api/admin/system-health/engines` | `admin/system_health.py` | system |
| GET | `/api/admin/system-health/heartbeat` | `admin/system_health.py` | system |
| GET | `/api/admin/system-health/report` | `admin/system_health.py` | system |
| POST | `/api/admin/system-health/engine/restart` | `admin/system_health.py` | command; process ownership review |
| POST | `/api/admin/system-health/engine/stop` | `admin/system_health.py` | command; process ownership review |
| POST | `/api/admin/system-health/engine/start` | `admin/system_health.py` | command; process ownership review |
| POST | `/api/admin/system-health/telegram/restart` | `admin/system_health.py` | command; process ownership review |
| POST | `/api/admin/system-health/mt5/restart` | `admin/system_health.py` | command; process ownership review |
| POST | `/api/admin/system-health/api/restart` | `admin/system_health.py` | command; process ownership review |
| GET | `/api/admin/trading/overview` | `admin/trading.py` | trading read model |
| GET | `/api/admin/trading/active-trades` | `admin/trading.py` | trading read model |
| GET | `/api/admin/trading/history` | `admin/trading.py` | trading read model |
| GET | `/api/admin/trading/signals` | `admin/trading.py` | trading read model |
| GET | `/api/admin/trading/risk` | `admin/trading.py` | trading read model |
| GET | `/api/admin/trading/performance` | `admin/trading.py` | trading read model |
| GET | `/api/admin/trading/engine` | `admin/trading.py` | trading read model |
| GET | `/api/admin/trading/engine/logs` | `admin/trading.py` | trading read model |
| POST | `/api/admin/trading/control/enable` | `admin/trading.py` | command; engine boundary |
| POST | `/api/admin/trading/control/disable` | `admin/trading.py` | command; engine boundary |
| POST | `/api/admin/trading/control/pause` | `admin/trading.py` | command; engine boundary |
| POST | `/api/admin/trading/control/resume` | `admin/trading.py` | command; engine boundary |
| POST | `/api/admin/trading/control/close-all` | `admin/trading.py` | command; capital-sensitive |
| POST | `/api/admin/trading/control/close-symbol` | `admin/trading.py` | command; capital-sensitive |
| POST | `/api/admin/trading/control/emergency-stop` | `admin/trading.py` | command; capital-sensitive |
| GET | `/api/admin/trade/{trade_id}/snapshot` | `admin/trading.py` | renderer/read model |
| GET | `/api/admin/trading/trade/{trade_id}/snapshot` | `admin/trading.py` | compatibility alias for existing frontend consumer |

## Current JWT Client Routes

Consumer: `admin_dashboard/app/client/**` through `lib/client-api.ts` and `lib/client-auth.ts`.

| Method | Path | Source | Contract status |
|---|---|---|---|
| GET | `/api/client/dashboard` | `client/dashboard.py` | canonical client read model |
| GET | `/api/client/overview` | `client/dashboard.py` | overlapping client read model |
| GET | `/api/client/profile` | `client/dashboard.py` | canonical client |
| PATCH | `/api/client/profile` | `client/dashboard.py` | canonical client |
| GET | `/api/client/trades` | `client/dashboard.py` | canonical client |
| GET | `/api/client/license` | `client/dashboard.py` | overlapping license read model |
| GET | `/api/client/subscription` | `client/dashboard.py` | canonical client |
| POST | `/api/client/subscription/cancel` | `client/dashboard.py` | canonical client |
| POST | `/api/client/subscription/renew` | `client/dashboard.py` | canonical client |
| GET | `/api/client/settings` | `client/dashboard.py` | canonical client |
| PATCH | `/api/client/settings` | `client/dashboard.py` | canonical client |
| GET | `/api/client/performance` | `client/dashboard.py` | canonical client |
| GET | `/api/client/accounts` | `client/accounts.py` | canonical client |
| POST | `/api/client/accounts` | `client/accounts.py` | capital-sensitive integration |
| PATCH | `/api/client/accounts/{account_id}` | `client/accounts.py` | canonical client |
| DELETE | `/api/client/accounts/{account_id}` | `client/accounts.py` | destructive; review |
| POST | `/api/client/accounts/{account_id}/disconnect` | `client/accounts.py` | canonical client |
| POST | `/api/client/accounts/{account_id}/reconnect` | `client/accounts.py` | capital-sensitive integration |
| GET | `/api/client/telegram` | `client/telegram.py` | canonical client |
| POST | `/api/client/telegram/connect` | `client/telegram.py` | security-sensitive; verification gap |
| POST | `/api/client/telegram/disconnect` | `client/telegram.py` | canonical client |
| PATCH | `/api/client/telegram/preferences` | `client/telegram.py` | canonical client |
| POST | `/api/client/telegram/test` | `client/telegram.py` | canonical client |
| GET | `/api/client/ea` | `client/ea.py` | canonical client |
| POST | `/api/client/ea/check-updates` | `client/ea.py` | canonical client |
| GET | `/api/client/ea/download/latest` | `client/ea.py` | artifact/release contract |
| GET | `/api/client/ea/download/{build_id}` | `client/ea.py` | artifact/release contract |

## License, Signed, and Legacy Routes

### License Domain Outside Client Prefix

Consumer: client web flows and Telegram license services. Authentication: active JWT.

| Method | Path | Source | Contract status |
|---|---|---|---|
| GET | `/api/licenses/my` | `routes/licenses.py` | overlapping license read model |
| POST | `/api/licenses/bind` | `routes/licenses.py` | duplicate binding workflow |
| POST | `/api/licenses/unbind` | `routes/licenses.py` | duplicate binding workflow |

### Signed Screenshot Access

| Method | Path | Source | Contract status |
|---|---|---|---|
| GET | `/api/screenshots/{trade_id}/{type}` | `routes/screenshots.py` | separate signed boundary |

### Legacy Static-Token Admin API

Consumer: legacy frontend pages, scripts, and compatibility callers. Authentication: `X-Admin-Token`.

| Method | Path | Source | Contract status |
|---|---|---|---|
| GET | `/admin/health` | `admin_health.py` | duplicate; deprecate later |
| GET | `/admin/health/summary` | `admin_health.py` | duplicate; deprecate later |
| GET | `/admin/health/engines` | `admin_health.py` | duplicate; deprecate later |
| GET | `/admin/users` | `admin_users.py` | duplicate; deprecate later |
| GET | `/admin/users/{user_id}` | `admin_users.py` | duplicate; deprecate later |
| PATCH | `/admin/users/{user_id}` | `admin_users.py` | duplicate; deprecate later |
| GET | `/admin/accounts` | `admin_accounts.py` | duplicate; legacy |
| GET | `/admin/accounts/{account_id}` | `admin_accounts.py` | duplicate; legacy |
| PATCH | `/admin/accounts/{account_id}` | `admin_accounts.py` | duplicate; legacy |
| POST | `/admin/accounts/{account_id}/pause` | `admin_accounts.py` | duplicate; legacy |
| POST | `/admin/accounts/{account_id}/resume` | `admin_accounts.py` | duplicate; legacy |
| POST | `/admin/accounts/{account_id}/disable` | `admin_accounts.py` | duplicate; legacy |
| POST | `/admin/accounts/{account_id}/remove` | `admin_accounts.py` | destructive; legacy |
| GET | `/admin/licenses` | `admin_licenses.py` | duplicate; legacy |
| GET | `/admin/licenses/{license_id}` | `admin_licenses.py` | duplicate; legacy |
| POST | `/admin/licenses` | `admin_licenses.py` | duplicate; legacy |
| PATCH | `/admin/licenses/{license_id}` | `admin_licenses.py` | duplicate; legacy |
| POST | `/admin/licenses/{license_id}/activate` | `admin_licenses.py` | duplicate; legacy |
| POST | `/admin/licenses/{license_id}/deactivate` | `admin_licenses.py` | duplicate; legacy |
| POST | `/admin/licenses/{license_id}/unbind` | `admin_licenses.py` | duplicate; legacy |
| POST | `/admin/licenses/{license_id}/reset` | `admin_licenses.py` | duplicate; legacy |
| DELETE | `/admin/licenses/{license_id}` | `admin_licenses.py` | destructive; legacy |
| GET | `/admin/audit/recent` | `admin_audit.py` | duplicate; legacy |
| GET | `/admin/audit/by-account/{account_id}` | `admin_audit.py` | duplicate; legacy |
| GET | `/admin/audit/by-severity` | `admin_audit.py` | duplicate; legacy |
| GET | `/admin/metrics` | `admin_metrics.py` | duplicate; legacy |

## Separate MT4 Bridge API

The bridge is a separate FastAPI application in `mt4_bridge/main.py`; these routes are not part of the 134-path main API snapshot.

| Method | Path | Consumer | Contract status |
|---|---|---|---|
| GET | `/health` | Local bridge monitoring | separate |
| GET, POST | `/account` | MT4 bridge client | separate |
| GET, POST | `/symbols` | MT4 bridge client | separate |
| GET, POST | `/rates` | MT4 bridge client | separate |
| GET, POST | `/ticks` | MT4 bridge client | separate |
| GET, POST | `/positions` | MT4 bridge client | separate |
| GET, POST | `/orders` | MT4 bridge client | separate |
| GET | `/api/health` | Bridge health monitor | separate |
| GET | `/api/health/summary` | Bridge health monitor | separate |
| GET | `/api/health/metrics` | Bridge health monitor | separate |

## Consumer and Contract Map

| Consumer | Current API paths | Contract owner today | Sprint 1 finding |
|---|---|---|---|
| Client dashboard | `/api/client/*`, `/api/licenses/*`, `/auth/*` | `client-api.ts`, `client-auth.ts`, page-local fetches | Client boundary exists but license and transport contracts are split |
| Current admin dashboard | `/api/admin/*`, `/auth/*` | `api.ts`, `auth.ts`, local license fetch | Current boundary is usable but read fan-out and duplicate wrappers remain |
| Legacy admin pages | `/admin/*`, some `/api/admin/*` | legacy aliases in `api.ts` | Static-token and JWT contracts coexist |
| Telegram bot | Services and selected license/account workflows | Telegram services and direct DB calls | Must not import HTTP routes; binding rules need one service later |
| Trading engine | Runtime, engine, risk, execution, events | Core engine contracts | API may observe/control through an explicit boundary only |
| MT4 bridge | Separate bridge routes | `mt4_bridge/main.py` | Read/write contract does not match all runtime expectations; no change in Sprint 1 |

## Known Contract Mismatches

These are documented findings only. Sprint 1 does not fix them.

- Legacy frontend account removal uses `DELETE /admin/accounts/{id}` while the legacy backend exposes `POST /admin/accounts/{id}/remove`.
- Frontend trading snapshot previously referenced `/api/admin/trading/trade/{id}/snapshot`; a backend compatibility alias now serves the same handler as `/api/admin/trade/{id}/snapshot`.
- Client license data is available through `/api/client/license` and `/api/licenses/my`; binding also exists under `/api/licenses/*`.
- Current and legacy admin license, user, account, health, and audit domains have overlapping names and different authorization/response conventions.
- Client trades and performance pages bypass existing typed wrappers and call generic client fetch directly.
- The MT4 runtime expects order-write paths that are not exposed by the current read-oriented bridge.

## Registry Rules

- This file is the baseline, not a permission or routing implementation.
- New endpoints must declare one domain owner, one authentication boundary, one consumer, and one response contract.
- Existing paths remain until consumer usage and replacement contract tests justify deprecation.
- No new feature is added to `/admin/*` legacy routes.
- A duplicate is not deleted merely because a newer path exists; compatibility usage must be measured first.
