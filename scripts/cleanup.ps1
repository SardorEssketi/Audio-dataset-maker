param(
  [switch]$All,
  [switch]$IncludeDataArtifacts
)

$ErrorActionPreference = "Stop"

function Remove-IfExists([string]$Path) {
  if (Test-Path -LiteralPath $Path) {
    Write-Host "Removing $Path"
    Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction SilentlyContinue
  }
}

$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Push-Location $repoRoot
try {
  # Always safe to delete (regenerated).
  Remove-IfExists ".pytest_cache"
  Get-ChildItem -Recurse -Directory -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -eq "__pycache__" } |
    ForEach-Object { Remove-IfExists $_.FullName }

  Remove-IfExists "frontend\\dist"

  if ($All) {
    Remove-IfExists ".venv311"
    Remove-IfExists ".venv"
    Remove-IfExists "venv"
    Remove-IfExists "frontend\\node_modules"
  }

  if ($IncludeDataArtifacts) {
    Remove-IfExists "data\\users"
    Remove-IfExists "data\\users.db"
    Get-ChildItem -LiteralPath "data" -Directory -Force -ErrorAction SilentlyContinue |
      Where-Object { $_.Name -like "*_out" -or $_.Name -like "_zip_test_*" } |
      ForEach-Object { Remove-IfExists $_.FullName }
  }

  Write-Host "Cleanup complete."
} finally {
  Pop-Location
}

