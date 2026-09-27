# Backend V2 Foundation Freeze

## Freeze Status

- Foundation: Backend V2
- Freeze point: after Sprint 4 stabilization
- Status: Frozen pending the next explicitly approved platform phase

## Freeze Rules

From this point forward:

- no new service/repository/DTO/aggregator architecture;
- no route renaming or broad route consolidation;
- no new owner, billing, cache, or realtime architecture;
- no database schema redesign;
- no Trading Engine or MT4/MT5 architecture changes;
- no frontend redesign as part of foundation maintenance;
- no cleanup-only refactor.

Only bug fixes are allowed without a new architecture approval.

## Bug Fix Definition

A change qualifies as a bug fix only when it:

- addresses a reproducible incorrect behavior or security issue;
- has a focused regression test;
- preserves the frozen route/DTO/service boundaries;
- does not introduce a new architectural layer;
- does not change an API contract without an approved compatibility adapter;
- passes the full regression suite.

## Frozen Contracts

- Main API registry: 134 paths / 158 operations
- Client dashboard response DTO and Golden Master
- Admin overview response DTO and Golden Master
- License and client-account service boundaries
- Existing repositories and transaction behavior
- Existing engine, runtime, risk, execution, Telegram, and frontend contracts
- Compatibility alias for the admin trading snapshot path

## Change Gate

Any proposed architectural change must include:

- the next platform phase it belongs to;
- affected consumers and contracts;
- migration and rollback plan;
- Golden Master or contract baseline;
- explicit approval before implementation.
