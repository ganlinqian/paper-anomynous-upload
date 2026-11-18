"""IO relay through project desktop. Native scp, complete files only."""
import json,pathlib,subprocess,time,traceback,os
import paramiko
from bridge_utils import *
B=pathlib.Path(__file__).resolve().parent;lower_priority()
cfg=json.loads((B/"REMOTE.json").read_text());root=cfg["remote_root"];out=B/"transfer";out.mkdir(exist_ok=False)
files=[];records=[];stages=[]
for stage,n in [("positive",6),("matrix",20),("boundary",12)]:
    candidates=[p for p in B.glob(stage+"_*/COMPLETE.json") if len(json.loads(p.read_text())["records"])==n]
    if not candidates:raise RuntimeError("missing complete stage "+stage)
    p=max(candidates,key=lambda p:p.stat().st_mtime);comp=json.loads(p.read_text());assert all(x["valid"] for x in comp["records"])
    stages.append({"stage":stage,"directory":str(p.parent),"complete_sha256":sha(p),"freeze_sha256":sha(p.parent/"FREEZE.json")})
    for row in comp["records"]:
        records.append(row)
        for rf in row["rf"]["radios"]:
            filename=row["id"]+"_"+rf["radio"]+".iq"
            files.append({"id":row["id"],"stage":stage,"radio":rf["radio"],"filename":filename,"source_raw":rf["raw"].replace("\\","/"),"expected_bytes":rf["bytes"]})
save(out/"MANIFEST.json",{"files":files,"stages":stages});save(out/"LEDGER.json",{"records":records,"stages":stages})
w=connect("192.0.2.4","win");wf=w.open_sftp()
c=paramiko.SSHClient();c.load_system_host_keys();c.set_missing_host_key_policy(paramiko.RejectPolicy());c.connect(cfg["host"],port=cfg["port"],username=cfg["user"],key_filename=cfg["key"],timeout=15);sf=c.open_sftp()
try:
    p="<DATA>/telltale_scenarios_20261104/transfer_"+time.strftime("%Y%m%d_%H%M%S",time.gmtime());wf.mkdir(p)
    wf.put(str(B/"source_receipt.py"),p+"/source_receipt.py");wf.put(str(out/"MANIFEST.json"),p+"/MANIFEST.json")
    hashing=run(w,"python "+p+"/source_receipt.py "+p+"/MANIFEST.json",timeout=450)
    save(out/"SOURCE_HASH_COMMAND.json",hashing);wf.get(p+"/SOURCE_RECEIPTS.json",str(out/"SOURCE_RECEIPTS.json"))
    sf.put(str(out/"LEDGER.json"),root+"/LEDGER.json");sf.put(str(out/"MANIFEST.json"),root+"/MANIFEST.json");sf.put(str(out/"SOURCE_RECEIPTS.json"),root+"/SOURCE_RECEIPTS.json")
    save(out/"QUEUE.json",{"files":files});sf.put(str(out/"QUEUE.json"),root+"/QUEUE.json.pending");sf.posix_rename(root+"/QUEUE.json.pending",root+"/QUEUE.json")
    start=time.monotonic();done=[]
    with (out/"scp.log").open("wb") as log:
        for row in files:
            src="claw-rig-9f835:"+row["source_raw"];dst="claw-cpu-9f835:"+root+"/raw/"+row["filename"]+".partial"
            command=["scp","-q","-3","-F",str(B/"transfer_ssh_config"),src,dst]
            ret=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=240)
            if ret.returncode:raise RuntimeError("scp failed "+row["filename"]+" rc="+str(ret.returncode))
            remote=root+"/raw/"+row["filename"]
            if sf.stat(remote+".partial").st_size!=row["expected_bytes"]:raise RuntimeError("destination size mismatch")
            sf.rename(remote+".partial",remote);done.append(row["filename"])
            save(out/"STATUS.json",{"completed":len(done),"planned":len(files),"bytes":sum(x["expected_bytes"] for x in files[:len(done)]),"elapsed_s":time.monotonic()-start})
            print(json.dumps({"completed":len(done),"planned":len(files),"filename":row["filename"],"elapsed_s":time.monotonic()-start}),flush=True)
    marker={"expected_files":len(files),"bytes":sum(x["expected_bytes"] for x in files),"utc":stamp()}
    save(out/"UPLOAD_COMPLETE.json",marker);sf.put(str(out/"UPLOAD_COMPLETE.json"),root+"/UPLOAD_COMPLETE.json")
    print(json.dumps(marker),flush=True)
except Exception:
    (out/"FAILURE.log").write_text(traceback.format_exc());raise
finally:wf.close();w.close();sf.close();c.close()
