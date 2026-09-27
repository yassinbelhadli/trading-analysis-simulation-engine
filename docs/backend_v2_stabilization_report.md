# Backend V2 Stabilization Report

## Status

- Sprint: Backend V2 Foundation, Sprint 4
- Status: Complete and verified
- Purpose: stabilization, contract verification, architecture verification, and freeze preparation
- No broad refactor was started

## Scope

Only technical debt documented in Sprints 1-3 was considered. The only runtime compatibility fix applied was the documented trading snapshot path alias:

- Existing: `GET /api/admin/trade/{trade_id}/snapshot`
- Added compatibility alias: `GET /api/admin/trading/trade/{trade_id}/snapshot`
- Both paths use the same handler, authorization, response, and database behavior.

No frontend change was required.

The architecture verifier was added at `scripts/check_backend_v2_stability.py`.

## Architecture Inventory

The inventory script reports:

| Item | Count | Definition |
|---|---:|---|
| Main API paths | 134 | OpenAPI paths, including the compatibility alias |
| Main API operations | 158 | HTTP operations in the main FastAPI app |
| API service modules | 14 | Python modules under `api/services`, excluding `__init__.py` |
| Repository modules | 7 | Python modules under `database/repositories`, excluding `__init__.py` |
| Pydantic DTO classes | 21 | `BaseModel` classes under `api/schemas` |
| V2 route adapters | 4 | License, client accounts, client dashboard, admin overview |
| Compatibility wrappers | 1 | `admin_overview_service.get_overview()` |

The complete route registry remains in [`api_docs.md`](api_docs.md).

## Contract Verification

Verified contracts:

- Client dashboard active, expired, suspended, and empty states
- Admin overview response and permission boundary
- License list/bind/unbind workflows
- Client account lifecycle
- Error status/details for invalid and unauthorized requests
- Database state before/after representative requests
- Audit deltas for mutating workflows
- DTO schemas on the migrated client/admin dashboard routes
- Snapshot compatibility alias

Golden Master results:

| Workflow | Result |
|---|---|
| License | PASS |
| Client account | PASS |
| Client dashboard | PASS |
| Admin overview | PASS |

## Architecture Verification

The verifier confirmed:

- migrated routes do not contain direct SQL or transaction calls;
- dashboard query services contain no SQL, writes, commits, or deletes;
- dashboard aggregators are session-free;
- migrated dashboard routes expose typed response schemas;
- compatibility paths exist;
- route count is frozen at 134 paths / 158 operations.

Routes and services outside the migrated scope were not silently changed. Their direct SQL and legacy boundaries remain documented in `docs/architecture.md` and the Sprint 1 registry.

## Regression Results

| Suite | Result |
|---|---|
| Architecture verifier | PASS |
| Sprint 1 QA | 54/54 PASS |
| Sprint 2 QA | 62/62 PASS |
| Auth QA | 22/22 PASS |
| Wizard QA | 13/13 PASS |
| TypeScript | PASS |
| Next build | PASS |

Existing non-blocking warnings remain: TestClient deprecation, missing QA `ADMIN_TOKEN`, SMTP-not-configured messages, and the QA performance inspection warning.

## Remaining Technical Debt

The following are intentionally not fixed in Sprint 4 because they require a new platform-phase decision or could change behavior:

- Billing service and payment-provider integration
- Telegram service convergence and verified chat linking
- Owner API, tenant visibility, and owner dashboard policy
- Cache and shared cross-process event transport
- SSE/WebSocket realtime delivery
- Website and public platform frontend
- Legacy `/admin/*` route retirement
- Remaining direct SQL in out-of-scope admin/client routes
- Response DTO coverage for non-migrated API domains
- Transaction/unit-of-work redesign
- Engine process ownership and process-local EventBus
- MT4 bridge write-contract gaps
- EA artifact validity and SMTP provisioning
- Existing license/account invariant divergence

## Known Risks

- Engine and API state can still diverge across processes.
- EventBus remains process-local, so no realtime guarantee exists.
- Admin trading metrics and client performance use different persisted fields and formulas.
- Health files can be stale while reporting a running state.
- Legacy admin auth and JWT admin auth remain separate.
- Some frontend legacy pages still call legacy paths/methods with incompatible auth.
- Owner visibility and tenant isolation are not yet defined.
- Database startup still relies on `create_all` in some paths rather than a single migration gate.

## Recommended Next Phase

After the freeze, the recommended platform order is:

1. Website: landing, pricing, documentation, and public auth entry points
2. Client Dashboard V2: UX redesign on the frozen client API
3. Admin Dashboard V2: UX redesign and page-level contract migration
4. Owner Dashboard: only after owner visibility and tenant policy are approved
5. Billing integration
6. Telegram convergence
7. VPS, domain, observability, and production rollout

## Exit Decision

Backend V2 Foundation is ready to freeze. No further architectural refactoring should begin until the next platform phase is explicitly approved.
