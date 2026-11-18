"""Read-only bench status (Pi + capture-pc) before/after a collection; changes nothing.  Prints one JSON object."""
import base64, json, pathlib, sys
SRC = pathlib.Path(r'<WORKSPACE>/ws_pi\results\scenario_rf_20261104')
sys.path.insert(0, str(SRC / 'burst_study')); from bridge_utils import *   # noqa

def win_ps(w, code, timeout=40):
    b64 = base64.b64encode(code.encode('utf-16-le')).decode()
    return run(w, 'powershell -NoProfile -NonInteractive -EncodedCommand ' + b64, timeout=timeout, check=False)

out = {'utc': stamp()}
p = connect('192.0.2.60', 'admin', 522)
try:
    out['pi_state'] = snapshot(p).splitlines()[:5]
    out['pi_thermal'] = thermal()
    out['pi_lock'] = run(p, 'ls -l /home/pi/telltale_g1_20261026/controller.lock 2>&1 || true')['stdout'].strip()
    out['pi_busy'] = run(p, "pgrep -af '^(perf|strace|resident_tool|python3.*(telltale|pi_api))' | grep -v pgrep || true")['stdout'].strip()
    out['pi_uptime'] = run(p, 'uptime')['stdout'].strip()
finally:
    p.close()
w = connect('192.0.2.4', 'win')
try:
    r = win_ps(w, "$ErrorActionPreference='Continue';[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false);"
                  "$q=(query user 2>&1|Out-String).Trim();"
                  "$svc=Get-Service ToDesk_Service -ErrorAction SilentlyContinue;"
                  "$rt=@(Get-Process -ErrorAction SilentlyContinue|Where-Object {$_.Name -match '^(ToDesk|AweSun|GameViewer|SunloginClient|TeamViewer|AnyDesk|rustdesk)'}|ForEach-Object {$_.Name+':'+$_.Id+':s'+$_.SessionId});"
                  "$py=@(Get-CimInstance Win32_Process|Where-Object {$_.Name -match '^(python|pythonw|hackrf_transfer)'}|ForEach-Object {$_.Name+':'+$_.ProcessId});"
                  "$conn=@(Get-NetTCPConnection -State Established -ErrorAction SilentlyContinue|Where-Object {$_.OwningProcess -in @(Get-Process -Name ToDesk* -ErrorAction SilentlyContinue).Id}|ForEach-Object {$_.RemoteAddress+':'+$_.RemotePort});"
                  "$idle=$null;try{Add-Type -Namespace W -Name U -MemberDefinition '[StructLayout(LayoutKind.Sequential)] public struct L{public uint s;public uint t;} [DllImport(\"user32.dll\")] public static extern bool GetLastInputInfo(ref L l);' -ErrorAction Stop}catch{};"
                  "[PSCustomObject]@{query_user=$q;todesk_service=[string]$svc.Status;todesk_start=[string]$svc.StartType;remote_tools=$rt;todesk_tcp=$conn;"
                  "workloads=$py;j_free_gb=[math]::Round(([IO.DriveInfo]::new('J')).AvailableFreeSpace/1GB,1);"
                  "cpu_load=(Get-CimInstance Win32_Processor|Measure-Object -Property LoadPercentage -Average).Average;"
                  "g1_lock=(Test-Path '<DATA>/.telltale_g1.lock');"
                  "boot=(Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToString('o');"
                  "explorer_sessions=@(Get-Process explorer -ErrorAction SilentlyContinue|ForEach-Object {$_.SessionId})}|ConvertTo-Json -Compress")
    out['win4_rc'] = r['rc']
    try:
        out['capture-pc'] = json.loads(r['stdout'].strip().splitlines()[-1])
    except Exception:
        out['win4_raw'] = (r['stdout'] + r['stderr'])[-2000:]
finally:
    w.close()
print(json.dumps(out, ensure_ascii=False, indent=1))
