import json,pathlib,shlex,subprocess,sys,time,paramiko
B=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(B/'burst_study'))
from bridge_utils import *
class Pipe:
 def __init__(self):
  lower_priority();self.out=B/'confirmation_processing_20261105';self.out.mkdir(exist_ok=False);self.deadline=time.monotonic()+18000;self.c=self.sf=self.w=self.wf=None;self.cfg=None;self.root=None
 def state(self,phase,**kw):
  x={'phase':phase,'utc':stamp(),**kw};save(self.out/'STATUS.json',x);print(json.dumps(x),flush=True)
 def study(self,name,done=True):
  p=B/name/'LATEST.json'
  if not p.exists():return None
  d=pathlib.Path(json.loads(p.read_text())['directory'])
  if (d/'FAILURE.log').exists():raise RuntimeError(name+' failed; preserve and inspect')
  if done and not ((d/'COMPLETE.json').exists() and (d/'POSTFLIGHT.json').exists()):return None
  return d
 def wait(self,fn,phase):
  while True:
   x=fn()
   if x:return x
   if time.monotonic()>self.deadline:raise TimeoutError(phase)
   self.state(phase);time.sleep(20)
 def manifest(self,d,stage):
  rows=[dict(x,stage=stage) for x in json.loads((d/'RESULTS.json').read_text())];files=[]
  for family in (('trace','order') if stage=='confirmation' else (None,)):
   for radio in ('930c','16bc'):
    for row in rows:
     if family is not None and row['family']!=family:continue
     rf=next(x for x in row['rf']['radios'] if x['radio']==radio);files.append({'id':row['id'],'stage':stage,'radio':radio,'filename':row['id']+'_'+radio+'.iq','source_raw':rf['raw'].replace('\\','/'),'expected_bytes':rf['bytes']})
  return rows,files
 def source_hash(self,files,drive):
  if self.w is None:self.w=connect('192.0.2.4','win');self.wf=self.w.open_sftp()
  folder=self.out/drive;folder.mkdir(exist_ok=True)
  reuse=B/'F_HASH_REUSE_REQUEST_20261105_0452.json'
  if drive=='F' and reuse.exists():
   request=json.loads(reuse.read_text(encoding='utf-8-sig'));previous=pathlib.Path(request['source_dir'])
   for name,hsh in request['artifact_sha256'].items():assert sha(previous/name)==hsh,('cached artifact changed',name)
   oldmanifest=json.loads((previous/'MANIFEST.json').read_text(encoding='utf-8-sig'));assert oldmanifest=={'files':files}
   h=json.loads((previous/'SOURCE_RECEIPTS.json').read_text(encoding='utf-8-sig'));complete=json.loads((previous/'HASH_COMPLETE.json').read_text(encoding='utf-8-sig'));assert json.loads((previous/'HASH_COMMAND.json').read_text(encoding='utf-8-sig'))['rc']==0
   receipts={x['filename']:x for x in h['files']};assert len(receipts)==len(files)==complete['files']==244
   for row in files:
    item=receipts[row['filename']];assert item['bytes']==row['expected_bytes'] and len(item['sha256'])==64 and all(c in '0123456789abcdef' for c in item['sha256'])
    assert pathlib.PureWindowsPath(item['source_raw']).as_posix().casefold()==pathlib.PureWindowsPath(row['source_raw']).as_posix().casefold()
    assert self.wf.stat(row['source_raw']).st_size==row['expected_bytes']
   for name in request['artifact_sha256']:(folder/name).write_bytes((previous/name).read_bytes())
   save(folder/'HASH_REUSE_RECEIPT.json',{'utc':stamp(),'original_hash_utc':complete['utc'],'source_dir':str(previous),'files':244,'current_source_sizes_verified':244,'raw_rehashed_now':False,'reason':'controller decoding failure after complete original hash; next remote extraction independently hashes each received full IQ'})
   self.state('source_hash_reused_F',files=244,original_hash_utc=complete['utc']);return h['files']
  save(folder/'MANIFEST.json',{'files':files});spool=drive+':/Data/telltale_confirm_hash_'+time.strftime('%Y%m%d_%H%M%S',time.gmtime());self.wf.mkdir(spool);self.wf.put(str(B/'source_receipt.py'),spool+'/source_receipt.py');self.wf.put(str(folder/'MANIFEST.json'),spool+'/MANIFEST.json');self.state('source_hash_'+drive,files=len(files),win4_spool=spool)
  wrapper="import json,os,pathlib,runpy,sys; d=pathlib.Path(__file__).resolve().parent;(d/'HASH_PID.json').write_text(json.dumps({'pid':os.getpid()}));sys.argv=[str(d/'source_receipt.py'),str(d/'MANIFEST.json')];runpy.run_path(str(d/'source_receipt.py'),run_name='__main__')"
  with self.wf.open(spool+'/hash_owned.py','w') as f:f.write(wrapper)
  ret=run(self.w,'python '+spool+'/hash_owned.py',timeout=1800);save(folder/'HASH_COMMAND.json',ret);self.wf.get(spool+'/SOURCE_RECEIPTS.json',str(folder/'SOURCE_RECEIPTS.json'));h=json.loads((folder/'SOURCE_RECEIPTS.json').read_text());assert len(h['files'])==len(files);save(folder/'HASH_COMPLETE.json',{'files':len(files),'utc':stamp(),'spool':spool});return h['files']
 def atomic(self,name,data):
  p=self.out/('REMOTE_'+name);save(p,data);self.sf.put(str(p),self.root+'/'+name+'.pending');self.sf.posix_rename(self.root+'/'+name+'.pending',self.root+'/'+name)
 def transfer(self,files,label):
  folder=self.out/label;folder.mkdir(exist_ok=True)
  for idx,row in enumerate(files):
   target=self.root+'/raw/'+row['filename'];cmd=['scp','-q','-3','-X','nrequests=256','-X','buffer=131072','-o','Compression=no','-F',str(self.out/'ssh_config'),'claw-confirm-rig:'+row['source_raw'],'claw-confirm-cpu:'+target+'.partial']
   with (folder/'scp.log').open('ab') as f:z=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=240)
   if z.returncode:raise RuntimeError('scp failed '+row['filename'])
   assert self.sf.stat(target+'.partial').st_size==row['expected_bytes'];self.sf.posix_rename(target+'.partial',target);self.state('transfer_'+label,completed=idx+1,planned=len(files))
 def allocate(self):
  # Interactive scheduled tasks intentionally do not receive platform API credentials.
  # The current agent performs pick_node through the authorized project bridge when requested.
  q=self.out/'BRIDGE_PICK.json'
  self.wait(lambda:q.exists(),'awaiting_authorized_bridge_CPU_pick')
  self.cfg=json.loads(q.read_text(encoding='utf-8-sig'));assert self.cfg['cores']==4 and self.cfg['mem_gb']>=12
  save(self.out/'PICK_COMMAND.json',{'source':'authorized project bridge','config_file':str(q),'utc':stamp()})
  self.root='/cache/telltale_ws_pi/confirm_'+time.strftime('%Y%m%d_%H%M%S',time.gmtime());self.cfg['remote_root']=self.root;save(self.out/'REMOTE_CONFIG.json',self.cfg);self.c=paramiko.SSHClient();self.c.load_system_host_keys();self.c.set_missing_host_key_policy(paramiko.RejectPolicy());self.c.connect(self.cfg['host'],port=self.cfg['port'],username=self.cfg['user'],key_filename=self.cfg['key'],timeout=15);self.sf=self.c.open_sftp();save(self.out/'REMOTE_ENV.json',run(self.c,"hostname; python -c 'import numpy,scipy,sklearn;print(numpy.__version__)'"));run(self.c,'mkdir -p '+shlex.quote(self.root+'/raw')+' '+shlex.quote(self.root+'/features'))
  for name in ('remote_extract_confirmation.py','remote_extensions.py','remote_evaluate.py','remote_confirmation_eval.py','remote_wait_confirmation_eval.py','remote_package_confirmations.py','relative_reference_features.py','remote_relative_reference_eval.py','blockwise_comparison.py','RELATIVE_REFERENCE_PROTOCOL.md','export_relative_reference.py'):self.sf.put(str(B/name),self.root+'/'+name)
  for name in ('CONFIRMATION_MODELS.json','BURST_EXPLORATORY_FREEZE.json','WAIT_CONFIRMATION_MODELS.json','RELATIVE_REFERENCE_MODELS.json'):self.sf.put(str(B/'analysis_extensions'/name),self.root+'/'+name)
  (self.out/'ssh_config').write_text('Host claw-confirm-rig\n HostName 192.0.2.4\n User win\n Port 22\n IdentityFile <SSH_KEY>\n StrictHostKeyChecking yes\n Compression no\nHost claw-confirm-cpu\n HostName '+self.cfg['host']+'\n User '+self.cfg['user']+'\n Port '+str(self.cfg['port'])+'\n IdentityFile '+self.cfg['key']+'\n StrictHostKeyChecking yes\n Compression no\n')
 def start(self):
  root=self.root;cmd='nohup env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python -u '+shlex.quote(root+'/remote_extract_confirmation.py')+' --root '+shlex.quote(root)+' --workers 4 >'+shlex.quote(root+'/extract.stdout.log')+' 2>'+shlex.quote(root+'/extract.stderr.log')+' </dev/null & echo $!';z=run(self.c,cmd,timeout=20);pid=int(z['stdout'].strip());save(self.out/'LAUNCH.json',{'pid':pid,'command':cmd,'utc':stamp(),'ps':run(self.c,'ps -p '+str(pid)+' -o pid,args')})
  with (B.parent.parent/'REMOTE_JOBS.md').open('a',encoding='utf-8') as f:f.write('\n## Confirmation CPU job '+stamp()+'\n\nNode '+self.cfg['id']+' '+self.cfg['host']+':'+str(self.cfg['port'])+'; root '+root+'; PID '+str(pid)+'; workers4/numeric1. Details results/scenario_rf_20261104/confirmation_processing_20261105/LAUNCH.json and REMOTE_CONFIG.json. Expected516 IQ/103.04GB including separately labeled interrupted campaign, max4h extraction; sources remain on capture-pc.\n')
 def close(self):
  for obj in (self.sf,self.c,self.wf,self.w):
   if obj:obj.close()
