import datetime,hashlib,json,pathlib,shlex,sys,paramiko
B=pathlib.Path(__file__).resolve().parent
raw=(B/'RELATIVE_PICK.stdout.log').read_bytes();cfg=json.loads(raw.decode('utf-16' if raw.startswith(b'\xff\xfe') else 'utf-8-sig'))
c=paramiko.SSHClient();c.load_system_host_keys();c.set_missing_host_key_policy(paramiko.RejectPolicy());c.connect(cfg['host'],port=cfg['port'],username=cfg['user'],key_filename=cfg['key'],timeout=15);sf=c.open_sftp()
def run(cmd):
 i,o,e=c.exec_command(cmd,timeout=30);out=o.read().decode();err=e.read().decode();rc=o.channel.recv_exit_status();assert rc==0,(rc,err);return out
stamp=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
if sys.argv[1]=='start':
 root='/cache/telltale_ws_pi/relative_export_'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d_%H%M%S');run('mkdir -p '+shlex.quote(root+'/features'))
 for name in ('export_relative_reference.py','relative_reference_features.py','remote_extensions.py','remote_evaluate.py','RELATIVE_REFERENCE_PROTOCOL.md'):sf.put(str(B/name),root+'/'+name)
 for name in ('CONFIRMATION_MODELS.json','WAIT_CONFIRMATION_MODELS.json'):sf.put(str(B/'analysis_extensions'/name),root+'/'+name)
 sources=B/'analysis_extensions/full_20261105';rows=json.loads((sources/'LEDGER.json').read_text())['records'];ids=set()
 a=json.loads((B/'analysis_extensions/CONFIRMATION_MODELS.json').read_text());w=json.loads((B/'analysis_extensions/WAIT_CONFIRMATION_MODELS.json').read_text())
 for m in list(a['families'].values())+[w]:ids.update(m['training_ids'])
 train=[x for x in rows if x['id'] in ids];assert len(train)==40
 p=B/'RELATIVE_TRAINING_LEDGER.json';p.write_text(json.dumps({'records':train}));sf.put(str(p),root+'/LEDGER.json')
 for x in train:sf.put(str(sources/'features'/(x['id']+'_930c.npz')),root+'/features/'+x['id']+'_930c.npz')
 cmd='nohup env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 nice -n 10 python -u '+root+'/export_relative_reference.py >'+root+'/export.stdout.log 2>'+root+'/export.stderr.log </dev/null & echo $!'
 pid=int(run(cmd).strip());receipt={'pid':pid,'command':cmd,'root':root,'cfg':cfg,'ps':run('ps -p '+str(pid)+' -o pid,args'),'utc':stamp(),'training_n':40};(B/'RELATIVE_EXPORT_LAUNCH.json').write_text(json.dumps(receipt,indent=2))
 with (B.parent.parent/'REMOTE_JOBS.md').open('a',encoding='utf-8') as f:f.write('\n## Relative-reference secondary export '+stamp()+'\nNode '+cfg['id']+' '+cfg['host']+':'+str(cfg['port'])+'; root '+root+'; PID '+str(pid)+'; CPU1/numeric1; expected <3min. No new-campaign inputs. Launch: results/scenario_rf_20261104/RELATIVE_EXPORT_LAUNCH.json; logs export.stdout.log/.stderr.log.\n')
 print(json.dumps({'pid':pid,'root':root,'node':cfg['id'],'training_n':40}))
elif sys.argv[1]=='fetch':
 launch=json.loads((B/'RELATIVE_EXPORT_LAUNCH.json').read_text());root=launch['root'];p=B/'analysis_extensions/RELATIVE_REFERENCE_MODELS.json'
 try:sf.get(root+'/RELATIVE_REFERENCE_MODELS.json',str(p))
 except Exception:
  print(run('tail -c 3000 '+root+'/export.stderr.log'));raise
 digest=run('sha256sum '+root+'/RELATIVE_REFERENCE_MODELS.json').split()[0];assert sha(p)==digest
 d=json.loads(p.read_text());assert d['feature_code_sha256']==sha(B/'relative_reference_features.py') and d['protocol_sha256']==sha(B/'RELATIVE_REFERENCE_PROTOCOL.md')
 receipt={'sha256':digest,'bytes':p.stat().st_size,'export_created_utc':d['created_utc'],'retrieved_utc':stamp(),'new_campaign_feature_accessed':False,'scope':'new C08 was collecting; no RF features/results from it used; old train40 only'}
 (B/'analysis_extensions/RELATIVE_REFERENCE_RECEIPT.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
sf.close();c.close()
