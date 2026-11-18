"""Resume only C13/C15 ordinary data pipelines after the inspected 07:45 connection failure."""
import argparse,os,tarfile,traceback,hashlib
from untraced_pipeline_utils import UntracedPipe
from sustained_pipeline_utils import SustainedPipe
from confirmation_pipeline_utils import *
read=lambda p:json.loads(pathlib.Path(p).read_text(encoding='utf-8-sig'))
ap=argparse.ArgumentParser();ap.add_argument('--dataset',choices=['C13','C15'],required=True);a=ap.parse_args()
Base=UntracedPipe if a.dataset=='C13' else SustainedPipe
class RecoveryPipe(Base):
 def __init__(self):
  lower_priority();self.out=B/('untraced_processing_20261105' if a.dataset=='C13' else 'sustained_processing_20261105')
  self.deadline=time.monotonic()+10800;self.c=self.sf=self.w=self.wf=None;self.cfg=None;self.root=None;self.reconnects=0
  save(self.out/'RESUME_CONTROLLER_PID.json',{'pid':os.getpid(),'script':str(pathlib.Path(__file__).resolve()),'dataset':a.dataset,'utc':stamp()})
 def reconnect(self):
  for obj in [self.sf,self.c]:
   if obj:
    try:obj.close()
    except Exception:pass
  self.c=paramiko.SSHClient();self.c.load_system_host_keys();self.c.set_missing_host_key_policy(paramiko.RejectPolicy());self.c.connect(self.cfg['host'],port=self.cfg['port'],username=self.cfg['user'],key_filename=self.cfg['key'],timeout=15)
  self.c.get_transport().set_keepalive(20);self.sf=self.c.open_sftp();self.sf.get_channel().settimeout(60)
 def step(self,fn,label):
  try:return fn(self.sf)
  except (EOFError,paramiko.SSHException,ConnectionResetError,TimeoutError) as e:
   self.reconnects+=1;save(self.out/('RECOVERY_RECONNECT_'+str(self.reconnects)+'.json'),{'utc':stamp(),'operation':label,'error':str(e)})
   self.reconnect();return fn(self.sf)
 def atomic(self,name,data):
  p=self.out/('REMOTE_'+name);save(p,data)
  def put(sf):sf.put(str(p),self.root+'/'+name+'.pending');sf.posix_rename(self.root+'/'+name+'.pending',self.root+'/'+name)
  self.step(put,'atomic '+name)
 def transfer(self,files,label):
  skipped=0
  for idx,row in enumerate(files):
   target=self.root+'/raw/'+row['filename']
   def present(sf):
    try:return sf.stat(target).st_size
    except FileNotFoundError:return None
   size=self.step(present,'raw size '+row['filename'])
   if size is not None:
    assert size==row['expected_bytes'];skipped+=1;self.state('transfer_F',completed=idx+1,planned=len(files),reused_complete_raw=skipped);continue
   for attempt in [1,2,3]:
    partial=target+'.recovery_'+str(attempt)+'.partial'
    cmd=['scp','-q','-3','-X','nrequests=256','-X','buffer=131072','-o','Compression=no','-o','ConnectTimeout=12','-o','ServerAliveInterval=20','-o','ServerAliveCountMax=2','-F',str(self.out/'ssh_config'),'claw-confirm-rig:'+row['source_raw'],'claw-confirm-cpu:'+partial]
    log=self.out/'F'/('recovery_'+row['filename']+'_attempt'+str(attempt)+'.log')
    try:
     with log.open('xb') as f:z=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=240)
     rc=z.returncode
    except subprocess.TimeoutExpired:rc=124
    save(log.with_suffix('.json'),{'utc':stamp(),'returncode':rc,'attempt':attempt,'filename':row['filename'],'log':str(log)})
    if rc==0:
     def promote(sf):
      try:part=sf.stat(partial)
      except FileNotFoundError:assert sf.stat(target).st_size==row['expected_bytes'];return
      assert part.st_size==row['expected_bytes'];sf.posix_rename(partial,target)
     self.step(promote,'promote '+row['filename']);break
    if attempt==3:raise RuntimeError('three bounded transfer attempts failed for '+row['filename'])
    time.sleep(4)
   self.state('transfer_F',completed=idx+1,planned=len(files),reused_complete_raw=skipped)
p=RecoveryPipe(); expected_failure={'C13':'f870e2a66ad441e13df4f5b503d2c077c8ef58ac669190425d92c5aa7102ab95','C15':'85ad54442e0bb4a51ba3b7be57ea4113e530f50ade0340a30e4db6d09ab1344b'}[a.dataset]
try:
 assert sha(p.out/'FAILURE.log')==expected_failure and read(p.out/'STATUS.json')['phase']=='failed'
 study='untraced_wait_study' if a.dataset=='C13' else 'sustained_burst_study';stage='untraced_wait_confirmation' if a.dataset=='C13' else 'sustained_burst_confirmation';N=64 if a.dataset=='C13' else 48
 d=p.study(study);assert d;rows,files=p.manifest(d,stage);assert len(files)==N and len(rows)==N//2
 folder=p.out/'F';assert read(folder/'MANIFEST.json')=={'files':files} and read(folder/'HASH_COMMAND.json')['rc']==0 and read(folder/'HASH_COMPLETE.json')['files']==N
 hashes=read(folder/'SOURCE_RECEIPTS.json')['files'];lookup={x['filename']:x for x in hashes};assert len(lookup)==N
 p.w=connect('192.0.2.4','win');p.wf=p.w.open_sftp()
 for x in files:
  s=lookup[x['filename']];assert s['bytes']==x['expected_bytes'] and len(s['sha256'])==64 and pathlib.PureWindowsPath(s['source_raw']).as_posix().casefold()==pathlib.PureWindowsPath(x['source_raw']).as_posix().casefold()
  assert p.wf.stat(x['source_raw']).st_size==s['bytes']
 backup=p.out/'failures/network_drop_20261105_0745';backup.mkdir(parents=True,exist_ok=False)
 for name in ['FAILURE.log','STATUS.json','STOP_REQUESTED.json','LAUNCH.json','CONTROLLER_PID.json']:
  if (p.out/name).exists():(backup/name).write_bytes((p.out/name).read_bytes())
 receipt={'utc':stamp(),'failure_sha256':expected_failure,'dataset':a.dataset,'recovery_code_sha256':sha(pathlib.Path(__file__)),'cached_source_receipts_sha256':sha(folder/'SOURCE_RECEIPTS.json'),'source_files':N,'source_sizes_verified_now':N,'raw_rehashed_now':False,'original_hash_complete':read(folder/'HASH_COMPLETE.json')}
 if a.dataset=='C13':
  p.cfg=read(p.out/'REMOTE_CONFIG.json');p.root=p.cfg['remote_root'];p.reconnect();old=read(p.out/'LAUNCH.json')
  z=run(p.c,'ps -p '+str(int(old['pid']))+' -o pid,args',check=False);assert z['rc']==1 and not z['stdout'].strip().endswith('remote_extract_confirmation.py')
  for name,expected in [('QUEUE.json',{'files':files}),('SOURCE_RECEIPTS.json',{'files':hashes}),('LEDGER.json',{'records':rows})]:
   raw=p.sf.open(p.root+'/'+name).read();assert json.loads(raw)==expected;(backup/('remote_'+name)).write_bytes(raw)
  stop=json.loads(p.sf.open(p.root+'/STOP_REQUESTED.json').read());assert stop['reason']=='own C13 controller failed; preserve artifacts'
  metas=[]
  for name in p.sf.listdir(p.root+'/features'):
   if not name.endswith('.json'):continue
   m=json.loads(p.sf.open(p.root+'/features/'+name).read());ss=lookup[m['filename']]
   assert m['full_contiguous'] and m['raw_sha256']==ss['sha256'] and m['raw_bytes']==ss['bytes'];metas.append(m)
  receipt['previous_extraction_receipts_verified']=len(metas);receipt['previous_features_reused']=False
  archive=p.root+'/failure_20261105_0745';p.sf.mkdir(archive)
  for name in ['STOP_REQUESTED.json','EXTRACTION_FAILURE.log','EXTRACTION_STATUS.json','extract.stdout.log','extract.stderr.log']:
   try:p.sf.rename(p.root+'/'+name,archive+'/'+name)
   except FileNotFoundError:pass
  p.sf.rename(p.root+'/features',archive+'/features');p.sf.mkdir(p.root+'/features')
  receipt['remote_archive']=archive;receipt['remote_previous_pid_absent']=old['pid']
  h=run(p.c,'sha256sum '+shlex.quote(p.root+'/remote_extract_confirmation.py'));assert h['stdout'].split()[0]=='c387e3c74a88bfbc77b1f9d5b0df7bf03361944a20c84fb4db28f2a1f8e1aef7'
  save(backup/'RECOVERY_RECEIPT.json',receipt);save(p.out/'RECOVERY_RECEIPT.json',receipt)
  assert sha(p.out/'FAILURE.log')==expected_failure;(p.out/'FAILURE.log').unlink();p.start()
 else:
  assert not (p.out/'REMOTE_CONFIG.json').exists()
  save(backup/'RECOVERY_RECEIPT.json',receipt);save(p.out/'RECOVERY_RECEIPT.json',receipt)
  assert sha(p.out/'FAILURE.log')==expected_failure;(p.out/'FAILURE.log').unlink()
  parent=B/'untraced_processing_20261105'
  def released():
   if (parent/'FAILURE.log').exists():raise RuntimeError('C13 recovery failed; inspect')
   needed=[parent/n for n in ['STATUS.json','RESOURCE_RELEASE.json','LOCAL_RESULTS_RECEIPT.json']]
   return all(x.exists() for x in needed) and read(needed[0])['phase']=='complete' and read(needed[1])['returncode']==0 and read(needed[2])['verified']
  p.wait(released,'waiting_C13_CPU_results_verified_and_released');p.allocate()
  for src,dest in [('FREEZE.json','COLLECTION_FREEZE.json'),('COMPLETE.json','COLLECTION_COMPLETE.json'),('POSTFLIGHT.json','COLLECTION_POSTFLIGHT.json'),('SUSTAINED_BURST_COLLECTION_VALIDATION.json','SUSTAINED_BURST_COLLECTION_VALIDATION.json')]:p.sf.put(str(d/src),p.root+'/'+dest)
  for name in ['PROTOCOL.md','collect_sustained_burst.py','pi_api.py','rig_capture_stagger.py','burst.c']:p.sf.put(str(d/'source'/name),p.root+'/'+name)
  p.atomic('SOURCE_RECEIPTS.json',{'files':hashes});p.atomic('LEDGER.json',{'records':rows});p.atomic('QUEUE.json',{'files':files});p.start()
 p.transfer(files,'F');p.atomic('UPLOAD_COMPLETE.json',{'expected_files':N,'bytes':sum(x['expected_bytes'] for x in files),'utc':stamp()})
 def extracted():
  try:p.sf.stat(p.root+'/EXTRACTION_FAILURE.log');raise RuntimeError('remote extraction failed')
  except FileNotFoundError:pass
  try:p.sf.stat(p.root+'/EXTRACTION_COMPLETE.json');return True
  except FileNotFoundError:return False
 p.wait(extracted,'waiting_full_extractions')
 package='remote_package_untraced_wait.py' if a.dataset=='C13' else 'remote_package_sustained_burst.py'
 z=run(p.c,'env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 nice -n 10 python '+shlex.quote(p.root+'/'+package)+(' --root '+shlex.quote(p.root) if a.dataset=='C15' else ''),timeout=180,check=False);save(p.out/'PACKAGE_COMMAND.json',z)
 if z['rc']:raise RuntimeError(z['stderr'])
 receipt=json.loads(p.sf.open(p.root+'/RESULT_PACKAGE_RECEIPT.json').read());out=p.out/'analysis';out.mkdir(exist_ok=False);archive=out/receipt['archive'];p.sf.get(p.root+'/'+receipt['archive'],str(archive));assert sha(archive)==receipt['sha256'] and archive.stat().st_size==receipt['bytes']
 with tarfile.open(archive) as t:
  for m in t.getmembers():
   q=pathlib.PurePosixPath(m.name);assert m.isfile() and not q.is_absolute() and '..' not in q.parts
  t.extractall(out,filter='data')
 manifest=read(out/'RESULT_MANIFEST.json');assert manifest['feature_files']==N*2 and manifest['raw_source_hashes_verified']==N
 for x in manifest['files']:
  q=out/x['path'];assert q.stat().st_size==x['bytes'] and sha(q)==x['sha256']
 save(p.out/'LOCAL_RESULTS_RECEIPT.json',{'verified':True,'files':len(manifest['files']),'package':receipt,'utc':stamp()});save(p.out/'BRIDGE_RELEASE_REQUEST.json',{'node':p.cfg['id'],'utc':stamp()})
 p.wait(lambda:(p.out/'RESOURCE_RELEASE.json').exists() and read(p.out/'RESOURCE_RELEASE.json')['returncode']==0,'awaiting_authorized_bridge_release');p.state('complete',verified_files=len(manifest['files']))
except Exception:
 (p.out/'FAILURE.log').write_text(traceback.format_exc(),encoding='utf-8',newline='');p.state('failed',detail='see preserved FAILURE.log')
 if p.sf and p.root:
  try:
   q=p.out/'STOP_REQUESTED_RECOVERY.json';save(q,{'utc':stamp(),'reason':'own recovery failed; preserve artifacts'});p.sf.put(str(q),p.root+'/STOP_REQUESTED.json')
  except Exception:pass
 raise
finally:p.close()
