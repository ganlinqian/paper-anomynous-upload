from pathlib import Path
import datetime,hashlib,json,shlex,paramiko
B=Path(__file__).resolve().parent;O=B/'analysis_extensions/model_response_20261105';O.mkdir(exist_ok=True);p=O/'MODEL_RESPONSE_AUDIT.json';assert not p.exists()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
cfg=json.loads((B/'confirmation_processing_20261105/REMOTE_CONFIG.json').read_text(encoding='utf-8-sig'));root=cfg['remote_root'];c=paramiko.SSHClient();c.load_system_host_keys();c.set_missing_host_key_policy(paramiko.RejectPolicy());c.connect(cfg['host'],port=cfg['port'],username=cfg['user'],key_filename=cfg['key'],timeout=15);c.get_transport().set_keepalive(20);sf=c.open_sftp()
try:
 for n in ['remote_model_response_audit.py','MODEL_RESPONSE_AUDIT_PROTOCOL.md']:sf.put(str(B/n),root+'/'+n)
 cmd='env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 nice -n 19 python '+shlex.quote(root+'/remote_model_response_audit.py')+' --root '+shlex.quote(root)
 try:sf.stat(root+'/MODEL_RESPONSE_AUDIT.json');existing=True
 except FileNotFoundError:existing=False
 if not existing:
  i,o,e=c.exec_command(cmd,timeout=60);stdout=o.read().decode();stderr=e.read().decode();rc=o.channel.recv_exit_status()
 else:stdout='reuse immutable remote result';stderr='';rc=0
 (O/'COMMAND.json').write_text(json.dumps({'command':cmd,'rc':rc,'stdout':stdout,'stderr':stderr,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'code_sha256':sha(B/'remote_model_response_audit.py')},indent=2),encoding='utf-8',newline='');assert rc==0,stderr
 sf.get(root+'/MODEL_RESPONSE_AUDIT.json',str(p));i,o,e=c.exec_command('sha256sum '+shlex.quote(root+'/MODEL_RESPONSE_AUDIT.json'),timeout=15);h=o.read().decode().split()[0];assert o.channel.recv_exit_status()==0 and sha(p)==h
 j=json.loads(p.read_text(encoding='utf-8-sig'));assert j['raw_sources_verified']==40 and j['code_sha256']==sha(B/'remote_model_response_audit.py') and j['protocol_sha256']==sha(B/'MODEL_RESPONSE_AUDIT_PROTOCOL.md')
 receipt={'file':p.name,'sha256':sha(p),'bytes':p.stat().st_size,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'node':cfg['id'],'root':root,'code_sha256':sha(B/'remote_model_response_audit.py')};p.with_name(p.name+'.RECEIPT.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8',newline='');print(json.dumps({'receipt':receipt,'models':{k:{'identity':z['identity'],'reverse':z['reverse'],'distribution':z['correct_count_distribution']} for k,z in j['models'].items()},'gain_slopes':j['uniform_db_direction_slope']}))
finally:sf.close();c.close()
