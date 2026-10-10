param(
  [string]$RepoRoot = "",
  [string]$OutRoot = "",
  [string]$PythonExe = $env:NULLCS_RELEASE_PYTHON,
  [switch]$SkipSidecarBuild
)

$ErrorActionPreference = "Stop"

if ($PythonExe -and -not $SkipSidecarBuild) {
  & $PythonExe (Join-Path $PSScriptRoot 'verify-release-runtime.py')
  if ($LASTEXITCODE -ne 0) { throw 'Selected release Python does not match the validated dependency lock.' }
}

if (-not $RepoRoot) {
  $RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\..\..")
}
if (-not $OutRoot) {
  $OutRoot = Join-Path $PSScriptRoot "..\src-tauri\resources\nullcs-backend"
}

$RepoRoot = (Resolve-Path $RepoRoot).Path
$OutRoot = [System.IO.Path]::GetFullPath($OutRoot)
$AllowedBase = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\src-tauri\resources"))
if (-not $OutRoot.StartsWith($AllowedBase.TrimEnd("\") + "\", [System.StringComparison]::OrdinalIgnoreCase)) {
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

function Remove-Packaging-Only-Files {
  param([string]$Root)
  $denyNames = @(
    "AGENTS.md",
    "CODEBASE_RECOVERY_CONTEXT.md",
    "TRAINING_PROVENANCE_REPORT.md",
    "TRAINING_REPORT.md",
    ".env",
    ".env.local",
    ".env.example"
  )
  Get-ChildItem -LiteralPath $Root -Recurse -Force -File |
    Where-Object {
      $_.Name -in $denyNames -or
      $_.Name -like ".env*" -or
      $_.Extension -in @(".pem", ".key", ".pfx", ".p12") -or
      $_.Name -like "*handoff*" -or
      $_.Name -like "*alpha_plan*" -or
      $_.Extension -eq ".pyc"
    } |
    Remove-Item -Force
}

Set-Content -LiteralPath (Join-Path $OutRoot ".nullcs-backend-root") -Value "NullCS packaged backend payload" -Encoding ASCII

Copy-Tree (Join-Path $RepoRoot "main\ui\api") (Join-Path $OutRoot "main\ui\api")
Copy-Tree (Join-Path $RepoRoot "main\src") (Join-Path $OutRoot "main\src")
# Release the verified canonical bundle only, not experimental model variants.
$modelFiles = @(
  "xgb_player_level_cs2cd.json", "xgb_player_level_cs2cd_features.txt",
  "xgb_player_level_cs2cd_training_manifest.json", "xgb_player_level_cs2cd_calibration.pkl",
  "encounter_nn_cs2cd.pt", "encounter_nn_cs2cd_features.json",
  "encounter_nn_cs2cd_preproc.pkl", "encounter_nn_cs2cd_training_manifest.json"
)
foreach ($name in $modelFiles) {
  Copy-One (Join-Path $RepoRoot "main\data\processed\models\$name") (Join-Path $OutRoot "main\data\processed\models\$name")
}
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
    --copy-metadata demoparser2 `
    --copy-metadata xgboost `
    --copy-metadata pandas `
    --collect-submodules sklearn `
    --collect-submodules scipy._external.array_api_compat `
    --collect-submodules torch `
    --collect-submodules uvicorn `
    --collect-submodules fastapi `
    --additional-hooks-dir (Join-Path $PSScriptRoot "pyinstaller-hooks") `
    --hidden-import uvicorn.protocols.http.h11_impl `
    --hidden-import uvicorn.lifespan.on `
    --hidden-import multipart `
    --hidden-import python_multipart `
    (Join-Path $RepoRoot "main\ui\api\desktop_sidecar.py")
  if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed to build nullcs-backend.exe"
  }
}

if (-not $SkipSidecarBuild) {
  & (Join-Path $OutRoot "nullcs-backend.exe") check-runtime
  if ($LASTEXITCODE -ne 0) { throw "Packaged inference dependencies failed their runtime check." }
  & $PythonExe (Join-Path $PSScriptRoot 'collect-release-notices.py')
  if ($LASTEXITCODE -ne 0) { throw 'Release license collection failed.' }
}

Remove-Packaging-Only-Files $OutRoot

# Authenticode must cover the executable that is actually launched, before hashing.
if ($env:NULLCS_WINDOWS_CERT_THUMBPRINT -and -not $SkipSidecarBuild) {
  $signTool = Get-Command signtool.exe -ErrorAction SilentlyContinue
  if (-not $signTool) { throw 'Put the Windows SDK signtool.exe on PATH before a signed release build.' }
  if (-not $env:NULLCS_WINDOWS_TIMESTAMP_URL) { throw 'A timestamp service is required for release signing.' }
  $sidecarPath = Join-Path $OutRoot 'nullcs-backend.exe'
  & $signTool.Source sign /sha1 $env:NULLCS_WINDOWS_CERT_THUMBPRINT /fd SHA256 /tr $env:NULLCS_WINDOWS_TIMESTAMP_URL /td SHA256 $sidecarPath
  if ($LASTEXITCODE -ne 0) { throw 'Sidecar signing failed.' }
  $signedSidecar = Get-AuthenticodeSignature -LiteralPath $sidecarPath
  if ($signedSidecar.Status -ne 'Valid' -or $signedSidecar.SignerCertificate.Thumbprint -ne $env:NULLCS_WINDOWS_CERT_THUMBPRINT -or -not $signedSidecar.TimeStamperCertificate) {
    throw 'Sidecar signature or timestamp verification failed.'
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
