import ctypes,json,pathlib,shlex,time,traceback
import paramiko
from bridge_utils import *
b=pathlib.Path(__file__).resolve().parent;lower_priority();cfg=json.loads((b/'REMOTE.json').read_text());root=cfg['remote_root'];out=b/'analysis';out.mkdir(exist_ok=True);deadline=time.monotonic()+5400
c=paramiko.SSHClient();c.load_system_host_keys();c.set_missing_host_key_policy(paramiko.RejectPolicy());c.connect(cfg['host'],port=cfg['port'],username=cfg['user'],key_filename=cfg['key'],timeout=15);sf=c.open_sftp()
try:
 sf.put(str(b/'matrix_early.py'),root+'/matrix_early.py')
 while not (b/'transfer/LEDGER.json').exists():
  if time.monotonic()>deadline:raise TimeoutError('no ledger')
  time.sleep(10)
 matrix=[x for x in json.loads((b/'transfer/LEDGER.json').read_text())['records'] if x['stage']=='matrix']
 while True:
  missing=[]
  for x in matrix:
   try:sf.stat(root+'/features/'+x['id']+'_930c.json')
   except OSError:missing.append(x['id'])
  print(json.dumps({'remaining_primary_matrix_features':len(missing),'utc':stamp()}),flush=True)
  if not missing:break
  if time.monotonic()>deadline:raise TimeoutError('matrix features not ready')
  time.sleep(20)
 cmd='env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python '+shlex.quote(root+'/matrix_early.py')+' --root '+shlex.quote(root)
 ret=run(c,cmd,timeout=60,check=False);save(out/'MATRIX_EARLY_COMMAND.json',ret)
 if ret['rc']:raise RuntimeError(ret['stderr'])
 sf.get(root+'/MATRIX_EARLY.json',str(out/'MATRIX_EARLY.json'));save(out/'MATRIX_EARLY_RECEIPT.json',{'local_sha256':sha(out/'MATRIX_EARLY.json'),'remote_path':root+'/MATRIX_EARLY.json','estimator_source_sha256':sha(b/'remote_evaluate.py'),'runner_source_sha256':sha(b/'matrix_early.py'),'utc':stamp()});print(ret['stdout'],flush=True)
except Exception:(out/'MATRIX_EARLY_FAILURE.log').write_text(traceback.format_exc());raise
finally:sf.close();c.close()
