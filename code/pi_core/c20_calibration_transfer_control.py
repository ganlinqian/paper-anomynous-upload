from pathlib import Path
import argparse,datetime,hashlib,json,shlex,paramiko
B=Path(__file__).resolve().parent;A=B/'analysis_extensions';D=B/'untraced_processing_20261105';O=A/'calibration_transfer_20261105';O.mkdir(exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
ap=argparse.ArgumentParser();ap.add_argument('action',choices=['freeze','evaluate']);a=ap.parse_args()
model=A/'early_burst_wait_20261105/C10_CALIBRATION_MODELS_RECONSTRUCTED.json';assert sha(model)=='ec83b153b44292f7b506f110ef6a6850bd8575e5128f23629b17aa75d9914f1a'
protocol=B/'C20_CALIBRATION_TRANSFER_PROTOCOL.md';code=B/'remote_c20_calibration_transfer.py';freeze=O/'C20_FREEZE.json'
if a.action=='freeze':
 assert not freeze.exists() and not (D/'analysis/UNTRACED_WAIT_EVALUATION.json').exists()
 state=read(D/'STATUS.json');assert state['phase']=='transfer_F' and state['completed']<64
 z={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'models_sha256':sha(model),'model_export_utc':read(model)['utc'],'protocol_sha256':sha(protocol),'code_sha256':sha(code),'controller_sha256':sha(Path(__file__)),'C13_status_at_freeze':state,'C13_model_predictions_read':False,'C13_collection_already_complete':True,'all_14_saved_models_reported':True,'no_refit':True}
 freeze.write_text(json.dumps(z,indent=2),encoding='utf-8',newline='');print(json.dumps({'path':str(freeze),'sha256':sha(freeze),'utc':z['utc']}));raise SystemExit(0)
f=read(freeze);assert all(f[k]==sha(p) for k,p in [('models_sha256',model),('protocol_sha256',protocol),('code_sha256',code)])
assert read(D/'STATUS.json')['phase']=='awaiting_authorized_bridge_release' and read(D/'LOCAL_RESULTS_RECEIPT.json')['verified']
cfg=read(D/'REMOTE_CONFIG.json');root=cfg['remote_root'];c=paramiko.SSHClient();c.load_system_host_keys();c.set_missing_host_key_policy(paramiko.RejectPolicy());c.connect(cfg['host'],port=cfg['port'],username=cfg['user'],key_filename=cfg['key'],timeout=15);s=c.open_sftp()
try:
 for p in [model,protocol,code,freeze]:s.put(str(p),root+'/'+p.name)
 cmd='env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 nice -n 19 python '+shlex.quote(root+'/'+code.name)+' --root '+shlex.quote(root)
 i,o,e=c.exec_command(cmd,timeout=90);stdout=o.read().decode();stderr=e.read().decode();rc=o.channel.recv_exit_status();z={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'command':cmd,'returncode':rc,'stdout':stdout,'stderr':stderr,'node':cfg['id'],'remote_root':root};(O/'COMMAND.json').write_text(json.dumps(z,indent=2),encoding='utf-8',newline='')
 if rc:raise RuntimeError(stderr)
 name='C20_CALIBRATION_TRANSFER_C13.json';p=O/name;assert not p.exists();s.get(root+'/'+name,str(p));i,o,e=c.exec_command('sha256sum '+shlex.quote(root+'/'+name));remote=o.read().decode();assert o.channel.recv_exit_status()==0 and sha(p)==remote.split()[0]
 j=read(p);assert j['models_sha256']==sha(model) and j['freeze_sha256']==sha(freeze) and j['raw_source_hashes_verified']==64 and len(j['models'])==14
 (O/(name+'.RECEIPT.json')).write_text(json.dumps({'utc':z['utc'],'sha256':sha(p),'bytes':p.stat().st_size,'code_sha256':sha(code),'node':cfg['id'],'remote_root':root},indent=2),encoding='utf-8',newline='')
 print(json.dumps({'path':str(p),'sha256':sha(p),'scores':{k:v['task_conditioned'] for k,v in j['models'].items()}}))
finally:s.close();c.close()
