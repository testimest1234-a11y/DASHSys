Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
& .\.venv\Scripts\python.exe -m dashsys_agent.cli doctor
& .\.venv\Scripts\python.exe -m dashsys_agent.cli build-catalog
& .\.venv\Scripts\python.exe -m dashsys_agent.cli eval-samples --api-mode mock
