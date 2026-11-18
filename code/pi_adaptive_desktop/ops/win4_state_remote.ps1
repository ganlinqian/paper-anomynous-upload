# Read-only state probe for the capture-pc capture bench (sent via ssh -EncodedCommand).
$ErrorActionPreference = 'Continue'
'now_local=' + (Get-Date).ToString('o')
'boot=' + (Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToString('o')
'console_user=' + (Get-CimInstance Win32_ComputerSystem).UserName
'--- query user'; query user 2>&1 | Out-String
'--- todesk processes'
Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'todesk' } | ForEach-Object { '{0} {1} sess={2} start={3} cmd={4}' -f $_.ProcessId, $_.Name, $_.SessionId, $_.CreationDate, $_.CommandLine }
'--- todesk services'
Get-CimInstance Win32_Service | Where-Object { $_.Name -match 'todesk' -or $_.DisplayName -match 'todesk' } | ForEach-Object { '{0} state={1} start={2} pid={3} path={4}' -f $_.Name, $_.State, $_.StartMode, $_.ProcessId, $_.PathName }
'--- todesk tcp'
$ids = @(Get-Process | Where-Object { $_.Name -match 'todesk' } | ForEach-Object { $_.Id })
Get-NetTCPConnection -ErrorAction SilentlyContinue | Where-Object { $ids -contains $_.OwningProcess } | ForEach-Object { '{0}:{1} -> {2}:{3} {4} pid={5}' -f $_.LocalAddress, $_.LocalPort, $_.RemoteAddress, $_.RemotePort, $_.State, $_.OwningProcess }
'udp_endpoints=' + @(Get-NetUDPEndpoint -ErrorAction SilentlyContinue | Where-Object { $ids -contains $_.OwningProcess }).Count
'--- winlogon'
$wl = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon'
'AutoAdminLogon=' + $wl.AutoAdminLogon + ' DefaultUserName=' + $wl.DefaultUserName + ' AutoLogonCount=' + $wl.AutoLogonCount
'--- recent logons (4624 type 2/10/11/7, 4634/4647)'
try { Get-WinEvent -FilterHashtable @{LogName='Security'; Id=4624,4647,4800,4801; StartTime=(Get-Date).AddHours(-30)} -MaxEvents 400 -ErrorAction Stop | Where-Object { $_.Id -ne 4624 -or (@('2','7','10','11') -contains ([xml]$_.ToXml()).Event.EventData.Data[8].'#text') } | Select-Object -First 25 | ForEach-Object { $x = [xml]$_.ToXml(); $d = @{}; foreach ($n in $x.Event.EventData.Data) { $d[$n.Name] = $n.'#text' }; '{0} id={1} user={2} type={3} proc={4}' -f $_.TimeCreated.ToString('s'), $_.Id, $d['TargetUserName'], $d['LogonType'], $d['ProcessName'] } } catch { 'security log: ' + $_.Exception.Message }
'--- other workloads'
Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^(python|pythonw|hackrf_transfer)' } | ForEach-Object { '{0} {1} {2}' -f $_.ProcessId, $_.Name, $_.CommandLine }
'cpu_load=' + (Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average
'J_free_GB=' + [math]::Round([IO.DriveInfo]::new('J').AvailableFreeSpace / 1GB, 1)
'--- interactive-session processes (session>0)'
Get-Process | Where-Object { $_.SessionId -gt 0 } | Sort-Object StartTime -ErrorAction SilentlyContinue | ForEach-Object { '{0} pid={1} sess={2} start={3} cpu={4}' -f $_.Name, $_.Id, $_.SessionId, $_.StartTime, [math]::Round($_.CPU,1) } | Select-Object -Last 45
