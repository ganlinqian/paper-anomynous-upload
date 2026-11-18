import hashlib,http.server,json,os,pathlib,random,shlex,sys,threading,time,traceback
B=pathlib.Path(__file__).resolve().parent;sys.path.insert(0,str(B.parent/'burst_study'));from bridge_utils import *
sys.path.insert(1,str(B.parent));from collect import Rig
SEED=b'Telltale:C07:20261104:fixture:v1';SIZE=16*1024*1024
class Handler(http.server.BaseHTTPRequestHandler):
 protocol_version='HTTP/1.1'
 def log_message(self,*args):pass
 def do_GET(self):
  token=self.headers.get('X-TT-Token','');values=self.server.registry.get(token);event={'token':token,'path':self.path,'request_headers':dict(self.headers),'client':self.client_address,'begin_desktop_ns':time.perf_counter_ns()}
  if self.path!='/approved/package' or values is None:self.send_error(403);return
  time.sleep(4);body=json.dumps({'values':values},sort_keys=True,separators=(',',':')).encode();self.send_response_only(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body);self.wfile.flush();event.update(end_desktop_ns=time.perf_counter_ns(),status=200,response_sha256=hashlib.sha256(body).hexdigest(),response_body=body.decode());self.server.events.append(event)

def main():
 lower_priority();campaign='waitconfirm_'+time.strftime('%Y%m%d_%H%M%S',time.gmtime())+'_'+os.urandom(3).hex();d=B/campaign;d.mkdir();save(B/'LATEST.json',{'directory':str(d),'campaign':campaign});pr='/home/pi/telltale_scenarios_rf_20261104/'+campaign;wr='<DATA>/telltale_wait_confirmation_20261105/'+campaign;lock='/home/pi/telltale_g1_20261026/controller.lock';p=w=pf=wf=rig=li=lo=le=wi=wo=we=server=None;pid=None;old=None;changed=False;rows=[]
 try:
  if not (B.parent/'wait_transfer/WAIT_UPLOAD_COMPLETE.json').exists():raise RuntimeError('J source transfer still active')
  prev=pathlib.Path(json.loads((B.parent/'burst_confirmation_study/LATEST.json').read_text())['directory']);assert (prev/'COMPLETE.json').exists();assert json.loads((prev/'POSTFLIGHT.json').read_text())['restore']['rc']==0
  assert sha(B.parent/'analysis_extensions/WAIT_CONFIRMATION_MODELS.json')=='2c802e7b01ee7b48cf17fee742f033f1267f557b272408db3a29fb1b352460d3'
  p=connect('192.0.2.60','admin',522);w=connect('192.0.2.4','win');pf=p.open_sftp();wf=w.open_sftp();pre=guard(p);old=pre['state'].splitlines()[:3]
  busy=run(p,"pgrep -af '^(perf|strace|resident_tool|python3.*telltale)' || true")['stdout']
  if busy.strip():raise RuntimeError('Pi occupied '+busy)
  code='import os,fcntl,sys\np='+repr(lock)+'\nfd=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)\ntry:\n fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)\n os.write(fd,'+repr(campaign.encode())+')\n print(\'LOCKED\',flush=True)\n sys.stdin.read()\nfinally:\n os.close(fd)\n if open(p).read()=='+repr(campaign)+':os.unlink(p)\n';li,lo,le=p.exec_command('python3 -u -c '+shlex.quote(code),timeout=30)
  if lo.readline().strip()!='LOCKED':raise RuntimeError('Pi lock '+le.read().decode())
  run(p,'mkdir -p '+pr);pf.put(str(B/'pi_api.py'),pr+'/pi_api.py');fixture=hashlib.shake_256(SEED).digest(SIZE);input_sha=hashlib.sha256(fixture).hexdigest();(d/'fixture.sha256').write_text(input_sha);gen='import hashlib,pathlib;pathlib.Path('+repr(pr+'/fixture.bin')+').write_bytes(hashlib.shake_256('+repr(SEED)+').digest('+str(SIZE)+'))';run(p,'python3 -c '+shlex.quote(gen));del fixture
  run(p,'test $(df -Pk '+pr+" | awk 'NR==2 {print $4}') -gt 2097152")
  server=http.server.ThreadingHTTPServer(('192.0.2.39',0),Handler);server.daemon_threads=True;server.registry={};server.events=[];threading.Thread(target=server.serve_forever,daemon=True).start();port=server.server_address[1]
  run(p,"sudo -n sh -c 'echo performance > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor; echo 1800000 > /sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq'");changed=True
  def start_worker(ident,actual,request,cover=False):
   nonlocal wi,wo,we,pid
   stem=pr+'/'+ident;config={'cover_code':'YES_' if cover else 'NO__','activity_code':'A___' if actual else 'Q___','input_path':pr+'/fixture.bin','output_path':stem+'.gz','input_sha256':input_sha,'port':port};td=d/'records'/ident;td.mkdir(parents=True);save(td/'private_config.json',config);pf.put(str(td/'private_config.json'),stem+'.json');cmd='env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 nice -n 10 strace -f -qq -ttt -T -yy -s 4096 -e trace=execve,openat,network -o '+stem+'.strace python3 -u '+pr+'/pi_api.py --private-config '+stem+'.json';wi,wo,we=p.exec_command(cmd,timeout=20);ready=json.loads(wo.readline());pid=ready['pid'];assert ready['ready'] and ready['input_sha256']==input_sha;return stem,td,ready
  def finish_worker(stem,td):
   nonlocal wi,wo,we,pid
   wi.write('{"research_flush":true}\n');wi.flush();wi.channel.shutdown_write();extra=wo.read().decode('utf-8','replace');err=we.read().decode('utf-8','replace');rc=wo.channel.recv_exit_status();wi=wo=we=None;pid=None;(td/'stderr.log').write_text(err);assert not extra.strip() and not err.strip() and rc==0,(extra,err,rc)
   pf.get(stem+'.private.json',str(td/'worker.private.json'));pf.get(stem+'.strace',str(td/'host.strace'));private=json.loads((td/'worker.private.json').read_text());gzip_exec=bool(__import__('re').search(r'execve\("[^"\n]*/gzip",[^\n]*= 0', (td/'host.strace').read_text(errors='replace')));return private,gzip_exec
  h=hashlib.sha256()
  for _ in range(64):h.update(b'C'*1048576)
  expected_cover_hash=h.hexdigest();pilots=[]
  for active,cover in [(a,c) for a in (False,True) for c in (False,True)]:
   ident='pilot'+('a' if active else 'q')+str(int(cover));token=os.urandom(16).hex();request={'id':token,'method':'solve','params':{'values':[13,31,53,73,97]}};server.registry[token]=request['params']['values'];stem,td,ready=start_worker(ident,active,request,cover);begin=time.perf_counter_ns();wi.write(json.dumps(request)+'\n');wi.flush();response=json.loads(wo.readline());elapsed=(time.perf_counter_ns()-begin)/1e9;private,gzip_exec=finish_worker(stem,td);pilots.append({'active':active,'response':response,'private':private,'elapsed_s':elapsed,'gzip_exec':gzip_exec});save(d/'PILOT.json',pilots);assert response['result']==267 and gzip_exec==active
   if active:assert private['archive_inside_wait'] and (private['archive']['fsync_end_ns']-private['archive']['begin_ns'])/1e9<3.5
   if cover:assert private['cover'].get('sha256')==expected_cover_hash and (private['cover']['end_ns']-private['cover']['begin_ns'])/1e9<3.5
  save(d/'PILOT.json',pilots)
  try:wf.mkdir('<DATA>/telltale_wait_confirmation_20261105')
  except OSError:pass
  rs='<DATA>/telltale_wait_confirmation_20261105/rig_'+campaign+'.py';wf.put(str(B.parent/'rig_capture_stagger.py'),rs);rig=Rig(w,rs,wr,campaign);plan=[]
  for block in range(8):
   cells=[{'expected_active':expected,'actual_active':actual,'cover':cover} for expected in (False,True) for actual in (False,True) for cover in (False,True)];random.Random(2026110510+block).shuffle(cells);token=os.urandom(16).hex();request={'id':token,'method':'solve','params':{'values':[13,31,53,73,97]}};server.registry[token]=request['params']['values']
   for cfg in cells:cfg.update(id='g'+os.urandom(6).hex(),block=block,stage='wait_confirmation',request=request,attack_attempt=cfg['expected_active']!=cfg['actual_active']);plan.append(cfg)
  sources=[B/'PROTOCOL.md',B/'collect_wait_confirm.py',B/'pi_api.py',B.parent/'rig_capture_stagger.py',B.parent/'burst_study/bridge_utils.py',B.parent/'ENGINEERING_RESTART_20261105.md',B.parent/'analysis_extensions/WAIT_CONFIRMATION_MODELS.json',B.parent/'analysis_extensions/WAIT_MODELS_RECEIPT.json'];sd=d/'source';sd.mkdir()
  for path in sources:(sd/path.name).write_bytes(path.read_bytes())
  freeze={'campaign':campaign,'stage':'wait_confirmation','plan':plan,'seconds':8,'cooldown_s':25,'winroot':wr,'piroot':pr,'pre_state':pre,'rig_preflight':rig.pre,'source_sha256':{str(x):sha(x) for x in sources},'utc':stamp(),'trusted_policy_in_worker':False,'pilot_sha256':sha(d/'PILOT.json'),'input_sha256':input_sha,'concurrent_resume_transfer':json.loads((B.parent/'resume_20261105_0305/STATUS.json').read_text())};save(d/'FREEZE.json',freeze);wf.put(str(d/'FREEZE.json'),wr+'/FREEZE.json')
  for idx,cfg in enumerate(plan):
   row=dict(cfg);row['pre']=guard(p);stem,td,ready=start_worker(cfg['id'],cfg['actual_active'],cfg['request'],cfg['cover']);row['ready']=ready;row['capture_ready']=rig.rpc({'op':'capture','id':cfg['id'],'seconds':8});time.sleep(random.Random(71104+idx).uniform(.25,.45));row['before']=rig.rpc({'op':'mark'});row['dispatch_desktop_ns']=time.perf_counter_ns();wi.write(json.dumps(cfg['request'],sort_keys=True,separators=(',',':'))+'\n');wi.flush();response=json.loads(wo.readline());row['return_desktop_ns']=time.perf_counter_ns();row['after']=rig.rpc({'op':'mark'});row['rf']=rig.rpc({'op':'finish'});private,gzip_exec=finish_worker(stem,td);trace={'request':cfg['request'],'response':response};save(td/'canonical_trace.json',trace);row.update(private=private,canonical_trace=trace,canonical_trace_sha256=sha(td/'canonical_trace.json'),elapsed_s=(row['return_desktop_ns']-row['dispatch_desktop_ns'])/1e9,kernel_gzip_exec=gzip_exec,post=guard(p));valid=response=={'id':cfg['request']['id'],'status':'complete','result':267} and gzip_exec==cfg['actual_active'] and all(r['rc']==0 and r['bytes']==r['expected_bytes']==320000000 for r in row['rf']['radios']) and all(m['running'] and 0<m['bytes']<320000000 for key in ('before','after') for m in row[key]['marks']);valid=valid and (not cfg['actual_active'] or private['archive_inside_wait']) and (not cfg['cover'] or private['cover'].get('sha256')==expected_cover_hash);row['valid']=bool(valid);save(td/'record.json',row);rows.append(row);save(d/'RESULTS.json',rows);save(d/'HTTP_EVENTS.json',server.events)
   for r in row['rf']['radios']:wf.get(r['log'].replace('\\','/'),str(td/(r['radio']+'.rf.log')))
   print(json.dumps({'completed':idx+1,'planned':len(plan),'id':cfg['id'],'active':cfg['actual_active'],'cover':cfg['cover'],'valid':valid,'archive_inside_wait':private['archive_inside_wait'],'elapsed_s':row['elapsed_s'],'utc':stamp()}),flush=True)
   if not valid:raise RuntimeError('invalid bounded acquisition')
   if idx<len(plan)-1:time.sleep(25)
  for block in range(8):assert len({x['canonical_trace_sha256'] for x in rows if x['block']==block})==1
  save(d/'COMPLETE.json',{'utc':stamp(),'trials':len(rows),'valid':sum(x['valid'] for x in rows),'raw_bytes':sum(q['bytes'] for x in rows for q in x['rf']['radios']),'same_canonical_trace_per_block':True})
 except Exception:(d/'FAILURE.log').write_text(traceback.format_exc(),encoding='utf-8');raise
 finally:
  close={}
  if pid and p:
   cmd=run(p,'cat /proc/'+str(pid)+'/cmdline',check=False)['stdout']
   if pr+'/pi_api.py' in cmd:close['own_worker_stop']=run(p,'kill -TERM '+str(pid),check=False)
  if wi:wi.channel.close()
  if rig:
   try:close['rig']=rig.stop()
   except Exception as ex:close['rig_error']=str(ex)
  if changed:close['restore']=run(p,"sudo -n sh -c 'echo "+str(int(old[1]))+" > /sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq; echo "+old[0]+" > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor'",check=False);close['pi_state']=snapshot(p)
  if li:li.channel.shutdown_write();close['pi_lock_release']=lo.channel.recv_exit_status()
  if server:server.shutdown();server.server_close()
  save(d/'POSTFLIGHT.json',close)
  for obj in (wf,pf,w,p):
   if obj:obj.close()
  print('ARTIFACT '+str(d),flush=True)
if __name__=='__main__':main()
