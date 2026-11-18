import json,pathlib,sys,paramiko
B=pathlib.Path(__file__).resolve().parent;sys.path.insert(0,str(B/'burst_study'));from bridge_utils import *
cfg=json.loads((B/'EXTENSION_REMOTE.json').read_text());c=paramiko.SSHClient();c.load_system_host_keys();c.set_missing_host_key_policy(paramiko.RejectPolicy());c.connect(cfg['host'],port=cfg['port'],username=cfg['user'],key_filename=cfg['key'],timeout=15)
try:
 root=cfg['remote_root'];ret=run(c,"pgrep -af '[p]ython -u remote_resume_extract.py'; tail -n 5 "+root+"/resume_extract_20261105.log; cat "+root+"/RESUME_CACHE_VALIDATION.json",timeout=15,check=False);save(B/'RESUME_CPU_CHECK.json',ret);print(json.dumps(ret))
finally:c.close()
