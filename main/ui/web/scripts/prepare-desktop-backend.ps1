param(
  [string]$RepoRoot = "",
  [string]$OutRoot = "",
  [string]$PythonExe = "",
  [switch]$SkipSidecarBuild
)

$ErrorActionPreference = "Stop"

if (-not $RepoRoot) {
  $RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\..\..")
}
if (-not $OutRoot) {
  $OutRoot = Join-Path $PSScriptRoot "..\src-tauri\resources\nullcs-backend"
}

$RepoRoot = (Resolve-Path $RepoRoot).Path
$OutRoot = [System.IO.Path]::GetFullPath($OutRoot)
$AllowedBase = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\src-tauri\resources"))
if (-not $OutRoot.StartsWith($AllowedBase, [System.StringComparison]::OrdinalIgnoreCase)) {
  throw "Refusing to prepare backend outside src-tauri resources: $OutRoot"
}

if (Test-Path $OutRoot) {
  Remove-Item -LiteralPath $OutRoot -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $OutRoot | Out-Null

function Copy-Tree {
  param([string]$From, [string]$To)
  if (-not (Test-Path $From)) {
    throw "Required backend input missing: $From"
  }
  New-Item -ItemType Directory -Force -Path $To | Out-Null
  Get-ChildItem -LiteralPath $From -Force |
    Where-Object { $_.Name -notin @("__pycache__", "state") -and $_.Extension -ne ".pyc" } |
    ForEach-Object {
      Copy-Item -LiteralPath $_.FullName -Destination $To -Recurse -Force -Exclude "__pycache__", "state", "*.pyc"
    }
}

function Copy-One {
  param([string]$From, [string]$To)
  if (-not (Test-Path $From)) {
    throw "Required backend input missing: $From"
  }
  New-Item -ItemType Directory -Force -Path ([System.IO.Path]::GetDirectoryName($To)) | Out-Null
  Copy-Item -LiteralPath $From -Destination $To -Force
}

$agentsPath = Join-Path $RepoRoot "AGENTS.md"
if (Test-Path $agentsPath) {
  Copy-One $agentsPath (Join-Path $OutRoot "AGENTS.md")
}
Set-Content -LiteralPath (Join-Path $OutRoot ".nullcs-backend-root") -Value "NullCS packaged backend payload" -Encoding ASCII

Copy-Tree (Join-Path $RepoRoot "main\ui\api") (Join-Path $OutRoot "main\ui\api")
Copy-Tree (Join-Path $RepoRoot "main\src") (Join-Path $OutRoot "main\src")
Copy-Tree (Join-Path $RepoRoot "main\data\processed\models") (Join-Path $OutRoot "main\data\processed\models")
Copy-One (Join-Path $RepoRoot "main\scripts\run_infer_pipeline.py") (Join-Path $OutRoot "main\scripts\run_infer_pipeline.py")
Copy-One (Join-Path $RepoRoot "main\scripts\explain_demo.py") (Join-Path $OutRoot "main\scripts\explain_demo.py")

if (-not $SkipSidecarBuild) {
  if (-not $PythonExe) {
    $candidate = Join-Path $RepoRoot "NewAnubisTri\.venv\Scripts\python.exe"
    $PythonExe = if (Test-Path $candidate) { $candidate } else { "python" }
  }
  $probe = & $PythonExe -m PyInstaller --version 2>$null
  if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller is not installed for $PythonExe. Install it in the backend environment or run with -SkipSidecarBuild for source-resource packaging only."
  }
  $workPath = Join-Path $PSScriptRoot "..\src-tauri\target\pyinstaller-work"
  $specPath = Join-Path $PSScriptRoot "..\src-tauri\target\pyinstaller-spec"
  New-Item -ItemType Directory -Force -Path $workPath, $specPath | Out-Null
  & $PythonExe -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --name nullcs-backend `
    --distpath $OutRoot `
    --workpath $workPath `
    --specpath $specPath `
    --paths (Join-Path $RepoRoot "main") `
    --collect-submodules main `
    --collect-submodules src `
    --collect-submodules demoparser2 `
    --collect-submodules xgboost `
    --collect-submodules sklearn `
    --collect-submodules torch `
    --collect-submodules uvicorn `
    --collect-submodules fastapi `
    --hidden-import uvicorn.protocols.http.h11_impl `
    --hidden-import uvicorn.lifespan.on `
    --hidden-import multipart `
    --hidden-import python_multipart `
    (Join-Path $RepoRoot "main\ui\api\desktop_sidecar.py")
  if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed to build nullcs-backend.exe"
  }
}

$manifestFiles = Get-ChildItem -LiteralPath $OutRoot -Recurse -File |
  Where-Object { $_.Name -ne "backend_manifest.json" } |
  Sort-Object FullName |
  ForEach-Object {
    $relative = $_.FullName.Substring($OutRoot.Length).TrimStart("\") -replace "\\", "/"
    [ordered]@{
      path = $relative
      sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLowerInvariant()
      bytes = $_.Length
    }
  }

$manifest = [ordered]@{
  schema_version = "nullcs.desktop-backend.v1"
  generated_at_utc = [DateTime]::UtcNow.ToString("o")
  files = @($manifestFiles)
}

$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $OutRoot "backend_manifest.json") -Encoding UTF8
Write-Host "[OK] prepared desktop backend resources at $OutRoot"
