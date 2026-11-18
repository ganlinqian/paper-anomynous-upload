import hashlib,json,pathlib,shlex,sys,time,paramiko
B=pathlib.Path(__file__).resolve().parent
q=B/'CHANNEL_AUDIT_PICK.stdout.log';raw=q.read_bytes();cfg=json.loads(raw.decode('utf-16' if raw.startswith(b'\xff\xfe') else 'utf-8-sig'))
root='/cache/telltale_ws_pi/extensions_20261104_181126'
c=paramiko.SSHClient();c.load_system_host_keys();c.set_missing_host_key_policy(paramiko.RejectPolicy());c.connect(cfg['host'],port=cfg['port'],username=cfg['user'],key_filename=cfg['key'],timeout=15);sf=c.open_sftp()
def run(cmd):
 i,o,e=c.exec_command(cmd,timeout=30);out=o.read().decode();err=e.read().decode();rc=o.channel.recv_exit_status();assert rc==0,(rc,err);return out
if sys.argv[1]=='start':
 sf.put(str(B/'remote_channel_audit.py'),root+'/remote_channel_audit.py')
 cmd='nohup env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 nice -n 10 python -u '+root+'/remote_channel_audit.py >'+root+'/channel_audit.stdout.log 2>'+root+'/channel_audit.stderr.log </dev/null & echo $!'
 pid=int(run(cmd).strip());receipt={'pid':pid,'command':cmd,'root':root,'cfg':cfg,'ps':run('ps -p '+str(pid)+' -o pid,args'),'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())};(B/'CHANNEL_AUDIT_LAUNCH.json').write_text(json.dumps(receipt,indent=2));print(json.dumps({'pid':pid,'node':cfg['id'],'root':root}))
 with (B.parent.parent/'REMOTE_JOBS.md').open('a',encoding='utf-8') as f:f.write('\n## Diagnostic-channel audit '+receipt['utc']+'\nNode '+cfg['id']+' '+cfg['host']+':'+str(cfg['port'])+'; root '+root+'; PID '+str(pid)+'; CPU4/numeric1; expected <3min. Launch and logs results/scenario_rf_20261104/CHANNEL_AUDIT_LAUNCH.json; remote channel_audit.stdout.log/.stderr.log. No raw reprocessing; exploratory, no primary model changes.\n')
elif sys.argv[1]=='fetch':
 out=B/'analysis_extensions/CHANNEL_AUDIT.json';sf.get(root+'/CHANNEL_AUDIT.json',str(out));s=run('sha256sum '+root+'/CHANNEL_AUDIT.json').split()[0];assert hashlib.sha256(out.read_bytes()).hexdigest()==s
 (B/'analysis_extensions/CHANNEL_AUDIT_RECEIPT.json').write_text(json.dumps({'sha256':s,'bytes':out.stat().st_size,'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'note':'remote source and local digest agree'},indent=2));d=json.loads(out.read_text());print(json.dumps({s:{ch:{k:dict((a,v['task_conditioned'][a]) for a in ['tp','fn','fp','tn','auc']) for k,v in m.items()} for ch,m in z['channels'].items()} for s,z in d['stages'].items()}))
sf.close();c.close()
