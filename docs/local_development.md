# Local Development

Single launcher for the whole multi-portal project: the FastAPI backend plus
all four Next.js frontends, each running as its own detached process.

This is development tooling only. It does not modify any application source,
config, or database schema.

## Requirements

- Python venv at `.venv\` with `uvicorn` installed (`requirements.txt`).
- Node.js on `PATH` (the repo is developed on Node 24).
- Each frontend's dependencies installed:
  `npm install` inside `website/`, `client_dashboard/`, `admin_dashboard/`,
  and `owner_portal/`.
- The target ports must be free (the launcher checks and fails clearly).

## Start everything

```powershell
.\scripts\dev_all.ps1
```

The launcher:

1. Runs a preflight check (directories, venv Python, `uvicorn`, Node, `next`
   installed in each frontend).
2. Verifies all five ports are free.
3. Starts each application as a separate background process.
4. Prints the startup summary, e.g.:

```
  API      http://127.0.0.1:8000
  Website  http://127.0.0.1:3010
  Client   http://127.0.0.1:3000
  Admin    http://127.0.0.1:3001
  Owner    http://127.0.0.1:3002

API Docs:
  http://127.0.0.1:8000/docs
```

The launcher returns after starting; the processes keep running in the
background. Their output goes to log files (see Logs below).

## Ports and URLs

| App    | Port | URL                      |
| ------ | ---- | ------------------------ |
| API    | 8000 | http://127.0.0.1:8000    |
| Website| 3010 | http://127.0.0.1:3010    |
| Client | 3000 | http://127.0.0.1:3000    |
| Admin  | 3001 | http://127.0.0.1:3001    |
| Owner  | 3002 | http://127.0.0.1:3002    |

API interactive docs: http://127.0.0.1:8000/docs

These ports were chosen to match what the applications already expect:

- The API already serves on **8000** (`api/main.py` runs uvicorn on port
  8000), and every frontend already falls back to
  `http://127.0.0.1:8000` for `NEXT_PUBLIC_API_URL`.
- No frontend hardcodes a dev port; all use plain `next dev`, so 3000–3010
  are assigned freely. The website's portal links default to
  `localhost:3000` (Client) and are pointed at Admin `3001` by the launcher.

## Check status

```powershell
.\scripts\dev_all.ps1 -Status
```

Lists each launcher-started app with its PID, port, and running state.

## Stop everything

```powershell
.\scripts\dev_all.ps1 -Stop
```

Stops **only** the processes this launcher started (tracked by PID in
`scripts/.dev_all_pids.json`), including their child processes (Next dev
workers). It never kills unrelated Node/Python processes.

## Logs

Per-run output is written under `logs/dev_all/`:

- `api.out.log` / `api.err.log`
- `website.out.log`, `client.out.log`, `admin.out.log`, `owner.out.log`
  (and matching `.err.log` files)

## Environment variables

The launcher preserves your existing environment. It only sets values that are
not already defined (e.g. `NEXT_PUBLIC_API_URL` for the frontends,
`NEXT_PUBLIC_CLIENT_PORTAL_URL` / `NEXT_PUBLIC_ADMIN_PORTAL_URL` for the
website) and restores everything after each start.

## Troubleshooting

### Port already in use

The launcher fails before starting anything and reports which process owns the
port. To find it yourself:

```powershell
Get-NetTCPConnection -LocalPort 3001 -State Listen |
  Select-Object LocalPort, OwningProcess
Get-Process -Id <OwningProcess> | Select-Object ProcessName, Id
```

Free the port (close that app) or change the conflicting app's port, then
rerun the launcher. Ports never collide between launcher apps because each
gets its own port.

### "next is not installed in <dir>"

Run `npm install` inside that directory, then rerun.

### "uvicorn not installed in the venv"

Run `pip install -r requirements.txt` (or `pip install uvicorn`) inside the
venv, then rerun.

### A launcher-started app immediately exits

Check its `.err.log` under `logs/dev_all/`. Next.js apps are lazy — the first
page load compiles the app, so a slow first response is normal.

### A previous run is still recorded

If a start was interrupted, the pid file still exists and the launcher asks
you to clean up first:

```powershell
.\scripts\dev_all.ps1 -Stop
.\scripts\dev_all.ps1 -Status
```
