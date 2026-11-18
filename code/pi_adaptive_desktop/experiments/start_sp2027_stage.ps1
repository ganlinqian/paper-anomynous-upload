# Registers (or re-registers) and starts the scheduled task for one supplement stage.
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File start_sp2027_stage.ps1 -Stage s1
param([ValidateSet('s1','s3','s2train','s2test')][string]$Stage)
$ErrorActionPreference = 'Stop'
$name = 'Telltale-ws_main-sp2027-' + $Stage
$script = Join-Path $PSScriptRoot 'run_sp2027.ps1'
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -ExecutionPolicy Bypass -File "' + $script + '" -Stage ' + $Stage) -WorkingDirectory $PSScriptRoot
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 3) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $name -Action $action -Principal $principal -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName $name
Start-Sleep -Seconds 3
$i = Get-ScheduledTaskInfo -TaskName $name
'task=' + $name + ' lastRun=' + $i.LastRunTime + ' result=' + $i.LastTaskResult
