param(
    [string]$ProjectRoot = (Get-Location).Path
)

$LogDir  = Join-Path $ProjectRoot "logs"
$PidFile = Join-Path $LogDir "background_runner.pid"

if (Test-Path $PidFile) {
    $enginePid = Get-Content $PidFile -Raw | ForEach-Object { $_.Trim() }
    Stop-Process -Id $enginePid -Force -ErrorAction SilentlyContinue

    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    Remove-Item (Join-Path $LogDir "heartbeat.json") -Force -ErrorAction SilentlyContinue
    Remove-Item (Join-Path $LogDir "health_report.json") -Force -ErrorAction SilentlyContinue

    Write-Host ("Engine stopped. PID=" + $enginePid)
} else {
    Write-Host "No PID file found at $PidFile"
}
