param(
    [string]$ProjectRoot = (Get-Location).Path
)

$LogDir  = Join-Path $ProjectRoot "logs"
$VbsFile = Join-Path $ProjectRoot "scripts\launcher.vbs"
$PidFile = Join-Path $LogDir "background_runner.pid"

if (-not (Test-Path $VbsFile)) {
    Write-Host "ERROR: Launcher not found at $VbsFile"
    exit 1
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

# === Singleton guard: check if engine already running ===
if (Test-Path $PidFile) {
    $enginePid = Get-Content $PidFile -Raw | ForEach-Object { $_.Trim() }
    $proc = Get-Process -Id $enginePid -ErrorAction SilentlyContinue

    $hbFile = Join-Path $LogDir "heartbeat.json"
    $hbStale = $true
    if (Test-Path $hbFile) {
        try {
            $hb = Get-Content $hbFile -Raw | ConvertFrom-Json
            $hbTime = [DateTime]::Parse($hb.last_heartbeat_utc).ToUniversalTime()
            $hbAge = ([DateTime]::UtcNow - $hbTime).TotalSeconds
            if ($hbAge -le 120) { $hbStale = $false }
        } catch { }
    }

    if ($proc -and -not $hbStale) {
        Write-Host ("Engine already running (PID=" + $enginePid + ", heartbeat " + [math]::Round($hbAge) + "s ago)")
        Write-Host "Use .\scripts\stop_background.ps1 first if you want to restart."
        exit 0
    }

    if ($proc) {
        Write-Host ("Stale PID=" + $enginePid + " - heartbeat too old (" + [math]::Round($hbAge) + "s). Cleaning up...")
        Stop-Process -Id $enginePid -Force -ErrorAction SilentlyContinue
    } else {
        Write-Host ("Stale PID=" + $enginePid + " - process dead. Cleaning up...")
    }
}

# Clean stale state before launch
Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $LogDir "heartbeat.json") -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $LogDir "health_report.json") -Force -ErrorAction SilentlyContinue

# Launch via VBScript for true detach (survives shell exit)
cscript //nologo $VbsFile

Write-Host "Engine launched via VBScript."
Write-Host "Waiting for PID file..."
Start-Sleep -Seconds 8

if (Test-Path $PidFile) {
    $enginePid = Get-Content $PidFile -Raw | ForEach-Object { $_.Trim() }
    Write-Host ("Engine started. PID=" + $enginePid)
    Write-Host ("Log: " + $LogDir + "\engine.log")
    Write-Host ("Heartbeat: " + $LogDir + "\heartbeat.json")
} else {
    Write-Host "PID file not yet written."
    Write-Host "Run: .\scripts\check_engine.ps1"
}
