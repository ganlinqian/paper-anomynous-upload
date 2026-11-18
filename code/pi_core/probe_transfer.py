import json,pathlib,shlex,subprocess,time
import paramiko
from bridge_utils import *
b=pathlib.Path(__file__).resolve().parent;lower_priority();cfg=json.loads((b/'REMOTE.json').read_text());source=json.loads((b/'transfer/SOURCE_RECEIPTS.json').read_text())['files'][0];remote=cfg['remote_root']+'/speed_probe_large_window.iq';cmd=['scp','-q','-3','-X','nrequests=256','-X','buffer=131072','-o','Compression=no','-F',str(b/'transfer_ssh_config'),'claw-rig-9f835:'+source['source_raw'].replace('\\','/'),'claw-cpu-9f835:'+remote];t=time.monotonic()
with (b/'transfer/SPEED_PROBE.log').open('wb') as log:ret=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,timeout=110)
elapsed=time.monotonic()-t;result={'command':cmd,'returncode':ret.returncode,'seconds':elapsed,'bytes':source['bytes'],'MBps':source['bytes']/elapsed/1e6,'utc':stamp(),'concurrent_with_default_transfer':True}
if ret.returncode==0:
 c=paramiko.SSHClient();c.load_system_host_keys();c.set_missing_host_key_policy(paramiko.RejectPolicy());c.connect(cfg['host'],port=cfg['port'],username=cfg['user'],key_filename=cfg['key'],timeout=15)
 try:
  receipt=run(c,'sha256sum '+shlex.quote(remote));result['sha256_match']=receipt['stdout'].split()[0]==source['sha256'];assert result['sha256_match'];run(c,'rm -- '+shlex.quote(remote))
 finally:c.close()
save(b/'transfer/SPEED_PROBE.json',result);print(json.dumps(result));raise SystemExit(ret.returncode)
