param(
    [switch]$StartTerminals
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendCmd = "python -m uvicorn main.ui.api.main:app --host 127.0.0.1 --port 8000 --reload"
$FrontendCmd = "npm run dev -- --host 0.0.0.0 --port 5173"

Write-Host "NullCS dev commands:"
Write-Host "  Backend : $BackendCmd"
Write-Host "  Frontend: $FrontendCmd"
Write-Host ""
Write-Host "Run from:"
Write-Host "  Backend : $RepoRoot"
Write-Host "  Frontend: $RepoRoot\main\ui\web"

if ($StartTerminals) {
    Start-Process powershell -ArgumentList @(
        "-NoExit",
        "-Command",
        "Set-Location '$RepoRoot'; $BackendCmd"
    )
    Start-Process powershell -ArgumentList @(
        "-NoExit",
        "-Command",
        "Set-Location '$RepoRoot\main\ui\web'; $FrontendCmd"
    )
    Write-Host ""
    Write-Host "Started backend and frontend terminals."
}
