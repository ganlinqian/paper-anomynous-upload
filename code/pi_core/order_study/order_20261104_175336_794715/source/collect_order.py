import json,os,pathlib,random,shlex,sys,time,traceback
B=pathlib.Path(__file__).resolve().parent;sys.path.insert(0,str(B.parent/'burst_study'));from bridge_utils import *
sys.path.insert(1,str(B.parent));from collect import Rig

def main():
 lower_priority();campaign='order_'+time.strftime('%Y%m%d_%H%M%S',time.gmtime())+'_'+os.urandom(3).hex();d=B/campaign;d.mkdir();save(B/'LATEST.json',{'directory':str(d),'campaign':campaign})
 w=p=wf=pf=rig=li=lo=le=wi=wo=we=None;changed=False;old=None;pid=None;rows=[];pr='/home/pi/telltale_scenarios_rf_20261104/'+campaign;wr='F:/Data/telltale_order_20261104/'+campaign;lock='/home/pi/telltale_g1_20261026/controller.lock'
 try:
  p=connect('192.0.2.60','admin',522);w=connect('192.0.2.4','win');pf=p.open_sftp();wf=w.open_sftp();pre=guard(p);old=pre['state'].splitlines()[:3]
  busy=run(p,"pgrep -af '^(perf|strace|resident_tool|python3.*telltale)' || true")['stdout']
  if busy.strip():raise RuntimeError('Pi occupied '+busy)
  locksrc='import os,fcntl,sys\np='+repr(lock)+'\nfd=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)\ntry:\n fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)\n os.write(fd,'+repr(campaign.encode())+')\n print(\'LOCKED\',flush=True)\n sys.stdin.read()\nfinally:\n os.close(fd)\n if open(p).read()=='+repr(campaign)+':os.unlink(p)\n'
  li,lo,le=p.exec_command('python3 -u -c '+shlex.quote(locksrc),timeout=30)
  if lo.readline().strip()!='LOCKED':raise RuntimeError('Pi lock failed '+le.read().decode())
  run(p,'mkdir -p '+pr);pf.put(str(B/'pi_api.py'),pr+'/pi_api.py');pf.put(str(B/'ordered.c'),pr+'/ordered.c');run(p,'cc -O2 -std=c11 -shared -fPIC '+pr+'/ordered.c -o '+pr+'/libordered.so')
  try:wf.mkdir('F:/Data/telltale_order_20261104')
  except OSError:pass
  rs='F:/Data/telltale_order_20261104/rig_'+campaign+'.py';wf.put(str(B.parent/'burst_study/rig_capture.py'),rs);rig=Rig(w,rs,wr,campaign)
  plan=[]
  for block in range(5):
   cells=[{'expected_order':expected,'actual_order':actual} for expected in (False,True) for actual in (False,True)];random.Random(2026110405+block).shuffle(cells);nonce=os.urandom(16).hex();values=[13,31,53,73,97]
   for cfg in cells:cfg.update(id='t'+os.urandom(6).hex(),block=block,stage='order',request={'id':nonce,'method':'solve','params':{'values':values}},attack_attempt=cfg['expected_order']!=cfg['actual_order']);plan.append(cfg)
  sources={str(B/'PROTOCOL.md'):sha(B/'PROTOCOL.md'),str(B/'collect_order.py'):sha(B/'collect_order.py'),str(B/'pi_api.py'):sha(B/'pi_api.py'),str(B/'ordered.c'):sha(B/'ordered.c'),str(B.parent/'burst_study/rig_capture.py'):sha(B.parent/'burst_study/rig_capture.py'),str(B.parent/'burst_study/bridge_utils.py'):sha(B.parent/'burst_study/bridge_utils.py')};sd=d/'source';sd.mkdir()
  for path in sources:(sd/pathlib.Path(path).name).write_bytes(pathlib.Path(path).read_bytes())
  save(d/'FREEZE.json',{'campaign':campaign,'stage':'order','plan':plan,'seconds':4,'cooldown_s':25,'winroot':wr,'piroot':pr,'pre_state':pre,'rig_preflight':rig.pre,'source_sha256':sources,'utc':stamp(),'trusted_policy_in_worker':False,'concurrent_transfer':json.loads((B.parent/'transfer/STATUS.json').read_text())});wf.put(str(d/'FREEZE.json'),wr+'/FREEZE.json')
  run(p,"sudo -n sh -c 'echo performance > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor; echo 1800000 > /sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq'");changed=True
  for idx,cfg in enumerate(plan):
   row=dict(cfg);td=d/'records'/cfg['id'];td.mkdir(parents=True);row['pre']=guard(p);stem=pr+'/'+cfg['id'];private={'order_code':'M_C_' if cfg['actual_order'] else 'C_M_'};save(td/'private_config.json',private);pf.put(str(td/'private_config.json'),stem+'.json')
   wi,wo,we=p.exec_command('env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 nice -n 10 python3 -u '+pr+'/pi_api.py --private-config '+stem+'.json',timeout=15)
   ready=json.loads(wo.readline());pid=ready['pid'];row['ready']=ready
   if not ready['ready']:raise RuntimeError('API worker not ready')
   row['capture_ready']=rig.rpc({'op':'capture','id':cfg['id'],'seconds':4});time.sleep(random.Random(61104+idx).uniform(.5,.7));row['before']=rig.rpc({'op':'mark'})
   message=json.dumps(cfg['request'],sort_keys=True,separators=(',',':'));row['dispatch_desktop_ns']=time.perf_counter_ns();wi.write(message+'\n');wi.flush();response_line=wo.readline();row['return_desktop_ns']=time.perf_counter_ns();row['after']=rig.rpc({'op':'mark'});row['rf']=rig.rpc({'op':'finish'})
   wi.channel.shutdown_write();extra=wo.read().decode('utf-8','replace');err=we.read().decode('utf-8','replace');rc=wo.channel.recv_exit_status();wi=wo=we=None;pid=None
   response=json.loads(response_line);trace={'request':cfg['request'],'response':response};save(td/'canonical_trace.json',trace);save(td/'timing.json',{'dispatch_desktop_ns':row['dispatch_desktop_ns'],'return_desktop_ns':row['return_desktop_ns'],'elapsed_s':(row['return_desktop_ns']-row['dispatch_desktop_ns'])/1e9});(td/'worker.stderr.log').write_text(err);pf.get(stem+'.private.json',str(td/'worker.private.json'))
   row['canonical_trace']=trace;row['canonical_trace_sha256']=sha(td/'canonical_trace.json');row['private']=json.loads((td/'worker.private.json').read_text());row['elapsed_s']=(row['return_desktop_ns']-row['dispatch_desktop_ns'])/1e9;row['returncode']=rc;row['post']=guard(p)
   valid=not err.strip() and not extra.strip() and rc==0 and response=={'id':cfg['request']['id'],'status':'complete','result':sum(cfg['request']['params']['values'])}
   valid=valid and all(r['rc']==0 and r['bytes']==r['expected_bytes']==160000000 for r in row['rf']['radios']) and all(m['running'] and 0<m['bytes']<160000000 for key in ('before','after') for m in row[key]['marks']) and ([q['kind'] for q in row['private']['phases']]==(['memory','cpu'] if cfg['actual_order'] else ['cpu','memory']))
   row['valid']=bool(valid);save(td/'record.json',row);rows.append(row);save(d/'RESULTS.json',rows)
   for r in row['rf']['radios']:wf.get(r['log'].replace('\\','/'),str(td/(r['radio']+'.rf.log')))
   print(json.dumps({'completed':idx+1,'planned':len(plan),'id':cfg['id'],'actual_order':cfg['actual_order'],'expected_order':cfg['expected_order'],'valid':valid,'elapsed_s':row['elapsed_s'],'utc':stamp()}),flush=True)
   if not valid:raise RuntimeError('invalid trace acquisition')
   if idx<len(plan)-1:time.sleep(25)
  for block in range(5):assert len({r['canonical_trace_sha256'] for r in rows if r['block']==block})==1,'canonical call/return differs'
  save(d/'COMPLETE.json',{'utc':stamp(),'trials':len(rows),'valid':sum(r['valid'] for r in rows),'raw_bytes':sum(q['bytes'] for r in rows for q in r['rf']['radios']),'same_canonical_trace_per_block':True})
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
  save(d/'POSTFLIGHT.json',close)
  for obj in (wf,pf,w,p):
   if obj:obj.close()
  print('ARTIFACT '+str(d),flush=True)
if __name__=='__main__':main()
