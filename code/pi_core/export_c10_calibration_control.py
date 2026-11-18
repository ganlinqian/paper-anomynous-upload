import pathlib,json,hashlib,datetime,shlex,paramiko
B=pathlib.Path(__file__).resolve().parent;D=B/'confirmation_processing_20261105';O=B/'analysis_extensions/early_burst_wait_20261105';cfg=json.loads((D/'REMOTE_CONFIG.json').read_text(encoding='utf-8-sig'));R=cfg['remote_root'];name='C10_CALIBRATION_MODELS_RECONSTRUCTED.json';p=O/name;sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
if p.exists():
 r=json.loads(p.with_name(name+'.RECEIPT.json').read_text(encoding='utf-8-sig'));assert sha(p)==r['sha256'];print(json.dumps({'already_verified':str(p),'sha256':sha(p)}));raise SystemExit(0)
assert (O/'EARLY_WAIT_CONFIRMATION.json').exists()
c=paramiko.SSHClient();c.load_system_host_keys();c.set_missing_host_key_policy(paramiko.RejectPolicy());c.connect(cfg['host'],port=cfg['port'],username=cfg['user'],key_filename=cfg['key'],timeout=15);c.get_transport().set_keepalive(20);sf=c.open_sftp();sf.get_channel().settimeout(60)
def run(cmd):
 i,o,e=c.exec_command(cmd,timeout=90);out=o.read().decode();err=e.read().decode();return {'returncode':o.channel.recv_exit_status(),'stdout':out,'stderr':err}
try:
 sf.put(str(B/'remote_export_c10_calibration.py'),R+'/remote_export_c10_calibration.py')
 cmd='env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 nice -n 19 python '+shlex.quote(R+'/remote_export_c10_calibration.py')+' --root '+shlex.quote(R)
 try:sf.stat(R+'/'+name);exists=True
 except FileNotFoundError:exists=False
 z={'returncode':0,'stdout':'reusing remote parameter artifact','stderr':''} if exists else run(cmd)
 z.update(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),command=cmd,code_sha256=sha(B/'remote_export_c10_calibration.py'))
 (O/'C10_CALIBRATION_EXPORT_COMMAND.json').write_text(json.dumps(z,indent=2),encoding='utf-8',newline='')
 assert z['returncode']==0,z
 pending=p.with_suffix('.json.pending');sf.get(R+'/'+name,str(pending));h=run('sha256sum '+shlex.quote(R+'/'+name));assert h['returncode']==0 and sha(pending)==h['stdout'].split()[0]
 j=json.loads(pending.read_text(encoding='utf-8-sig'));assert len(j['models'])==14 and j['max_heldout_probability_difference']<1e-12 and j['code_sha256']==sha(B/'remote_export_c10_calibration.py');assert j['source_evaluation_sha256']==sha(O/'EARLY_WAIT_CONFIRMATION.json');pending.replace(p)
 r={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'sha256':sha(p),'bytes':p.stat().st_size,'node':cfg['id'],'remote_root':R,'parameter_reconstruction_only':True,'heldout_predictions_matched':True,'model_count':14}
 p.with_name(name+'.RECEIPT.json').write_text(json.dumps(r,indent=2),encoding='utf-8',newline='');print(json.dumps(r))
finally:sf.close();c.close()
