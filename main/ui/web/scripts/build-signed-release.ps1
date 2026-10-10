param([Parameter(Mandatory=$true)][string]$InstallerUrl)
$ErrorActionPreference = 'Stop'
# Signing secrets must be supplied by the operator, never stored in the repository.
foreach ($name in @('NULLCS_UPDATE_ENDPOINT','NULLCS_UPDATE_PUBLIC_KEY','TAURI_SIGNING_PRIVATE_KEY','NULLCS_WINDOWS_CERT_THUMBPRINT','NULLCS_WINDOWS_TIMESTAMP_URL','NULLCS_AUDIT_PYTHON','NULLCS_RELEASE_PYTHON')) {
  if (-not [Environment]::GetEnvironmentVariable($name)) { throw "Missing release setting: $name" }
}
$download = [Uri]$InstallerUrl
if ($download.Scheme -ne 'https' -or $download.Host -ne 'github.com' -or $download.Port -ne 443 -or $download.UserInfo -or $download.Query -or $download.Fragment -or $download.AbsolutePath -notmatch '^/gjones01/NullCS/releases/download/[^/]+/[^/]+\.exe$' -or [Uri]::UnescapeDataString($download.AbsolutePath) -match '[\x00-\x1f\x7f\\]') { throw 'Expected the final HTTPS GitHub release installer URL.' }
$endpoint = [Uri]$env:NULLCS_UPDATE_ENDPOINT
if ($endpoint.Scheme -ne 'https' -or $endpoint.UserInfo -or $endpoint.Query -or $endpoint.Fragment) { throw 'Updates require HTTPS without embedded credentials, queries or fragments.' }
if (-not (Get-Command signtool.exe -ErrorAction SilentlyContinue)) { throw 'Windows SDK signtool.exe must be on PATH to sign the backend.' }
$webRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$config = @{ plugins = @{ updater = @{ pubkey = $env:NULLCS_UPDATE_PUBLIC_KEY; endpoints = @($env:NULLCS_UPDATE_ENDPOINT); requireSignedVersion = $true } }; bundle = @{ createUpdaterArtifacts = $true; windows = @{ certificateThumbprint = $env:NULLCS_WINDOWS_CERT_THUMBPRINT; digestAlgorithm = 'sha256'; timestampUrl = $env:NULLCS_WINDOWS_TIMESTAMP_URL } } }
$configPath = Join-Path $webRoot 'src-tauri/target/release-signing-config.json'
New-Item -ItemType Directory -Force -Path (Split-Path $configPath) | Out-Null
[IO.File]::WriteAllText($configPath, ($config | ConvertTo-Json -Depth 6), [Text.UTF8Encoding]::new($false))
Push-Location $webRoot
try {
  $env:PATH = "$env:USERPROFILE\.cargo\bin;$env:PATH"
  # Fail closed: do not produce a publishable release with unresolved advisories.
  $repoRoot = [IO.Path]::GetFullPath((Join-Path $webRoot '../../..'))
  $pipelinePython = (Resolve-Path -LiteralPath $env:NULLCS_RELEASE_PYTHON).Path
  $env:NULLCS_RELEASE_PYTHON = $pipelinePython
  & $pipelinePython (Join-Path $PSScriptRoot 'verify-release-runtime.py')
  if ($LASTEXITCODE -ne 0) { throw 'Release runtime does not match the validated lock.' }
  & $pipelinePython -m pip check
  if ($LASTEXITCODE -ne 0) { throw 'Release dependency requirements are inconsistent.' }
  $releasePackages = & $pipelinePython -c 'import site; print(site.getsitepackages()[-1])'
  if ($LASTEXITCODE -ne 0) { throw 'Cannot locate release dependencies.' }
  & $env:NULLCS_AUDIT_PYTHON -m pip_audit --path $releasePackages --progress-spinner off
  if ($LASTEXITCODE -ne 0) { throw 'Python dependency audit failed. Resolve advisories in a separately validated release environment.' }
  & cargo audit --file src-tauri/Cargo.lock
  if ($LASTEXITCODE -ne 0) { throw 'Rust dependency audit failed.' }
  & npm.cmd audit --omit=dev
  if ($LASTEXITCODE -ne 0) { throw 'Desktop frontend dependency audit failed.' }
  & $pipelinePython -B -m pytest (Join-Path $repoRoot 'main/ui/api/tests') -q -p no:cacheprovider
  if ($LASTEXITCODE -ne 0) { throw 'Backend regression tests failed.' }
  & cargo test --manifest-path src-tauri/Cargo.toml --lib
  if ($LASTEXITCODE -ne 0) { throw 'Native integrity tests failed.' }
  $buildStarted = Get-Date
  & npx.cmd tauri build --config $configPath
  if ($LASTEXITCODE -ne 0) { throw 'Signed release build failed.' }
  $installer = Get-ChildItem -LiteralPath 'src-tauri/target/release/bundle/nsis' -Filter '*.exe' | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if (-not $installer) { throw 'Installer was not produced.' }
  if ($installer.LastWriteTime -lt $buildStarted) { throw 'Refusing to publish a stale installer.' }
  $signature = Get-AuthenticodeSignature -LiteralPath $installer.FullName
  if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Thumbprint -ne $env:NULLCS_WINDOWS_CERT_THUMBPRINT -or -not $signature.TimeStamperCertificate) { throw 'Installer Authenticode or timestamp verification failed.' }
  foreach ($executable in @('src-tauri/target/release/nullcs-desktop.exe', 'src-tauri/resources/nullcs-backend/nullcs-backend.exe')) {
    $signed = Get-AuthenticodeSignature -LiteralPath $executable
    if ($signed.Status -ne 'Valid' -or $signed.SignerCertificate.Thumbprint -ne $env:NULLCS_WINDOWS_CERT_THUMBPRINT -or -not $signed.TimeStamperCertificate) { throw "Executable signing verification failed: $executable" }
  }
  if ($download.Segments[-1] -ne [Uri]::EscapeDataString($installer.Name) -and [Uri]::UnescapeDataString($download.Segments[-1]) -ne $installer.Name) { throw 'Installer URL filename does not match the built installer.' }
  $updaterSignature = Get-Content -Raw -LiteralPath ($installer.FullName + '.sig')
  $version = (Get-Content -Raw 'src-tauri/tauri.conf.json' | ConvertFrom-Json).version
  $signatureText = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($updaterSignature.Trim()))
  $trustedLine = $signatureText -split "`n" | Where-Object { $_.StartsWith('trusted comment:') }
  $versionField = "version:$version"
  if (-not $trustedLine -or -not (($trustedLine.Trim() -split "`t") -contains $versionField)) {
    throw 'The update signature is not version-bound. Use a compatible Tauri CLI and re-sign; never disable signed-version verification.'
  }

  $manifest = @{version=$version; notes='NullCS desktop analysis update. See the release notes for parser and model compatibility.'; pub_date=[DateTime]::UtcNow.ToString('o'); platforms=@{'windows-x86_64'=@{signature=$updaterSignature.Trim(); url=$InstallerUrl}}}
  [IO.File]::WriteAllText((Join-Path $installer.DirectoryName 'latest.json'), ($manifest | ConvertTo-Json -Depth 5), [Text.UTF8Encoding]::new($false))
  Get-FileHash -LiteralPath $installer.FullName -Algorithm SHA256 | Format-List
  Write-Host 'Signed artifacts prepared. Test installation, analysis, and update from the prior release before publishing.'
} finally { Pop-Location }
