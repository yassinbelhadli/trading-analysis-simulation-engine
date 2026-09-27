<#
dev_all.ps1 - local development launcher for the multi-portal project.

Starts the FastAPI backend and all four Next.js frontends as separate
detached processes on dedicated ports. Tracks the exact PIDs it spawns so
stopping only ever touches those processes.

USAGE:
  .\scripts\dev_all.ps1            start everything
  .\scripts\dev_all.ps1 -Status    show launcher-started processes
  .\scripts\dev_all.ps1 -Stop      stop only launcher-started processes

PORTS (match the defaults the apps already expect; no source was changed):
  API      8000
  Website  3010
  Client   3000
  Admin    3001
  Owner    3002
#>
[CmdletBinding()]
param(
    [switch]$Stop,
    [switch]$Status
)

$ErrorActionPreference = "Stop"

$Script:Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$PidFile = Join-Path $PSScriptRoot ".dev_all_pids.json"
$LogDir = Join-Path (Join-Path $Script:Root "logs") "dev_all"
$Python = Join-Path $Script:Root ".venv\Scripts\python.exe"

$Apps = @(
    @{ Name = "API";     Dir = "";                Kind = "api";  Port = 8000 },
    @{ Name = "Website"; Dir = "website";         Kind = "next"; Port = 3010 },
    @{ Name = "Client";  Dir = "client_dashboard"; Kind = "next"; Port = 3000 },
    @{ Name = "Admin";   Dir = "admin_dashboard"; Kind = "next"; Port = 3001 },
    @{ Name = "Owner";   Dir = "owner_portal";    Kind = "next"; Port = 3002 }
)

function Test-PortFree([int]$Port) {
    $listener = $null
    try {
        $listener = New-Object System.Net.Sockets.TcpListener(
            [System.Net.IPAddress]::Loopback, $Port)
        $listener.Start()
        return $true
    } catch {
        return $false
    } finally {
        if ($listener) { $listener.Stop() }
    }
}

function Get-PortOwner([int]$Port) {
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (-not $conn) { return @{ Pid = 0; Proc = "unknown" } }
    $proc = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
    return @{ Pid = $conn.OwningProcess; Proc = $proc.ProcessName }
}

function Assert-Preflight {
    $errors = @()
    if (-not (Test-Path (Join-Path $Script:Root "api\main.py"))) {
        $errors += "API source missing: api\main.py"
    }
    if (-not (Test-Path $Python)) {
        $errors += "venv python missing: .venv\Scripts\python.exe"
    } else {
        & $Python -c "import uvicorn" 2>$null | Out-Null
        if ($LASTEXITCODE -ne 0) { $errors += "uvicorn not installed in the venv" }
    }
    if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
        $errors += "node not found on PATH"
    }
    foreach ($app in $Apps) {
        if ($app.Kind -ne "next") { continue }
        $dir = Join-Path $Script:Root $app.Dir
        if (-not (Test-Path $dir)) { $errors += "Directory missing: $($app.Dir)" }
        if (-not (Test-Path (Join-Path $dir "package.json"))) {
            $errors += "package.json missing in $($app.Dir)"
        }
        if (-not (Test-Path (Join-Path $dir "node_modules\next\dist\bin\next"))) {
            $errors += "next is not installed in $($app.Dir) - run: npm install (in $($app.Dir))"
        }
    }
    if ($errors.Count -gt 0) {
        Write-Host "Preflight failed:" -ForegroundColor Red
        $errors | ForEach-Object { Write-Host ("  - " + $_) -ForegroundColor Red }
        return $false
    }
    return $true
}

function Assert-PortsFree {
    $busy = @()
    foreach ($app in $Apps) {
        if (-not (Test-PortFree $app.Port)) {
            $owner = Get-PortOwner $app.Port
            $busy += ("  {0,-8} port {1} is in use by PID {2} ({3})" -f $app.Name, $app.Port, $owner.Pid, $owner.Proc)
        }
    }
    if ($busy.Count -gt 0) {
        Write-Host "Port conflict - nothing was started:" -ForegroundColor Red
        $busy | ForEach-Object { Write-Host $_ -ForegroundColor Red }
        Write-Host "Free the port (or stop that process), then rerun. See docs/local_development.md." -ForegroundColor Red
        return $false
    }
    return $true
}

function Get-DescendantPids([int]$ParentId) {
    $result = New-Object System.Collections.Generic.List[int]
    $children = Get-CimInstance Win32_Process -Filter "ParentProcessId=$ParentId" -ErrorAction SilentlyContinue
    foreach ($c in $children) {
        $result.Add([int]$c.ProcessId)
        foreach ($sub in (Get-DescendantPids ([int]$c.ProcessId))) { $result.Add($sub) }
    }
    return $result
}

function Read-PidFile {
    if (-not (Test-Path $PidFile)) { return @() }
    $records = Get-Content -Path $PidFile -Raw | ConvertFrom-Json
    if ($records -isnot [array]) { $records = @($records) }
    return $records
}

function Write-Summary {
    Write-Host ""
    Write-Host "All applications started as separate processes." -ForegroundColor Green
    Write-Host ""
    foreach ($app in $Apps) {
        Write-Host ("  {0,-8} http://127.0.0.1:{1}" -f $app.Name, $app.Port)
    }
    Write-Host ""
    Write-Host "API Docs:"
    Write-Host "  http://127.0.0.1:8000/docs"
    Write-Host ""
    Write-Host ("Logs:      {0}" -f $LogDir)
    Write-Host "Stop:      .\scripts\dev_all.ps1 -Stop"
    Write-Host "Status:    .\scripts\dev_all.ps1 -Status"
}

function Set-LauncherEnv {
    param([string]$Key, [string]$Value)
    if (-not $script:LauncherEnvSnapshot.ContainsKey($Key)) {
        $script:LauncherEnvSnapshot[$Key] = [Environment]::GetEnvironmentVariable($Key, "Process")
    }
    [Environment]::SetEnvironmentVariable($Key, $Value, "Process")
}

function Restore-LauncherEnv {
    foreach ($Key in $script:LauncherEnvSnapshot.Keys) {
        [Environment]::SetEnvironmentVariable($Key, $script:LauncherEnvSnapshot[$Key], "Process")
    }
    $script:LauncherEnvSnapshot.Clear()
}

function Start-All {
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
    $script:LauncherEnvSnapshot = @{}
    $nodePath = (Get-Command node).Source
    $records = @()

    foreach ($app in $Apps) {
        if ($app.Kind -eq "api") {
            Set-LauncherEnv "PYTHONIOENCODING" "utf-8"
            $argList = "-m uvicorn api.main:app --host 127.0.0.1 --port $($app.Port)"
            $out = Join-Path $LogDir "api.out.log"
            $err = Join-Path $LogDir "api.err.log"
            $proc = Start-Process -FilePath $Python -ArgumentList $argList `
                -WorkingDirectory $Script:Root -RedirectStandardOutput $out `
                -RedirectStandardError $err -WindowStyle Hidden -PassThru
        } else {
            if (-not [Environment]::GetEnvironmentVariable("NEXT_PUBLIC_API_URL", "Process")) {
                Set-LauncherEnv "NEXT_PUBLIC_API_URL" "http://127.0.0.1:8000"
            }
            if ($app.Name -eq "Website") {
                if (-not [Environment]::GetEnvironmentVariable("NEXT_PUBLIC_CLIENT_PORTAL_URL", "Process")) {
                    Set-LauncherEnv "NEXT_PUBLIC_CLIENT_PORTAL_URL" "http://localhost:3000"
                }
                if (-not [Environment]::GetEnvironmentVariable("NEXT_PUBLIC_ADMIN_PORTAL_URL", "Process")) {
                    Set-LauncherEnv "NEXT_PUBLIC_ADMIN_PORTAL_URL" "http://localhost:3001"
                }
            }
            $dir = Join-Path $Script:Root $app.Dir
            $nextBin = Join-Path $dir "node_modules\next\dist\bin\next"
            $argList = ('"{0}" dev -p {1} -H 127.0.0.1' -f $nextBin, $app.Port)
            $out = Join-Path $LogDir ($app.Name.ToLower() + ".out.log")
            $err = Join-Path $LogDir ($app.Name.ToLower() + ".err.log")
            $proc = Start-Process -FilePath $nodePath -ArgumentList $argList `
                -WorkingDirectory $dir -RedirectStandardOutput $out `
                -RedirectStandardError $err -WindowStyle Hidden -PassThru
        }
        Restore-LauncherEnv
        $records += @{
            name    = $app.Name
            pid     = $proc.Id
            port    = $app.Port
            dir     = $app.Dir
            started = (Get-Date).ToUniversalTime().ToString("o")
        }
        Write-Host ("  started {0,-8} pid {1,-6} port {2}" -f $app.Name, $proc.Id, $app.Port) -ForegroundColor Green
        Start-Sleep -Milliseconds 400
    }

    $records | ConvertTo-Json | Set-Content -Path $PidFile -Encoding UTF8
    Write-Summary
}

function Stop-All {
    $records = Read-PidFile
    if ($records.Count -eq 0) {
        Write-Host "No launcher processes recorded. Nothing to stop." -ForegroundColor Yellow
        return
    }
    $stopped = @()
    foreach ($rec in $records) {
        $pidVal = [int]$rec.pid
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$pidVal" -ErrorAction SilentlyContinue
        if (-not $proc) {
            Write-Host ("  {0,-8} not running (pid {1})" -f $rec.name, $pidVal) -ForegroundColor Yellow
            continue
        }
        if ($proc.CommandLine -notmatch "next|uvicorn|api\.main") {
            Write-Host ("  {0,-8} pid {1} does not look like a launcher process - skipped" -f $rec.name, $pidVal) -ForegroundColor Yellow
            continue
        }
        $children = Get-DescendantPids $pidVal
        foreach ($child in ($children | Sort-Object -Descending)) {
            Stop-Process -Id $child -Force -ErrorAction SilentlyContinue
        }
        Stop-Process -Id $pidVal -Force -ErrorAction SilentlyContinue
        $stopped += $rec.name
        Write-Host ("  stopped {0,-8} pid {1}" -f $rec.name, $pidVal) -ForegroundColor Green
    }
    Remove-Item -Path $PidFile -Force -ErrorAction SilentlyContinue
    if ($stopped.Count -gt 0) {
        Write-Host "Launcher processes stopped." -ForegroundColor Green
    } else {
        Write-Host "Pid file cleaned; nothing was stopped." -ForegroundColor Yellow
    }
}

function Show-Status {
    $records = Read-PidFile
    if ($records.Count -eq 0) {
        Write-Host "No launcher processes recorded. Run .\scripts\dev_all.ps1 to start everything." -ForegroundColor Yellow
        return
    }
    Write-Host ""
    Write-Host ("  {0,-8} {1,-9} {2,-6} {3}" -f "Name", "Status", "Port", "URL")
    foreach ($rec in $records) {
        $proc = Get-Process -Id ([int]$rec.pid) -ErrorAction SilentlyContinue
        $status = if ($proc) { "running" } else { "STOPPED" }
        Write-Host ("  {0,-8} {1,-9} {2,-6} http://127.0.0.1:{3}" -f $rec.name, $status, $rec.port, $rec.port)
    }
    Write-Host ""
}

if ($Stop) { Stop-All; exit 0 }
if ($Status) { Show-Status; exit 0 }

Write-Host "ICT EA Pro - local development launcher" -ForegroundColor Cyan
Write-Host ("Root: {0}" -f $Script:Root)
Write-Host ""

if (-not (Assert-Preflight)) { exit 1 }
if (-not (Assert-PortsFree)) { exit 1 }
if (Test-Path $PidFile) {
    Write-Host "A previous launcher run is still recorded (pid file exists)." -ForegroundColor Yellow
    Write-Host "Run .\scripts\dev_all.ps1 -Status to inspect, or .\scripts\dev_all.ps1 -Stop to clean up first." -ForegroundColor Yellow
    exit 1
}

Start-All
