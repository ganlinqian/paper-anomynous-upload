from pathlib import Path
import datetime,hashlib,json,shlex,paramiko
B=Path(__file__).resolve().parent;O=B/'analysis_extensions/early_burst_wait_20261105';p=O/'BURST_CONFIRMATION_DETAILS.json';assert not p.exists()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
cfg=json.loads((B/'confirmation_processing_20261105/REMOTE_CONFIG.json').read_text(encoding='utf-8-sig'));root=cfg['remote_root'];c=paramiko.SSHClient();c.load_system_host_keys();c.set_missing_host_key_policy(paramiko.RejectPolicy());c.connect(cfg['host'],port=cfg['port'],username=cfg['user'],key_filename=cfg['key'],timeout=15);c.get_transport().set_keepalive(20);sf=c.open_sftp()
try:
 sf.put(str(B/'remote_burst_confirmation_details.py'),root+'/remote_burst_confirmation_details.py');cmd='env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 nice -n 19 python '+shlex.quote(root+'/remote_burst_confirmation_details.py')+' --root '+shlex.quote(root)
 try:sf.stat(root+'/BURST_CONFIRMATION_DETAILS.json');existing=True
 except FileNotFoundError:existing=False
 if not existing:
  i,o,e=c.exec_command(cmd,timeout=60);stdout=o.read().decode();stderr=e.read().decode();rc=o.channel.recv_exit_status()
 else:stdout='reuse immutable remote result';stderr='';rc=0
 (O/'BURST_DETAILS_COMMAND.json').write_text(json.dumps({'command':cmd,'rc':rc,'stdout':stdout,'stderr':stderr,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()},indent=2),encoding='utf-8',newline='');assert rc==0,stderr
 sf.get(root+'/BURST_CONFIRMATION_DETAILS.json',str(p));i,o,e=c.exec_command('sha256sum '+shlex.quote(root+'/BURST_CONFIRMATION_DETAILS.json'),timeout=15);h=o.read().decode().split()[0];assert o.channel.recv_exit_status()==0 and sha(p)==h
 j=json.loads(p.read_text(encoding='utf-8-sig'));assert len(j['rows'])==72 and j['evaluation_code_sha256']==sha(B/'remote_burst_confirmation_details.py')
 receipt={'file':p.name,'sha256':sha(p),'bytes':p.stat().st_size,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'node':cfg['id'],'root':root,'code_sha256':sha(B/'remote_burst_confirmation_details.py')};p.with_name(p.name+'.RECEIPT.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8',newline='');print(json.dumps(receipt))
finally:sf.close();c.close()
