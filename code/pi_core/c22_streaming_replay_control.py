from pathlib import Path
import hashlib,json,paramiko,shlex,datetime
B=Path(__file__).resolve().parent;D=B/'untraced_processing_20261105';A=B/'analysis_extensions';O=A/'streaming_replay_20261105';O.mkdir(exist_ok=True)
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'));sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert read(D/'LOCAL_RESULTS_RECEIPT.json')['verified'] and read(D/'STATUS.json')['phase']=='awaiting_authorized_bridge_release'
cfg=read(D/'REMOTE_CONFIG.json');mcfg=read(B/'confirmation_processing_20261105/REMOTE_CONFIG.json')
assert all(cfg[k]==mcfg[k] for k in ['id','host','port','user']),'No cross-node fallback or copy authorized by this replay'
root=cfg['remote_root']+'/C22_streaming_replay';data=mcfg['remote_root'];p=O/'C22_STREAMING_REPLAY.json';assert not p.exists()
c=paramiko.SSHClient();c.load_system_host_keys();c.set_missing_host_key_policy(paramiko.RejectPolicy());c.connect(cfg['host'],port=cfg['port'],username=cfg['user'],key_filename=cfg['key'],timeout=15);s=c.open_sftp()
try:
 try:s.mkdir(root)
 except IOError:s.stat(root)
 for local,name in [(A/'coarse_observation_20261105/COARSE_OBSERVATION_ABLATION_MODELS.json','MODELS.json'),(A/'coarse_observation_20261105/C18_SCALAR_VALUES.json','SCALARS.json'),(B/'C22_STREAMING_REPLAY_PROTOCOL.md','PROTOCOL.md'),(B/'remote_c22_streaming_replay.py','remote_c22_streaming_replay.py')]:s.put(str(local),root+'/'+name)
 cmd='env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 nice -n 19 python '+shlex.quote(root+'/remote_c22_streaming_replay.py')+' --data-root '+shlex.quote(data)+' --output-root '+shlex.quote(root)
 i,o,e=c.exec_command(cmd,timeout=160);stdout=o.read().decode();stderr=e.read().decode();rc=o.channel.recv_exit_status();z={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'command':cmd,'returncode':rc,'stdout':stdout,'stderr':stderr,'node':cfg['id'],'remote_root':root};(O/'COMMAND.json').write_text(json.dumps(z,indent=2),encoding='utf-8',newline='')
 assert rc==0,z
 s.get(root+'/'+p.name,str(p));i,o,e=c.exec_command('sha256sum '+shlex.quote(root+'/'+p.name));rh=o.read().decode();assert o.channel.recv_exit_status()==0 and sha(p)==rh.split()[0]
 j=read(p);assert j['raw_files']==80 and j['prediction_agreement']==80 and j['code_sha256']==sha(B/'remote_c22_streaming_replay.py')
 (O/(p.name+'.RECEIPT.json')).write_text(json.dumps({'utc':z['utc'],'sha256':sha(p),'bytes':p.stat().st_size,'node':cfg['id'],'remote_root':root},indent=2),encoding='utf-8',newline='')
 print(json.dumps({k:v for k,v in j.items() if k not in ['predictions','benchmark']}))
finally:s.close();c.close()
