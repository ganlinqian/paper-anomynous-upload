from pathlib import Path
import json,hashlib,datetime,shlex,paramiko
B=Path(__file__).resolve().parent;F=B/'analysis_extensions/full_20261105';O=B/'analysis_extensions/coarse_observation_20261105';O.mkdir(exist_ok=True);sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();cfg=json.loads((B/'confirmation_processing_20261105/REMOTE_CONFIG.json').read_text(encoding='utf-8-sig'));R=cfg['remote_root']
if (O/'COARSE_OBSERVATION_ABLATION.json.RECEIPT.json').exists():
 r=json.loads((O/'COARSE_OBSERVATION_ABLATION.json.RECEIPT.json').read_text());assert sha(O/'COARSE_OBSERVATION_ABLATION.json')==r['sha256'];print(json.dumps({'already_verified':True}));raise SystemExit(0)
manifest={x['path']:x for x in json.loads((F/'RESULT_MANIFEST_20261105.json').read_text(encoding='utf-8-sig'))['files']};ledger={x['id']:x for x in json.loads((F/'LEDGER.json').read_text(encoding='utf-8-sig'))['records']};original=json.loads((B/'analysis_extensions/CONFIRMATION_MODELS.json').read_text(encoding='utf-8-sig'))
c=paramiko.SSHClient();c.load_system_host_keys();c.set_missing_host_key_policy(paramiko.RejectPolicy());c.connect(cfg['host'],port=cfg['port'],username=cfg['user'],key_filename=cfg['key'],timeout=15);c.get_transport().set_keepalive(20);sf=c.open_sftp();sf.get_channel().settimeout(60)
def exists(p):
 try:sf.stat(p);return True
 except FileNotFoundError:return False
def run(cmd):
 i,o,e=c.exec_command(cmd,timeout=90);out=o.read().decode();err=e.read().decode();return {'returncode':o.channel.recv_exit_status(),'stdout':out,'stderr':err}
try:
 for sub in ['coarse_training','coarse_training/features']:
  if not exists(R+'/'+sub):sf.mkdir(R+'/'+sub)
 inp={'returned_manifest_sha256':sha(F/'RESULT_MANIFEST_20261105.json'),'families':{}}
 for family,m in original['families'].items():
  inp['families'][family]=[]
  for rid in m['training_ids']:
   p=F/'features'/(rid+'_930c.npz');rel='features/'+p.name;assert sha(p)==manifest[rel]['sha256']==m['training_feature_sha256'][rid];assert p.stat().st_size==manifest[rel]['bytes'];sf.put(str(p),R+'/coarse_training/features/'+p.name)
   inp['families'][family].append({'id':rid,'actual':ledger[rid]['actual_order' if family=='order' else 'actual_active'],'npz_sha256':sha(p)})
 ip=O/'COARSE_TRAIN_INPUT.json';ip.write_text(json.dumps(inp,indent=2),encoding='utf-8',newline='');sf.put(str(ip),R+'/'+ip.name)
 for n in ['COARSE_OBSERVATION_ABLATION_PROTOCOL.md','remote_coarse_observation_ablation.py']:sf.put(str(B/n),R+'/'+n)
 cmd='env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 nice -n 19 python '+shlex.quote(R+'/remote_coarse_observation_ablation.py')+' --root '+shlex.quote(R)
 z={'returncode':0,'stdout':'reuse remote preserved result','stderr':''} if exists(R+'/COARSE_OBSERVATION_ABLATION.json') else run(cmd);z.update(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),command=cmd,code_sha256=sha(B/'remote_coarse_observation_ablation.py'));(O/'COMMAND.json').write_text(json.dumps(z,indent=2),encoding='utf-8',newline='');assert z['returncode']==0,z
 for name in ['COARSE_OBSERVATION_ABLATION_MODELS.json','COARSE_OBSERVATION_ABLATION.json']:
  p=O/name;tmp=p.with_suffix('.json.pending');sf.get(R+'/'+name,str(tmp));h=run('sha256sum '+shlex.quote(R+'/'+name));assert h['returncode']==0 and sha(tmp)==h['stdout'].split()[0];tmp.replace(p);p.with_name(name+'.RECEIPT.json').write_text(json.dumps({'sha256':sha(p),'bytes':p.stat().st_size,'node':cfg['id'],'remote_root':R,'code_sha256':sha(B/'remote_coarse_observation_ablation.py')},indent=2),encoding='utf-8',newline='')
 j=json.loads((O/'COARSE_OBSERVATION_ABLATION.json').read_text());assert j['raw_primary_hashes_verified']==122 and j['models_sha256']==sha(O/'COARSE_OBSERVATION_ABLATION_MODELS.json');print(z['stdout'])
finally:sf.close();c.close()
