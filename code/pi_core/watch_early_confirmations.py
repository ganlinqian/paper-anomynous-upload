"""Fetch complete family results as soon as primary-channel features are available."""
import hashlib,json,pathlib,shlex,subprocess,sys,time,traceback,paramiko
B=pathlib.Path(__file__).resolve().parent;D=B/'confirmation_processing_20261105';O=B/'analysis_extensions/early_confirm_20261105';O.mkdir(exist_ok=False);deadline=time.monotonic()+12600;c=sf=None;last=None
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def stamp():return time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
def state(phase,**kw):
 global last
 x={'phase':phase,'utc':stamp(),**kw};save(O/'STATUS.json',x)
 if phase!=last:print(json.dumps(x),flush=True);last=phase
def wait(fn,phase):
 while True:
  if (D/'FAILURE.log').exists():raise RuntimeError('main confirmation controller stopped; inspect preserved failure')
  z=fn()
  if z:return z
  if time.monotonic()>deadline:raise TimeoutError(phase)
  state(phase);time.sleep(20)
def config():
 try:
  z=json.loads((D/'REMOTE_CONFIG.json').read_text())
  return z if 'remote_root' in z else None
 except (FileNotFoundError,json.JSONDecodeError):return None
def remote(cmd):
 i,o,e=c.exec_command(cmd,timeout=90);a=o.read().decode();b=e.read().decode();rc=o.channel.recv_exit_status();return {'returncode':rc,'stdout':a,'stderr':b}
try:
 cfg=wait(config,'waiting_actual_CPU_allocation')
 c=paramiko.SSHClient();c.load_system_host_keys();c.set_missing_host_key_policy(paramiko.RejectPolicy());c.connect(cfg['host'],port=cfg['port'],username=cfg['user'],key_filename=cfg['key'],timeout=15);c.get_transport().set_keepalive(20);sf=c.open_sftp();root=cfg['remote_root']
 def queue_ready():
  try:return sf.stat(root+'/QUEUE.json').st_size>100
  except FileNotFoundError:return False
 wait(queue_ready,'waiting_remote_queue')
 z=subprocess.run([sys.executable,str(B/'validate_c08_only.py')],capture_output=True,text=True,encoding='utf-8',errors='replace');save(O/'VALIDATION_COMMAND.json',{'rc':z.returncode,'stdout':z.stdout,'stderr':z.stderr})
 if z.returncode:raise RuntimeError('C08 standalone validation failed')
 for name in ('remote_early_confirmation.py','C08_COLLECTION_VALIDATION.json','CONFIRMATION_PARTIAL_COLLECTION_VALIDATION.json'):sf.put(str(B/name),root+'/'+name)
 for stage,family in [('confirmation','trace'),('confirmation','order'),('confirmation_partial','trace'),('confirmation_partial','order')]:
  rr=[x for x in json.loads(sf.open(root+'/LEDGER.json').read())['records'] if x['stage']==stage and x['family']==family];assert len(rr)==(40 if stage=='confirmation' else 21)
  def ready():
   for x in rr:
    try:
     if sf.stat(root+'/features/'+x['id']+'_930c.json').st_size<100:return False
    except FileNotFoundError:return False
   return True
  wait(ready,'waiting_primary_features_'+stage+'_'+family)
  state('evaluating_'+stage+'_'+family);cmd='env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 nice -n 19 python '+shlex.quote(root+'/remote_early_confirmation.py')+' --root '+shlex.quote(root)+' --stage '+stage+' --family '+family;z=remote(cmd);save(O/(stage+'_'+family+'_COMMAND.json'),z)
  if z['returncode']:raise RuntimeError(z['stderr'])
  name='EARLY_'+stage.upper()+'_'+family.upper()+'.json';local=O/name;sf.get(root+'/'+name,str(local));digest=remote('sha256sum '+shlex.quote(root+'/'+name))
  assert digest['returncode']==0 and hashlib.sha256(local.read_bytes()).hexdigest()==digest['stdout'].split()[0]
  save(O/(name+'.RECEIPT.json'),{'sha256':digest['stdout'].split()[0],'bytes':local.stat().st_size,'utc':stamp(),'primary_raw_files':len(rr),'diagnostic_channel_not_checked':True,'models_fixed':True})
  state('received_'+stage+'_'+family,file=str(local),n=len(rr));print(json.dumps({'result':name,'summary':z['stdout']}),flush=True)
 state('complete',families=4)
except Exception:(O/'FAILURE.log').write_text(traceback.format_exc(),encoding='utf-8');raise
finally:
 if sf:sf.close()
 if c:c.close()
