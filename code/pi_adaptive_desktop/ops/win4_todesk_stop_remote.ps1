# Stops ToDesk on capture-pc (service + session client). StartMode is left unchanged (Auto); restore with Start-Service ToDesk_Service.
$ErrorActionPreference = 'Continue'
'elevated=' + ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
'before=' + ((@(Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'todesk' } | ForEach-Object { '{0} {1} sess={2}' -f $_.ProcessId, $_.Name, $_.SessionId })) -join '; ')
try { Stop-Service -Name ToDesk_Service -Force -ErrorAction Stop; 'stop-service ok' } catch { 'stop-service failed: ' + $_.Exception.Message }
Start-Sleep -Seconds 3
Get-Process -Name ToDesk* -ErrorAction SilentlyContinue | ForEach-Object { $id = $_.Id; $s = $_.SessionId; try { Stop-Process -Id $id -Force -ErrorAction Stop; 'killed {0} sess={1}' -f $id, $s } catch { 'kill {0} failed: {1}' -f $id, $_.Exception.Message } }
Start-Sleep -Seconds 10
'service=' + (Get-Service ToDesk_Service).Status + ' startmode=' + (Get-CimInstance Win32_Service -Filter "Name='ToDesk_Service'").StartMode
'after=' + ((@(Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'todesk' } | ForEach-Object { '{0} {1} sess={2}' -f $_.ProcessId, $_.Name, $_.SessionId })) -join '; ')
'utc=' + [DateTime]::UtcNow.ToString('o')
