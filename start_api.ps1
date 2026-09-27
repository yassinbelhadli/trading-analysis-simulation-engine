# Start API with the correct Python (venv)
Write-Host "Killing old Python processes..." -ForegroundColor Yellow
taskkill /F /IM python.exe 2>$null
Start-Sleep -Seconds 2

Set-Location -LiteralPath "$PSScriptRoot"
Write-Host "Starting ICT EA Pro API from $PSScriptRoot ..." -ForegroundColor Green
& "$PSScriptRoot\.venv\Scripts\python.exe" -m api.main
