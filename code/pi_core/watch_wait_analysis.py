import json,pathlib,shlex,sys,time,traceback
B=pathlib.Path(__file__).resolve().parent;sys.path.insert(0,str(B/'burst_study'));from bridge_utils import *
import paramiko
cfg=json.loads((B/'EXTENSION_REMOTE.json').read_text());root=cfg['remote_root'];out=B/'analysis_extensions';lower_priority();c=paramiko.SSHClient();c.load_system_host_keys();c.set_missing_host_key_policy(paramiko.RejectPolicy());c.connect(cfg['host'],port=cfg['port'],username=cfg['user'],key_filename=cfg['key'],timeout=15);sf=c.open_sftp();deadline=time.monotonic()+6500
try:
 while True:
  ledger=json.loads(sf.open(root+'/LEDGER.json').read());rows=[x for x in ledger['records'] if x['stage']=='wait'];missing=32
  if len(rows)==32:
   missing=0
   for x in rows:
    try:sf.stat(root+'/features/'+x['id']+'_930c.json')
    except OSError:missing+=1
  save(out/'WAIT_ANALYSIS_STATUS.json',{'missing_primary':missing,'utc':stamp()})
  if not missing:break
  if time.monotonic()>deadline:raise TimeoutError('wait primary incomplete')
  time.sleep(15)
 ret=run(c,'env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 nice -n 10 python '+shlex.quote(root+'/remote_wait_eval.py')+' --root '+shlex.quote(root),timeout=60,check=False);save(out/'WAIT_EARLY_COMMAND.json',ret)
 if ret['rc']:raise RuntimeError(ret['stderr'])
 p=out/'WAIT_EARLY.json';sf.get(root+'/'+p.name,str(p));hs=run(c,'sha256sum '+shlex.quote(root+'/'+p.name))['stdout'].split()[0];assert sha(p)==hs;save(out/'WAIT_RECEIPT.json',{'remote_path':root+'/'+p.name,'sha256':hs,'verified':True,'utc':stamp(),'analysis_source_sha256':sha(B/'remote_wait_eval.py')});print(ret['stdout'],flush=True)
except Exception:(out/'WAIT_ANALYSIS_FAILURE.log').write_text(traceback.format_exc());raise
finally:sf.close();c.close()
