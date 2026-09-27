# UI/UX Review — Human Acceptance Phase

Date: 2026-08-13 · Stack running via `dev_all.ps1` · All pages captured at 1440x900 (2x scale), logged in with the demo accounts (owner/admin/client).

Screenshots: `reviews/ui_ux_review/{client,admin,owner,website}/` (60 PNGs total).

> Scope: Human Acceptance → UI/UX review only. No code was changed. Findings below are observations + questions, not a work plan.

---

## 0. Executive summary

- **Backend/auth/permissions: proven.** UI: functional end-to-end (all 3 portals + workflows work with the demo accounts).
- **The UI is "builders-grade", not "product-grade":** dark slate theme, `system-ui` font, emoji icons everywhere, no logo, no topbar, no visual hierarchy. Nothing looks broken — it looks generic.
- **Website (:3010) is a scaffold, not a SaaS site:** homepage is an internal design-system preview page, and **all 8 subpages are 404** (features, pricing, faq, docs, contact, terms, privacy, risk-disclosure). Login/Create-account links on it point to routes that 404.
- **Several pages are effectively empty** (admin: MT5 Accounts, Coupons, Notifications, EA Builds, Performance) and one leaks internal contract text to users (owner Revenue).

---

## 1. Global findings (all 3 portals)

| Aspect | Observed | Verdict |
|---|---|---|
| Theme | Dark only: body `#0F172A` (slate-900), sidebar `#1E293B` (slate-800), text `#F1F5F9` | Single generic dark theme; light mode is a toggle that exists but nothing distinct |
| Typography | `system-ui` stack, 16px base | No brand font, no type scale, no hierarchy beyond h1 |
| Branding | Text-only "ICT EA Pro" wordmark, **no logo, 0 images anywhere** | No identity |
| Icons | **Emojis used as icons**: client 30–38/page, admin 53–54/page, owner 23–24/page (📊📈🏆🏦🔑💳🧾🔔✈️👤⚙️🛡️🆘☀️🚪… also in buttons: "↻ Renew", "✕ Cancel") | The single biggest "generic" signal — emojis render differently per OS, look unprofessional in a trading product |
| Topbar | `topbarH=0` — **no header on any portal** | Only sidebar + content; no breadcrumbs, no global search, no top user menu |
| Sidebar | 256px (client) / 224px (admin, owner); grouped labels; 14/26/11 items | Grouping is reasonable; admin at 26 items needs hierarchy |
| Cards | Consistent rounded slate cards, but heights vary wildly (82px stats ↔ 280px charts) | No consistent grid rhythm |
| Tables | Dense, no visible pagination controls, no bulk actions | Function over polish |
| Charts | Client dashboard: 7 canvases (real). Admin/owner: **0 charts anywhere** (revenue/performance/usage = numbers only) | Trading product with no data visualization in back office |
| Responsive | 1440px: no horizontal overflow anywhere. 682px (panel): sidebar collapses to ☰ drawer, layouts stack | Works; not designed for mobile-first, but no breakage found |
| Empty states | Real empty pages show nothing or a bare heading (no icon/illustration/CTA) | See section 3 |

---

## 2. Client portal (:3000) — 14 pages — all workflows pass

Screenshots: `reviews/ui_ux_review/client/client-01..14.png`

**Good**
- Full journey works: Overview, Trading Activity, Performance, MT5 Accounts, EA Downloads, License, Subscription, Billing, Notifications, Telegram, Profile, Settings, Security (2FA + Active Sessions), Support, logout.
- Multilingual selector (EN/AR/FR/ES) present in Profile + Settings. ✓ (matches project rule)
- 2FA setup + session revoke exist under Security. ✓

**Weak / empty**
- **Billing (08)**: placeholder page — "Payment method management is part of a future phase", "Add payment method — Coming soon", invoice row renders an empty dash.
- **Telegram (10)**: "Send Test Notification — Coming soon" only action; connection status shows `Chat ID —` `Username —`.
- **Download EA (05)**: shows "Latest Version **v1.2.0** Released 01/08/2026" while the seeded EA build is **9.9.9-demo** — frontend hardcoded value vs backend data mismatch.

**Data/UX inconsistencies (demo seed vs UI)**
- Greeting: "Welcome, **Demo** 👋" (seeded first name "Demo" — looks like placeholder data).
- License page: "Used Accounts **1** / 3" · MT5 Accounts page: "**2** / 3 Accounts Used" — same data, two different counts.
- Dashboard: "Today's Profit +$0.00" next to "Total P&L +$2155.00" with no explanation (trades closed before today, but a client can't know that).
- Account cards: "Challenge" + "DemoProp Broker" labels with an "MT4" badge on a portal named "MT5 Accounts".
- No "Signals" section for clients (signals exist only in the admin portal).

**Look & feel**
- Dashboard = wall of stat cards + 2 chart cards + 2 tables; nothing draws the eye; no profit/loss color-coding beyond text (green/red).
- `#1F2937`-ish stat cards with no icon treatment, no sparkline.
- Sidebar bottom: "Light Mode" toggle + "Sign Out" with emoji buttons — feels like a utility app.

---

## 3. Admin portal (:3001) — 26 pages — workflows pass, but several pages are EMPTY

Screenshots: `reviews/ui_ux_review/admin/admin-01..26.png`

**Effectively empty pages (heading only, no content, no empty state)**
- `03-accounts` — MT5 Accounts: content area is blank after the heading.
- `08-coupons` — Coupons: blank.
- `14-performance` — Trading Performance: **0 cards, 0 content**.
- `17-ea-builds` — EA Builds: blank (1 card only).
- `20-notifications` — Notifications: blank (1 card only).

**Thin data**
- Payments: 1 row. Promotions: 1 row. Tickets: 2 rows. Plans: 2 subscriptions.
- Dashboard: 9 cards + a "Recent Audit Logs" table, no charts.

**Other**
- Sidebar has 26 items in 4 groups — no collapse/expand, no badges for pending items.
- Sidebar footer widget: "Engine RUNNING PID 4076 · 1 active · Demo admin" — raw PID shown to an admin UI (internal detail leaking to UI).
- Trade History / Audit Logs tables are long (30 rows) with no pagination control visible at capture time.

---

## 4. Owner portal (:3002) — 11 pages — workflows pass

Screenshots: `reviews/ui_ux_review/owner/owner-01..11.png`

**Leak of internal contract text (must fix)**
- Revenue page body literally shows: *"Revenue Owner only Canonical revenue surface (Owner Portal). Contract: GET /api/admin/analytics/revenue."* — a developer note rendered as user-facing content.

**Charts missing**
- Revenue: MRR $99.00 / ARR $1188.00 + "Usage", "Growth & Churn", "Plan Distribution" headings — but **0 charts/canvases**; numbers only.

**Other**
- Engine Control: "SYSTEM VERSION —" and "UPTIME —" render as empty dashes; PID 4076 shown raw.
- Promotions: 1 row. Billing Oversight: 4 cards, sparse.

---

## 5. Website (:3010) — NOT a real SaaS site yet

Screenshots: `reviews/ui_ux_review/website/web-01..09.png`

- Homepage is an **internal W1 design-system preview**, with literal text:
  - "This is an internal W1 preview for the Website design system. Final landing, pricing, and documentation content starts only after the foundation gate passes."
  - "No checkout, dashboard data, or private API calls are used by this preview."
  - "COMPONENT STATES / Email Form primitive" + a "Send preview" button.
- **All 8 subpages → 404**: /features, /pricing, /faq, /docs, /contact, /terms, /privacy, /risk-disclosure.
- **Broken login/register links**: footer "Log in"/"Create account" → `http://localhost:3000/client/login` and `http://localhost:3000/client/register`, **both 404** (real client routes are `/login` and `/register`).
- No real marketing copy, no pricing cards, no trading content. Answer to "واش Website كتشبه SaaS حقيقي؟": **no** — it's a scaffold.

---

## 6. Priority questions for the one-by-one walkthrough

1. **Brand direction**: dark-only vs light+dark, new color accent (current = plain slate/blue `#3B82F6`), logo, font pairing (e.g. Inter/Space Grotesk vs system-ui).
2. **Icon system**: replace emojis with a proper icon set (lucide/phosphor) — agree this is priority #1?
3. **Topbar**: add header (page title, breadcrumbs, search, user menu) on all portals?
4. **Empty pages**: admin 03/08/14/17/20 + client Billing — keep "Coming soon" pattern or design proper empty states with CTA?
5. **Charts**: which back-office pages need real charts (owner revenue, admin performance, client performance)?
6. **Content cleanup**: remove contract text (owner Revenue), fix v1.2.0 vs 9.9.9-demo, fix license "1/3 vs 2/3", decide greeting/name.
7. **Website**: rebuild as real marketing site (hero, features, pricing, faq, docs, contact, legal) — confirm this is the "Website redesign" phase scope.

Suggested walk order (one page at a time, per your preference): Client Dashboard → Client License/Subscription → Client Accounts → Client Trades → … then Admin dashboard → Owner dashboard → Website.
