# Product Readiness Audit — Human Validation Gap Analysis

**Date:** 2026-08-13
**Type:** READ-ONLY audit. No code, database, backend, DNS, deployment, or provider changes were made.
**Root:** `C:\Users\AGA GAMING\Desktop\test saas` (not a git repo — no git rollback available).

---

## 0. Scope and method

Everything below was verified by reading the actual source (routes, libs, guards,
backend services) and checking the local environment. No services were started or
stopped during this audit (all five ports — 8000/3000/3001/3002/3010 — are currently
free).

---

## 1. Website (`website/`)

### 1.1 Routes that actually exist

| Route | File | Type |
|---|---|---|
| `/` | `app/page.tsx` | Renders `FoundationPreview` — **internal design-system preview, not a product page** |

That is the **only** route. The page literally states: *"This is an internal W1
preview for the Website design system. Final landing, pricing, and documentation
content starts only after the foundation gate passes."*

### 1.2 Nav links → 404

`lib/navigation.ts` (header + footer) links to routes that **do not exist**:
`/features`, `/pricing`, `/faq`, `/docs`, `/contact`, `/terms`, `/privacy`,
`/risk-disclosure`. Every one renders a Next.js 404.

### 1.3 Portal URL bugs

`lib/urls.ts`:
- `adminPortal` default is `http://localhost:3000` — that is the **client** portal (admin is 3001).
- No owner portal URL, no pricing/checkout URLs.
- Login/register links point to `/client/login`, `/client/register` (the client portal
  routes are `/login`, `/register` — path mismatch, likely 404 inside the portal too).

### 1.4 Visual state

A genuinely good component foundation exists (`components/primitives/*`,
`content/*`, `layout/*`, design tokens in `globals.css`) — but the page shows
preview copy ("00 backend changes", "Form primitive preview", non-functional
"Send preview" button).

### 1.5 Required for a production-quality public website

1. Real landing/hero with product copy, imagery, branding.
2. `/features`, `/pricing`, `/faq`, `/docs`, `/contact` pages (+ legal: `/terms`,
   `/privacy`, `/risk-disclosure`).
3. Correct portal URLs (client 3000, admin 3001, owner 3002) + i18n-ready
   strings (project requires AR/EN/FR/ES support via translator pattern).
4. Pricing wired to real plans (backend `plans` already exists) or static until billing (6.3).

---

## 2. Client Dashboard (`client_dashboard/`)

### 2.1 Route inventory (all exist)

- Auth/public: `/login`, `/register`, `/forgot-password`, `/reset-password`,
  `/verify-email`, `/forbidden`, `/` (redirector).
- Dashboard (14): `/dashboard` (overview), `activity`, `performance`, `accounts`,
  `accounts/[accountId]`, `downloads`, `license`, `subscription`, `billing`,
  `notifications`, `telegram`, `profile`, `settings`, `security`, `support`.

### 2.2 Pages that call the backend (real, via `lib/api.ts` / `lib/auth.ts`)

Overview, activity/trades, performance, accounts (CRUD + reconnect/disconnect),
license, subscription (+cancel/renew), notifications (preferences), telegram
status (read-only), EA builds/downloads, profile, settings, security (2FA
setup/enable/disable, sessions, change password), auth (login/register/refresh/
logout/forgot/reset/me).

### 2.3 Pages that are placeholders / gated

- `billing`: "Add payment method — Coming soon" (dead button).
- `telegram`: "Send Test Notification — Coming soon".
- `downloads`: macOS build — "Coming soon" (Windows path is real).
- `support`: **static contact card only** — no ticket system client-side
  ("ticket system are part of a future phase"). No `/api/client/tickets` exists.
- `verify-email`: functional page, but **no code can reach a human** (see §5.3).

### 2.4 Authentication / 2FA / isolation flow

- JWT + refresh-token rotation, auto-refresh on 401 (`lib/auth.ts`).
- 2FA: full setup→enable→verify-on-login→disable flow.
- `ClientAuthGuard` (`components/ClientAuthGuard.tsx`): local route gate —
  role must be `client` (staff → `/forbidden`), `email_verified` must be true
  (else forced to `/verify-email`). Backend `require_permission` is authoritative.

### 2.5 Seeded data dependency

Overview/performance/activity/accounts render meaningful UI **only with real
data** (trades, accounts, license, subscription). QA scripts seed the **QA DB**
(`ict_funded_ea_qa`) at runtime; the **dev DB** (`ict_funded_ea`) has no demo
dataset and no persistent demo accounts.

### 2.6 Safe local test-account mechanism?

**No.** QA scripts create ephemeral users only inside `ict_funded_ea_qa`
(e.g. `portal-a@testmail.com` / `Passw0rd!123`). Nothing seeds the dev DB, and
nothing creates an email-verified client (see P0-2).

---

## 3. Admin Dashboard (`admin_dashboard/`)

### 3.1 Route inventory (all exist)

`/login`, `/forbidden`, `/dashboard`, and 30 dashboard pages: `users`, `roles`,
`clients`, `clients/[clientId]`, `audit`, `system`, `security`, `settings`,
`tickets`, `news`, `licenses`, `subscriptions`, `payments`, `revenue`,
`promotions`, `coupons`, `notifications`, `telegram`, `accounts`,
`accounts/[id]`, `ea-builds`, and trading: `trading`, `trades`, `signals`,
`history`, `risk`, `performance`, `engine`, `replay/[tradeId]`.

### 3.2 Real API integrations (`lib/api.ts` — all JWT)

Overview, users CRUD, roles/permissions, clients, audit-logs, system-health +
engine/telegram/mt5/api restart, trading overview/trades/history/signals/risk/
performance/engine/logs/control/close-symbol/snapshot, plans, subscriptions,
payments, revenue analytics, promotions, licenses, news + broadcast + engine
status, tickets (reply/escalate/ban), settings (schema + update).

### 3.3 Legacy / must-not-use calls

**No legacy non-JWT calls remain.** Instead, four pages are deliberate
**ContractGap placeholders** (`components/ContractGap.tsx`): `accounts`,
`accounts/[id]`, `ea-builds`, `notifications`, `telegram`. They render a 🚧
"Backend contract pending" card per the approved Phase 4 decision — no invented
endpoints, no fake data. `coupons` is "Coupon system coming soon." The audit
log UI uses `action` (there is no `event_type` query param — a QA fix already
landed for this).

### 3.4 Auth / 2FA / RBAC

Full JWT + 2FA flow (`lib/auth.ts`). `AuthGuard` checks authentication only;
`PermissionGuard` (`components/auth/permission_guard.tsx`) wraps every page
with `permission="<resource>.<action>"` (owner bypasses) and backend
`require_permission` 403s on bypass. Verified across all 30 pages.

### 3.5 Safe local admin account?

**No.** QA scripts create `qa_admin@test.local` / `AdminPass123!` and
`qa_owner_portal@test.local` / `PortalPassw0rd!456` **only in the QA DB at
runtime**. The dev DB only has the seeded owner admin
(`scripts/seed_auth.py` + `ADMIN_EMAIL`/`ADMIN_PASSWORD` env).

---

## 4. Owner Portal (`owner_portal/`)

### 4.1 Route inventory (all exist)

`/login`, `/forbidden`, `/dashboard` + 12 pages: `users`, `roles`, `audit`,
`system`, `settings`, `engine`, `billing`, `revenue`, `promotions`, `news`,
`dashboard` (overview).

### 4.2 Real API integrations (`lib/api.ts`)

Same JWT surface as admin for its scope (overview, users, roles, audit,
system-health, engine control, settings read + guarded update with secret
deny-list, plans/subscriptions/payments/revenue, promotions, news/broadcast).

### 4.3 Owner-only enforcement

- `OwnerAuthGuard` (`components/auth/owner_auth_guard.tsx`): enforces
  localStorage session **and** live `/auth/me` role claim — non-owner is
  cleared and sent to `/forbidden` (OQ-4 defense in depth).
- `permission_guard` + backend `require_permission` are authoritative.

### 4.4 2FA

Full flow (setup/enable/verify/disable) via `lib/auth.ts`.

### 4.5 Safe local owner account?

Same as admin: QA-only at runtime; dev DB relies on the seeded owner admin.

---

## 5. Backend / Auth

### 5.1 Seed mechanisms

- `scripts/seed_auth.py` — roles + permissions + default **owner** admin
  (`ADMIN_EMAIL` / `ADMIN_PASSWORD` env; safe to re-run, upserts).
- QA scripts (`_qa_*.py`) self-seed the QA DB with ephemeral fixtures at runtime.
- `scripts/seed_ftmo_account.py`, `reset_admin_pwd.py` — operational helpers.

### 5.2 Development / local accounts

Only the seeded owner admin in the dev DB. QA fixtures (dev-DB-absent):
`portal-a@testmail.com` / `Passw0rd!123`, `qa_admin@test.local` /
`AdminPass123!`, `qa_owner_portal@test.local` / `PortalPassw0rd!456`
(all test-only, `email_verified=True` in QA fixtures).

### 5.3 Email configuration — exact blocker

`config/.env` (names only, values not printed): `SMTP_HOST` **empty**,
`SMTP_PASS` **empty**; `SMTP_PORT`, `SMTP_USER`, `SMTP_FROM` set.

`api/services/email_service.py::send_email` returns `False` when
`smtp_host`/`smtp_user`/`smtp_pass` is missing → **every transactional email
fails**: registration verification codes, forgot-password, notifications.
Consequence: a client who registers is created with `email_verified=False` and
`ClientAuthGuard` forces them to `/verify-email`, where no code can be delivered
(register page even says "we could not send the verification email right now").
**This blocks the human client-role workflow completely.** `EMAIL_TEST_MODE=true`
mocks the send but does not surface the code to a human tester.

### 5.4 Databases

- Dev: `ict_funded_ea` (default in `database/db.py`).
- QA: `ict_funded_ea_qa` (scripts set `DATABASE_URL` explicitly).

---

## 6. Phase 6.0 — what was implemented and its impact on human testing

**Implemented (per `docs/phase6_platform_integrations.md` §14.1):**
- `api/services/notifications/` pipeline — preferences, rules, messages,
  templates, channels (telegram/email/audit), dispatcher; every provider is
  behind an interface with `TELEGRAM_TEST_MODE` / `EMAIL_TEST_MODE` so QA never
  touches real providers.
- Single Telegram entrypoint: `telegram_bot/app.py` `build_application()`;
  `bot.py` + `api_client.py` delegate.
- `admin_health_service.get_integrations()` + honest `restart_service()`;
  `/api/admin/system-health/integrations` + restart endpoints.
- Permission-gated `emails.*` / `telegram.*` admin endpoints
  (`api/routes/admin/notifications.py`, registered in `admin/bundle.py`).
- `config/settings.py`: `TELEGRAM_BOT_USERNAME` / `BOT_USERNAME`;
  client telegram status route.

**Impact on human testing:** neutral-to-positive. It adds the client Telegram
status page (works) and the admin "Notifications"/"Telegram" pages remain
ContractGap placeholders **by design** (no invented contracts). It does **not**
unblock email (§5.3) and does not change the Website.

---

## 7. Local development verification

- `scripts/dev_all.ps1` — verified: ports **API 8000 / Client 3000 / Admin 3001
  / Owner 3002 / Website 3010**; preflight (api source, venv uvicorn, node,
  next installs); port-conflict abort; PID file
  (`scripts/.dev_all_pids.json`); descendant-aware `-Stop`; `-Status`.
- `docs/local_development.md` exists and matches the launcher.
- Current state: **nothing running; all 5 ports free** (read-only `netstat`).

---

## 8. UX / visual review (based on actual implementation)

| Surface | Biggest visual/UX problems |
|---|---|
| **Website** | Not a product site at all — design-system preview; every header/footer link 404s; wrong admin portal URL default; no hero/copy/imagery/pricing. |
| **Client** | Functional but generic: emoji icon nav, plain tables, default CSS variables; "Coming soon" dead buttons (billing, telegram test, macOS download); support page is a static contact card; empty states dominate without seeded data. |
| **Admin** | Same generic styling; five 🚧 ContractGap placeholder pages; coupons "coming soon"; emoji icons; several `any`-typed API responses (trading section) keep tables rough. |
| **Owner** | Same visual system as admin (near-duplicate code); sparse pages; functional but not polished. |

Cross-cutting: the three portals share one functional-but-unrefined design
language (CSS variables, plain tables/cards); no shared design-token story with
the (good) website primitives; no empty-state guidance for humans; no demo
data, so first-run screens look broken.

---

## 9. Product Readiness Gap List

### P0 — blocking human validation

| # | Gap | Evidence |
|---|---|---|
| P0-1 | **No production website** — `/` is a foundation preview; all nav links 404; wrong portal URLs. | §1.1–1.3 |
| P0-2 | **No human-testable client account** — email verification is impossible (SMTP unset) and the guard hard-blocks unverified clients at `/verify-email`. | §2.4, §5.3 |
| P0-3 | **No persistent dev-db demo dataset / test accounts** for client, admin, owner (QA fixtures live only in `ict_funded_ea_qa` and vanish). | §2.6, §3.5, §4.5 |
| P0-4 | **Full login → dashboard → permissions → logout workflow cannot be completed** across the three roles today. | §2–4 combined |

### P1 — important

| # | Gap |
|---|---|
| P1-1 | Real email delivery blocked (SMTP credentials unavailable) — blocks register/verify, forgot-password, and all notification emails; need a documented local alternative (e.g. dev code echo / seeded verified accounts). |
| P1-2 | Website marketing pages (features/pricing/faq/docs/contact/legal) don't exist. |
| P1-3 | Client billing, client telegram "Send test", downloads-macOS are dead "Coming soon" controls — either wire or hide. |
| P1-4 | Client support has no ticket system (static contact only). |
| P1-5 | Admin ContractGap pages (accounts, EA builds, notifications, telegram) + coupons placeholder look unfinished in demos. |

### P2 — polish

| # | Gap |
|---|---|
| P2-1 | Portal design language (emoji icons, generic tables/cards) below the quality of the website primitives; no shared tokens. |
| P2-2 | `any`-typed trading API payloads in admin/owner libs; rough tables. |
| P2-3 | Empty states are plain text ("No signals yet") — no next-action guidance. |
| P2-4 | `lib/urls.ts` admin default wrong (3000 instead of 3001); missing owner/pricing URLs. |

---

## 10. Recommended next implementation step

**Do not start Phase 6.1–6.4.** Fix human validation first, in this order:

1. **Human Validation Kit (P0-2/P0-3/P0-4):** a `scripts/seed_demo.py` (dev DB,
   idempotent) that creates three fixed, documented accounts — owner, admin,
   client — all `email_verified=True`, 2FA off by default, plus a small demo
   dataset (license, subscription, MT5 accounts, trades, signals, audit rows).
   This unlocks the complete login → dashboard → permissions → logout
   workflow for a human with zero email dependency.
2. **Local email-verification escape hatch (P0-2):** with `EMAIL_TEST_MODE=true`,
   echo the verification code to the API logs / dev console so a freshly
   registered account can be verified without SMTP (documented in
   `docs/local_development.md`).
3. **Website first real page (P0-1):** replace the preview root with the actual
   landing page (real copy, correct portal URLs) and stub the 5 nav routes so
   no 404s — before or together with the Human Validation Kit.

Proposed acceptance: a human can, with the launcher, log in as owner, admin and
client, navigate every page, see realistic data, and confirm permission
isolation (client blocked from admin surfaces and vice versa) — all with no
SMTP, no Telegram, no billing.

---

*End of audit. No files other than this document were created or modified.*
