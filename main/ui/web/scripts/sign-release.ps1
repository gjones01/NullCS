param(
  [string[]]$Paths,
  [string]$CertThumbprint = $env:NULLCS_SIGN_CERT_THUMBPRINT,
  [string]$CertPath = $env:NULLCS_SIGN_CERT_PATH,
  [string]$CertPassword = $env:NULLCS_SIGN_CERT_PASSWORD,
  [string]$TimestampUrl = $(if ($env:NULLCS_TIMESTAMP_URL) { $env:NULLCS_TIMESTAMP_URL } else { "http://timestamp.digicert.com" })
)

$ErrorActionPreference = "Stop"

if (-not $Paths -or $Paths.Count -eq 0) {
  throw "No paths supplied to sign."
}

$signtool = Get-Command signtool.exe -ErrorAction SilentlyContinue
if (-not $signtool) {
  $sdkTools = Get-ChildItem "C:\Program Files (x86)\Windows Kits\10\bin" -Recurse -Filter signtool.exe -ErrorAction SilentlyContinue |
    Sort-Object FullName -Descending |
    Select-Object -First 1
  if ($sdkTools) {
    $signtool = $sdkTools
  }
}
if (-not $signtool) {
  throw "signtool.exe was not found. Install the Windows SDK signing tools."
}

foreach ($path in $Paths) {
  if (-not (Test-Path $path)) {
    throw "Cannot sign missing file: $path"
  }
  $args = @("sign", "/fd", "SHA256", "/tr", $TimestampUrl, "/td", "SHA256")
  if ($CertThumbprint) {
    $args += @("/sha1", $CertThumbprint)
  } elseif ($CertPath) {
    $args += @("/f", $CertPath)
    if ($CertPassword) {
      $args += @("/p", $CertPassword)
    }
  } else {
    throw "Set NULLCS_SIGN_CERT_THUMBPRINT or NULLCS_SIGN_CERT_PATH before signing."
  }
  $args += $path
  & $signtool.Source @args
  if ($LASTEXITCODE -ne 0) {
    throw "Signing failed: $path"
  }
}
