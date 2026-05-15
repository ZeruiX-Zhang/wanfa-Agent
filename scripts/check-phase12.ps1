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

Write-Host "Reality OS Phase 12 doctor"
Write-Host "Root: $Root"

& (Join-Path $PSScriptRoot "check-phase3.ps1")
if ($LASTEXITCODE -ne 0) {
  $exitCode = 1
}

$required = @(
  "apps\api\main.py",
  "apps\api\schemas.py",
  "apps\extension\manifest.json",
  "apps\web\components\pending-knowledge-panel.tsx",
  "apps\web\components\reality-adapter-ui.tsx",
  "apps\web\lib\reality-adapter-data.ts",
  "apps\web\playwright.config.ts",
  "apps\web\tests\e2e\reality-flow.spec.ts",
  "apps\web\tests\e2e\pages\reality-os-page.ts",
  "services\knowledge\adapter.py",
  "services\retrieval\adapter.py",
  "services\prompt-orchestrator\prompt_orchestrator\adapter.py",
  "services\verification\adapter.py",
  "services\evals\smoke.py",
  "services\workflow\schemas.py",
  "services\supervisor\shell.py",
  "services\tool-gateway\tool_gateway\gateway.py",
  "docs\PHASE_4_ACCEPTANCE_REPORT.md",
  "docs\PHASE_5_ACCEPTANCE_REPORT.md",
  "docs\PHASE_6_ACCEPTANCE_REPORT.md",
  "docs\PHASE_7_ACCEPTANCE_REPORT.md",
  "docs\PHASE_8_ACCEPTANCE_REPORT.md",
  "docs\PHASE_9_ACCEPTANCE_REPORT.md",
  "docs\PHASE_10_ACCEPTANCE_REPORT.md",
  "docs\PHASE_11_ACCEPTANCE_REPORT.md",
  "docs\PHASE_12_ACCEPTANCE_REPORT.md",
  "docs\PHASE_13_HARDENING_REPORT.md",
  "docs\PRODUCTION_READINESS.md",
  "docs\DEPRECATED_ENTRYPOINTS.md"
)

foreach ($relative in $required) {
  Test-RequiredPath (Join-Path $Root $relative)
}

$packageJson = Get-Content -Raw -LiteralPath (Join-Path $Root "package.json")
foreach ($scriptName in @("api:smoke", "smoke:phase10", "web:e2e", "web:build:strict", "doctor:phase12")) {
  if ($packageJson -match "`"$scriptName`"") {
    Write-Host "[ok] root script present: $scriptName"
  }
  else {
    Write-Host "[missing] root script: $scriptName"
    $exitCode = 1
  }
}

exit $exitCode
