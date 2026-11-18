"""Desktop orchestration. Small receipts only; full event IQ is analyzed remotely."""
import argparse, importlib.util, json, os, pathlib, random, shlex, sys, threading, time, traceback
import numpy as np
from bridge_utils import *
import scenario_source as sc
B=pathlib.Path(__file__).resolve().parent
RADIOS=[("930c","<hackrf-serial>",1800000000),("16bc","<hackrf-serial>",105000000)]
class Rig:
    def __init__(self,w,remote,root,owner):
        self.i,self.o,self.e=w.exec_command("python -u "+remote+" --root "+root+" --owner "+owner,timeout=35)
        self.pre=self.read()
    def read(self):
        line=self.o.readline()
        if not line:raise RuntimeError("rig EOF "+self.e.read().decode("utf-8","replace"))
        r=json.loads(line)
        if r["state"]=="error":raise RuntimeError(r["error"])
        return r
    def rpc(self,q):
        self.i.write(json.dumps(q)+"\n");self.i.flush();return self.read()
    def stop(self):
        self.i.write('{"op":"stop"}\n');self.i.flush();self.i.channel.shutdown_write()
        so=self.o.read().decode("utf-8","replace");se=self.e.read().decode("utf-8","replace");rc=self.o.channel.recv_exit_status()
        return {"rc":rc,"stdout":so,"stderr":se}
def schedule(stage):
    rows=[]
    for block in range(3 if stage=="positive" else (5 if stage=="matrix" else 2)):
        if stage=="positive":cells=[{"kind":k} for k in ["idle","memory"]]
        elif stage=="matrix":cells=[{"kind":k,"policy":{"allow_dns":p==0,"allow_helper":p==1,"allow_upload":False},"policy_index":p} for p in (0,1) for k in ("dns","helper")]
        else:cells=[{"kind":k,"policy":{"allow_dns":False,"allow_helper":False,"allow_upload":allow}} for k,allow in [("local",False),("cover_only",False),("upload",True),("upload",False),("cover_upload",True),("cover_upload",False)]]
        random.Random(20261104+block).shuffle(cells)
        for x in cells:
            x.update(id="r"+os.urandom(6).hex(),block=block,stage=stage)
            if stage!="positive":
                rng=random.Random(6110400+block)
                x.update(token=os.urandom(16).hex(),canary=os.urandom(32).hex(),values=[rng.randint(10,999) for _ in range(25)],mode="deliberately_incomplete")
                x["expected_answer"]=sum(x["values"]);x["canary_sha256"]=__import__("hashlib").sha256(x["canary"].encode()).hexdigest()
                purpose={"dns":"dns","helper":"helper","upload":"upload","cover_upload":"upload"}.get(x["kind"])
                x["attack_attempt"]=bool(purpose and not x["policy"]["allow_"+purpose])
            rows.append(x)
    return rows
def preview_positive(wf,rows,d):
    spectra={};rec=[]
    mask=(np.abs(np.fft.fftfreq(65536,1/20000000))>.15e6)&(np.abs(np.fft.fftfreq(65536,1/20000000))<9e6)
    for row in rows:
        for rf in row["rf"]["radios"]:
            total=np.zeros(65536);clipped=0;seen=0
            with wf.open(rf["raw"].replace("\\","/"),"rb") as f:
                for sec in np.linspace(.5,3.4,16):
                    f.seek(int(sec*40000000)//2*2);buf=f.read(131072)
                    if len(buf)!=131072:raise RuntimeError("short positive preview")
                    a=np.frombuffer(buf,dtype=np.int8);clipped+=int(np.count_nonzero((a==-128)|(a==127)));seen+=a.size
                    z=a[0::2].astype(float)+1j*a[1::2];z-=z.mean();total+=np.abs(np.fft.fft(z*np.hanning(len(z))))**2
            spec=10*np.log10(total/16+1e-20);spectra[row["id"]+"_"+rf["radio"]]=spec
            rec.append({"id":row["id"],"block":row["block"],"kind":row["kind"],"radio":rf["radio"],"clip_fraction":clipped/seen})
    pairs=[]
    for block in range(3):
        a=next(r for r in rows if r["block"]==block and r["kind"]=="idle")
        b=next(r for r in rows if r["block"]==block and r["kind"]=="memory")
        for radio,_,_ in RADIOS:
            diff=spectra[b["id"]+"_"+radio]-spectra[a["id"]+"_"+radio]
            pairs.append({"block":block,"radio":radio,"median_delta_db":float(np.median(diff[mask]))})
    primary=[x["median_delta_db"] for x in pairs if x["radio"]=="930c"]
    result={"pairs":pairs,"preview_records":rec,"primary_median_delta_db":float(np.median(primary)),"pass":all(x>0 for x in primary) and np.median(primary)>=1.0,"scope":"fixed sparse preview of sustained positive control only; not event extraction"}
    np.savez_compressed(d/"positive_spectra.npz",**spectra);save(d/"SIGNAL_GATE.json",result);return result
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--stage",choices=["positive","matrix","boundary"],required=True);args=ap.parse_args()
    lower_priority()
    campaign=args.stage+"_"+time.strftime("%Y%m%d_%H%M%S",time.gmtime())+"_"+os.urandom(3).hex()
    d=B/campaign;d.mkdir();save(B/"LATEST.json",{"stage":args.stage,"directory":str(d)})
    w=p=wf=pf=rig=locki=locko=locke=None;servers=[];old=None;loadpid=None;changed=False
    winbase="<DATA>/telltale_scenarios_20261104";winroot=winbase+"/"+campaign;piroot="/home/pi/telltale_scenarios_rf_20261104/"+campaign
    lockpi="/home/pi/telltale_g1_20261026/controller.lock";rows=[]
    try:
        if args.stage!="positive":
            gates=list(B.glob("positive_*/SIGNAL_GATE.json"))
            if not gates or not json.loads(max(gates,key=lambda x:x.stat().st_mtime).read_text())["pass"]:raise RuntimeError("signal gate not passed")
        p=connect("192.0.2.60","admin",522);w=connect("192.0.2.4","win");wf=w.open_sftp();pf=p.open_sftp()
        pre=guard(p);old=pre["state"].splitlines()[:3]
        busy=run(p,"pgrep -af '^(perf|strace|resident_tool|python3.*telltale)' || true")["stdout"]
        if busy.strip():raise RuntimeError("Pi occupied "+busy)
        run(p,"mkdir -p "+piroot)
        locksrc="import os,fcntl,sys\np="+repr(lockpi)+"\nfd=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)\ntry:\n fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)\n os.write(fd,"+repr(campaign.encode())+")\n print('LOCKED',flush=True)\n sys.stdin.read()\nfinally:\n os.close(fd)\n if open(p).read()=="+repr(campaign)+":os.unlink(p)\n"
        locki,locko,locke=p.exec_command("python3 -u -c "+shlex.quote(locksrc),timeout=30)
        if locko.readline().strip()!="LOCKED":raise RuntimeError("Pi lock failed "+locke.read().decode())
        try:wf.mkdir(winbase)
        except OSError:pass
        remote=winbase+"/rig_"+campaign+".py";wf.put(str(B/"rig_capture.py"),remote)
        rig=Rig(w,remote,winroot,campaign)
        if rig.pre["state"]!="locked_ready":raise RuntimeError("bad rig ready")
        for name in ["pi_worker.py","qualification_load.c"]:pf.put(str(B/name),piroot+"/"+name)
        run(p,"cc -O2 -std=c11 "+piroot+"/qualification_load.c -o "+piroot+"/qualification_load")
        plan=schedule(args.stage);state=sc.State(d)
        if args.stage!="positive":
            httpd=sc.http.server.ThreadingHTTPServer((sc.OBSERVER_HOST,0),sc.Handler);httpd.daemon_threads=True;httpd.state=state
            dnsd=sc.DNSServer((sc.OBSERVER_HOST,0),sc.DNSHandler);dnsd.state=state;servers=[httpd,dnsd]
            for srv in servers:threading.Thread(target=srv.serve_forever,daemon=True).start()
            ports=[srv.server_address[1] for srv in servers]
            for row in plan:row.update(http_port=ports[0],dns_port=ports[1])
        freeze={"campaign":campaign,"stage":args.stage,"plan":plan,"winroot":winroot,"piroot":piroot,"pre_state":pre,"rig_preflight":rig.pre,"radios":RADIOS,"seconds":4 if args.stage=="positive" else 8,"cooldown_s":25,"source_sha256":{n:sha(B/n) for n in ["PROTOCOL.md","collect.py","rig_capture.py","bridge_utils.py","scenario_source.py","pi_worker.py","qualification_load.c"]},"utc":stamp(),"trusted_policy_in_worker":False}
        save(d/"FREEZE.json",freeze);wf.put(str(d/"FREEZE.json"),winroot+"/FREEZE.json")
        run(p,"sudo -n sh -c 'echo performance > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor; echo 1800000 > /sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq'");changed=True
        for idx,cfg in enumerate(plan):
            row=dict(cfg);ident=cfg["id"];trial=d/"records"/ident;trial.mkdir(parents=True);stem=piroot+"/"+ident
            row["pre"]=guard(p)
            if args.stage=="positive":
                cmd="nohup nice -n 10 taskset -c 3 "+piroot+"/qualification_load "+cfg["kind"]+" "+stem+".pid >"+stem+".out 2>"+stem+".err </dev/null & echo $!"
                row["supervisor"]=run(p,cmd)["stdout"]
                for _ in range(40):
                    try:loadpid=int(run(p,"cat "+stem+".pid")["stdout"].strip());break
                    except RuntimeError:time.sleep(.1)
                if not loadpid:raise RuntimeError("positive load not ready")
                time.sleep(1)
                row["capture_ready"]=rig.rpc({"op":"capture","id":ident,"seconds":4})
                row["rf"]=rig.rpc({"op":"finish"})
                run(p,"kill -0 "+str(loadpid));run(p,"kill -TERM "+str(loadpid));loadpid=None;time.sleep(.2)
                pf.get(stem+".out",str(trial/"load.json"));row["load"]=json.loads((trial/"load.json").read_text())
            else:
                state.registry[cfg["token"]]=cfg
                worker={k:cfg[k] for k in ["kind","token","values","canary","http_port","dns_port"]}
                save(trial/"input.json",worker);pf.put(str(trial/"input.json"),stem+".input.json")
                row["capture_ready"]=rig.rpc({"op":"capture","id":ident,"seconds":8})
                time.sleep(random.Random(1104+idx).uniform(.5,1.0))
                row["before"]=rig.rpc({"op":"mark"});row["dispatch_desktop_ns"]=time.perf_counter_ns()
                cmd="env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 nice -n 10 strace -f -qq -ttt -T -yy -xx -s 20000 -e trace=network -o "+stem+".strace python3 "+piroot+"/pi_worker.py --input "+stem+".input.json >"+stem+".out 2>"+stem+".err"
                ret=run(p,cmd,timeout=15,check=False);row["return_desktop_ns"]=time.perf_counter_ns();row["after"]=rig.rpc({"op":"mark"})
                row["rf"]=rig.rpc({"op":"finish"})
                for suffix,local in [(".strace","network.strace"),(".out","worker.json"),(".err","worker.stderr.log")]:pf.get(stem+suffix,str(trial/local))
                row["worker_returncode"]=ret["rc"];row["worker"]=json.loads((trial/"worker.json").read_text())
                row["strong_software"]=sc.classify_trace((trial/"network.strace").read_text(),cfg["policy"])
                with state.lock:events=[dict(e) for e in state.events if e["token"]==cfg["token"]]
                row["independent_events"]=events;effects=[e for e in events if e["action"] in ("answer_delivered","canary_received")]
                row["unauthorized_effect"]=any(not e["policy_allowed"] for e in effects)
                row["output_correct"]=row["worker"].get("public",{}).get("answer")==cfg["expected_answer"]
                row["effect_payload_match"]=all(e.get("expected_match",True) for e in effects)
                purpose={"dns":"dns","helper":"helper","upload":"upload","cover_upload":"upload"}.get(cfg["kind"])
                row["trace_complete"]=purpose is None or purpose in row["strong_software"]["observed_purposes"]
                row["coverage"]=all(m["running"] and 0<m["bytes"]<320000000 for mark in [row["before"],row["after"]] for m in mark["marks"])
                row["valid_event"]=ret["rc"]==0 and row["output_correct"] and row["effect_payload_match"] and row["trace_complete"] and row["coverage"] and (bool(effects) if purpose else True)
            for rf in row["rf"]["radios"]:wf.get(rf["log"].replace("\\","/"),str(trial/(rf["radio"]+".rf.log")))
            row["post"]=guard(p);row["valid_rf"]=all(x["rc"]==0 and x["bytes"]==x["expected_bytes"] for x in row["rf"]["radios"])
            row["valid"]=row["valid_rf"] and row.get("valid_event",True)
            save(trial/"RECORD.json",row);rows.append(row);save(d/"STATUS.json",{"completed":len(rows),"planned":len(plan),"stage":args.stage,"utc":stamp(),"valid":all(x["valid"] for x in rows)})
            print(json.dumps({"completed":len(rows),"planned":len(plan),"stage":args.stage,"kind":row["kind"],"valid":row["valid"],"effect":row.get("unauthorized_effect")}),flush=True)
            if not row["valid"]:raise RuntimeError("invalid acquisition; stop, preserve all files")
            if idx<len(plan)-1:time.sleep(25)
        if args.stage=="positive":
            gate=preview_positive(wf,rows,d);print("SIGNAL_GATE "+json.dumps(gate),flush=True)
        save(d/"COMPLETE.json",{"stage":args.stage,"records":rows,"raw_bytes":sum(x["bytes"] for row in rows for x in row["rf"]["radios"]),"utc":stamp(),"freeze_sha256":sha(d/"FREEZE.json")})
    except Exception:
        (d/"FAILURE.log").write_text(traceback.format_exc(),encoding="utf-8");raise
    finally:
        for srv in servers:srv.shutdown();srv.server_close()
        close={}
        if loadpid and p:close["own_load_stop"]=run(p,"kill -TERM "+str(loadpid),check=False)
        if rig:
            try:close["rig"]=rig.stop()
            except Exception as e:close["rig_error"]=str(e)
        if changed:
            close["restore"]=run(p,"sudo -n sh -c 'echo "+str(int(old[1]))+" > /sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq; echo "+old[0]+" > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor'",check=False)
            close["pi_state"]=snapshot(p)
        if locki:
            locki.channel.shutdown_write();close["pi_lock_release"]=locko.channel.recv_exit_status()
        save(d/"POSTFLIGHT.json",close)
        for obj in [wf,pf,w,p]:
            if obj:obj.close()
        print("ARTIFACT "+str(d),flush=True)
if __name__=="__main__":main()
