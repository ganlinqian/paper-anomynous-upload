"""capture-pc bounded receive-only acquisition; JSON stdin/stdout; no models.
sp2027 copy (2026-11-06): capture code identical to rig_capture_stagger.py of session ws_pi.  The console-user
refusal is replaced by session_check(): only the bench console session of user win may exist, ToDesk must be closed,
and any other terminal session refuses; the check repeats before every capture.  CPU load and remote tools are recorded.
"""
import argparse, ctypes, json, msvcrt, os, pathlib, subprocess, sys, time, traceback
RADIOS=[("930c","<hackrf-serial>",1800000000),("16bc","<hackrf-serial>",105000000)]
def emit(x):
    print(json.dumps(x,ensure_ascii=True),flush=True)
def ps(code):
    r=subprocess.run(["powershell","-NoProfile","-NonInteractive","-Command",code],capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=25)
    if r.returncode: raise RuntimeError("preflight PowerShell: "+r.stdout+r.stderr)
    return r.stdout
def session_check():
    # sp2027: only the bench console session of user win may exist, ToDesk must not run; anything else refuses
    qu=subprocess.run(["query","user"],capture_output=True,text=True,errors="replace",timeout=10)
    if qu.returncode not in (0,1):raise RuntimeError("unable to inspect terminal users")
    # capture-pc returns rc=1 even when it lists sessions, so parse the listing regardless of rc
    rows=[l.split() for l in qu.stdout.strip().splitlines()[1:] if l.strip()]
    if len(rows)>1 or any(len(r)<2 or r[0].lstrip(">").lower()!="win" or r[1].lower()!="console" for r in rows):raise RuntimeError("terminal session other than the bench console: "+qu.stdout)
    td=subprocess.run(["tasklist","/FI","IMAGENAME eq ToDesk.exe","/FO","CSV","/NH"],capture_output=True,text=True,errors="replace",timeout=10)
    if td.returncode or "todesk.exe" in td.stdout.lower():raise RuntimeError("ToDesk running or tasklist failed: "+td.stdout+td.stderr)
    return {"rc":qu.returncode,"stdout":qu.stdout,"stderr":qu.stderr,"todesk_running":False,"utc":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--root",required=True);ap.add_argument("--owner",required=True);a=ap.parse_args()
    root=pathlib.Path(a.root);drive=root.drive.rstrip(":");assert drive in ("F","J"),"only verified SATA drives";root.mkdir(parents=True,exist_ok=False)
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(),0x4000)
    lock=pathlib.Path("<DATA>/.telltale_g1.lock");held=False;handle=None;active=[]
    try:
        pre=json.loads(ps("$ErrorActionPreference='Stop';[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false);"
          "$p=Get-CimInstance Win32_LogicalDisk -Filter \"DeviceID='"+drive+":'\"|Get-CimAssociatedInstance -Association Win32_LogicalDiskToPartition;"
          "$ix=@($p|Select-Object -ExpandProperty DiskIndex -Unique);if($ix.Count -ne 1){throw 'unknown target mapping'};"
          "$d=Get-CimInstance Win32_DiskDrive -Filter ('Index='+$ix[0]);"
          "$ph=@(Get-PhysicalDisk|Where-Object {$_.SerialNumber.Trim() -eq $d.SerialNumber.Trim()});"
          "if($ph.Count -ne 1 -or $ph[0].BusType -notin @('SATA','NVMe','ATA')){throw 'unsafe target bus'};"
          "if([IO.DriveInfo]::new('"+drive+"').AvailableFreeSpace -lt 35GB){throw 'space below35GB'};"
          "$u=(Get-CimInstance Win32_ComputerSystem).UserName;if($u -and ($u -notmatch '\\\\win$')){throw ('console user '+$u)};"
          "$py=@(Get-CimInstance Win32_Process|Where-Object {($_.Name -match '^(python|pythonw|hackrf_transfer).*') -and $_.ProcessId -ne "+str(os.getpid())+"});"
          "if($py.Count){throw ('other workload '+($py.ProcessId -join ','))};"
          "[PSCustomObject]@{bus=[string]$ph[0].BusType;disk=$ix[0];model=$d.Model;free=[IO.DriveInfo]::new('"+drive+"').AvailableFreeSpace;console_user=$u;other_workloads=$py.Count;cpu_load=(Get-CimInstance Win32_Processor|Measure-Object -Property LoadPercentage -Average).Average;remote_tools=@(Get-Process -ErrorAction SilentlyContinue|Where-Object {$_.Name -match '^(ToDesk|AweSun|GameViewer|SunloginClient|TeamViewer|AnyDesk|rustdesk)'}|ForEach-Object {$_.Name+':'+$_.Id})}|ConvertTo-Json -Compress"))
        pre["target_drive"]=drive;pre["concurrent_source_transfer"]=True
        pre["query_user"]=session_check()
        enum=subprocess.run(["C:/HackRF/bin/hackrf_info.exe"],capture_output=True,text=True,errors="replace",timeout=20)
        if enum.returncode or any(s not in enum.stdout for _,s,_ in RADIOS):raise RuntimeError("SDR enumeration failed")
        pre["hackrf_info"]=enum.stdout
        handle=open("F:/telltale_survey.lock","a+b");handle.seek(0)
        if not handle.read(1):handle.write(b"0");handle.flush()
        handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
        with lock.open("x",encoding="utf-8") as f:f.write(a.owner)
        held=True;emit({"state":"locked_ready","preflight":pre,"pid":os.getpid(),"root":str(root)})
        for line in sys.stdin:
            q=json.loads(line)
            if q["op"]=="stop":break
            if q["op"]=="capture":
                if active:raise RuntimeError("overlapping capture")
                ident=q["id"];secs=q["seconds"];n=int(secs*20000000)
                if not ident.isalnum() or secs not in (4,8):raise ValueError("capture bounds")
                sess=session_check()
                for short,serial,freq in RADIOS:
                    raw=root/(ident+"_"+short+".iq");log=root/(ident+"_"+short+".rf.log")
                    if raw.exists():raise RuntimeError("raw exists")
                    f=log.open("xb")
                    cmd=["C:/HackRF/bin/hackrf_transfer.exe","-d",serial,"-f",str(freq),"-s","20000000","-l","32","-g","20","-a","0","-n",str(n),"-r",str(raw)]
                    proc=subprocess.Popen(cmd,stdout=f,stderr=subprocess.STDOUT,creationflags=0x08000000)
                    active.append({"radio":short,"raw":raw,"log":log,"f":f,"proc":proc,"expected":2*n,"command":cmd,"spawn_ns":time.perf_counter_ns()})
                    if len(active)==1:time.sleep(0.25)
                until=time.monotonic()+5
                while True:
                    marks=[{"radio":x["radio"],"bytes":x["raw"].stat().st_size if x["raw"].exists() else 0,"running":x["proc"].poll() is None} for x in active]
                    if all(x["running"] and x["bytes"]>=16000000 for x in marks):break
                    if time.monotonic()>until or any(not x["running"] for x in marks):raise RuntimeError("capture did not become ready "+str(marks))
                    time.sleep(.03)
                emit({"state":"capturing","win_mono_ns":time.perf_counter_ns(),"marks":marks,"session_check":sess})
            elif q["op"]=="mark":
                emit({"state":"mark","win_mono_ns":time.perf_counter_ns(),"marks":[{"radio":x["radio"],"bytes":x["raw"].stat().st_size,"running":x["proc"].poll() is None} for x in active]})
            elif q["op"]=="finish":
                out=[]
                for x in active:
                    rc=x["proc"].wait(timeout=15);x["f"].close()
                    out.append({"radio":x["radio"],"raw":str(x["raw"]),"log":str(x["log"]),"rc":rc,"bytes":x["raw"].stat().st_size,"expected_bytes":x["expected"],"command":x["command"],"spawn_win_mono_ns":x["spawn_ns"]})
                active=[];emit({"state":"complete","win_mono_ns":time.perf_counter_ns(),"radios":out})
            else:raise ValueError("unknown op")
    finally:
        # These bounded receivers finish at 4/8 seconds; do not terminate unrelated processes.
        for x in active:
            try:x["proc"].wait(timeout=20)
            finally:x["f"].close()
        if held and lock.exists() and lock.read_text(encoding="utf-8")==a.owner:lock.unlink()
        if handle:
            try:handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
            finally:handle.close()
if __name__=="__main__":
    try:main()
    except Exception:
        emit({"state":"error","error":traceback.format_exc()});raise
