import json,pathlib,shlex,sys,paramiko
B=pathlib.Path(__file__).resolve().parent;sys.path.insert(0,str(B/'burst_study'));from bridge_utils import *
cfg=json.loads((B/'EXTENSION_REMOTE.json').read_text());root=cfg['remote_root'];c=paramiko.SSHClient();c.load_system_host_keys();c.set_missing_host_key_policy(paramiko.RejectPolicy());c.connect(cfg['host'],port=cfg['port'],username=cfg['user'],key_filename=cfg['key'],timeout=15);s=c.open_sftp()
try:
 s.put(str(B/'explore_burst_scores.py'),root+'/explore_burst_scores.py');ret=run(c,'env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 nice -n 10 python '+shlex.quote(root+'/explore_burst_scores.py')+' --root '+shlex.quote(root),timeout=60,check=False);save(B/'analysis_extensions/BURST_EXPLORATORY_COMMAND.json',ret)
 if ret['rc']:raise RuntimeError(ret['stderr'])
 p=B/'analysis_extensions/BURST_EXPLORATORY_FREEZE.json';s.get(root+'/'+p.name,str(p));hs=run(c,'sha256sum '+shlex.quote(root+'/'+p.name))['stdout'].split()[0];assert sha(p)==hs;save(B/'analysis_extensions/BURST_EXPLORATORY_RECEIPT.json',{'sha256':hs,'verified':True,'utc':stamp()});print(ret['stdout'])
finally:s.close();c.close()
