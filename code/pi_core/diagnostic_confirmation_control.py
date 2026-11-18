"""Use the actual main CPU node; copy only 40 verified old diagnostic NPZs."""
from pathlib import Path
import argparse,datetime,hashlib,json,shlex,paramiko
B=Path(__file__).resolve().parent;D=B/'confirmation_processing_20261105';F=B/'analysis_extensions/full_20261105';O=B/'analysis_extensions/diagnostic_confirm_20261105';O.mkdir(exist_ok=True)
ap=argparse.ArgumentParser();ap.add_argument('action',choices=['export','evaluate']);ap.add_argument('--stage',choices=['confirmation','confirmation_partial','wait_confirmation']);ap.add_argument('--family',choices=['trace','order','wait']);a=ap.parse_args()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
cfg=json.loads((D/'REMOTE_CONFIG.json').read_text(encoding='utf-8-sig'));root=cfg['remote_root'];c=paramiko.SSHClient();c.load_system_host_keys();c.set_missing_host_key_policy(paramiko.RejectPolicy());c.connect(cfg['host'],port=cfg['port'],username=cfg['user'],key_filename=cfg['key'],timeout=15);sf=c.open_sftp()
def run(cmd):
 i,o,e=c.exec_command(cmd,timeout=90);out=o.read().decode();err=e.read().decode();return {'returncode':o.channel.recv_exit_status(),'stdout':out,'stderr':err}
def exists(path):
 try:sf.stat(path);return True
 except FileNotFoundError:return False
def fetch(name,extra):
 p=O/name;pending=p.with_suffix('.json.pending');sf.get(root+'/'+name,str(pending));h=run('sha256sum '+shlex.quote(root+'/'+name));assert h['returncode']==0 and sha(pending)==h['stdout'].split()[0];pending.replace(p)
 receipt={'sha256':sha(p),'bytes':p.stat().st_size,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'node':cfg['id'],'remote_root':root,**extra};p.with_name(name+'.RECEIPT.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8',newline='');return p
try:
 sf.put(str(B/'remote_diagnostic_confirmation.py'),root+'/remote_diagnostic_confirmation.py');sf.put(str(B/'DIAGNOSTIC_CHANNEL_PROTOCOL.md'),root+'/DIAGNOSTIC_CHANNEL_PROTOCOL.md')
 if a.action=='export':
  name='DIAGNOSTIC_CHANNEL_MODELS.json';p=O/name
  if p.exists():
   rc=json.loads(p.with_name(name+'.RECEIPT.json').read_text(encoding='utf-8-sig'));assert sha(p)==rc['sha256'];print(json.dumps({'already_exported':str(p),'sha256':sha(p)}));raise SystemExit(0)
  manifest=json.loads((F/'RESULT_MANIFEST_20261105.json').read_text(encoding='utf-8-sig'));known={r['path']:r for r in manifest['files']};old={r['id']:r for r in json.loads((F/'LEDGER.json').read_text(encoding='utf-8-sig'))['records']}
  original=json.loads((B/'analysis_extensions/CONFIRMATION_MODELS.json').read_text(encoding='utf-8-sig'))['families'];original['wait']=json.loads((B/'analysis_extensions/WAIT_CONFIRMATION_MODELS.json').read_text(encoding='utf-8-sig'))
  inp={'protocol_sha256':sha(B/'DIAGNOSTIC_CHANNEL_PROTOCOL.md'),'returned_manifest_sha256':sha(F/'RESULT_MANIFEST_20261105.json'),'families':{}}
  if not exists(root+'/diagnostic_training_features'):sf.mkdir(root+'/diagnostic_training_features')
  for family,mm in original.items():
   rows=[]
   for rid in mm['training_ids']:
    rel='features/'+rid+'_16bc.npz';q=F/rel;assert sha(q)==known[rel]['sha256'] and q.stat().st_size==known[rel]['bytes'];truth=old[rid]['actual_order' if family=='order' else 'actual_active'];assert isinstance(truth,bool)
    rows.append({'id':rid,'actual':truth,'npz_sha256':sha(q)});sf.put(str(q),root+'/diagnostic_training_features/'+q.name)
   inp['families'][family]=rows
  p=O/'DIAGNOSTIC_TRAIN_INPUT.json';p.write_text(json.dumps(inp,indent=2),encoding='utf-8',newline='');sf.put(str(p),root+'/'+p.name)
  command='env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 nice -n 19 python '+shlex.quote(root+'/remote_diagnostic_confirmation.py')+' --root '+shlex.quote(root)+' --action export'
 else:
  assert a.stage and a.family;name='DIAGNOSTIC_'+a.stage.upper()+'_'+a.family.upper()+'.json';p=O/name
  if p.exists():
   rc=json.loads(p.with_name(name+'.RECEIPT.json').read_text(encoding='utf-8-sig'));assert sha(p)==rc['sha256'];print(json.dumps({'already_verified':str(p),'sha256':sha(p)}));raise SystemExit(0)
  mp=O/'DIAGNOSTIC_CHANNEL_MODELS.json';rc=json.loads(mp.with_name(mp.name+'.RECEIPT.json').read_text(encoding='utf-8-sig'));assert sha(mp)==rc['sha256']
  command='env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 nice -n 19 python '+shlex.quote(root+'/remote_diagnostic_confirmation.py')+' --root '+shlex.quote(root)+' --action evaluate --stage '+a.stage+' --family '+a.family+' --model-sha256 '+sha(mp)
 z={'returncode':0,'stdout':'reuse preserved remote result','stderr':''} if exists(root+'/'+name) else run(command)
 stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%H%M%S');(O/(a.action+'_'+(a.family or 'models')+'_'+stamp+'_COMMAND.json')).write_text(json.dumps({'command':command,'code_sha256':sha(B/'remote_diagnostic_confirmation.py'),**z},indent=2),encoding='utf-8',newline='')
 if z['returncode']==3:print(z['stdout']);raise SystemExit(3)
 if z['returncode']:raise RuntimeError(z['stderr'])
 p=fetch(name,{'code_sha256':sha(B/'remote_diagnostic_confirmation.py'),'action':a.action})
 j=json.loads(p.read_text(encoding='utf-8-sig'))
 if a.action=='export':
  assert j['code_sha256']==sha(B/'remote_diagnostic_confirmation.py');print(json.dumps({'models':str(p),'sha256':sha(p),'training_ids':sum(len(v['training_ids']) for v in j['families'].values())}))
 else:
  assert j['diagnostic_models_sha256']==sha(O/'DIAGNOSTIC_CHANNEL_MODELS.json');print(json.dumps({'file':str(p),'sha256':sha(p),'raw_hashes':j['raw_source_hashes_verified'],'scores':{ch:{k:{t:v['task_conditioned'][t] for t in ['tp','fn','fp','tn','balanced_accuracy']} for k,v in z.items()} for ch,z in j['channels'].items()}}))
finally:sf.close();c.close()
