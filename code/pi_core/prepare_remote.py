import json,pathlib,shlex
import paramiko
from bridge_utils import *
B=pathlib.Path(__file__).resolve().parent
cfg=json.loads((B/"REMOTE.json").read_text());r=cfg["remote_root"]
c=paramiko.SSHClient();c.load_system_host_keys();c.set_missing_host_key_policy(paramiko.RejectPolicy())
c.connect(cfg["host"],port=cfg["port"],username=cfg["user"],key_filename=cfg["key"],timeout=15)
try:
    check=run(c,"hostname; mkdir -p "+r+"/raw "+r+"/features")
    if cfg["hostname_verified"] not in check["stdout"]:raise RuntimeError("node identity mismatch")
    sf=c.open_sftp()
    for name in ["remote_extract.py","remote_evaluate.py","PROTOCOL.md","ANALYSIS_FREEZE.md"]:sf.put(str(B/name),r+"/"+name)
    save(B/"remote_initial_queue.json",{"files":[]});sf.put(str(B/"remote_initial_queue.json"),r+"/QUEUE.json")
    command="nohup env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python "+r+"/remote_extract.py --root "+r+" --workers 4 >"+r+"/extract.stdout.log 2>"+r+"/extract.stderr.log </dev/null & echo $!"
    out=run(c,command);pid=int(out["stdout"].strip());save(B/"REMOTE_LAUNCH.json",{"pid":pid,"command":command,"remote":cfg,"utc":stamp()})
    print(json.dumps({"pid":pid,"root":r,"node":cfg["node"]}));sf.close()
finally:c.close()
