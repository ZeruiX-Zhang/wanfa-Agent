$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$exitCode = 0

function Test-RequiredPath {
  param([Parameter(Mandatory = $true)][string]$Path)

  if (Test-Path -LiteralPath $Path) {
    Write-Host "[ok] $Path"
  }
  else {
    Write-Host "[missing] $Path"
    $script:exitCode = 1
  }
}

Write-Host "Reality OS Phase 3 doctor"
Write-Host "Root: $Root"

& (Join-Path $PSScriptRoot "check-phase2.ps1")
if ($LASTEXITCODE -ne 0) {
  $exitCode = 1
}

$required = @(
  "apps\web\package.json",
  "apps\web\app\layout.tsx",
  "apps\web\app\page.tsx",
  "apps\web\components\layout-shell.tsx",
  "apps\web\components\reality-workspace-page.tsx",
  "apps\web\lib\reality-workspaces.ts",
  "apps\web\app\dashboard\page.tsx",
  "apps\web\app\input\page.tsx",
  "apps\web\app\decision\[id]\page.tsx",
  "apps\web\app\knowledge\page.tsx",
  "apps\web\app\search\page.tsx",
  "apps\web\app\verification\[id]\page.tsx",
  "apps\web\app\workflow\page.tsx",
  "apps\web\app\supervisor\page.tsx",
  "apps\web\app\reflection\page.tsx",
  "apps\web\app\settings\page.tsx",
  "docs\PHASE_3_ACCEPTANCE_REPORT.md"
)

foreach ($relative in $required) {
  Test-RequiredPath (Join-Path $Root $relative)
}

$packageJson = Get-Content -Raw -LiteralPath (Join-Path $Root "package.json")
foreach ($scriptName in @("web:dev", "web:build", "web:lint", "doctor:phase3")) {
  if ($packageJson -match "`"$scriptName`"") {
    Write-Host "[ok] root script present: $scriptName"
  }
  else {
    Write-Host "[missing] root script: $scriptName"
    $exitCode = 1
  }
}

exit $exitCode
