"""Run on the main job's actual allocated CPU node after verified early results exist."""
import argparse,datetime,hashlib,json,pathlib,shlex,paramiko
B=pathlib.Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('--stage',choices=['confirmation','confirmation_partial','wait_confirmation'],required=True);ap.add_argument('--family',choices=['trace','order','wait'],required=True);a=ap.parse_args()
D=B/'confirmation_processing_20261105';O=B/'analysis_extensions/window_diagnostic_20261105';O.mkdir(exist_ok=True)
if a.stage!='wait_confirmation':
 early=B/'analysis_extensions/early_confirm_20261105'/('EARLY_'+a.stage.upper()+'_'+a.family.upper()+'.json')
 receipt=json.loads(early.with_name(early.name+'.RECEIPT.json').read_text());assert hashlib.sha256(early.read_bytes()).hexdigest()==receipt['sha256']
cfg=json.loads((D/'REMOTE_CONFIG.json').read_text());root=cfg['remote_root']
c=paramiko.SSHClient();c.load_system_host_keys();c.set_missing_host_key_policy(paramiko.RejectPolicy());c.connect(cfg['host'],port=cfg['port'],username=cfg['user'],key_filename=cfg['key'],timeout=15);sf=c.open_sftp()
def run(cmd):
 i,o,e=c.exec_command(cmd,timeout=90);out=o.read().decode();err=e.read().decode();return {'returncode':o.channel.recv_exit_status(),'stdout':out,'stderr':err}
try:
 for name in ['remote_execution_window_eval.py','execution_window_features.py','EXECUTION_WINDOW_PROTOCOL.md']:sf.put(str(B/name),root+'/'+name)
 sf.put(str(B/'analysis_extensions/EXECUTION_WINDOW_MODELS.json'),root+'/EXECUTION_WINDOW_MODELS.json')
 cmd='env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 nice -n 19 python '+shlex.quote(root+'/remote_execution_window_eval.py')+' --root '+shlex.quote(root)+' --stage '+a.stage+' --family '+a.family
 z=run(cmd);tag=a.stage+'_'+a.family;(O/(tag+'_COMMAND.json')).write_text(json.dumps(z,indent=2),encoding='utf-8')
 if z['returncode']:raise RuntimeError(z['stderr'])
 name='WINDOW_DIAGNOSTIC_'+a.stage.upper()+'_'+a.family.upper()+'.json';p=O/name
 assert not p.exists(),'preserve existing result; inspect instead of silently overwriting'
 sf.get(root+'/'+name,str(p));h=run('sha256sum '+shlex.quote(root+'/'+name));assert h['returncode']==0
 digest=hashlib.sha256(p.read_bytes()).hexdigest();assert digest==h['stdout'].split()[0]
 receipt={'sha256':digest,'bytes':p.stat().st_size,'node':cfg['id'],'remote_root':root,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'models_fixed':True,'diagnostic_channel_not_checked':True,'command':cmd}
 p.with_name(name+'.RECEIPT.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8');print(json.dumps({'result':str(p),'sha256':digest,'summary':z['stdout']}))
finally:sf.close();c.close()
