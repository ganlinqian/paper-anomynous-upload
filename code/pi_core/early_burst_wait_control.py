"""Use existing allocated main CPU node; no new reservation or collection change."""
import argparse,datetime,hashlib,json,pathlib,shlex,paramiko
B=pathlib.Path(__file__).resolve().parent;D=B/'confirmation_processing_20261105';O=B/'analysis_extensions/early_burst_wait_20261105';O.mkdir(exist_ok=True)
ap=argparse.ArgumentParser();ap.add_argument('--family',choices=['burst','wait'],required=True);a=ap.parse_args()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
name='EARLY_'+a.family.upper()+'_CONFIRMATION.json';p=O/name
if p.exists():
 receipt=json.loads(p.with_name(name+'.RECEIPT.json').read_text(encoding='utf-8-sig'));assert sha(p)==receipt['sha256'];print(json.dumps({'already_verified':str(p),'sha256':sha(p)}));raise SystemExit(0)
cfg=json.loads((D/'REMOTE_CONFIG.json').read_text(encoding='utf-8-sig'));root=cfg['remote_root']
c=paramiko.SSHClient();c.load_system_host_keys();c.set_missing_host_key_policy(paramiko.RejectPolicy());c.connect(cfg['host'],port=cfg['port'],username=cfg['user'],key_filename=cfg['key'],timeout=15);sf=c.open_sftp()
def run(cmd):
 i,o,e=c.exec_command(cmd,timeout=90);out=o.read().decode();err=e.read().decode();return {'returncode':o.channel.recv_exit_status(),'stdout':out,'stderr':err}
try:
 sf.put(str(B/'remote_early_burst_wait.py'),root+'/remote_early_burst_wait.py')
 cmd='env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 nice -n 19 python '+shlex.quote(root+'/remote_early_burst_wait.py')+' --root '+shlex.quote(root)+' --family '+a.family
 try:sf.stat(root+'/'+name);exists=True
 except FileNotFoundError:exists=False
 z={'returncode':0,'stdout':'reusing preserved remote early result without recomputing','stderr':''} if exists else run(cmd)
 z.update(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),code_sha256=sha(B/'remote_early_burst_wait.py'),command=cmd)
 stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%H%M%S');(O/(a.family+'_COMMAND_'+stamp+'.json')).write_text(json.dumps(z,indent=2),encoding='utf-8')
 if z['returncode']==3:print(json.dumps({'ready':False,'summary':z['stdout']}));raise SystemExit(3)
 if z['returncode']:raise RuntimeError(z['stderr'])
 pending=p.with_suffix('.json.pending');sf.get(root+'/'+name,str(pending));h=run('sha256sum '+shlex.quote(root+'/'+name));assert h['returncode']==0 and sha(pending)==h['stdout'].split()[0];pending.replace(p)
 j=json.loads(p.read_text(encoding='utf-8-sig'));assert j['primary_raw_hashes_verified']==(72 if a.family=='burst' else 64) and j['diagnostic_channel_pending_or_not_checked']
 assert j['evaluation_code_sha256']==sha(B/'remote_early_burst_wait.py')
 receipt={'sha256':sha(p),'bytes':p.stat().st_size,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'primary_raw_files':j['primary_raw_hashes_verified'],'diagnostic_channel_not_checked':True,'node':cfg['id'],'remote_root':root,'code_sha256':sha(B/'remote_early_burst_wait.py')}
 p.with_name(name+'.RECEIPT.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8');print(json.dumps({'ready':True,'file':str(p),'sha256':receipt['sha256'],'n':j['primary_raw_hashes_verified']}))
finally:sf.close();c.close()
