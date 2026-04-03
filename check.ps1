param(
  [switch]$SkipFrontend,
  [switch]$SkipBackend
)

$ErrorActionPreference = "Stop"

function RunStep([string]$Name, [scriptblock]$Block) {
  Write-Host ""
  Write-Host "==> $Name"
  & $Block
}

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

function Resolve-Python([string]$Root) {
  $candidates = @(
    (Join-Path $Root ".venv311\\Scripts\\python.exe"),
    (Join-Path $Root ".venv\\Scripts\\python.exe"),
    (Join-Path $Root "venv\\Scripts\\python.exe")
  )

  foreach ($c in $candidates) {
    if (Test-Path $c) { return $c }
  }

  $cmd = Get-Command python -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }

  throw "Python not found. Create a venv (e.g. `py -3.11 -m venv .venv311`) and install requirements."
}

$py = Resolve-Python $repoRoot

if (-not $SkipBackend) {
  RunStep "Backend: Syntax Check (py_compile)" {
    & $py -m py_compile `
      backend\\app.py `
      backend\\routes\\pipelines.py `
      backend\\routes\\config.py `
      backend\\routes\\websocket.py `
      backend\\services\\config_service.py `
      backend\\services\\pipeline_executor.py
  }

  RunStep "Backend: Pytest" {
    & $py -m pytest -q
  }
}

if (-not $SkipFrontend) {
  if (!(Test-Path (Join-Path $repoRoot "frontend\\package.json"))) {
    throw "frontend/package.json not found."
  }

  RunStep "Frontend: Lint" {
    Push-Location (Join-Path $repoRoot "frontend")
    try { npm run lint } finally { Pop-Location }
  }

  RunStep "Frontend: Build" {
    Push-Location (Join-Path $repoRoot "frontend")
    try { npm run build } finally { Pop-Location }
  }
}

Write-Host ""
Write-Host "All checks passed."
