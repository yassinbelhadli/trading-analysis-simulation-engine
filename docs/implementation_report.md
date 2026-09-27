# ICT Funded EA Pro — Implementation & Audit Report

Date: 2026-08-14 · Scope: full-stack consistency, security, and UX audit (website, client/admin/owner portals, API, Telegram bot, EA distribution)

---

## 1. What was done

### 1.1 Security fixes (backend, server-side enforcement)
| Area | Change |
|---|---|
| `api/routes/admin/roles.py` | Role create/update only grants permissions the caller actually holds; non-owners cannot rename roles to built-in names; owner bypasses. |
| `api/routes/admin/users.py` | No API path to the `owner` role — even an existing owner cannot promote via API (provisioning is script-only, frozen OQ-1 contract). Last-owner demotion protected; non-owners cannot assign roles at/above their own level. |
| `api/main.py` | CORS `*` replaced with an explicit allowlist (localhost 3000–3002/3010 + `FRONTEND_URL`/`PORTAL_URLS` envs); `allow_credentials=False`. |
| `telegram_bot/handlers/callbacks/pause_resume.py` | All four handlers (pause/resume/start/restart) enforce account ownership — the bot can never control another client's account. |
| `api/routes/client/dashboard.py` | `POST /api/client/subscription/renew` no longer extends paid access for free while the current period is active (400 with a clear message). Renewal is accepted only after the period ends; paid renewals are handled by the billing team. |
| `api/routes/client/telegram.py` | Chat-ID trust removed. `/connect` now issues a single-use, 10-minute bind code stored hashed — a client-supplied `chat_id` can no longer claim/hijack another user's chat. |

### 1.2 Telegram — secure connect flow (one shared backend state)
- Dashboard `POST /client/telegram/connect` → issues 8-char bind code (unambiguous alphabet, hashed at rest, expires in 600 s).
- Bot `telegram_bot/commands/bind_cmd.py` → `/bind <CODE>` resolves the real Telegram user id and links it to the platform account that owns the code. Telegram ID is the stable identifier; username is display-only.
- `telegram_bot/app.py` registers `/bind` in the single shared `Application` factory.
- Client page (`client_dashboard/app/dashboard/telegram/page.tsx`) rebuilt: connect-code panel with copy, auto-poll until linked, disconnect (confirm dialog), test message, notification toggles + bot interface language saved via `PATCH /client/telegram/preferences`.
- `ToggleRow` extracted into the shared design system (`design-system/components/ui.tsx`) — no more duplicated component.

### 1.3 Website — claims now match capabilities
- `lib/urls.ts`: admin portal default corrected `:3000` → `:3001`.
- `app/pricing/page.tsx`: plans realigned to backend `api/services/plans_config.py` — Starter $29/mo, Professional $59/mo, Premium $99/mo, Enterprise $999 one-time (replaced fictional $97/$147/$197 + $497 lifetime). Comparison table now reflects actual feature flags (multi-account, analytics, API access, priority support).
- `app/faq/page.tsx` + `app/contact/page.tsx`: plan names and support claims aligned.
- Added `app/robots.ts`, `app/sitemap.ts`, `app/not-found.tsx`, `app/loading.tsx` (site URL via `NEXT_PUBLIC_SITE_URL`, localhost default).
- Legal pages dated 2026-08-13 — verified current, no change needed.

### 1.4 Admin / Owner portals — honest surfaces
- `admin_dashboard/app/dashboard/notifications/page.tsx`: replaced "Not available" placeholder with a real page (email + telegram channel status, recent deliveries, test broadcasts, permission-gated with `emails.send` / `telegram.send`).
- `admin_dashboard/app/dashboard/telegram/page.tsx`: real bot status page (bot username, linked users, delivery mode, test broadcast).
- `admin_dashboard/lib/api.ts`: added email/telegram status + test functions.
- `admin_dashboard/app/dashboard/ea-builds/page.tsx`: wording corrected (client distribution exists via `/api/client/ea`; admin publishing was the unimplemented gap — implemented 2026-08-15, see §5).
- `owner_portal/app/dashboard/system/integrations/page.tsx`: wording corrected (read-only registry exists; configuration endpoints do not).
- All other "Not available" placeholders verified against the real API contract and left as accurate (admin MT5 accounts, coupons; owner alerts, refunds, coupons, secrets).

### 1.5 EA distribution decision
- Client `/dashboard/downloads` **kept** — it is the only distribution surface for licensed clients (latest build, changelog, update check, download via `/api/client/ea`).
- The real gap was admin/owner **publishing** (upload/release) — documented on the admin page rather than faked; completed in the 2026-08-15 pass (§5).

### 1.6 N-icon removal
- `devIndicators: false` in all four `next.config.ts` files (dev-only; never present in production builds).

---

## 2. Verification

### 2.1 QA suites (live API, PostgreSQL)
| Suite | Result |
|---|---|
| `scripts/_qa_client_portal.py` | 53/53 |
| `scripts/_qa_admin_portal.py` | 92/92 |
| `scripts/_qa_owner_portal.py` | 110/110 |
| `scripts/_qa_notifications.py` | 49/49 |
| `scripts/_qa_client_sprint1.py` (frozen contract) | 54/54 |
| `scripts/_qa_auth_full.py` | 22/22 |
| `scripts/_qa_client_sprint2.py` (updated for secure bind flow) | 68/68 |
| `scripts/_qa_ea_builds.py` (new, EA publishing) | 46/46 |

Note: the owner suite originally dropped to 107/110 after the first RBAC edit (owner could promote via API, which cascaded into two more failures). Fixed by making owner provisioning script-only; suite restored to 110/110.

### 2.2 Production builds
| App | Result |
|---|---|
| client_dashboard | ✓ Compiled (14.3 s) |
| admin_dashboard | ✓ Compiled (incl. new `/dashboard/ea-builds` page) |
| owner_portal | ✓ Compiled (6.1 s) |
| website | ✓ Compiled (7.6 s) |

### 2.3 Route smoke test (40/40)
- Client surfaces 200: dashboard, telegram (status + connect), license, subscription, accounts, trades, performance, settings, EA.
- Admin/owner surfaces 200: overview, users, roles, permissions, licenses, subscriptions, payments, plans, clients, audit-logs, settings, promotions, news, tickets, trading, system-health, emails/telegram status, revenue analytics.
- Negative: client token → 403 on all admin surfaces; unauthenticated → 401.

### 2.4 Live behavioral checks
- `POST /client/telegram/connect` returns an 8-char code, 600 s expiry; a supplied `chat_id` is ignored (no binding).
- Renewal: active subscription → 400 "active until …"; after cancel → 200 with future `renew_date`.
- Client token on `/api/admin/emails/status` → 403 (RBAC enforced server-side).

---

## 3. Current state

- API running on `http://127.0.0.1:8000` (uvicorn from `.venv`, detached, pid-tracked in `scripts/.dev_all_pids.json`).
- The four Next.js dev servers are **down** (not restarted during recovery per instruction). Start everything with `scripts\dev_all.ps1` (client :3000, admin :3001, owner :3002, website :3010).
- Demo credentials (documented in `docs/human_validation_kit.md`): `demo.owner@ict-ea-demo.dev` / `demo.admin@ict-ea-demo.dev` / `demo.client@ict-ea-demo.dev` (2FA off, email verified).

## 4. Known remaining gaps (out of scope for this pass)
- `.ex5` artifact in `storage/ea/ict_ea_v1.2.0.ex5` is a 25-byte placeholder — the **real compiled build must be supplied by the owner** before clients receive a genuine binary. Publishing infra + QA use seeded test bytes only; nothing fake is presented as a real build.
- Notification **delivery pipeline** beyond preferences storage and channel status/test endpoints (Phase 6.0 skeleton).
- Owner portal billing: refunds/coupons not implemented (accurate placeholders).
- Email delivery not configured in this dev environment (`email_configured=false`; status surfaces this honestly).

---

## 5. EA Build Publishing (2026-08-15)

### 5.1 Backend — `api/routes/admin/ea_builds.py` (registered in `api/routes/admin/bundle.py`)
Two-phase release workflow so nothing looks published without a real artifact:

| Method / Path | Permission | Behavior |
|---|---|---|
| `GET /api/admin/ea-builds` | `ea.read` | List releases (same table + storage dir as the client download API — single source of truth). |
| `POST /api/admin/ea-builds` | `ea.publish` | Create release; version normalized (`vX.Y.Z` → `X.Y.Z`), 409 on duplicate, 400 on invalid format. |
| `POST /api/admin/ea-builds/{id}/upload` | `ea.publish` | Multipart upload; only `.ex4/.ex5`, size floor 1024 B, cap 50 MB; atomic tmp+replace; commit-rollback deletes the file on DB failure. |
| `POST /api/admin/ea-builds/{id}/set-latest` | `ea.publish` | Marks latest; enforces the single-latest invariant. |
| `PATCH /api/admin/ea-builds/{id}` | `ea.publish` | Release notes/changelog only; version immutable. |
| `DELETE /api/admin/ea-builds/{id}` | `ea.publish` | Row first, artifact best-effort (audit `file_removed`); re-delete 404. |

Audit events on every mutation: `ea_build.created / uploaded / set_latest / updated / deleted`.

### 5.2 Permissions — `security/access_control.py`
- Added `EA_READ = "ea.read"` and `EA_PUBLISH = "ea.publish"`; granted to `admin`; `owner` inherits via `*`. `client` / `support` hold neither → 403.
- `PermissionGuard` accepts `permission` (split on `.`) and passes `resource`/`action` to `checkPermission`.

### 5.3 Admin frontend
- `admin_dashboard/lib/api.ts`: `EABuildAdminItem` + list/create/update/set-latest/delete/upload (multipart without manual `Content-Type`).
- `admin_dashboard/app/dashboard/ea-builds/page.tsx`: real publishing UI — release table (latest badge, published status, release date), create/edit modal, upload/replace `.ex5`, set-latest, delete confirmation; gated by `ea.read` / `ea.publish` guards.

### 5.4 Behavior & tests
- Client round-trip verified from the same rows/files: `/api/client/ea` lists new versions, download returns the exact uploaded bytes, license rules preserved (no license → 403).
- `scripts/_qa_ea_builds.py` (46/46): auth guards, create/normalize/409/400s, upload validation (extension/size cap), disk round-trip, single-latest invariant, patch, delete + artifact removal, audit events.
- Live smoke (dev API on :8000): admin lists 3 demo builds; client → 403 on admin EA endpoints; client `/api/client/ea` shows latest 1.2.0 available. Dev DB roles re-seeded so the live admin role includes `ea.read`/`ea.publish` (idempotent `seed_roles_and_permissions`).
- Admin dashboard production build passes with the new page; API restarted to serve the new router (pid recorded in `scripts/.dev_all_pids.json`).
- QA-suite maintenance: `_qa_client_sprint2.py` updated from 54 → 68 checks to test the secure Telegram bind contract (code rotation, wrong-code rejection, bot-side `/bind` simulation via the real `bind_command` handler with stubbed update/context).
