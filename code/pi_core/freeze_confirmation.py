import json,pathlib,shlex,sys
B=pathlib.Path(__file__).resolve().parent;sys.path.insert(0,str(B/'burst_study'));from bridge_utils import *
import paramiko
cfg=json.loads((B/'EXTENSION_REMOTE.json').read_text());root=cfg['remote_root'];c=paramiko.SSHClient();c.load_system_host_keys();c.set_missing_host_key_policy(paramiko.RejectPolicy());c.connect(cfg['host'],port=cfg['port'],username=cfg['user'],key_filename=cfg['key'],timeout=15);s=c.open_sftp()
try:
 for n in ('export_confirmation_models.py','remote_wait_eval.py'):s.put(str(B/n),root+'/'+n)
 ret=run(c,'env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 nice -n 10 python '+shlex.quote(root+'/export_confirmation_models.py')+' --root '+shlex.quote(root),timeout=60);save(B/'analysis_extensions/CONFIRMATION_FREEZE_COMMAND.json',ret);p=B/'analysis_extensions/CONFIRMATION_MODELS.json';s.get(root+'/'+p.name,str(p));remote=run(c,'sha256sum '+shlex.quote(root+'/'+p.name))['stdout'].split()[0];assert sha(p)==remote;save(p.with_name('CONFIRMATION_MODELS_RECEIPT.json'),{'sha256':remote,'verified':True,'utc':stamp(),'remote_path':root+'/'+p.name});print(ret['stdout'])
 validation=pathlib.Path(json.loads((B/'io_wait_study/LATEST.json').read_text())['directory'])/'WAIT_COLLECTION_VALIDATION.json';assert json.loads(validation.read_text())['pass'];s.put(str(validation),root+'/WAIT_COLLECTION_VALIDATION.json')
finally:s.close();c.close()
