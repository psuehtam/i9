$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot '.venv/Scripts/pythonw.exe'
$user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -Hidden -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit (New-TimeSpan -Hours 3) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$start = New-ScheduledTaskAction -Execute $python -Argument '-m scripts.operations supervise' -WorkingDirectory $projectRoot
$backup = New-ScheduledTaskAction -Execute $python -Argument '-m scripts.operations backup' -WorkingDirectory $projectRoot
Register-ScheduledTask -TaskName 'i9-Iniciar' -Action $start -Trigger (New-ScheduledTaskTrigger -AtLogOn -User $user) -Settings (New-ScheduledTaskSettingsSet -Hidden -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries) -Principal $principal -Force | Out-Null
Register-ScheduledTask -TaskName 'i9-Backup-Diario' -Action $backup -Trigger (New-ScheduledTaskTrigger -Daily -At '03:00') -Settings $settings -Principal $principal -Force | Out-Null
Write-Host 'Inicialização e backup diário configurados.'
