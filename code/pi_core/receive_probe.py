import json, pathlib, os, time, traceback
from bridge_utils import *
from collect import Rig
B=pathlib.Path(__file__).resolve().parent
campaign="rxprobe_"+time.strftime("%Y%m%d_%H%M%S",time.gmtime())
d=B/campaign;d.mkdir();w=connect("192.0.2.4","win");sf=w.open_sftp();rig=None
root="<DATA>/telltale_scenarios_20261104/"+campaign
try:
    src="<DATA>/telltale_scenarios_20261104/rig_"+campaign+".py";sf.put(str(B/"rig_capture.py"),src)
    rig=Rig(w,src,root,campaign)
    ready=rig.rpc({"op":"capture","id":"r"+os.urandom(6).hex(),"seconds":4})
    out=rig.rpc({"op":"finish"});passed=all(x["rc"]==0 and x["bytes"]==160000000 for x in out["radios"])
    for x in out["radios"]:sf.get(x["log"].replace("\\","/"),str(d/(x["radio"]+".rf.log")))
    save(d/"PROBE.json",{"ready":ready,"result":out,"pass":passed,"purpose":"engineering receive diagnostic; not a task/attack sample"})
    print(json.dumps({"pass":passed,"directory":str(d)}))
    if not passed:raise RuntimeError("receive probe failed")
finally:
    if rig:
        try:save(d/"POSTFLIGHT.json",rig.stop())
        except Exception as e:save(d/"POSTFLIGHT.json",{"error":str(e)})
    sf.close();w.close()
