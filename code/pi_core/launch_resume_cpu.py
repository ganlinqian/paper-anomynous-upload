import json,pathlib,shlex,sys,paramiko
B=pathlib.Path(__file__).resolve().parent;sys.path.insert(0,str(B/'burst_study'));from bridge_utils import *
cfg=json.loads((B/'EXTENSION_REMOTE.json').read_text());root=cfg['remote_root'];c=paramiko.SSHClient();c.load_system_host_keys();c.set_missing_host_key_policy(paramiko.RejectPolicy());c.connect(cfg['host'],port=cfg['port'],username=cfg['user'],key_filename=cfg['key'],timeout=15);s=c.open_sftp()
try:
 s.put(str(B/'remote_resume_extract.py'),root+'/remote_resume_extract.py');cmd='cd '+shlex.quote(root)+' && nohup env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python -u remote_resume_extract.py >resume_extract_20261105.log 2>&1 </dev/null & echo $!';ret=run(c,cmd,timeout=20);pid=int(ret['stdout'].strip());check=run(c,'ps -p '+str(pid)+' -o pid,args',check=False);save(B/'RESUME_CPU_LAUNCH.json',{'pid':pid,'command':cmd,'ps':check,'utc':stamp(),'reservation':'92144231a6','root':root});print(json.dumps({'pid':pid,'ps':check,'root':root}))
finally:s.close();c.close()
