# Isolated checks: no installation, Docker startup or changes to the user's .env.
$ErrorActionPreference = 'Stop'
$tokens = $null; $parseErrors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot 'windows.ps1'), [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count) { throw ($parseErrors | Out-String) }
foreach ($name in @('New-Secret', 'Configure-Environment', 'Test-DockerReady', 'Test-ApplicationImages')) {
    $definition = $ast.Find({ param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name }, $true)
    Invoke-Expression $definition.Extent.Text
}
function Status([string]$Message) { }
function Assert([bool]$condition, [string]$message) { if (-not $condition) { throw $message } }
$checkoutRoot = Split-Path -Parent $PSScriptRoot
$shortcuts = @{
    'instalar.bat'='install'; 'iniciar.bat'='start'; 'desligar.bat'='stop';
    'atalhos\instalar.bat'='install'; 'atalhos\iniciar.bat'='start';
    'atalhos\reiniciar.bat'='restart'; 'atalhos\desligar.bat'='stop'
}
foreach ($relative in $shortcuts.Keys) {
    $shortcutPath = Join-Path $checkoutRoot $relative
    $contents = [IO.File]::ReadAllText($shortcutPath)
    Assert ($contents -match '-File "(%~dp0[^\"]+)" -Action (\w+)') "Comando invalido no atalho $relative"
    $target = $Matches[1].Replace('%~dp0', ((Split-Path -Parent $shortcutPath) + '\'))
    $actionName = $Matches[2]
    Assert ([IO.Path]::GetFullPath($target) -eq (Join-Path $checkoutRoot 'scripts\windows.ps1')) "Destino incorreto: $relative"
    Assert (Test-Path -LiteralPath $target) "Controlador ausente: $relative"
    Assert ($actionName -eq $shortcuts[$relative]) "Acao incorreta: $relative"
    Assert ($contents.Contains('"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"')) "PowerShell incorreto: $relative"
}
Write-Host 'PASS: destinos e acoes dos sete atalhos de instalacao e uso diario.'
$projectRoot = Join-Path ([IO.Path]::GetTempPath()) ('i9 installer test ' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $projectRoot | Out-Null
Configure-Environment
$path = Join-Path $projectRoot '.env'
$initial = [IO.File]::ReadAllText($path)
Assert ($initial -match 'ALLOW_SOURCE_DOWNLOAD=true') 'Downloads manuais devem estar permitidos.'
Assert ($initial -match 'I9_CATALOG_AUTO_REFRESH=false') 'Consulta periodica deve estar desativada.'
Assert ($initial -match 'I9_UPDATES_PAUSED=true') 'Downloads automaticos devem estar pausados.'
$secrets = @(Get-Content -LiteralPath $path | Where-Object { $_ -match '^(POSTGRES_PASSWORD|ADMIN_API_KEY)=' } | ForEach-Object { ($_ -split '=')[1] })
Assert ($secrets.Count -eq 2 -and $secrets[0] -ne $secrets[1] -and $secrets[0].Length -eq 64) 'Credenciais distintas e aleatorias.'
Configure-Environment
Assert ([IO.File]::ReadAllText($path) -eq $initial) 'Reinstalacao deve preservar configuracao.'
[IO.File]::WriteAllText($path, $initial.Replace('ALLOW_SOURCE_DOWNLOAD=true', 'ALLOW_SOURCE_DOWNLOAD=false'))
Configure-Environment
Assert ([IO.File]::ReadAllText($path).Contains('ALLOW_SOURCE_DOWNLOAD=false')) 'Preferencia existente foi alterada.'
$script:dockerExe = Join-Path $projectRoot 'docker-probe.cmd'
[IO.File]::WriteAllText($script:dockerExe, "@echo off`r`necho Docker indisponivel 1>&2`r`nexit /b 1`r`n")
Assert (-not (Test-DockerReady)) 'Docker parado deve retornar falso sem interromper o instalador.'
Assert ($ErrorActionPreference -eq 'Stop') 'A verificacao nao deve alterar o tratamento de outros erros.'
[IO.File]::WriteAllText($script:dockerExe, "@echo off`r`nexit /b 0`r`n")
Assert (Test-DockerReady) 'Docker pronto deve permitir continuar.'
$imageProbe = @'
@echo off
if "%1"=="compose" (
echo nexus-test-api
echo nexus-test-migrate
exit /b 0
)
if "%3"=="nexus-test-migrate" exit /b 1
exit /b 0
'@
[IO.File]::WriteAllText($script:dockerExe, $imageProbe.Replace("`n", "`r`n"))
Assert (-not (Test-ApplicationImages)) 'Imagem de migracao ausente deve preparar a primeira execucao.'
[IO.File]::WriteAllText($script:dockerExe, $imageProbe.Replace('exit /b 1', 'exit /b 0').Replace("`n", "`r`n"))
Assert (Test-ApplicationImages) 'Instalacao completa deve iniciar sem reconstruir imagens.'
Write-Host 'PASS: sintaxe, caminho com espacos, configuracao inicial, credenciais e reinstalacao.'
Write-Host "Arquivos isolados de teste: $projectRoot"
