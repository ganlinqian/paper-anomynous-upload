import json,pathlib,shlex,sys,time,paramiko
from confirmation_pipeline_utils import Pipe,B,connect,save,sha,stamp,run,lower_priority
class SustainedPipe(Pipe):
 def __init__(self):
  lower_priority();self.out=B/'sustained_processing_20261105';self.out.mkdir(exist_ok=False);self.deadline=time.monotonic()+18000;self.c=self.sf=self.w=self.wf=None;self.cfg=None;self.root=None
 def source_hash(self,files,drive):
  assert drive=='F' and len(files)==48
  self.w=connect('192.0.2.4','win');self.wf=self.w.open_sftp();folder=self.out/'F';folder.mkdir();save(folder/'MANIFEST.json',{'files':files});spool='F:/Data/telltale_sustained_hash_'+time.strftime('%Y%m%d_%H%M%S',time.gmtime());self.wf.mkdir(spool);self.wf.put(str(B/'source_receipt.py'),spool+'/source_receipt.py');self.wf.put(str(folder/'MANIFEST.json'),spool+'/MANIFEST.json');self.state('source_hash_F_48',files=48,win4_spool=spool)
  code="import json,os,pathlib,runpy,sys;d=pathlib.Path(__file__).resolve().parent;(d/'HASH_PID.json').write_text(json.dumps({'pid':os.getpid()}));sys.argv=[str(d/'source_receipt.py'),str(d/'MANIFEST.json')];runpy.run_path(str(d/'source_receipt.py'),run_name='__main__')"
  with self.wf.open(spool+'/hash_owned.py','w') as f:f.write(code)
  z=run(self.w,'python -X utf8 '+spool+'/hash_owned.py',timeout=1800);save(folder/'HASH_COMMAND.json',z);assert z['rc']==0;self.wf.get(spool+'/SOURCE_RECEIPTS.json',str(folder/'SOURCE_RECEIPTS.json'));h=json.loads((folder/'SOURCE_RECEIPTS.json').read_text(encoding='utf-8-sig'));assert len(h['files'])==48;save(folder/'HASH_COMPLETE.json',{'utc':stamp(),'files':48,'spool':spool});return h['files']
 def allocate(self):
  p=self.out/'BRIDGE_PICK.json';self.wait(lambda:p.exists(),'awaiting_authorized_bridge_CPU_pick');self.cfg=json.loads(p.read_text(encoding='utf-8-sig'));assert self.cfg['cores']==2 and self.cfg['mem_gb']>=8
  self.root='/cache/telltale_ws_pi/sustained_'+time.strftime('%Y%m%d_%H%M%S',time.gmtime());self.cfg['remote_root']=self.root;save(self.out/'REMOTE_CONFIG.json',self.cfg)
  self.c=paramiko.SSHClient();self.c.load_system_host_keys();self.c.set_missing_host_key_policy(paramiko.RejectPolicy());self.c.connect(self.cfg['host'],port=self.cfg['port'],username=self.cfg['user'],key_filename=self.cfg['key'],timeout=15);self.c.get_transport().set_keepalive(20);self.sf=self.c.open_sftp();self.sf.get_channel().settimeout(60)
  save(self.out/'REMOTE_ENV.json',run(self.c,"hostname; python -c 'import numpy,scipy,sklearn;print(numpy.__version__)'"));run(self.c,'mkdir -p '+shlex.quote(self.root+'/raw')+' '+shlex.quote(self.root+'/features'))
  for n in ['remote_extract_confirmation.py','remote_extensions.py','remote_evaluate.py','remote_sustained_burst_eval.py','remote_package_sustained_burst.py']:self.sf.put(str(B/n),self.root+'/'+n)
  self.sf.put(str(B/'analysis_extensions/BURST_EXPLORATORY_FREEZE.json'),self.root+'/BURST_EXPLORATORY_FREEZE.json')
  (self.out/'ssh_config').write_text('Host claw-confirm-rig\n HostName 192.0.2.4\n User win\n Port 22\n IdentityFile <SSH_KEY>\n StrictHostKeyChecking yes\n Compression no\nHost claw-confirm-cpu\n HostName '+self.cfg['host']+'\n User '+self.cfg['user']+'\n Port '+str(self.cfg['port'])+'\n IdentityFile '+self.cfg['key']+'\n StrictHostKeyChecking yes\n Compression no\n',encoding='utf-8',newline='')
 def start(self):
  r=self.root;cmd='nohup env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 nice -n 10 python -u '+shlex.quote(r+'/remote_extract_confirmation.py')+' --root '+shlex.quote(r)+' --workers 2 >'+shlex.quote(r+'/extract.stdout.log')+' 2>'+shlex.quote(r+'/extract.stderr.log')+' </dev/null & echo $!'
  z=run(self.c,cmd,timeout=20);pid=int(z['stdout'].strip());save(self.out/'LAUNCH.json',{'pid':pid,'command':cmd,'utc':stamp(),'ps':run(self.c,'ps -p '+str(pid)+' -o pid,args')})
  with (B.parent.parent/'REMOTE_JOBS.md').open('a',encoding='utf-8') as f:f.write('\n## Sustained C15 CPU job '+stamp()+'\nNode '+self.cfg['id']+' '+self.cfg['host']+':'+str(self.cfg['port'])+'; root '+r+'; PID '+str(pid)+'; workers2/numeric1, 48IQ/7.68GB, expected <35min. Launch and logs: results/scenario_rf_20261104/sustained_processing_20261105/LAUNCH.json; remote extract.stdout.log/.stderr.log. C13 CPU job fully verified and released before fresh selection.\n')
