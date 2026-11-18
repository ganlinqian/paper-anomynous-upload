from pathlib import Path
import argparse,json,hashlib,datetime,shlex,paramiko
ap=argparse.ArgumentParser();ap.add_argument('action',choices=['export','evaluate']);ap.add_argument('--dataset',choices=['C10','C13']);a=ap.parse_args();B=Path(__file__).resolve().parent;F=B/'analysis_extensions/full_20261105';O=B/'analysis_extensions/coarse_real_tool_20261105';O.mkdir(exist_ok=True);sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert a.action=='export' or a.dataset
D=B/('untraced_processing_20261105' if a.dataset=='C13' else 'confirmation_processing_20261105');cfg=json.loads((D/'REMOTE_CONFIG.json').read_text(encoding='utf-8-sig'));R=cfg['remote_root'];name='COARSE_REAL_TOOL_MODELS.json' if a.action=='export' else 'COARSE_REAL_TOOL_'+a.dataset+'.json';p=O/name
if p.exists():
 r=json.loads(p.with_name(name+'.RECEIPT.json').read_text());assert sha(p)==r['sha256'];print(json.dumps({'already_verified':str(p),'sha256':sha(p)}));raise SystemExit(0)
c=paramiko.SSHClient();c.load_system_host_keys();c.set_missing_host_key_policy(paramiko.RejectPolicy());c.connect(cfg['host'],port=cfg['port'],username=cfg['user'],key_filename=cfg['key'],timeout=15);c.get_transport().set_keepalive(20);sf=c.open_sftp();sf.get_channel().settimeout(60)
def exists(p):
 try:sf.stat(p);return True
 except FileNotFoundError:return False
def run(cmd):
 i,o,e=c.exec_command(cmd,timeout=90);out=o.read().decode();err=e.read().decode();return {'returncode':o.channel.recv_exit_status(),'stdout':out,'stderr':err}
try:
 for n in ['COARSE_REAL_TOOL_PROTOCOL.md','remote_coarse_real_tool.py']:sf.put(str(B/n),R+'/'+n)
 if a.action=='export':
  assert not (B/'untraced_processing_20261105/REMOTE_CONFIG.json').exists(),'audit chronology: C13 not yet allocated at this export'
  manifest={x['path']:x for x in json.loads((F/'RESULT_MANIFEST_20261105.json').read_text(encoding='utf-8-sig'))['files']};ledger={x['id']:x for x in json.loads((F/'LEDGER.json').read_text(encoding='utf-8-sig'))['records']};orig=json.loads((B/'analysis_extensions/WAIT_CONFIRMATION_MODELS.json').read_text(encoding='utf-8-sig'));inp={'rows':[],'old_manifest_sha256':sha(F/'RESULT_MANIFEST_20261105.json')}
  for sub in ['coarse_real_training','coarse_real_training/features']:
   if not exists(R+'/'+sub):sf.mkdir(R+'/'+sub)
  for rid in orig['training_ids']:
   p0=F/'features'/(rid+'_930c.npz');rel='features/'+p0.name;assert sha(p0)==manifest[rel]['sha256']==orig['training_feature_sha256'][rid];assert p0.stat().st_size==manifest[rel]['bytes'];sf.put(str(p0),R+'/coarse_real_training/features/'+p0.name);inp['rows'].append({'id':rid,'actual':ledger[rid]['actual_active'],'npz_sha256':sha(p0)})
  ip=O/'COARSE_REAL_TOOL_TRAIN_INPUT.json';ip.write_text(json.dumps(inp,indent=2),encoding='utf-8',newline='');sf.put(str(ip),R+'/'+ip.name)
 else:
  mp=O/'COARSE_REAL_TOOL_MODELS.json';rc=json.loads(mp.with_name(mp.name+'.RECEIPT.json').read_text());assert sha(mp)==rc['sha256'];sf.put(str(mp),R+'/'+mp.name)
 cmd='env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 nice -n 19 python '+shlex.quote(R+'/remote_coarse_real_tool.py')+' --root '+shlex.quote(R)+' --action '+a.action+(' --dataset '+a.dataset if a.dataset else '')
 z={'returncode':0,'stdout':'reuse preserved remote result','stderr':''} if exists(R+'/'+name) else run(cmd);z.update(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),command=cmd,code_sha256=sha(B/'remote_coarse_real_tool.py'));(O/(name+'.COMMAND.json')).write_text(json.dumps(z,indent=2),encoding='utf-8',newline='')
 if z['returncode']==3:print(z['stdout']);raise SystemExit(3)
 assert z['returncode']==0,z
 tmp=p.with_suffix('.json.pending');sf.get(R+'/'+name,str(tmp));h=run('sha256sum '+shlex.quote(R+'/'+name));assert h['returncode']==0 and sha(tmp)==h['stdout'].split()[0];j=json.loads(tmp.read_text());assert j['code_sha256']==sha(B/'remote_coarse_real_tool.py');tmp.replace(p)
 r={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'sha256':sha(p),'bytes':p.stat().st_size,'node':cfg['id'],'remote_root':R,'code_sha256':sha(B/'remote_coarse_real_tool.py')};p.with_name(name+'.RECEIPT.json').write_text(json.dumps(r,indent=2),encoding='utf-8',newline='');print(json.dumps(r));print(z['stdout'])
finally:sf.close();c.close()
