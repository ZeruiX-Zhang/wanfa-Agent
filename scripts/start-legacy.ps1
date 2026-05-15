param(
  [Parameter(Mandatory = $true)]
  [ValidateSet(
    "all",
    "sou-backend",
    "sou-web",
    "prompt-backend",
    "prompt-desktop",
    "work-api",
    "work-desktop",
    "work-smoke"
  )]
  [string]$Target,

  [switch]$Run
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$LegacyRoot = Join-Path $Root "legacy"

function Get-EnvDefault {
  param(
    [Parameter(Mandatory = $true)][string]$Name,
    [Parameter(Mandatory = $true)][string]$Default
  )

  $value = [Environment]::GetEnvironmentVariable($Name)
  if ([string]::IsNullOrWhiteSpace($value)) {
    return $Default
  }
  return $value
}

function Get-PythonCommand {
  param([Parameter(Mandatory = $true)][string]$ProjectPath)

  $venvPython = Join-Path $ProjectPath ".venv\Scripts\python.exe"
  if (Test-Path -LiteralPath $venvPython) {
    return $venvPython
  }
  return "python"
}

function Show-Command {
  param(
    [Parameter(Mandatory = $true)][string]$Name,
    [Parameter(Mandatory = $true)][string]$WorkingDirectory,
    [Parameter(Mandatory = $true)][string[]]$Commands
  )

  Write-Host ""
  Write-Host "[$Name]"
  Write-Host "cd `"$WorkingDirectory`""
  foreach ($command in $Commands) {
    Write-Host $command
  }
}

function Invoke-InDirectory {
  param(
    [Parameter(Mandatory = $true)][string]$WorkingDirectory,
    [Parameter(Mandatory = $true)][scriptblock]$Block
  )

  Push-Location -LiteralPath $WorkingDirectory
  try {
    & $Block
  }
  finally {
    Pop-Location
  }
}

$SouBackendPort = Get-EnvDefault "SOU_BACKEND_PORT" "8001"
$SouFrontendPort = Get-EnvDefault "SOU_FRONTEND_PORT" "3001"
$PromptAgentPort = Get-EnvDefault "PROMPT_AGENT_PORT" "8787"
$WorkApiPort = Get-EnvDefault "WORK_API_PORT" "8002"

$SouBackend = Join-Path $LegacyRoot "sou\backend"
$SouFrontend = Join-Path $LegacyRoot "sou\frontend"
$PromptAgent = Join-Path $LegacyRoot "prompt-agent"
$Work = Join-Path $LegacyRoot "work"

function Show-All {
  Show-Command "sou-backend" $SouBackend @(
    "`$env:PYTHONPATH='.deps'",
    ".\.venv\Scripts\python.exe -m alembic upgrade head",
    ".\.venv\Scripts\python.exe scripts\seed.py",
    ".\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port $SouBackendPort"
  )
  Show-Command "sou-web" $SouFrontend @(
    "npm.cmd run dev -- --port $SouFrontendPort"
  )
  Show-Command "prompt-backend" $PromptAgent @(
    "python -m uvicorn app.main:app --host 127.0.0.1 --port $PromptAgentPort"
  )
  Show-Command "prompt-desktop" $PromptAgent @(
    "npm.cmd run tauri:dev"
  )
  Show-Command "work-api" $Work @(
    "`$env:API_PORT='$WorkApiPort'",
    "python scripts/init_platform.py",
    "python scripts/run_api.py"
  )
  Show-Command "work-desktop" $Work @(
    "python scripts/run_desktop.py"
  )
  Show-Command "work-smoke" $Work @(
    "python scripts/smoke_test_rag.py"
  )
}

if (-not $Run) {
  if ($Target -eq "all") {
    Show-All
    exit 0
  }

  switch ($Target) {
    "sou-backend" {
      Show-Command "sou-backend" $SouBackend @(
        "`$env:PYTHONPATH='.deps'",
        ".\.venv\Scripts\python.exe -m alembic upgrade head",
        ".\.venv\Scripts\python.exe scripts\seed.py",
        ".\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port $SouBackendPort"
      )
    }
    "sou-web" {
      Show-Command "sou-web" $SouFrontend @("npm.cmd run dev -- --port $SouFrontendPort")
    }
    "prompt-backend" {
      Show-Command "prompt-backend" $PromptAgent @("python -m uvicorn app.main:app --host 127.0.0.1 --port $PromptAgentPort")
    }
    "prompt-desktop" {
      Show-Command "prompt-desktop" $PromptAgent @("npm.cmd run tauri:dev")
    }
    "work-api" {
      Show-Command "work-api" $Work @(
        "`$env:API_PORT='$WorkApiPort'",
        "python scripts/init_platform.py",
        "python scripts/run_api.py"
      )
    }
    "work-desktop" {
      Show-Command "work-desktop" $Work @("python scripts/run_desktop.py")
    }
    "work-smoke" {
      Show-Command "work-smoke" $Work @("python scripts/smoke_test_rag.py")
    }
  }
  exit 0
}

if ($Target -eq "all") {
  throw "Refusing to run all legacy services at once. Print the command list first, then run one target at a time."
}

switch ($Target) {
  "sou-backend" {
    Invoke-InDirectory $SouBackend {
      $python = Get-PythonCommand $SouBackend
      $env:PYTHONPATH = ".deps"
      & $python -m alembic upgrade head
      & $python scripts\seed.py
      & $python -m uvicorn app.main:app --host 0.0.0.0 --port $SouBackendPort
    }
  }
  "sou-web" {
    Invoke-InDirectory $SouFrontend {
      & npm.cmd run dev -- --port $SouFrontendPort
    }
  }
  "prompt-backend" {
    Invoke-InDirectory $PromptAgent {
      & python -m uvicorn app.main:app --host 127.0.0.1 --port $PromptAgentPort
    }
  }
  "prompt-desktop" {
    Invoke-InDirectory $PromptAgent {
      & npm.cmd run tauri:dev
    }
  }
  "work-api" {
    Invoke-InDirectory $Work {
      $env:API_PORT = $WorkApiPort
      & python scripts\init_platform.py
      & python scripts\run_api.py
    }
  }
  "work-desktop" {
    Invoke-InDirectory $Work {
      & python scripts\run_desktop.py
    }
  }
  "work-smoke" {
    Invoke-InDirectory $Work {
      & python scripts\smoke_test_rag.py
    }
  }
}
