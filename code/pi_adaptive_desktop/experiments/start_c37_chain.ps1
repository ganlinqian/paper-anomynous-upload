# Registers and starts the scheduled task for run_c37_chain.ps1 (session ws_revision).
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File start_c37_chain.ps1 [-SmokeOnly] [-SkipSmoke]
param([switch]$SmokeOnly, [switch]$SkipSmoke)
$ErrorActionPreference = 'Stop'
$name = 'Telltale-ws_revision-c37-chain'
$extra = $(if ($SmokeOnly) { ' -SmokeOnly' } else { '' }) + $(if ($SkipSmoke) { ' -SkipSmoke' } else { '' })
$script = Join-Path $PSScriptRoot 'run_c37_chain.ps1'
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -ExecutionPolicy Bypass -File "' + $script + '"' + $extra) -WorkingDirectory $PSScriptRoot
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 5) -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $name -Action $action -Principal $principal -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName $name
Start-Sleep -Seconds 3
$i = Get-ScheduledTaskInfo -TaskName $name
'task=' + $name + ' lastRun=' + $i.LastRunTime + ' result=' + $i.LastTaskResult
