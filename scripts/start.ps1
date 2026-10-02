param([switch]$Install)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
if ($Install) {
    if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) { python -m venv .venv }
    & .venv/Scripts/python.exe -m pip install -r requirements.txt
    Push-Location dashboard
    try { npm.cmd ci; npm.cmd run build } finally { Pop-Location }
}
& .venv/Scripts/python.exe -m scripts.operations start
if ($LASTEXITCODE -ne 0) { throw 'Falha na inicialização; consulte os logs.' }
