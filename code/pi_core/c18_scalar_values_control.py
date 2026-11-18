from pathlib import Path
import json,hashlib,paramiko,shlex,datetime
B=Path(__file__).resolve().parent;O=B/'analysis_extensions/coarse_observation_20261105';cfg=json.loads((B/'confirmation_processing_20261105/REMOTE_CONFIG.json').read_text(encoding='utf-8-sig'));R=cfg['remote_root'];sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();p=O/'C18_SCALAR_VALUES.json';assert not p.exists()
c=paramiko.SSHClient();c.load_system_host_keys();c.set_missing_host_key_policy(paramiko.RejectPolicy());c.connect(cfg['host'],port=cfg['port'],username=cfg['user'],key_filename=cfg['key'],timeout=15);sf=c.open_sftp()
def run(cmd):
 i,o,e=c.exec_command(cmd,timeout=60);out=o.read().decode();err=e.read().decode();return {'returncode':o.channel.recv_exit_status(),'stdout':out,'stderr':err}
try:
 sf.put(str(B/'remote_c18_scalar_values.py'),R+'/remote_c18_scalar_values.py');cmd='env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 nice -n 19 python '+shlex.quote(R+'/remote_c18_scalar_values.py')+' --root '+shlex.quote(R);z=run(cmd);(O/'C18_SCALAR_VALUES_COMMAND.json').write_text(json.dumps({'command':cmd,**z},indent=2),encoding='utf-8',newline='');assert z['returncode']==0,z
 sf.get(R+'/'+p.name,str(p));h=run('sha256sum '+shlex.quote(R+'/'+p.name));assert h['returncode']==0 and sha(p)==h['stdout'].split()[0];j=json.loads(p.read_text());assert j['code_sha256']==sha(B/'remote_c18_scalar_values.py');p.with_name(p.name+'.RECEIPT.json').write_text(json.dumps({'sha256':sha(p),'bytes':p.stat().st_size,'node':cfg['id'],'remote_root':R,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()},indent=2),encoding='utf-8',newline='');print(z['stdout'])
finally:sf.close();c.close()
