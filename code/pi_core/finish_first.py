import json,pathlib,shlex,time,traceback
import paramiko
from bridge_utils import *
b=pathlib.Path(__file__).resolve().parent;lower_priority();cfg=json.loads((b/'REMOTE.json').read_text());root=cfg['remote_root'];out=b/'analysis';out.mkdir(exist_ok=True);dest=out/'all_features';dest.mkdir(exist_ok=True);deadline=time.monotonic()+3600
c=paramiko.SSHClient();c.load_system_host_keys();c.set_missing_host_key_policy(paramiko.RejectPolicy());c.connect(cfg['host'],port=cfg['port'],username=cfg['user'],key_filename=cfg['key'],timeout=15);sf=c.open_sftp()
try:
 while True:
  try:sf.stat(root+'/EXTRACTION_COMPLETE.json');break
  except OSError:pass
  try:sf.stat(root+'/EXTRACTION_FAILURE.log');raise RuntimeError('remote extraction failed')
  except FileNotFoundError:pass
  if time.monotonic()>deadline:raise TimeoutError('first extraction incomplete')
  time.sleep(10)
 ret=run(c,'env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python '+shlex.quote(root+'/remote_evaluate.py')+' --root '+shlex.quote(root),timeout=60,check=False);save(out/'FULL_EVALUATION_COMMAND.json',ret)
 if ret['rc']:raise RuntimeError(ret['stderr'])
 sf.get(root+'/EXTRACTION_COMPLETE.json',str(out/'EXTRACTION_COMPLETE.json'));sf.get(root+'/EVALUATION.json',str(out/'EVALUATION.json'));receipts=json.loads((out/'EXTRACTION_COMPLETE.json').read_text())['receipts'];source={x['filename']:x for x in json.loads((b/'transfer/SOURCE_RECEIPTS.json').read_text())['files']};assert len(receipts)==len(source)==76
 for x in receipts:assert x['raw_sha256']==source[x['filename']]['sha256'] and x['raw_bytes']==source[x['filename']]['bytes'] and x['full_contiguous']
 names=['EVALUATION.json','EXTRACTION_COMPLETE.json']+['features/'+x['id']+'_'+x['radio']+suffix for x in receipts for suffix in ('.npz','.json')];code='import hashlib,json,pathlib;r=pathlib.Path('+repr(root)+');names='+repr(names)+';print(json.dumps({n:hashlib.sha256((r/n).read_bytes()).hexdigest() for n in names}))';hashes=json.loads(run(c,'python -c '+shlex.quote(code),timeout=30)['stdout']);total=0
 for name in names:
  target=out/pathlib.PurePosixPath(name).name if '/' not in name else dest/pathlib.PurePosixPath(name).name
  if not target.exists():sf.get(root+'/'+name,str(target))
  assert sha(target)==hashes[name],name;total+=target.stat().st_size
 save(out/'FULL_RECEIPTS.json',{'all_raw_hashes_match':True,'raw_files':76,'full_contiguous':True,'small_result_files':len(names),'small_result_bytes':total,'small_result_sha256':hashes,'utc':stamp()});result=json.loads((out/'EVALUATION.json').read_text());print(json.dumps({'verified_raw':76,'returned_files':len(names),'task_plus_rf':result['task_plus_rf'],'strong_content_audit':result['strong_content_audit'],'boundary_records':len(result['boundary'])}))
except Exception:(out/'FULL_FINISH_FAILURE.log').write_text(traceback.format_exc());raise
finally:sf.close();c.close()
