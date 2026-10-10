param(
  [Parameter(Mandatory = $true)]
  [string]$DemoPath,
  [string]$DemoId = ""
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $DemoPath)) {
  throw "Demo path not found: $DemoPath"
}

if (-not $DemoId) {
  # Must be an id the temporal (encounter-NN) loader resolves. A TEST_/BENCH_ id maps to
  # <upload root>/<demo_id>/<demo_id>.dem, which run_infer_pipeline.py writes itself, so the whole
  # pipeline completes. Any other prefix (the previous "SMOKE_<stamp>") needs
  # demos/<demo_id>/meta.json pointing at a real source_demo and is now rejected up front.
  $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
  $DemoId = "TEST_$stamp"
}

Write-Host "Running inference pipeline on demo:" $DemoPath
$ProcessedRoot = Join-Path $PSScriptRoot "..\data\processed"
$ProcessedRoot = [System.IO.Path]::GetFullPath($ProcessedRoot)
python main/scripts/run_infer_pipeline.py --dem_path "$DemoPath" --demo_id "$DemoId" --out_dir "$ProcessedRoot"
if ($LASTEXITCODE -ne 0) {
  exit $LASTEXITCODE
}

Write-Host ""
Write-Host "Pipeline complete for demo_id=$DemoId"
Write-Host ""
Write-Host "Start backend (terminal 1):"
Write-Host "  python -m uvicorn main.ui.api.main:app --host 127.0.0.1 --port 8000 --reload"
Write-Host ""
Write-Host "Start frontend (terminal 2):"
Write-Host "  cd main/ui/web"
Write-Host "  npm run dev -- --host 0.0.0.0 --port 5173"
Write-Host "  Open the Network URL printed by Vite."
Write-Host ""
Write-Host "Manual UI checks:"
Write-Host "  1) Upload demo works"
Write-Host "  2) Processing reaches done"
Write-Host "  3) Players list loads with Player, SteamID, Analyze"
Write-Host "  4) Analyze shows Reason Signals + severity chips (LOW/MEDIUM/HIGH/CONTEXT)"
Write-Host "  5) Severity Legend is visible on the right and not clipped"
Write-Host "  6) Evidence tabs and table render"
Write-Host "  7) Browser console has no errors"
