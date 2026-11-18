"""Builds experiments/rig_capture_stagger_sp2027.py from the read-only original by exact, counted replacements.

Only the session precondition changes (2026-11-06 user instruction: close ToDesk, then collect while the idle
bench console session of 'win' stays logged in).  The capture code path is byte-identical.
"""
import hashlib, pathlib
SRC = pathlib.Path(r'<WORKSPACE>/ws_pi\results\scenario_rf_20261104\rig_capture_stagger.py')
DST = pathlib.Path(r'<WORKSPACE>/ws_main\results\sp2027\experiments\rig_capture_stagger_sp2027.py')
t = SRC.read_bytes().decode('utf-8')
assert '\r\n' in t
N = '\r\n'
SESSION = N.join([
    'def session_check():',
    '    # sp2027: only the bench console session of user win may exist, ToDesk must not run; anything else refuses',
    '    qu=subprocess.run(["query","user"],capture_output=True,text=True,errors="replace",timeout=10)',
    '    if qu.returncode not in (0,1):raise RuntimeError("unable to inspect terminal users")',
    '    # capture-pc returns rc=1 even when it lists sessions, so parse the listing regardless of rc',
    '    rows=[l.split() for l in qu.stdout.strip().splitlines()[1:] if l.strip()]',
    '    if len(rows)>1 or any(len(r)<2 or r[0].lstrip(">").lower()!="win" or r[1].lower()!="console" for r in rows):raise RuntimeError("terminal session other than the bench console: "+qu.stdout)',
    '    td=subprocess.run(["tasklist","/FI","IMAGENAME eq ToDesk.exe","/FO","CSV","/NH"],capture_output=True,text=True,errors="replace",timeout=10)',
    '    if td.returncode or "todesk.exe" in td.stdout.lower():raise RuntimeError("ToDesk running or tasklist failed: "+td.stdout+td.stderr)',
    '    return {"rc":qu.returncode,"stdout":qu.stdout,"stderr":qu.stderr,"todesk_running":False,"utc":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())}',
    ''])
REPL = [
    ('"""capture-pc bounded receive-only acquisition; JSON stdin/stdout; no models."""',
     '"""capture-pc bounded receive-only acquisition; JSON stdin/stdout; no models.' + N +
     'sp2027 copy (2026-11-06): capture code identical to rig_capture_stagger.py of session ws_pi.  The console-user' + N +
     'refusal is replaced by session_check(): only the bench console session of user win may exist, ToDesk must be closed,' + N +
     'and any other terminal session refuses; the check repeats before every capture.  CPU load and remote tools are recorded.' + N +
     '"""'),
    ('def main():' + N, SESSION + 'def main():' + N),
    ("\"$u=(Get-CimInstance Win32_ComputerSystem).UserName;if($u){throw ('console user '+$u)};\"",
     "\"$u=(Get-CimInstance Win32_ComputerSystem).UserName;if($u -and ($u -notmatch '\\\\\\\\win$')){throw ('console user '+$u)};\""),
    ("console_user=$u;other_workloads=$py.Count}|ConvertTo-Json -Compress",
     "console_user=$u;other_workloads=$py.Count;cpu_load=(Get-CimInstance Win32_Processor|Measure-Object -Property LoadPercentage -Average).Average;"
     "remote_tools=@(Get-Process -ErrorAction SilentlyContinue|Where-Object {$_.Name -match '^(ToDesk|AweSun|GameViewer|SunloginClient|TeamViewer|AnyDesk|rustdesk)'}|ForEach-Object {$_.Name+':'+$_.Id})}|ConvertTo-Json -Compress"),
    ('        qu=subprocess.run(["query","user"],capture_output=True,text=True,errors="replace",timeout=10)' + N, ''),
    ('        pre["query_user"]={"rc":qu.returncode,"stdout":qu.stdout,"stderr":qu.stderr}' + N +
     '        if qu.returncode==0 and len(qu.stdout.strip().splitlines())>1:raise RuntimeError("logged in terminal user")' + N +
     '        if qu.returncode not in (0,1):raise RuntimeError("unable to inspect terminal users")' + N,
     '        pre["query_user"]=session_check()' + N),
    ('                if not ident.isalnum() or secs not in (4,8):raise ValueError("capture bounds")' + N,
     '                if not ident.isalnum() or secs not in (4,8):raise ValueError("capture bounds")' + N + '                sess=session_check()' + N),
    ('emit({"state":"capturing","win_mono_ns":time.perf_counter_ns(),"marks":marks})',
     'emit({"state":"capturing","win_mono_ns":time.perf_counter_ns(),"marks":marks,"session_check":sess})'),
]
for old, new in REPL:
    assert t.count(old) == 1, ('not unique', old[:80], t.count(old))
    t = t.replace(old, new)
DST.write_bytes(t.encode('utf-8'))
compile(t, str(DST), 'exec')
print('src', hashlib.sha256(SRC.read_bytes()).hexdigest())
print('dst', hashlib.sha256(DST.read_bytes()).hexdigest(), len(t))
