param([string]$Destination)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
if ($Destination) { & .venv/Scripts/python.exe -m scripts.operations backup --path $Destination }
else { & .venv/Scripts/python.exe -m scripts.operations backup }
if ($LASTEXITCODE -ne 0) { throw 'Backup não concluído.' }
