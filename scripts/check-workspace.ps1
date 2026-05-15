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

Write-Host "Reality OS workspace doctor"
Write-Host "Root: $Root"

$required = @(
  "README.md",
  ".env.example",
  ".gitignore",
  "package.json",
  "scripts\start-legacy.ps1",
  "scripts\api-smoke.ps1",
  "docs\ENVIRONMENT.md",
  "docs\STARTUP_COMMANDS.md",
  "docs\PROTECTED_ASSETS.md",
  "docs\LEGACY_INVENTORY.md",
  "docs\PRODUCTION_READINESS.md",
  "docs\DEPRECATED_ENTRYPOINTS.md",
  "apps\api\main.py",
  "apps\api\schemas.py",
  "apps\extension\manifest.json",
  "apps\web\package.json",
  "apps\web\app\layout.tsx",
  "apps\web\app\page.tsx",
  "apps\web\components\layout-shell.tsx",
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
  "legacy\sou",
  "legacy\prompt-agent",
  "legacy\study",
  "legacy\prompt-rag-backup",
  "legacy\work"
)

foreach ($relative in $required) {
  Test-RequiredPath (Join-Path $Root $relative)
}

$forbiddenEnvNames = @(".env", ".env.local", ".env.production", ".env.development", ".env.test")
$forbiddenEnvFiles = Get-ChildItem -LiteralPath $Root -Recurse -Force -File -ErrorAction SilentlyContinue |
  Where-Object { $forbiddenEnvNames -contains $_.Name }

if ($forbiddenEnvFiles.Count -gt 0) {
  Write-Host "[fail] real env files found:"
  foreach ($file in $forbiddenEnvFiles) {
    Write-Host "  $($file.FullName)"
  }
  $exitCode = 1
}
else {
  Write-Host "[ok] no real .env files found"
}

$portVariables = @(
  "REALITY_OS_API_PORT",
  "REALITY_OS_WEB_PORT",
  "SOU_BACKEND_PORT",
  "SOU_FRONTEND_PORT",
  "PROMPT_AGENT_PORT",
  "PROMPT_AGENT_DESKTOP_PORT",
  "WORK_API_PORT"
)

$envExamplePath = Join-Path $Root ".env.example"
$envExample = Get-Content -Raw -LiteralPath $envExamplePath
foreach ($name in $portVariables) {
  if ($envExample -match "(?m)^$name=") {
    Write-Host "[ok] env var present: $name"
  }
  else {
    Write-Host "[missing] env var: $name"
    $exitCode = 1
  }
}

$packageJson = Get-Content -Raw -LiteralPath (Join-Path $Root "package.json")
foreach ($scriptName in @("api:smoke", "smoke:evaluate", "web:e2e", "web:build:strict", "web:dev", "web:build", "web:lint")) {
  if ($packageJson -match "`"$scriptName`"") {
    Write-Host "[ok] root script present: $scriptName"
  }
  else {
    Write-Host "[missing] root script: $scriptName"
    $exitCode = 1
  }
}

exit $exitCode
