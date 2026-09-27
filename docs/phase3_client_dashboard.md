# Phase 3 — Client Dashboard V2 (Planning Specification)

## Document Status

- Status: **Planning only (amended)** — no code, no deployment, no DNS, no VPS purchase
- Amendment: Client 2FA must NOT be staff-only (see section 0.7)
- Target: `https://app.ictfundedeapro.com`
- Application boundary: a **separate Client Portal application**, not the Admin dashboard, not the Website (W1)
- Related documents: `docs/backend_v2_freeze.md` (frozen contracts), `docs/platform_architecture.md`, `docs/production_windows_vps_specification.md`, `docs/phase2_website.md`
- Read this document before writing any Client Portal code. Implementation requires explicit owner approval after this specification is accepted.

## Scope Guardrails

This phase builds only the **Client Portal frontend** against the **existing, frozen Backend V2 contracts**. It must NOT:

- Deploy, configure DNS, purchase a VPS, or touch production.
- Modify the Trading Engine, Telegram bot, Billing, or Backend V2 architecture.
- Create Owner functionality.
- Redesign the approved Website W1 foundation.
- Add speculative backend endpoints.
- Implement Telegram or Billing (integration boundaries only).

The **only** backend adjustment permitted in this phase is the permission-scope correction for client 2FA documented in section 0.7 (staff-only → self-scoped on three existing `/auth/2fa/*` endpoints). No other Backend V2 change is allowed.

---

## 0. Current-State Inspection (measured facts)

The existing client surface lives inside the `admin_dashboard/` Next.js app under `app/client/`. Key facts verified in the repository:

### 0.1 Frontend today

- Client routes live in `admin_dashboard/app/client/**` and are guarded by `components/auth/client_guard.tsx` (checks `localStorage` token presence, redirects to `/client/login`; public routes: login, register, forgot-password, reset-password, verify-email).
- Client session utilities in `lib/client-auth.ts`: localStorage keys `client_at`, `client_rt`, `client_user`; `login()`, `register()`, `refreshAccessToken()`, `logout()`, `authFetch()` (401 → refresh → retry).
- Client API client in `lib/client-api.ts`: typed fetchers for `/api/client/*` plus `/api/client/ea` downloads and `/api/client/accounts/*`.
- Existing client pages: dashboard home, accounts, telegram, subscription, license, download (EA), profile, settings, trades, performance.
- Navigation today: `ClientSidebar.tsx` (Overview, Accounts, Telegram, Download EA, Profile, Subscription, License, Settings, Trades, Performance) + mobile nav in `app/client/dashboard/layout.tsx`.
- All UI text is currently **English-only** (no i18n anywhere in the app).
- The admin surface uses the same Next.js app (`app/dashboard/**`, `app/login`, etc.) with an independent `lib/auth.ts` and admin sidebar. The two surfaces share the app but use different token keys and guards.
- `dashboard/` (Python) is a legacy helper package (chart/image capture, telegram sending) — not a frontend.

### 0.2 Backend contracts (frozen, to be reused as-is)

Auth (`/auth/*`):
- `POST /auth/login`, `POST /auth/register`, `POST /auth/refresh`, `POST /auth/logout`, `POST /auth/logout-all`, `GET /auth/me`, `POST /auth/change-password`
- `POST /auth/verify-email/send`, `POST /auth/verify-email/confirm`, `POST /auth/forgot-password`, `POST /auth/reset-password`
- `GET /auth/sessions`, `DELETE /auth/sessions/{session_id}`
- `POST /auth/2fa/setup`, `POST /auth/2fa/enable`, `POST /auth/2fa/disable`, `POST /auth/2fa/verify` (see section 0.7 for the staff-only gap), `POST /auth/check-permission`

Client (`/api/client/*`):
- `GET /api/client/dashboard` → `ClientDashboardResponse` DTO (frozen Golden Master)
- `GET/PATCH /api/client/profile`, `GET /api/client/overview`
- `GET /api/client/trades`, `GET /api/client/performance`
- `GET/PATCH /api/client/settings`
- `GET /api/client/license`
- `GET /api/client/subscription`, `POST /api/client/subscription/cancel`, `POST /api/client/subscription/renew`

Client accounts (`/api/client/accounts`):
- `GET ""` (list + limits), `POST ""` (add + verify via broker), `PATCH /{id}` (rename), `DELETE /{id}` (soft remove), `POST /{id}/disconnect`, `POST /{id}/reconnect`

Client EA (`/api/client/ea`):
- `GET ""` (latest + changelog), `POST /check-updates`, `GET /download/latest`, `GET /download/{build_id}` (license-gated file download)

Client Telegram (`/api/client/telegram`):
- `GET ""`, `POST /connect`, `POST /disconnect`, `PATCH /preferences`, `POST /test`

Licenses:
- `GET /licenses/my`, `POST /licenses/bind`, `POST /licenses/unbind`

### 0.3 Services (backend, to be reused)

- `ClientDashboardQueryService` — read-only orchestration (repositories only).
- `ClientDashboardAggregator` — pure calculations + DTO shaping (no DB).
- `ClientAccountService` — add/rename/remove/disconnect/reconnect; broker verification via `mt_connector`; engine lifecycle via `engine_manager`; credentials encrypted at rest.
- `LicenseService` — list, active-license resolution, account limits, bind/unbind.

### 0.4 DTOs

`api/schemas/client_dashboard.py`: `ClientDashboardResponse`, `DashboardLicenseDTO`, `DashboardSubscriptionDTO`, `TradingStatusDTO`, `DashboardSignalDTO`, `DashboardTradeDTO`, `EquityPointDTO`, `DashboardTodayDTO`, `DashboardTotalsDTO`.

### 0.5 Security model

- JWT bearer access (30 min) + rotating refresh, server-side `LoginSession` rows.
- Role-based login redirect: staff → `/dashboard`, client → `/client/dashboard`.
- `has_permission()` + `POST /auth/check-permission` for fine-grained checks.
- Roles: `owner`, `admin`, `support`, `analyst`, `risk_manager`, `billing`, `notification_mgr` (staff) and `client`.
- TOTP 2FA foundation is universal (SHA1, 6 digits, 30s, ±1 period skew). Login-time 2FA already works for any user: `POST /auth/login` returns `two_factor_required` when `two_factor_enabled`, and `POST /auth/2fa/verify` completes step 2 — **neither endpoint has a staff-only gate**.
- **Measured gap:** `POST /auth/2fa/setup|enable|disable` currently carry a staff-only guard (`_is_staff` check in `api/routes/auth_router.py`). This is the one contract gap to resolve for client 2FA (section 0.7).
- **Measured fact:** no backup/recovery-code system exists anywhere in the auth foundation. Account recovery is the email flow (`forgot-password` → `reset-password`, which revokes all sessions). 2FA-loss recovery is a manual support/admin action — no new recovery system is built in this phase.

### 0.6 QA / tests today

- `tests/e2e_test_runner.py` (engine + bot + signal monitoring).
- `tests/test_permissions.py`, `test_db_repositories.py`, MT5/execution/stress tests.
- **No client-portal e2e tests exist yet** — a QA plan is part of this phase.

### 0.7 Amendment — Client 2FA must NOT be staff-only (approved correction)

The Client Portal **must** support the security capabilities already present in the auth foundation, using the existing `/auth` contracts:

- Enable TOTP 2FA
- Disable TOTP 2FA
- 2FA verification during login (already universal)
- Recovery/security flow per the existing auth contract (email password reset; see note below)
- Active sessions
- Revoke session
- Change password
- Logout

Rules for this amendment:

- **Reuse** the existing frozen `/auth` endpoints — do NOT build a new 2FA system.
- **Do NOT create new auth endpoints** where existing contracts already support the requirement.
- **Do NOT change Backend V2 auth behavior** (TOTP verification logic, token flow, session rotation, refresh, email-verification all stay exactly as-is).
- **Single contract gap to resolve:** the staff-only guard on `POST /auth/2fa/setup`, `POST /auth/2fa/enable`, `POST /auth/2fa/disable` must be relaxed so any **authenticated user can manage their own account's 2FA** (self-scoped, matching the existing `change-password`/`sessions` pattern). This is a **permission-scope correction, not a new endpoint and not a change to the verification mechanism**. Per `docs/backend_v2_freeze.md` (Change Gate), it is recorded here and must be part of the explicit implementation approval; it does not widen access to any other account or to staff/admin surface.
- **Recovery:** with no backup-code system in the foundation, the supported recovery flow is the email password reset (`forgot-password`/`reset-password`, which revokes sessions). The spec does not invent a recovery-code system; loss of the authenticator device is a manual support/admin flow and is documented as out of scope.

**Verification requirements (must be proven before implementation approval):**

- Client security pages cannot access staff/admin functionality (no admin API calls, no staff routes rendered).
- Client can manage **only their own** sessions, passwords, and 2FA (server-scoped by `current_user.id`; the portal never sends a foreign id).
- Admin/Owner security remains separate and unchanged (staff surface untouched).
- Existing login behavior for users with 2FA enabled continues to work for clients (already universal).

---

## 1. Application Decision

**Build a separate Next.js application at `client_dashboard/`** (its own `package.json`, `next.config`, build output, deployment unit). Rationale:

- The target domain `app.ictfundedeapro.com` must serve only client content; it must not co-host admin routes.
- Freeze rules forbid redesigning admin; keeping them in one app creates accidental coupling (shared guards, shared nav, shared `lib/`).
- A separate app boundary lets the Client Portal evolve (Billing, Support, Notifications) without touching Admin.
- The Website W1 app remains untouched.

Consumed endpoints are the **frozen Backend V2 contracts** listed in section 0.2. No backend changes are authorized in this phase.

---

## 2. Page Map (16 required surfaces)

| # | Section | Source contract(s) | Primary state |
|---|---|---|---|
| 1 | Dashboard Overview | `GET /api/client/dashboard` | Rebuild as the portal home |
| 2 | MT5 Accounts | `GET /api/client/accounts` | Rebuild |
| 3 | Account Details | `GET /api/client/accounts` + `GET /api/client/performance` (per-account filter where supported) | **New page** (view-only detail + actions: rename/disconnect/reconnect/remove) |
| 4 | Trading Activity | `GET /api/client/trades` | Rebuild (open/closed/all) |
| 5 | Performance | `GET /api/client/performance` | Rebuild |
| 6 | License | `GET /api/client/license` + `/licenses/my`, `POST /licenses/bind`, `POST /licenses/unbind` | Rebuild |
| 7 | EA Downloads | `GET /api/client/ea` + download endpoints | Rebuild |
| 8 | Subscription | `GET /api/client/subscription` + cancel/renew | Rebuild |
| 9 | Telegram | `GET /api/client/telegram` + connect/disconnect/test | Rebuild (read-only boundary in this phase) |
| 10 | Notifications | `GET /api/client/settings` + `PATCH /api/client/settings` (`preferences.notifications`) | **New page** (preferences UI) |
| 11 | Settings | `GET/PATCH /api/client/settings` | Rebuild |
| 12 | Security | `GET /auth/me`, `POST /auth/change-password`, `GET /auth/sessions`, `DELETE /auth/sessions/{id}`, `POST /auth/2fa/setup\|enable\|disable` (self-scoped) | **New page** (full client 2FA + sessions) |
| 13 | Profile | `GET/PATCH /api/client/profile` | Rebuild |
| 14 | Support | No contract yet | **Placeholder page** (integration boundary) |
| 15 | Billing | No contract yet | **Placeholder page** (integration boundary) |
| 16 | Logout / Sessions | `POST /auth/logout`, `POST /auth/logout-all`, `GET /auth/sessions` | Rebuild + extend |

---

## 3. Navigation & Route Tree

```
app.ictfundedeapro.com
└── /login                       public
└── /register                    public
└── /forgot-password             public
└── /reset-password              public
└── /verify-email                public (verified → redirect /dashboard)
└── /dashboard                   protected  → Overview
│   ├── accounts                 → MT5 Accounts (list)
│   │   └── [accountId]          → Account Details (NEW)
│   ├── activity                 → Trading Activity
│   ├── performance              → Performance
│   ├── license                  → License
│   ├── downloads                → EA Downloads
│   ├── subscription             → Subscription
│   ├── telegram                 → Telegram (read-only status)
│   ├── notifications            → Notifications (NEW)
│   ├── settings                 → Settings
│   ├── security                 → Security (NEW)
│   ├── profile                  → Profile
│   ├── support                  → Support (placeholder)
│   └── billing                  → Billing (placeholder)
```

Sidebar groups (desktop) / bottom or hamburger nav (mobile):

- **Account**: Overview, Trading Activity, Performance
- **Trading**: MT5 Accounts, EA Downloads
- **Manage**: License, Subscription, Billing*, Notifications, Telegram
- **Account & Help**: Profile, Settings, Security, Support*

`*` Billing and Support render a clearly labelled placeholder card (see section 8).

Route ownership rules:

- Every protected route is wrapped by `ClientAuthGuard`.
- Redirects: not authenticated → `/login`; authenticated but email not verified → `/verify-email` (per login response behavior); role != `client` → dedicated `forbidden` page (no admin/owner content ever rendered in this app).

---

## 4. Permissions Model

Enforced in two layers (defense in depth):

1. **Backend (authoritative):** every client endpoint already scopes by `get_current_user` and repository filters on `user_id`. The portal adds nothing client-side that grants access.
2. **Frontend (UX only):** the portal never renders admin/owner routes, never calls admin endpoints, never writes global settings.

Hard rules (must be enforced in the portal):

- Client sees only their own rows: accounts, trades, licenses, subscriptions, sessions, profile.
- Client cannot access Admin data or Owner functionality (no admin API calls; no admin links; no owner URLs).
- Client cannot modify system-wide settings (`/admin/settings`, `site_settings`). The portal only uses `PATCH /api/client/settings`.
- Client cannot access other clients' accounts/trades/licenses/subscriptions (server enforces ownership; the UI never accepts a foreign id).
- Sensitive mutations (`remove`, `disconnect`, `reconnect`, `cancel subscription`, `logout-all`) require a **confirmation dialog** (and password re-entry where backend supports it).
- `POST /auth/check-permission` is available if a route needs a gate, but the portal should not require it for the frozen client surface.
- **2FA self-management:** `setup`/`enable`/`disable` are called with the client's own bearer token and act only on their own account (per section 0.7). Never render staff/admin security controls.

---

## 5. API Boundaries

- **Consume, don't duplicate:** the portal calls the frozen endpoints in section 0.2 exactly; no business logic is re-implemented in TypeScript (no re-computation of P&L, win rate, days-remaining, or limits client-side).
- **No direct database access** — everything goes through the API client layer.
- **No speculative endpoints:** if a view needs data the frozen contracts don't provide, the page shows the defined empty/partial state (section 6) and is flagged as a contract gap for a later approved phase — never a new backend endpoint in this phase.
- One typed API client module (`lib/api.ts`) mirroring `lib/client-api.ts`, with typed responses copied from the backend DTOs (single source of truth remains the backend; the TS types are a local mirror only).
- Token handling mirrors the existing `lib/client-auth.ts` pattern (localStorage, 401→refresh→retry) — this pattern is already proven in this codebase.

---

## 6. Loading / Error / Empty States

Global conventions (shared components):

- **Loading:** skeleton cards matching card layout; page never blocks on more than the one primary query; secondary sections lazy-load.
- **Error:** friendly message + "Try again" retry; distinct from auth-expiry (on 401 the client layer refreshes; on refresh failure → `/login`).
- **Empty:** per-section empty state with a clear next action (e.g., no accounts → "Connect your first MT5 account"; no license → "Activate your license"; no subscription → "View plans" placeholder → billing).
- **Contract gap:** if a frozen endpoint returns `null` for a section, render the empty state; never invent data.
- One "page-level error" boundary per route.

---

## 7. Responsive Requirements

- **Desktop (≥1024px):** persistent sidebar + topbar, multi-column stat/card grids (reuse current 12-col card patterns).
- **Tablet (768–1023px):** collapsible sidebar; cards stack to 2 columns; tables become scrollable (existing pattern).
- **Mobile (<768px):** hamburger/drawer nav (existing pattern); single-column stacks; tables switch to card/row layouts; touch targets ≥44px; sticky header.
- Numeric tables must be horizontally scrollable, never shrink to illegible.

---

## 8. Accessibility Requirements (WCAG 2.1 AA target)

- Semantic landmarks: `<header>`, `<nav>`, `<main>`, `<footer>` per layout.
- Keyboard navigable menus, dialogs, drawers (focus trap + focus restore).
- ARIA labels for icon-only controls (theme toggle, hamburger, close).
- Colour is never the only signal: status dots paired with text labels (existing pattern already does this — keep it).
- Contrast: use the existing CSS variable palette and verify against AA; maintain focus-visible styles.
- Form fields: labels, error messages linked via `aria-describedby`, validation messages readable by screen readers.
- Tables: `<th>` scoped, captions where useful.
- Motion: no required animations; reduced-motion respected.

---

## 9. Security Requirements

- Tokens in `localStorage` per the existing proven pattern; never in URL params.
- No credentials (broker password, current password, 2FA) ever written to logs, console, or URL; never persisted in the browser.
- Broker passwords sent only to `POST /api/client/accounts` and `POST /api/client/accounts/{id}/reconnect` in-memory; cleared from form state on submit.
- No secret is imported into the frontend bundle; frontend reads only public config (`NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_PORTAL_URL`).
- All requests go over HTTPS in production; `authFetch` retry-on-401 only, never blanket error swallowing.
- Session controls exposed (list active sessions, revoke a session, logout all) via the frozen `/auth/sessions` contracts.
- Confirm destructive actions; show clear feedback; never reveal backend stack traces (backend already fails closed — portal must surface only `detail` messages).
- The app must never render admin/owner links or data even if a token for a staff role is present — role gate at login redirect (staff → not authorized here).

---

## 10. Future Integration Boundaries (placeholders only — NOT implemented now)

| Future system | Boundary in this phase | Later contract expectation |
|---|---|---|
| **Telegram** | Render connection status + bot link from `GET /api/client/telegram` (read-only). Connect/disconnect/test endpoints exist but UI wiring is deferred to the Telegram phase; page shows status card + "coming soon" for actions. | `POST /connect`, `POST /test` wired to UI with chat verification flow. |
| **Billing** | `/billing` page renders a placeholder card (plans/actions disabled). No checkout, no payment data, no new endpoints. | A dedicated Billing phase adds checkout, invoices, payment methods, and cancel/renew wiring against approved Billing contracts. |
| **Support** | `/support` placeholder with the configured support email (`site_settings` `email.support_address`) as a mailto link only. | A dedicated Support phase (tickets) with its own contracts. |
| **MT5 accounts** | Full CRUD against existing `ClientAccountService` (add/rename/disconnect/reconnect/remove) — this is wired now since contracts exist. | Per-account detail enrichments only if new frozen contracts are approved. |
| **EA downloads** | Wire downloads via existing license-gated endpoints; check-updates call available. | Signed download URLs / version badge only if a future phase approves it. |

Integration rule: **every placeholder has a defined card, a clear "not available yet" message, and no fake data.**

---

## 11. Detailed Page Requirements (selected)

### 3. Account Details (`/dashboard/accounts/[accountId]`) — NEW
- Data: the matching account from `GET /api/client/accounts` (the portal filters client-side from the frozen list — no new endpoint).
- Shows: platform, server, login (masked suffix), broker, type, demo/real, balance, equity, currency, leverage, engine status, last sync, license binding.
- Actions (all existing contracts): rename, disconnect, reconnect (password field, in-memory only), remove (confirm dialog; warns engine will stop).
- Empty/not-found → friendly 404-style state with link back to Accounts.

### 12. Security — NEW (full client 2FA + session management)

- `GET /auth/me`: show email, email-verified status, 2FA state (`two_factor_enabled`, `two_factor_pending`).
- **Enable 2FA flow (reuses existing endpoints):**
  1. `POST /auth/2fa/setup` with current password → returns `secret` + `otpauth_uri`; render QR (from URI) + manual secret, show one-time only.
  2. User scans with authenticator and enters a code.
  3. `POST /auth/2fa/enable` with the code → `two_factor_enabled = true`.
- **Disable 2FA flow:** confirm dialog + current TOTP code → `POST /auth/2fa/disable`.
- **Login with 2FA (already universal):** `POST /auth/login` returns `two_factor_required` + `two_factor_token`; the portal shows the code step and calls `POST /auth/2fa/verify`. This is part of the auth flow, not a settings page.
- **Recovery:** supported path is the existing email flow (`forgot-password` → reset code → `reset-password`, revokes sessions). No backup codes are built in this phase (measured gap, section 0.7).
- **Change password:** `POST /auth/change-password` (current + new; notes that other sessions are revoked).
- **Active sessions:** `GET /auth/sessions`, revoke per session `DELETE /auth/sessions/{id}`, `POST /auth/logout-all` with confirm.
- All actions self-scoped to the authenticated client; no staff/admin controls rendered.

### 10. Notifications — NEW
- Data: `GET /api/client/settings` → `preferences.notifications` + toggles; save via `PATCH /api/client/settings`.
- Reads the same keys the Telegram page uses (`signals`, `filled`, `tp`, `sl`, `news`, `weekly_report`, `monthly_report`) and email/telegram on/off flags.
- Explicitly a preferences UI only; actual delivery belongs to the Telegram/notification phases.

### 14/15. Support & Billing — placeholders
- Support: support email `mailto` + opening-hours card; no ticket system.
- Billing: current plan summary from `GET /api/client/subscription` (read-only) + disabled "manage plans" card labelled as coming in the Billing phase.

---

## 12. State, Persistence & Data Flow

- **Server components** fetch where possible; interactive sections fetch client-side via the API client.
- One lightweight fetch layer (`lib/api.ts`) with typed methods per endpoint group (auth, client, accounts, ea, telegram, settings).
- Client-side state: React state/`useSWR`-style caching decision left to implementation, but **no global store** required for this scope; avoid over-engineering.
- No data is cached in the browser beyond React query caches; no sensitive data written to localStorage except tokens + minimal user meta (existing pattern).
- Language preference: `User.language` (EN/AR/FR/ES) is returned by `/auth/me` and `/api/client/settings`. **i18n is out of scope for this phase** but the UI must be structured so translation keys can be added later without a rewrite (single strings module, no hardcoded inline copy in new components beyond what exists today).

---

## 13. QA Plan (to run in the Full E2E QA phase)

- Unit: TS type-mirror tests against frozen DTO shapes; pure formatting helpers.
- Component: loading/error/empty states for each page.
- API contract tests: portal client hits frozen endpoints on a test database; assert no new endpoints called.
- E2E (portal): login → dashboard → connect account → view details → disconnect → remove → license → download → logout → session revoke. Use the existing `tests/e2e_test_runner.py` style with the backend running locally; add `tests/` portal smoke coverage.
- **2FA regression:** client enables 2FA (setup → verify code → enable), logs out, logs in through the 2FA step, disables 2FA; assert non-staff client is able to complete all four `/auth/2fa/*` steps and that no other user's 2FA is touched; assert `two_factor_enabled`/`two_factor_pending` reflect state.
- Permission regression: client token cannot reach any `/admin/*` or `/api/admin/*`; staff token redirected away from portal.
- a11y: keyboard + axe checks on the main flows.

---

## 14. Delivery Order (after approval)

0. **Prerequisite (approved backend permission-scope correction only):** relax the staff-only guard on `POST /auth/2fa/setup|enable|disable` to self-scoped (section 0.7). No endpoint, DTO, or verification-logic changes; regression tests for client 2FA added.
1. Scaffold `client_dashboard/` Next.js app (design tokens mirrored from the approved design system; **not** a W1 redesign).
2. Shared layout, guards, `lib/api.ts`, `lib/auth.ts` (ported pattern).
3. Auth flow pages (login/register/forgot/reset/verify + email-verified gate + 2FA login step).
4. Dashboard Overview rebuild.
5. Accounts list + Account Details (new).
6. Trading Activity + Performance rebuild.
7. License + EA Downloads rebuild.
8. Subscription + Settings + Notifications + Profile.
9. Security (full client 2FA + sessions) + Telegram read-only + Support/Billing placeholders.
10. Logout/session management + QA pass.

## 15. Non-Goals (explicitly excluded)

- No backend code changes (freeze rules apply) **except** the recorded permission-scope correction in section 0.7 (staff-only → self-scoped for `/auth/2fa/setup|enable|disable`), which requires explicit approval.
- No new 2FA system, no backup/recovery-code system.
- No Telegram or Billing implementation.
- No Owner functionality.
- No i18n implementation (structured for it only).
- No redesign of Website W1.
- No deployment, DNS, or VPS work.

---

## 16. Stop Condition

Specification complete. **STOP** — implementation begins only after explicit owner approval of this document.
