"""Resume the same remote job after complete J hashes and a dropped SFTP channel."""
import os,tarfile,traceback,hashlib
from confirmation_pipeline_utils import *
def read(p):return json.loads(pathlib.Path(p).read_text(encoding='utf-8-sig'))
class ResumePipe(Pipe):
 def __init__(self):
  lower_priority();self.out=B/'confirmation_processing_20261105';assert self.out.exists();self.deadline=time.monotonic()+14400;self.w=self.wf=self.c=self.sf=None
  self.cfg=read(self.out/'REMOTE_CONFIG.json');self.root=self.cfg['remote_root'];self.reconnects=0;self.reconnect()
  save(self.out/'RESUME_CONTROLLER_PID.json',{'pid':os.getpid(),'script':str(pathlib.Path(__file__).resolve()),'utc':stamp()})
 def reconnect(self):
  for obj in (self.sf,self.c):
   if obj:
    try:obj.close()
    except Exception:pass
  self.c=paramiko.SSHClient();self.c.load_system_host_keys();self.c.set_missing_host_key_policy(paramiko.RejectPolicy());self.c.connect(self.cfg['host'],port=self.cfg['port'],username=self.cfg['user'],key_filename=self.cfg['key'],timeout=15)
  self.c.get_transport().set_keepalive(20);self.sf=self.c.open_sftp();self.sf.get_channel().settimeout(60)
 def sftp_step(self,fn,label):
  try:return fn(self.sf)
  except (EOFError,paramiko.SSHException,ConnectionResetError,TimeoutError) as e:
   self.reconnects+=1;save(self.out/('SFTP_RECONNECT_'+str(self.reconnects)+'.json'),{'utc':stamp(),'operation':label,'error_type':type(e).__name__,'error':str(e),'policy':'one fresh connection retry of identical idempotent metadata operation'})
   self.reconnect();return fn(self.sf)
 def atomic(self,name,data):
  p=self.out/('REMOTE_'+name);save(p,data)
  def put(sf):sf.put(str(p),self.root+'/'+name+'.pending');sf.posix_rename(self.root+'/'+name+'.pending',self.root+'/'+name)
  self.sftp_step(put,'atomic '+name)
 def transfer(self,files,label):
  folder=self.out/label;folder.mkdir(exist_ok=True)
  for idx,row in enumerate(files):
   target=self.root+'/raw/'+row['filename'];cmd=['scp','-q','-3','-X','nrequests=256','-X','buffer=131072','-o','Compression=no','-F',str(self.out/'ssh_config'),'claw-confirm-rig:'+row['source_raw'],'claw-confirm-cpu:'+target+'.partial']
   with (folder/'scp.log').open('ab') as f:z=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=240)
   if z.returncode:raise RuntimeError('scp failed '+row['filename']+'; preserve partial and native log')
   def finish(sf):
    try:part=sf.stat(target+'.partial')
    except FileNotFoundError:
     assert sf.stat(target).st_size==row['expected_bytes'];return
    assert part.st_size==row['expected_bytes'];sf.posix_rename(target+'.partial',target);assert sf.stat(target).st_size==row['expected_bytes']
   self.sftp_step(finish,'promote completed upload '+row['filename']);self.state('transfer_'+label,completed=idx+1,planned=len(files),recovered_controller=True)
p=ResumePipe()
try:
 assert sha(p.out/'FAILURE.log')=='d86eef504737d67ca61de2d99b3c7bd6b73f58ca90f49e0ebf17d9f6142c8fbd','inspect current failure before any recovery'
 assert read(p.out/'STATUS.json')['phase']=='failed'
 dF=p.study('confirmation_study');partial=B/'confirmation_study/confirm_20261105_032747_8137bb';dB=p.study('burst_confirmation_study');dW=p.study('wait_confirmation_study')
 assert dF and dB and dW
 rowsNew,filesNew=p.manifest(dF,'confirmation');rowsPartial,filesPartial=p.manifest(partial,'confirmation_partial');rowsB,filesB=p.manifest(dB,'burst_confirmation');rowsW,filesW=p.manifest(dW,'wait_confirmation')
 rowsF=rowsNew+rowsPartial;filesF=filesNew+filesPartial;filesJ=filesB+filesW;allrows=rowsF+rowsB+rowsW;allfiles=filesF+filesJ
 assert (len(rowsF),len(filesF),len(rowsB),len(rowsW),len(filesJ),len(allrows),len(allfiles))==(122,244,72,64,272,258,516)
 for vp in [B/'C08_COLLECTION_VALIDATION.json',B/'CONFIRMATION_PARTIAL_COLLECTION_VALIDATION.json',B/'CONFIRMATION_COLLECTION_VALIDATION.json',dW/'WAIT_CONFIRMATION_COLLECTION_VALIDATION.json']:assert read(vp)['pass']
 assert read(p.out/'F_UPLOAD_COMPLETE.json')['files']==244
 hashes={};cache_receipts={}
 for drive,files in [('F',filesF),('J',filesJ)]:
  folder=p.out/drive;assert read(folder/'MANIFEST.json')=={'files':files};complete=read(folder/'HASH_COMPLETE.json');assert complete['files']==len(files) and read(folder/'HASH_COMMAND.json')['rc']==0
  hh=read(folder/'SOURCE_RECEIPTS.json')['files'];lookup={r['filename']:r for r in hh};assert len(lookup)==len(files)
  for r in files:
   h=lookup[r['filename']];assert h['bytes']==r['expected_bytes'] and len(h['sha256'])==64 and all(c in '0123456789abcdef' for c in h['sha256'])
   assert pathlib.PureWindowsPath(h['source_raw']).as_posix().casefold()==pathlib.PureWindowsPath(r['source_raw']).as_posix().casefold()
  hashes[drive]=hh;cache_receipts[drive]={'hash_complete':complete,'artifacts':{n:sha(folder/n) for n in ['MANIFEST.json','HASH_COMPLETE.json','HASH_COMMAND.json','SOURCE_RECEIPTS.json']},'raw_rehashed_now':False}
 for n in ['STOP_REQUESTED.json','EXTRACTION_FAILURE.log','EXTRACTION_COMPLETE.json']:
  try:p.sf.stat(p.root+'/'+n)
  except FileNotFoundError:continue
  raise RuntimeError('unexpected remote marker '+n+'; inspect instead of replacing')
 launch=read(p.out/'LAUNCH.json');z=run(p.c,'ps -p '+str(int(launch['pid']))+' -o pid,etime,stat,args --no-headers',timeout=15);assert p.root+'/remote_extract_confirmation.py' in z['stdout']
 snapshots={}
 for n,expected in [('SOURCE_RECEIPTS.json',{'files':hashes['F']}),('LEDGER.json',{'records':rowsF}),('QUEUE.json',{'files':filesF})]:
  raw=p.sf.open(p.root+'/'+n).read();assert json.loads(raw)==expected,('unexpected remote state',n);snapshots[n]=raw
 sourceF={r['filename']:r for r in hashes['F']}
 for r in filesF:
  j=json.loads(p.sf.open(p.root+'/features/'+r['id']+'_'+r['radio']+'.json').read());h=sourceF[r['filename']];assert j['full_contiguous'] and j['raw_sha256']==h['sha256'] and j['raw_bytes']==h['bytes']
 raw_names=set(p.sf.listdir(p.root+'/raw'));assert all(r['filename'] not in raw_names and r['filename']+'.partial' not in raw_names for r in filesJ),'J transfer already started; needs a different resume audit'
 failure=p.out/'failures/sftp_drop_20261105_055849';failure.mkdir(parents=True,exist_ok=False)
 for n in ['STATUS.json','FAILURE.log']:(failure/n).write_bytes((p.out/n).read_bytes())
 for n in ['process_confirmations.py','confirmation_pipeline_utils.py']:(failure/n).write_bytes((B/n).read_bytes())
 for n,raw in snapshots.items():(failure/('remote_before_'+n)).write_bytes(raw)
 receipt={'utc':stamp(),'original_failure_sha256':sha(failure/'FAILURE.log'),'recovery_code_sha256':sha(pathlib.Path(__file__)),'reuse_existing_remote_job':launch['pid'],'remote_root':p.root,'remote_ps':z,'cache_sources':cache_receipts,'F_features_and_raw_digests_verified':244,'J_transfer_previously_started':False,'all_records':258,'all_raw_files':516,'source_bytes':sum(r['expected_bytes'] for r in allfiles),'note':'complete source digests reused, not freshly rehashed here; each remote extractor still hashes the full raw stream'}
 save(failure/'RECOVERY_VALIDATION.json',receipt);save(p.out/'SFTP_RECOVERY_RECEIPT.json',receipt)
 assert sha(p.out/'FAILURE.log')==receipt['original_failure_sha256'];(p.out/'FAILURE.log').unlink()
 p.state('resuming_same_remote_job_after_J_hash',remote_pid=launch['pid'],source_files=516,verified_existing_F_features=244)
 p.atomic('SOURCE_RECEIPTS.json',{'files':hashes['F']+hashes['J']});p.atomic('LEDGER.json',{'records':allrows})
 p.sf.put(str(B/'CONFIRMATION_COLLECTION_VALIDATION.json'),p.root+'/CONFIRMATION_COLLECTION_VALIDATION.json');p.sf.put(str(dW/'WAIT_CONFIRMATION_COLLECTION_VALIDATION.json'),p.root+'/WAIT_CONFIRMATION_COLLECTION_VALIDATION.json')
 p.atomic('QUEUE.json',{'files':allfiles});save(p.out/'J_QUEUE_APPENDED.json',{'utc':stamp(),'rows':258,'files':516,'same_remote_pid':launch['pid']})
 p.transfer(filesJ,'J');p.atomic('UPLOAD_COMPLETE.json',{'expected_files':516,'bytes':sum(r['expected_bytes'] for r in allfiles),'utc':stamp()})
 def extracted():
  try:p.sf.stat(p.root+'/EXTRACTION_FAILURE.log');raise RuntimeError('Remote confirmation extraction failure')
  except FileNotFoundError:pass
  try:p.sf.stat(p.root+'/EXTRACTION_COMPLETE.json');return True
  except FileNotFoundError:return False
 p.wait(extracted,'waiting_516_full_extractions');p.state('evaluating_frozen_models')
 z=run(p.c,'env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 nice -n 10 python '+shlex.quote(p.root+'/remote_package_confirmations.py'),timeout=240,check=False);save(p.out/'PACKAGE_COMMAND.json',z)
 if z['rc']:raise RuntimeError(z['stderr'])
 receipt=json.loads(p.sf.open(p.root+'/RESULT_PACKAGE_RECEIPT.json').read());analysis=p.out/'analysis';analysis.mkdir();archive=analysis/receipt['archive'];p.sf.get(p.root+'/'+receipt['archive'],str(archive));assert sha(archive)==receipt['sha256'] and archive.stat().st_size==receipt['bytes']
 with tarfile.open(archive) as t:
  for member in t.getmembers():
   q=pathlib.PurePosixPath(member.name)
   if q.is_absolute() or '..' in q.parts or not member.isfile():raise RuntimeError('unsafe archive member')
  t.extractall(analysis,filter='data')
 manifest=json.loads((analysis/'RESULT_MANIFEST.json').read_text())
 for item in manifest['files']:
  q=analysis/item['path'];assert q.stat().st_size==item['bytes'] and sha(q)==item['sha256']
 save(p.out/'LOCAL_RESULTS_RECEIPT.json',{'verified':True,'files':len(manifest['files']),'package':receipt,'utc':stamp()})
 save(p.out/'BRIDGE_RELEASE_REQUEST.json',{'node':p.cfg['id'],'utc':stamp(),'reason':'results verified; release through authorized project bridge without copying scoped credentials'})
 def released():
  q=p.out/'RESOURCE_RELEASE.json'
  return q.exists() and json.loads(q.read_text(encoding='utf-8-sig'))['returncode']==0
 p.wait(released,'awaiting_authorized_bridge_release');p.state('complete',verified_files=len(manifest['files']))
except Exception:
 (p.out/'FAILURE.log').write_text(traceback.format_exc(),encoding='utf-8',newline='')
 p.state('failed',detail='see preserved FAILURE.log and failures/ history')
 raise
finally:p.close()
