param(
    [string]$ProjectRoot = (Get-Location).Path
)

$LogDir     = Join-Path $ProjectRoot "logs"
$PidFile    = Join-Path $LogDir "background_runner.pid"
$Heartbeat  = Join-Path $LogDir "heartbeat.json"
$HealthRpt  = Join-Path $LogDir "health_report.json"
$EngineLog  = Join-Path $LogDir "engine.log"

Write-Host "=== Engine Health Check ==="
Write-Host ""

# --- 1. PID file + process alive ---
if (Test-Path $PidFile) {
    $enginePid = Get-Content $PidFile -Raw | ForEach-Object { $_.Trim() }
    $proc = Get-Process -Id $enginePid -ErrorAction SilentlyContinue
    if ($proc) {
        Write-Host ("[OK]  Process alive  PID=" + $enginePid + " RAM=" + [math]::Round($proc.WorkingSet64/1MB) + "MB")
    } else {
        Write-Host ("[FAIL] Process dead   PID=" + $enginePid + " (stale)")
        Write-Host "  -> Restart with: .\scripts\start_background.ps1"
    }
}
else {
    Write-Host "[WARN] No PID file at $PidFile"
    Write-Host "  -> Start with: .\scripts\start_background.ps1"
}

# --- 2. Heartbeat freshness + content ---
if (Test-Path $Heartbeat) {
    try {
        $hb = Get-Content $Heartbeat -Raw | ConvertFrom-Json
        $now = [DateTime]::UtcNow
        $hbTime = [DateTime]::Parse($hb.last_heartbeat_utc).ToUniversalTime()
        $age = ($now - $hbTime).TotalSeconds

        Write-Host ("[OK]  Heartbeat fresh  age=" + [math]::Round($age) + "s pid=" + $hb.pid + " status=" + $hb.status)
        Write-Host ("      Cycles: " + $hb.cycles + "  MT5: " + $hb.mt5_connected)

        if ($age -gt 120) {
            Write-Host "[WARN] Heartbeat stale  (>120s old) - engine may be hung"
        }
        if ($hb.status -ne "RUNNING") {
            Write-Host ("[FAIL] Status: " + $hb.status + " (expected RUNNING)")
        }
    }
    catch {
        $errMsg = $_.Exception.Message
        Write-Host ("[WARN] Heartbeat unreadable: " + $errMsg)
    }
}
else {
    Write-Host "[WARN] No heartbeat file at $Heartbeat"
}

# --- 3. Log file growing ---
if (Test-Path $EngineLog) {
    $logSize = (Get-Item $EngineLog).Length
    $logLines = (Get-Content $EngineLog).Count
    Write-Host ("[OK]  Engine log  size=" + [math]::Round($logSize/1KB) + "KB lines=" + $logLines)

    $last3 = Get-Content $EngineLog -Tail 3
    Write-Host "      Last lines:"
    $last3 | ForEach-Object { Write-Host ("        " + $_) }

    $matches = Select-String -Path $EngineLog -Pattern "ERROR|CRITICAL" -SimpleMatch
    if ($matches) {
        Write-Host ("[WARN] " + $matches.Count + " ERROR/CRITICAL lines found in log")
        $matches | Select-Object -First 3 | ForEach-Object {
            $line = $_.Line
            if ($line.Length -gt 120) { $line = $line.Substring(0, 120) }
            Write-Host ("       L" + $_.LineNumber + ": " + $line)
        }
    }
}
else {
    Write-Host "[WARN] No engine.log at $EngineLog"
}

# --- 4. Health report (if available) ---
if (Test-Path $HealthRpt) {
    try {
        $hr = Get-Content $HealthRpt -Raw | ConvertFrom-Json
        $hrTime = [DateTime]::Parse($hr.timestamp_utc).ToUniversalTime()
        $hrAge = ([DateTime]::UtcNow - $hrTime).TotalSeconds
        Write-Host ("[OK]  Health report  age=" + [math]::Round($hrAge) + "s cycles=" + $hr.cycles + " active=" + $hr.active_trades + " natural=" + $hr.natural_closed + " stalled=" + $hr.stale_cleanup)
        Write-Host ("      MT5=" + $hr.mt5_connected + " TG=" + $hr.telegram_connected + " mem=" + $hr.memory_mb + "MB cpu=" + $hr.cpu_percent + "% uptime=" + $hr.uptime_hours + "h")
    } catch {
        Write-Host "[WARN] Health report unreadable"
    }
}
else {
    Write-Host "[....] No health report yet (first after 5min, then hourly)"
}

Write-Host ""
Write-Host "=== Commands ==="
Write-Host "  Start: .\scripts\start_background.ps1"
Write-Host "  Stop:  .\scripts\stop_background.ps1"
Write-Host "  Check: .\scripts\check_engine.ps1"
Write-Host "  Tail:  Get-Content logs\engine.log -Tail 20 -Wait"
