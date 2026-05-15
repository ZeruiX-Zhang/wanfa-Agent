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

Write-Host "Reality OS Phase 2 doctor"
Write-Host "Root: $Root"

$required = @(
  "README.md",
  ".env.example",
  ".gitignore",
  "package.json",
  "scripts\start-legacy.ps1",
  "scripts\check-phase2.ps1",
  "docs\ENVIRONMENT.md",
  "docs\STARTUP_COMMANDS.md",
  "docs\PROTECTED_ASSETS.md",
  "docs\LEGACY_INVENTORY.md",
  "docs\PHASE_1_ACCEPTANCE_REPORT.md",
  "docs\PHASE_2_ACCEPTANCE_REPORT.md",
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

exit $exitCode
