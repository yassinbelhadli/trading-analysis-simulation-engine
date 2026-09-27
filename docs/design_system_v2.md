# Design System V2 — Cross-Portal Design Direction

## Status

- **Phase**: Planning / specification only. No application code, backend, API contract, database, auth, or Trading Engine changes are made by this document.
- **Approved direction**: Goblin green (primary accent) + blue (secondary tech/info accent) + black (main foundation). Premium, dark, powerful trading-fintech visual language. Explicitly **not** crypto-casino, **not** excessive neon, **not** generic SaaS.
- **Scope**: One shared design system across Website, Client Portal, Admin Portal, and Owner Portal — with deliberately non-identical layouts per portal purpose.
- **Supersedes**: `docs/website_design_system.md` for the cross-portal direction. The W1 token layer (`admin_dashboard/app/globals.css` + `ThemeProvider`) remains the implemented baseline until V2 is implemented in a future phase. W1 items still awaiting owner approval (logo asset, font licensing, final copy) remain open.
- **Evidence base**: `reviews/ui_ux_review/UI_UX_Review.md` + 60 screenshots in `reviews/ui_ux_review/{client,admin,owner,website}/` (structural DOM/CSS audit; the review model had no image input, so analysis is structural — screenshots are for human review).

---

## 1. Brand Direction (owner-approved)

| Dimension | Decision |
|---|---|
| Product name | ICT Funded EA Pro (short label: ICT EA Pro) |
| Positioning | Disciplined automation infrastructure for funded-account traders |
| Promise | Clarity, control, capital protection, operational visibility |
| Personality | Precise, calm, technical, confident, transparent |
| Primary accent | **Goblin green** — brand identity, primary actions, live/active states, key metrics |
| Secondary accent | **Blue** — tech/info accent, links, secondary actions, neutral info, "system" flavor |
| Foundation | **Black** — near-black dark surfaces; the base of every screen |
| Explicitly excluded | Crypto-casino aesthetics, excessive neon/glow, generic SaaS blue-gradients, random extra accents |
| Allowed | Neutrals (grays), semantic colors (success/warning/danger/info) kept **separate** from brand accents |
| Icon rule | Professional icon system replaces **all emoji** across every portal and the Website |

### 1.1 Usage rules

- Goblin green is the **brand color**: primary buttons, active nav states, key figures, brand moments. Used sparingly and consistently — never everywhere.
- Blue is the **tech/info color**: informational accents, links, secondary/supporting actions, "system" elements. Never competes with green for primary-action meaning.
- Black is the **foundation**: page background, sidebar/shell surfaces. Depth is built with near-black layers + borders, not with colorful panels.
- Semantic colors (success/warning/danger/info) mean only what they mean. They are **not** decoration.
- No other accents. If a new accent is proposed, it must be justified and owner-approved.

---

## 2. Color Tokens (proposed anchors — exact hex to be locked with owner during implementation)

> Token naming follows the future token layer; values below are working proposals anchored to the approved direction. Green/blue values were chosen to read premium and dark-friendly, not neon.

### 2.1 Black foundation (surfaces)

| Token | Value | Use |
|---|---|---|
| `surface/base` | `#0A0C10` | App/page background (black foundation) |
| `surface/raised` | `#11151C` | Cards, panels, sidebar |
| `surface/overlay` | `#161B24` | Modals, dropdowns, popovers |
| `surface/input` | `#0D1117` | Form fields |
| `surface/hover` | `#1A2029` | Hover row/button backgrounds |
| `border/default` | `#1E2530` | Standard borders |
| `border/strong` | `#2A3342` | Table dividers, focus rings base |

### 2.2 Goblin green (primary accent)

| Token | Value | Use |
|---|---|---|
| `brand/green-300` | `#6EE7A0` | Highlight text, charts on dark |
| `brand/green-400` | `#3DD68C` | Hover of primary, active metric |
| `brand/green-500` | `#12B76A` | Primary buttons, active nav, key values (base) |
| `brand/green-700` | `#0B8A50` | Pressed primary, deep accents |
| `brand/green-900` | `#065F46` | Large brand fills, banner/hero moments |
| `brand/green-tint` | `rgba(18,183,106,0.12)` | Selected rows, subtle active backgrounds |

### 2.3 Blue (secondary tech/info accent)

| Token | Value | Use |
|---|---|---|
| `brand/blue-300` | `#7DB4FF` | Info text on dark, chart series 2 |
| `brand/blue-400` | `#4C8DFF` | Hover of secondary accent |
| `brand/blue-500` | `#2F7BF6` | Links, info badges, secondary accents (base) |
| `brand/blue-700` | `#1E4FD8` | Deep info fills |
| `brand/blue-tint` | `rgba(47,123,246,0.12)` | Info backgrounds, selected system rows |

### 2.4 Neutral scale + text

| Token | Value | Use |
|---|---|---|
| `text/primary` | `#E6EAF0` | Primary text |
| `text/secondary` | `#9AA6B5` | Secondary text, labels |
| `text/muted` | `#5C6B7E` | Muted, placeholders, disabled |
| `text/inverse` | `#0A0C10` | Text on green/blue fills |
| `neutral/50…950` | gray ramp `#F4F6F8 → #0A0C10` | Backgrounds, hover, disabled fills |

### 2.5 Semantic (separate from brand)

| Token | Value | Use |
|---|---|---|
| `semantic/success` | `#16A34A` | Success badges, positive deltas |
| `semantic/warning` | `#F59E0B` | Warnings, pending states |
| `semantic/danger` | `#EF4444` | Errors, destructive actions, risk stops |
| `semantic/info` | `#2F7BF6` | Informational states |

---

## 3. Typography (proposal — license approval still pending)

| Role | Font | Notes |
|---|---|---|
| Display / headings / numerals | Space Grotesk | Technical, powerful character; fits trading-fintech |
| UI / body | Inter | Proven UI workhorse, tight on dark |
| Data / IDs / PIDs / hashes | JetBrains Mono | Engine status, account numbers, audit rows |

- Scale: 11 (micro/labels, uppercase optional), 12 (caption), 13 (base), 14 (body), 16 (subtitle), 18 (card title), 20 (section), 24 (page), 32 (hero). Tabular numerals for all numeric tables.
- Line height: 1.5 body, 1.2 headings. Letter-spacing: -0.01em on 20+.
- Owner-approved font licensing is a hard gate before implementation (same open item as W1).

---

## 4. Icon System

- **Replace every emoji** currently used across Client (30–38/page), Admin (53–54/page), Owner (23–24/page) and the Website.
- Single stroke-based open-source family (Lucide-class): stroke 1.5–1.75px, sizes 16 / 20 / 24.
- Semantics via icon + color, never emoji. Status dots: 8px circle, filled with the semantic color.
- Icons never carry meaning alone — always paired with text labels in nav and actions.
- No emoji anywhere in UI copy, empty states, or status badges.

---

## 5. Component Specs

### 5.1 Sidebar (all portals, different per portal)
- Surface `surface/raised`, 240px (collapsible to 64px, drawer < 1024px).
- Active item: `brand/green-tint` background + 3px `brand/green-500` left rail + green icon + `text/primary`.
- Sections grouped by portal IA (see §6). Section labels `text/muted` uppercase 11px.
- Footer zone reserved for context (role, version) — never raw PIDs or internal strings (§9 fixes).

### 5.2 Topbar
- **New component** (currently absent — `topbarH=0` in all portals). 56px, `surface/base` with bottom `border/default`.
- Left: page title + breadcrumb. Right: global search (where applicable), notifications bell with semantic-count dot, user menu (avatar initials, role, sign-out).
- Contextual actions (New promotion, Send broadcast, Engine controls) dock right when a page defines them.

### 5.3 Cards
- `surface/raised`, 1px `border/default`, 12px radius, 16px padding.
- Header row: title (18px) + optional action link. No emoji icons; icon chips use stroke icons on `surface/hover`.
- Stat cards: icon chip (green for primary metrics, blue for info, semantic for warnings), value 24px Space Grotesk, delta badge.

### 5.4 Tables
- Header: 11px uppercase `text/muted`; rows 56px, hover `surface/hover`; row dividers `border/default`.
- Numeric columns right-aligned with tabular numerals; status badges §5.9; empty rows §5.12.
- Pagination footer with page count; bulk actions bar appears on selection (sticky under topbar).

### 5.5 Buttons
- Primary: `brand/green-500`, text `#0A0C10` (inverse), hover `green-400`, pressed `green-700`, focus ring `border/strong` + 2px offset.
- Secondary: transparent, 1px `border/strong`, `text/primary`.
- Danger: `semantic/danger` outline (filled only inside destructive confirmations).
- Ghost: text-only; Icon buttons 32px with tooltips.
- All destructive or irreversible buttons **require a confirmation modal** (§5.8) and show a success/error toast.

### 5.6 Forms
- Inputs: `surface/input`, 1px `border/default`, 40px height, 13px; focus ring `brand/green-500` 2px.
- Validation: inline messages under fields, `semantic/danger` text; disabled = 40% opacity.
- Save bars: sticky footer with Cancel (ghost) / Save (primary); saving state disables both.

### 5.7 Modals
- `surface/overlay` panel, 1px `border/strong`, 16px radius, overlay `rgba(0,0,0,0.6)`.
- Titles 18px; body copy 14px; footer right-aligned actions.
- Destructive confirmations: danger-filled button, typed-confirmation (e.g. type user email) for irreversibles (delete user, emergency-stop, refund).
- Close via Esc, overlay click, and ✕ ghost button; focus trapped; returns focus on close.

### 5.8 Alerts / Toasts
- Toasts: top-right stack, 4–6s auto-dismiss, manual dismiss, semantic left rail (success/warning/danger/info).
- Inline banners for page-level states (e.g. "Engine paused — trades halted") with action button.
- Every mutation that succeeds or fails surfaces feedback; **no silent failures** (§10.4).

### 5.9 Status badges
- Pill: 11px, 20px height; colored tint bg + colored text (green/blue/amber/red/gray) per state map per portal (engine, subscription, license, account, trade, news, role).
- Live status ("RUNNING") uses green dot + label — never raw internals (§9).

### 5.10 Charts
- Dark-native: gridlines `border/default`, no chart-frame box, Space Grotesk numerals.
- Series: green (primary), blue (secondary), gray (comparison), semantic for thresholds.
- **Empty states for charts** (§5.12) — e.g. Revenue page currently renders 0 charts when no data; must render a styled "No data yet" chart placeholder instead of nothing.
- Tooltips: `surface/overlay` + `border/strong`, follow cursor.

### 5.11 Loading / Error states
- Loading: skeleton rows (gray shimmer, 60% opacity) — never blank flash; spinners only for full-screen transitions.
- Error: inline banner + retry button; user-facing copy only — **never expose internal errors** (project rule).

### 5.12 Empty states
- **Required everywhere** a list/chart can be empty: stroke icon in a 64px `surface/hover` circle, title (16px), 1-line explanation (13px `text/secondary`), primary action when meaningful.
- No data ≠ blank page. Audit: Admin accounts/coupons/performance, EA builds, notifications, Owner revenue currently render 0 cards — all must ship empty states.

### 5.13 Responsive
- Breakpoints: 1280 / 1024 / 768 / 640. Sidebar → drawer at < 1024 (already works at 682px, keep the pattern).
- Tables → card list at < 768 (headers as labels). Stats grid 4→2→1. No horizontal overflow at 1440 (verified) — preserve at all widths.
- Not mobile-first today; V2 keeps the desktop-first shell but guarantees no breakage (verified down to 682px).

### 5.14 Accessibility
- WCAG AA contrast on all text (semantic tints chosen to pass on black surfaces — verify at implementation).
- Keyboard: full focus path, visible focus rings, Esc/Enter in modals and dropdowns.
- Form errors linked via `aria-describedby`; icons `aria-hidden` with text labels; tables with proper scope/headers.

---

## 6. Portal Product Differentiation (Client vs Admin vs Owner vs Website)

One design system, four deliberately different products. Shared tokens and components; **different information architecture and density**.

### 6.1 Website — marketing / conversion
- Purpose: explain, build trust, convert. Editorial layout, generous whitespace, hero, feature sections, pricing, FAQ, docs, contact, legal.
- IA: Home, Features, Pricing, FAQ, Docs, Contact, Risk Disclosure, Legal.
- Known state (must be fixed in implementation phase): homepage is a W1 internal preview; **all 8 subpages 404**; footer links point to nonexistent `:3000/client/login` and `:3000/client/register` (real client routes are `/login`, `/register`). See `reviews/ui_ux_review/UI_UX_Review.md` and `docs/website_w1_report.md`.
- Tone: premium dark fintech, green primary CTA, blue secondary links; no fake performance claims, no casino imagery.

### 6.2 Client Portal — customer portal
- Purpose: the trader's daily cockpit — accounts, license, metrics, trades, settings, support.
- **Preserve and improve the patterns owners like**; keep it simple and customer-focused; green/blue/black applied; emoji → professional icons.
- Density: comfortable (56–72px rows, spacious cards). Language switcher prominent (AR/EN/FR/ES).
- IA: Dashboard, My Accounts (MT4/MT5), License, Performance/Reports, Billing & Subscription, Notifications, Telegram setup, Support/Tickets, Settings, Profile.
- Known placeholders to design for: Billing and Telegram currently "Coming soon" — replace with styled empty states + honest copy (§5.12).
- Defects to fix (from review): License card shows "1/3" vs MT5 Accounts "2/3" for the same data (same metric, different counts — must reconcile to one source); EA Downloads shows hardcoded v1.2.0 vs seeded `9.9.9-demo` (serve real data); greeting "Welcome, Demo 👋" (emoji → icon/plain).

### 6.3 Admin Portal — operations console
- Purpose: day-to-day operations — accounts, licenses, subscriptions, support, content, monitoring.
- **Not** "client with permissions": denser tables (44–48px rows), filter bars, bulk actions, operational workflows (approve, suspend, reissue, escalate, broadcast).
- IA: Overview, Accounts, Clients, Licenses, Subscriptions, Plans, Payments, Promotions, Coupons *(see matrix — contract gap)*, Trades, Support Tickets, News, EA Builds, Notifications, System Health, Audit.
- Density signals: compact stat strip, filterable multi-column tables, action menus, staff-task flows. Two-column layouts for workflows, not marketing cards.
- Defects to fix: sidebar footer shows raw `Engine RUNNING PID 4076` (→ status badge, no PID); Coupons page is a dead surface (see §8 row 8).

### 6.4 Owner Portal — control plane
- Purpose: business + platform control — financials, users/roles/permissions, system config, engine control, comms/news/alerts, integrations; future support/developer/finance roles.
- **Not** "admin with more permissions": owner surfaces are control actions + oversight, with confirmations and audit everywhere.
- IA: Dashboard (overview), Revenue, Billing (plans/subscriptions/payments), Promotions, Users & Roles, Permissions, Audit Logs, System (health/services/integrations), Engine Control, Settings, News & Broadcasts, Communications, Alerts *(future)*, Integrations *(future)*.
- Density: highest of the three portals; control-panel feel; every mutating control returns explicit success/failure + audit reference.

### 6.5 Explicit differentiation checklist

| Dimension | Website | Client | Admin | Owner |
|---|---|---|---|---|
| Job | Convert | Serve customer | Run operations | Control platform |
| Layout | Editorial | Comfortable app | Dense console | Dense control plane |
| Primary action | Sign up / purchase | Manage my stuff | Process ops task | Authorize platform change |
| Tables | None | Light | Full + filters + bulk | Full + deep filters |
| Confirmations | Light | Light | Medium | Heavy (typed for irreversible) |
| Audit visibility | None | Own activity | Per-entity | Global, filterable |
| Language | Multi | Multi (AR/EN/FR/ES) | Operator (EN) | Operator (EN) |

---

## 7. Owner Capability Matrix

### 7.1 Status definitions

| Status | Meaning | Owner UI rule |
|---|---|---|
| **A** | Endpoint frozen + working mutation (create/update/delete/control) | Build the real control |
| **B** | Endpoint exists but mutation incomplete/insufficient | Show read view only; document gap |
| **C** | Read-only (endpoint + data, no mutation) | Show data; no fake controls |
| **D** | Contract gap — backend capability missing | Do **not** invent API or dead buttons; document the exact gap + required future capability |
| **E** | Provider/integration dependency | Works only when external service configured; gate on config, label honestly |

> Rules: for C/D/E the frontend must **not** invent API, fake functionality, or add dead buttons. Every row below is grounded in the real contracts in `api/routes/admin/*` and `security/access_control.py` (verified this phase).

### 7.2 Matrix

| # | Owner capability (surface) | Backing endpoint | Permission | Mutation | Audit | Status |
|---|---|---|---|---|---|---|
| 1 | Platform overview KPIs (Dashboard) | `GET /api/admin/overview` | `admin.overview` | — read | — | **C** |
| 2 | Revenue analytics (Revenue) | `GET /api/admin/analytics/revenue` (`admin/billing.py:316`) | `billing.read` | — read | — | **C** |
| 3 | Plans view/edit + restore defaults (Billing → Plans) | `GET /api/admin/plans`; `PUT /api/admin/plans/{id}`; `POST /api/admin/plans/restore-defaults` | `subscriptions.read` / `subscriptions.update` | Full CRUD | `audit_id` | **A** |
| 4 | Subscriptions view/update/cancel (Billing → Subscriptions) | `GET /api/admin/subscriptions`; `PATCH /api/admin/subscriptions/{id}`; `POST /api/admin/subscriptions/{id}/cancel` | `subscriptions.read` / `.update` / `.cancel` | Full | `audit_id` | **A** |
| 5 | Payments ledger (Billing → Payments) | `GET /api/admin/payments` | `billing.read` | — read | — | **C** |
| 6 | Refunds (Billing → Refunds, proposed) | **none** — permission `billing.refund` exists (enum only) | `billing.refund` | — none | — | **D** — needs future `POST /api/admin/payments/{id}/refund` + refund service. Do not build UI now. |
| 7 | Promotions CRUD + toggle (Promotions) | `GET/POST/PUT/DELETE /api/admin/promotions`; `POST /api/admin/promotions/{id}/toggle` | `subscriptions.read` / `subscriptions.update` | Full | `audit_id` | **A** |
| 8 | Coupons (proposed Owner surface; Admin page already exists) | **none** — no coupon endpoint anywhere in `api/` (verified by grep) | — none | — none | — | **D** — contract gap. Admin "Coupons" page is currently a dead surface; document gap, ship neither Admin nor Owner coupons until a `coupons` module exists. |
| 9 | Users list/detail (Users) | `GET /api/admin/users`; `GET /api/admin/users/{id}` | `users.read` | — read | — | **C** |
| 10 | Create user (Users) | `POST /api/admin/users` | `users.create` | Full | `audit_id` | **A** |
| 11 | Update user (Users) | `PATCH /api/admin/users/{id}` | `users.update` | Full | `audit_id` | **A** |
| 12 | Suspend / activate / delete user (Users) | `POST /api/admin/users/{id}/suspend`; `POST /{id}/activate`; `DELETE /{id}` | `clients.suspend` / `clients.activate` / `users.delete` | Full | `audit_id` | **A** |
| 13 | Roles & permissions CRUD (Roles) | `GET /api/admin/roles`; `GET /api/admin/roles/{id}`; `POST/PATCH/DELETE /api/admin/roles/{id}`; `GET /api/admin/permissions` | `roles.read` / `.create` / `.update` / `.delete` | Full | `audit_id` | **A** |
| 14 | Assign roles to users (Roles) | `POST /api/admin/roles/assign` | `roles.assign` | Full (last-owner guard) | `audit_id` | **A** |
| 15 | Audit logs + summary (Audit Logs) | `GET /api/admin/audit-logs`; `GET /api/admin/audit-logs/summary` | `audit.read` | — read | — | **C** |
| 16 | System health (System → Health) | `GET /api/admin/system-health`; `/summary`; `/engines`; `/heartbeat`; `/report` | `system.health.read` | — read | — | **C** |
| 17 | Engine start/stop/restart (Engine) | `POST /api/admin/system-health/engine/{restart|stop|start}` | `engine.restart` / `engine.stop` / `engine.start` | Full | `audit_id` | **A** |
| 18 | Service restarts telegram/mt5/api (System → Services) | `POST /api/admin/system-health/{telegram|mt5|api}/restart` | `system.settings` | Partial — returns `supported: bool`; capability depends on deployment (process registry/service manager) | `audit_id` | **B** — keep read-only display until deployment support is confirmed for the target host |
| 19 | Engine status + logs (Engine) | `GET /api/admin/trading/engine`; `GET /api/admin/trading/engine/logs` | `engine.read` | — read | — | **C** |
| 20 | Trading control enable/disable (Engine) | `POST /api/admin/trading/control/enable`; `POST /.../disable` | `engine.start` / `engine.stop` | Full (MT5 accounts `engine_status`) | `audit_id` | **A** |
| 21 | Trading control pause/resume/close-all/close-symbol/emergency-stop (Engine) | `POST /api/admin/trading/control/{pause|resume|close-all|close-symbol|emergency-stop}` | `engine.control` | Full | `audit_id` | **A** |
| 22 | System settings (Settings) | `GET /api/admin/settings/schema`; `GET /api/admin/settings`; `PUT /api/admin/settings` | `system.settings` | Full (validated settings store) | `audit_id` | **A** |
| 23 | Secrets management (Settings → Secrets) | **none** — `system.secrets` permission exists in the enum but **zero routes wire it** (verified) | `system.secrets` | — none | — | **D** — explicitly **not** implemented in this phase. Requires a future approved security phase. Never expose decrypted secrets in any Owner UI; do not wire `system.secrets`. |
| 24 | News CRUD (News) | `GET/POST/PATCH/DELETE /api/admin/news` | `admin.overview` | Full | `audit_id` | **A** |
| 25 | News broadcast (News) | `POST /api/admin/news/{id}/broadcast` | `admin.overview` | Full | `audit_id` | **A** |
| 26 | Engine status banner (News) | `GET /api/admin/news/engine-status` | `admin.overview` | — read | — | **C** |
| 27 | Email status + test send (Communications) | `GET /api/admin/emails/status`; `POST /api/admin/emails/test` | `emails.read` / `emails.send` | Test-only send | `audit_id` | **A** (test) / **E** (production delivery requires real SMTP creds — never configured in dev) |
| 28 | Telegram status + test send (Communications) | `GET /api/admin/telegram/status`; `POST /api/admin/telegram/test` | `telegram.send` | Test-only send | `audit_id` | **A** (test) / **E** (production delivery requires real bot/provider; mock scan mode in dev) |
| 29 | Integrations registry (System → Integrations) | `GET /api/admin/system-health/integrations` | `system.health.read` | — read | — | **C** |
| 30 | Integration configuration (Integrations, proposed) | **none** | — none | — none | — | **D** — Phase 6.0 backend work (see `docs/phase6_platform_integrations.md`). Registry is read-only today. |
| 31 | Owner alerts management (Alerts, proposed) | **none** — notification preferences are client-scoped today; no owner alert-rule endpoint | — none | — none | — | **D** — needs future alert-rules module (rules, channels, escalation). |
| 32 | Future roles: support / developer / finance (Roles) | Role CRUD + assign (rows 13–14) can create and grant these roles today | `roles.*` | Full | `audit_id` | **A** — ready; role seeding + guardrails are a future phase |
| 33 | Trades oversight (Owner read view; Admin does ops) | `GET /api/admin/trading/*` (trades, engine, monitor, reports) | `trades.read` / `engine.read` / `trades.view` | — read | — | **C** (export: `trades.export` permission exists — confirm an export endpoint before exposing) |

### 7.3 Summary

- **A (build real controls):** plans, subscriptions, promotions, users, roles, engine control, system settings, news, test sends.
- **C (read-only):** overview, revenue, payments, audit, health, engine status/logs, integrations registry, trades oversight.
- **B (partial):** service restarts (deployment-dependent).
- **D (contract gaps — document, do not fake):** refunds, coupons, secrets, integration configuration, owner alerts.
- **E (provider dependencies):** production email/Telegram delivery.

---

## 8. Owner Security Rules (bind on the Owner Portal)

1. **Server-side enforcement always** — hiding a control in the UI is not authorization; every mutation is permission-checked and audit-logged server-side.
2. **Dangerous actions** (engine emergency-stop, close-all, delete user, cancel subscription, refund) require: correct permission + typed confirmation + audit log + clear success/error feedback + safe failure (no partial state).
3. **No decrypted secrets in the Owner UI** — never render secrets, tokens, or passwords; `system.secrets` is a documented gap (row 23), not a feature.
4. **Feedback contract** — every mutation returns visible success/failure; failures show user-safe copy; details go to server logs only.
5. **Audit everywhere** — every A-status mutation already returns `audit_id`; Owner UI must surface "Audited ✓" context on controls.

---

## 9. Carry-over Fixes from the UI/UX Review (implementation-phase tasks — NOT now)

| # | Issue (evidence) | Fix in V2 implementation |
|---|---|---|
| 1 | Owner Revenue leaks literal dev text `Contract: GET /api/admin/analytics/revenue` (`owner_portal/app/dashboard/revenue/page.tsx:42`) | Remove internal contract strings from UI; render data with real labels + empty states |
| 2 | Admin sidebar footer shows raw `Engine RUNNING PID 4076` | Status badge (green dot + "Engine running"), no PID |
| 3 | Client License "1/3" vs MT5 Accounts "2/3" for same metric | Single data source per metric |
| 4 | EA Downloads shows hardcoded `v1.2.0` vs seeded `9.9.9-demo` | Serve real build data |
| 5 | "Welcome, Demo 👋" | Professional greeting, no emoji |
| 6 | No logo anywhere (0 `<img>` per page audit) | Brand mark + logomark lockup (logo asset still owner-pending) |
| 7 | No topbar in any portal (`topbarH=0`) | Add topbar per §5.2 |
| 8 | Empty/thin pages render 0 cards | Empty states per §5.12 |
| 9 | Revenue page renders 0 charts without data | Chart empty states per §5.10 |
| 10 | Website: internal W1 preview + 8×404 subpages + dead footer links | Website rebuild phase (separate owner decision) |

Open questions that remain owner decisions (from the review report): icon family confirmation, topbar scope, empty-state copy tone, chart set priority, content cleanup scope, Website rebuild timing.

---

## 10. Out of Scope / Not Implemented Now

- No application code, backend, API contracts, database schema, auth, or Trading Engine changes.
- No Owner controls beyond what §7 marks **A**; C/D/E rows are documented, not built.
- No `system.secrets` wiring; no secrets in any UI.
- No Coupons, Refunds, Integration configuration, or Owner Alerts endpoints invented.
- Website rebuild and logo/font assets await owner decisions.
- Implementation of this design system is a **future phase** gated on owner sign-off of: palette anchors, fonts/licensing, logo, and icon family.

---

## References

- `reviews/ui_ux_review/UI_UX_Review.md` + 60 screenshots in `reviews/ui_ux_review/{client,admin,owner,website}/`
- `docs/website_design_system.md` (W1; superseded as cross-portal direction, still the implemented token layer)
- `docs/website_w1_report.md`, `docs/website_navigation.md` (Website current state + nav inventory)
- `docs/phase5_owner_portal_final.md`, `docs/phase4_admin_dashboard.md`, `docs/phase3_client_dashboard.md`
- `docs/phase6_platform_integrations.md` (integrations roadmap for matrix rows 29–30)
- `security/access_control.py` (Permission enum — source of all permission names in §7)
- `api/routes/admin/*.py` (endpoint inventory — verified this phase, incl. `admin/billing.py:316` for revenue)
