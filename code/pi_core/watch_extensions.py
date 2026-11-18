import json,pathlib,shlex,time,traceback
import paramiko
from bridge_utils import *
b=pathlib.Path(__file__).resolve().parent;lower_priority();cfg=json.loads((b/'EXTENSION_REMOTE.json').read_text());root=cfg['remote_root'];out=b/'analysis_extensions';out.mkdir(exist_ok=True);deadline=time.monotonic()+7000;ledger=json.loads((b/'extension_transfer/LEDGER.json').read_text())['records'];c=paramiko.SSHClient();c.load_system_host_keys();c.set_missing_host_key_policy(paramiko.RejectPolicy());c.connect(cfg['host'],port=cfg['port'],username=cfg['user'],key_filename=cfg['key'],timeout=15);sf=c.open_sftp()
try:
 sf.put(str(b/'early_extensions.py'),root+'/early_extensions.py')
 for stage in ('trace','order','burst'):
  rows=[x for x in ledger if x['stage']==stage]
  while True:
   missing=[]
   for row in rows:
    try:sf.stat(root+'/features/'+row['id']+'_930c.json')
    except OSError:missing.append(row['id'])
   print(json.dumps({'stage':stage,'missing_primary':len(missing),'utc':stamp()}),flush=True)
   if not missing:break
   if time.monotonic()>deadline:raise TimeoutError('early features incomplete')
   time.sleep(15)
  cmd='env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python '+shlex.quote(root+'/early_extensions.py')+' --root '+shlex.quote(root)+' --stage '+stage;ret=run(c,cmd,timeout=60,check=False);save(out/(stage.upper()+'_EARLY_COMMAND.json'),ret)
  if ret['rc']:raise RuntimeError(ret['stderr'])
  filename=stage.upper()+'_EARLY.json';sf.get(root+'/'+filename,str(out/filename));remote_sha=run(c,'sha256sum '+shlex.quote(root+'/'+filename))['stdout'].split()[0];assert sha(out/filename)==remote_sha;save(out/(stage.upper()+'_RECEIPT.json'),{'remote_path':root+'/'+filename,'sha256':remote_sha,'verified':True,'utc':stamp(),'evaluation_source_sha256':sha(b/'remote_extensions.py')});print(ret['stdout'],flush=True)
except Exception:(out/'EARLY_FAILURE.log').write_text(traceback.format_exc());raise
finally:sf.close();c.close()
