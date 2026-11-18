# Registers (or re-registers) and starts the scheduled task that runs run_sp2027_chain.ps1.
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File start_sp2027_chain.ps1 [-Stages s1,s3,s2train,s2test] [-Bzip2Mib 2] [-StopToDesk] [-Suffix c27]
param([string]$Stages = 's1,s3,s2train,s2test', [int]$Bzip2Mib = 2, [switch]$StopToDesk, [string]$Suffix = '')
$ErrorActionPreference = 'Stop'
$name = 'Telltale-ws_main-sp2027-chain' + $(if ($Suffix) { '-' + $Suffix } else { '' })
$extra = ' -Bzip2Mib ' + $Bzip2Mib + $(if ($StopToDesk) { ' -StopToDesk' } else { '' })
$script = Join-Path $PSScriptRoot 'run_sp2027_chain.ps1'
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -ExecutionPolicy Bypass -File "' + $script + '" -Stages ' + $Stages + $extra) -WorkingDirectory $PSScriptRoot
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 5) -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $name -Action $action -Principal $principal -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName $name
Start-Sleep -Seconds 3
$i = Get-ScheduledTaskInfo -TaskName $name
'task=' + $name + ' lastRun=' + $i.LastRunTime + ' result=' + $i.LastTaskResult
