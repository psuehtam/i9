param([ValidateSet('install','start','stop','restart')][string]$Action = 'start')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$logDirectory = Join-Path $projectRoot 'data\logs'
New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
$logPath = Join-Path $logDirectory 'windows.log'
function Status([string]$Message) {
    Write-Host $Message
    Add-Content -LiteralPath $logPath -Value ("{0} {1}" -f (Get-Date -Format s), $Message)
}
function Docker {
    & $script:dockerExe @args
    if ($LASTEXITCODE -ne 0) { throw 'Falha no Docker. Confira a mensagem acima.' }
}
function New-Secret {
    $bytes = New-Object byte[] 32
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    return ([BitConverter]::ToString($bytes)).Replace('-', '').ToLowerInvariant()
}
function Disable-LegacyAutomation {
    # Only touch the old i9 tasks when their action belongs to this checkout.
    foreach ($name in @('i9-Iniciar', 'i9-Backup-Diario')) {
        $task = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
        if (-not $task) { continue }
        foreach ($action in $task.Actions) {
            if ($action.WorkingDirectory -and [IO.Path]::GetFullPath($action.WorkingDirectory).TrimEnd('\') -eq $projectRoot.TrimEnd('\')) {
                Disable-ScheduledTask -InputObject $task | Out-Null
                Status "Agendamento antigo desativado: $name"
                break
            }
        }
    }
}
function Configure-Environment {
    $path = Join-Path $projectRoot '.env'
    $lines = @()
    if (Test-Path -LiteralPath $path) { $lines = @(Get-Content -LiteralPath $path) }
    $defaults = [ordered]@{ POSTGRES_PASSWORD=(New-Secret); ADMIN_API_KEY=(New-Secret); ALLOW_SOURCE_DOWNLOAD='true'; I9_CATALOG_AUTO_REFRESH='false'; I9_ON_DEMAND_WORKER='true'; I9_CHECK_ON_START='true'; I9_UPDATES_PAUSED='true' }
    foreach ($key in $defaults.Keys) {
        $index = -1
        for ($i=0; $i -lt $lines.Count; $i++) { if ($lines[$i] -match "^\s*$key\s*=") { $index=$i; break } }
        if ($index -lt 0) { $lines += "$key=$($defaults[$key])" }
        elseif ($lines[$index] -match '=\s*(CHANGE_ME[^\s]*|)\s*$') {
            # Never rotate an existing database password silently.
            if ($key -eq 'POSTGRES_PASSWORD') {
                $configuration = & $script:dockerExe compose config --format json 2>$null
                if ($LASTEXITCODE -ne 0) { throw 'Configuracao existente incompleta. Confira o .env antes de continuar.' }
                $projectName = ($configuration | ConvertFrom-Json).name
                $volume = & $script:dockerExe volume ls -q --filter "label=com.docker.compose.project=$projectName" --filter 'label=com.docker.compose.volume=postgres-data'
                if ($LASTEXITCODE -ne 0) { throw 'Nao foi possivel verificar o volume existente.' }
                if ($volume) { throw 'Senha de exemplo em instalacao existente. Corrija POSTGRES_PASSWORD no .env antes de continuar.' }
            }
            $lines[$index] = "$key=$($defaults[$key])"
            Status "Configuracao de exemplo substituida: $key"
        }
    }
    [IO.File]::WriteAllLines($path, [string[]]$lines, (New-Object Text.UTF8Encoding($false)))
}
function Test-DockerReady {
    # Windows PowerShell turns native stderr into a terminating error under Stop,
    # even when redirected. A stopped daemon is expected during startup.
    $ErrorActionPreference = 'Continue'
    try {
        & $script:dockerExe info *> $null
        return ($LASTEXITCODE -eq 0)
    } catch { return $false }
}
function Wait-Docker {
    if (Test-DockerReady) { return }
    $desktop = Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'
    if (-not (Test-Path -LiteralPath $desktop)) { $desktop = Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\Docker Desktop.exe' }
    if (Test-Path -LiteralPath $desktop) { Start-Process -FilePath $desktop -WindowStyle Hidden }
    Status 'Aguardando o Docker (ate 3 minutos)...'
    for ($i=0; $i -lt 60; $i++) {
        if (Test-DockerReady) { return }
        Start-Sleep -Seconds 3
    }
    throw 'Docker indisponivel. Abra o Docker Desktop, conclua a configuracao e execute novamente.'
}
function Wait-Application {
    for ($i=0; $i -lt 60; $i++) {
        try {
            $session = Invoke-RestMethod 'http://localhost:8000/api/v3/auth/session' -TimeoutSec 3
            if ($null -ne $session.authenticated) { return $session }
        } catch { }
        Start-Sleep -Seconds 2
    }
    throw 'O sistema nao ficou pronto. Consulte os servicos com docker compose logs.'
}
function Test-ApplicationImages {
    $images = & $script:dockerExe compose config --images migrate api
    if ($LASTEXITCODE -ne 0 -or -not $images) { throw 'Nao foi possivel verificar as imagens do NEXUS.' }
    foreach ($image in ($images | Select-Object -Unique)) {
        # Missing images are expected on first launch, including after a partial install.
        $ErrorActionPreference = 'Continue'
        & $script:dockerExe image inspect $image *> $null
        $exists = ($LASTEXITCODE -eq 0)
        $ErrorActionPreference = 'Stop'
        if (-not $exists) { return $false }
    }
    return $true
}
try {
    $script:dockerExe = (Get-Command docker.exe -CommandType Application -ErrorAction SilentlyContinue).Source
    if (-not $script:dockerExe) { $script:dockerExe = Join-Path $env:ProgramFiles 'Docker\Docker\resources\bin\docker.exe' }
    if (-not (Test-Path -LiteralPath $script:dockerExe)) {
        $perUserDocker = Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin\docker.exe'
        if (Test-Path -LiteralPath $perUserDocker) { $script:dockerExe = $perUserDocker }
    }
    if ($Action -in @('start', 'restart') -and ((-not (Test-Path -LiteralPath $script:dockerExe)) -or (-not (Test-Path -LiteralPath (Join-Path $projectRoot '.env'))))) {
        Status 'Primeiro uso detectado. Preparando a instalacao do NEXUS...'
        $Action = 'install'
    }
    if ($Action -eq 'install') {
        $disk = Get-PSDrive -Name ([IO.Path]::GetPathRoot($projectRoot).Substring(0,1))
        if ($disk.Free -lt 15GB) { throw 'Libere pelo menos 15 GB no disco do projeto.' }
        $os = Get-CimInstance Win32_OperatingSystem
        if ([int]$os.BuildNumber -lt 19045) { throw 'Atualize o Windows para uma versao compativel com Docker Desktop e WSL 2.' }
        $computer = Get-CimInstance Win32_ComputerSystem
        $cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
        if (-not $computer.HypervisorPresent -and -not $cpu.VirtualizationFirmwareEnabled) { throw 'Ative a virtualizacao na BIOS/UEFI e execute novamente.' }
        if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) { throw 'Instale o WSL 2 no Windows e reinicie antes de continuar.' }
        & wsl.exe --status *> $null
        if ($LASTEXITCODE -ne 0) { throw 'Abra o PowerShell como administrador, execute wsl --install --no-distribution, reinicie e execute instalar.bat novamente.' }
        if (-not (Test-Path -LiteralPath $script:dockerExe)) {
            if (-not (Get-Command winget -ErrorAction SilentlyContinue)) { throw 'Instale Docker Desktop em https://docs.docker.com/desktop/setup/install/windows-install/ e execute novamente.' }
            Status 'Instalando Docker Desktop pelo WinGet...'
            & winget install --exact --id Docker.DockerDesktop --source winget --accept-source-agreements
            if ($LASTEXITCODE -ne 0) { throw 'Instalacao do Docker interrompida. Conclua o instalador e execute novamente; reinicie se solicitado.' }
            $perUserDocker = Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin\docker.exe'
            if (Test-Path -LiteralPath $perUserDocker) { $script:dockerExe = $perUserDocker }
        }
    }
    if (-not (Test-Path -LiteralPath $script:dockerExe)) { throw 'Docker nao encontrado. Execute instalar.bat primeiro.' }
    if ($Action -eq 'stop') {
        if (Test-DockerReady) { Docker compose --profile maintenance stop }
        Status 'Sistema parado. Dados preservados.'
        exit 0
    }
    Wait-Docker
    Disable-LegacyAutomation
    if ($Action -eq 'install') { Configure-Environment }
    if (-not (Test-Path -LiteralPath '.env')) { throw 'Configuracao ausente. Execute instalar.bat primeiro.' }
    if ($Action -eq 'restart') { Docker compose stop }
    # Stop the old standalone worker when upgrading to on-demand operation.
    Docker compose --profile maintenance stop worker
    $owned = & $script:dockerExe compose ps -q api
    $listener = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
    if ($listener -and -not $owned) { throw 'A porta 8000 esta ocupada. Encerre a outra aplicacao antes de iniciar o NEXUS.' }
    if ($Action -eq 'install' -or -not (Test-ApplicationImages)) { Status 'Preparando dependencias e banco (a primeira execucao pode demorar)...'; Docker compose up --build -d postgres migrate api }
    else { Status 'Iniciando o sistema...'; Docker compose up --no-build -d postgres migrate api }
    $session = Wait-Application
    if ($session.setup_required) {
        $adminName = Read-Host 'Escolha o usuario administrador'
        & $script:dockerExe compose exec api python -m scripts.setup_admin --username $adminName
        if ($LASTEXITCODE -ne 0) { throw 'A conta administrativa nao foi configurada. Execute iniciar.bat para tentar novamente; os dados foram preservados.' }
    }
    Status 'NEXUS pronto: http://localhost:8000/veiculos'
    Start-Process 'http://localhost:8000/veiculos'
    try {
        Write-Host 'Fechar a aba do navegador nao interrompe uma importacao.'
        Read-Host 'Pressione ENTER nesta janela para encerrar o sistema (ou use desligar.bat)' | Out-Null
    } finally {
        Docker compose --profile maintenance stop
        Status 'Sistema encerrado. Dados preservados.'
    }
} catch {
    Status ("Erro: " + $_.Exception.Message)
    Write-Host "Registro: $logPath"
    exit 1
}
