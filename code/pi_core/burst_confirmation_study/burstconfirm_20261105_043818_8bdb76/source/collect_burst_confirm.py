import json,os,pathlib,random,shlex,sys,time,traceback
B=pathlib.Path(__file__).resolve().parent;sys.path.insert(0,str(B.parent/'burst_study'));from bridge_utils import *
sys.path.insert(1,str(B.parent));from collect import Rig
def main():
 lower_priority();campaign='burstconfirm_'+time.strftime('%Y%m%d_%H%M%S',time.gmtime())+'_'+os.urandom(3).hex();d=B/campaign;d.mkdir();save(B/'LATEST.json',{'directory':str(d),'campaign':campaign})
 w=p=wf=pf=rig=li=lo=le=wi=wo=we=None;changed=False;old=None;pid=None;rows=[];pr='/home/pi/telltale_scenarios_rf_20261104/'+campaign;wr='<DATA>/telltale_burst_confirmation_20261104/'+campaign;lock='/home/pi/telltale_g1_20261026/controller.lock'
 try:
  assert (B.parent/'wait_transfer/WAIT_UPLOAD_COMPLETE.json').exists(),'J source reads not complete'
  modelpath=B.parent/'analysis_extensions/BURST_EXPLORATORY_FREEZE.json';assert sha(modelpath)=='e43e226984b4034dcd0f86aa3423dcd6a0e1faa88ebc3b4c9449fb23640c1f22'
  p=connect('192.0.2.60','admin',522);w=connect('192.0.2.4','win');pf=p.open_sftp();wf=w.open_sftp();pre=guard(p);old=pre['state'].splitlines()[:3]
  busy=run(p,"pgrep -af '^(perf|strace|resident_tool|python3.*telltale)' || true")['stdout']
  if busy.strip():raise RuntimeError('Pi occupied '+busy)
  locksrc='import os,fcntl,sys\np='+repr(lock)+'\nfd=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)\ntry:\n fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)\n os.write(fd,'+repr(campaign.encode())+')\n print(\'LOCKED\',flush=True)\n sys.stdin.read()\nfinally:\n os.close(fd)\n if open(p).read()=='+repr(campaign)+':os.unlink(p)\n'
  li,lo,le=p.exec_command('python3 -u -c '+shlex.quote(locksrc),timeout=30)
  if lo.readline().strip()!='LOCKED':raise RuntimeError('Pi lock failed '+le.read().decode())
  run(p,'mkdir -p '+pr)
  for src,dest in [(B/'pi_api.py','pi_api.py'),(B.parent/'burst_study/burst.c','burst.c'),(B.parent/'order_study/ordered.c','ordered.c')]:pf.put(str(src),pr+'/'+dest)
  for stem in ('burst','ordered'):run(p,'cc -O2 -std=c11 -shared -fPIC '+pr+'/'+stem+'.c -o '+pr+'/lib'+stem+'.so')
  try:wf.mkdir('<DATA>/telltale_burst_confirmation_20261104')
  except OSError:pass
  rs='<DATA>/telltale_burst_confirmation_20261104/rig_'+campaign+'.py';wf.put(str(B.parent/'rig_capture_stagger.py'),rs);rig=Rig(w,rs,wr,campaign)
  plan=[]
  for block in range(6):
   cells=[{'milliseconds':ms,'cover':cover,'family':'burst','actual_condition':ms>0,'expected_condition':False} for ms in (0,10,30,100,300,1000) for cover in (False,True)];random.Random(2026110409+block).shuffle(cells);nonce=os.urandom(16).hex()
   for cfg in cells:cfg.update(id='v'+os.urandom(6).hex(),block=block,stage='burst_confirmation',request={'id':nonce,'method':'solve','params':{'values':[13,31,53,73,97]}},attack_attempt=cfg['milliseconds']>0);plan.append(cfg)
  paths=[B/'PROTOCOL.md',B/'collect_burst_confirm.py',B/'pi_api.py',B.parent/'burst_study/burst.c',B.parent/'order_study/ordered.c',B.parent/'rig_capture_stagger.py',B.parent/'burst_study/bridge_utils.py',B.parent/'ENGINEERING_RESTART_20261105.md',modelpath,B.parent/'analysis_extensions/BURST_EXPLORATORY_RECEIPT.json'];sources={str(x):sha(x) for x in paths};sd=d/'source';sd.mkdir()
  for path in paths:(sd/path.name).write_bytes(path.read_bytes())
  concurrent={}
  for label,name in [('F','extension_transfer/STATUS.json'),('J','wait_transfer/STATUS.json'),('resume','resume_20261105_0305/STATUS.json')]:
   if (B.parent/name).exists():concurrent[label]=json.loads((B.parent/name).read_text())
  save(d/'FREEZE.json',{'campaign':campaign,'stage':'burst_confirmation','plan':plan,'seconds':4,'cooldown_s':25,'winroot':wr,'piroot':pr,'pre_state':pre,'rig_preflight':rig.pre,'source_sha256':sources,'utc':stamp(),'trusted_policy_in_worker':False,'models_sha256':sha(modelpath),'all_trials_test_only':True,'concurrent_transfer':concurrent});wf.put(str(d/'FREEZE.json'),wr+'/FREEZE.json')
  run(p,"sudo -n sh -c 'echo performance > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor; echo 1800000 > /sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq'");changed=True
  pilots=[]
  for ms,cv in [(0,False),(1000,True)]:
   family='burst';ac=ms>0
   stem=pr+'/pilot_'+str(ms)+str(int(cv));cfg={'cover_code':'YES_' if cv else 'NO__','execution_code':str(ms).zfill(4)};tmp=d/'pilot_config.json';save(tmp,cfg);pf.put(str(tmp),stem+'.json');request={'id':'pilot','method':'solve','params':{'values':[13,31,53,73,97]}}
   wi,wo,we=p.exec_command('env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 nice -n 10 python3 -u '+pr+'/pi_api.py --private-config '+stem+'.json',timeout=15);ready=json.loads(wo.readline());pid=ready['pid'];assert ready['ready'];wi.write(json.dumps(request)+'\n');wi.flush();response=json.loads(wo.readline());wi.write('{"research_flush":true}\n');wi.flush();wi.channel.shutdown_write();extra=wo.read().decode();err=we.read().decode();rc=wo.channel.recv_exit_status();wi=wo=we=None;pid=None;assert rc==0 and not extra.strip() and not err.strip() and response['result']==267
   private=json.loads(pf.open(stem+'.private.json').read());pilots.append({'family':family,'actual':ac,'response':response,'private':private})
  save(d/'PILOT.json',pilots)
  import hashlib
  h=hashlib.sha256()
  for _ in range(64):h.update(b'C'*1048576)
  expected_cover_hash=h.hexdigest();time.sleep(25)
  for idx,cfg in enumerate(plan):
   row=dict(cfg);td=d/'records'/cfg['id'];td.mkdir(parents=True);row['pre']=guard(p);stem=pr+'/'+cfg['id'];ac=cfg['actual_condition'];family=cfg['family'];private={'cover_code':'YES_' if cfg['cover'] else 'NO__','execution_code':str(cfg['milliseconds']).zfill(4)};save(td/'private_config.json',private);pf.put(str(td/'private_config.json'),stem+'.json')
   wi,wo,we=p.exec_command('env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 nice -n 10 python3 -u '+pr+'/pi_api.py --private-config '+stem+'.json',timeout=15);ready=json.loads(wo.readline());pid=ready['pid'];row['ready']=ready
   if not ready['ready']:raise RuntimeError('worker not ready')
   row['capture_ready']=rig.rpc({'op':'capture','id':cfg['id'],'seconds':4});time.sleep(random.Random(60804+idx).uniform(.25,.45));row['before']=rig.rpc({'op':'mark'});message=json.dumps(cfg['request'],sort_keys=True,separators=(',',':'));row['dispatch_desktop_ns']=time.perf_counter_ns();wi.write(message+'\n');wi.flush();response_line=wo.readline();row['return_desktop_ns']=time.perf_counter_ns();row['after']=rig.rpc({'op':'mark'});row['rf']=rig.rpc({'op':'finish'});row['rf_finish_desktop_ns']=time.perf_counter_ns();wi.write('{"research_flush":true}\n');wi.flush();row['flush_desktop_ns']=time.perf_counter_ns();wi.channel.shutdown_write();extra=wo.read().decode('utf-8','replace');err=we.read().decode('utf-8','replace');rc=wo.channel.recv_exit_status();wi=wo=we=None;pid=None
   response=json.loads(response_line);trace={'request':cfg['request'],'response':response};save(td/'canonical_trace.json',trace);(td/'worker.stderr.log').write_text(err);pf.get(stem+'.private.json',str(td/'worker.private.json'));row['canonical_trace']=trace;row['canonical_trace_sha256']=sha(td/'canonical_trace.json');row['private']=json.loads((td/'worker.private.json').read_text());row['elapsed_s']=(row['return_desktop_ns']-row['dispatch_desktop_ns'])/1e9;row['returncode']=rc;row['post']=guard(p)
   valid=not err.strip() and not extra.strip() and rc==0 and response=={'id':cfg['request']['id'],'status':'complete','result':267}
   valid=valid and all(q['rc']==0 and q['bytes']==q['expected_bytes']==160000000 for q in row['rf']['radios']) and all(m['running'] and 0<m['bytes']<160000000 for key in ('before','after') for m in row[key]['marks'])
   valid=valid and ((row['private']['operations']>0)==ac)
   if cfg['milliseconds']>0:valid=valid and abs(row['private']['burst_elapsed_s']*1000-cfg['milliseconds'])<5
   if cfg['cover']:valid=valid and row['private']['cover'].get('sha256')==expected_cover_hash
   valid=valid and row['flush_desktop_ns']>row['rf_finish_desktop_ns'] and row['private']['flush_received_ns']>row['private']['reply_ns'];row['valid']=bool(valid);save(td/'record.json',row);rows.append(row);save(d/'RESULTS.json',rows)
   for q in row['rf']['radios']:wf.get(q['log'].replace('\\','/'),str(td/(q['radio']+'.rf.log')))
   print(json.dumps({'completed':idx+1,'planned':len(plan),'family':family,'id':cfg['id'],'milliseconds':cfg['milliseconds'],'cover':cfg['cover'],'valid':valid,'elapsed_s':row['elapsed_s'],'utc':stamp()}),flush=True)
   if not valid:raise RuntimeError('invalid confirmation acquisition; retain all')
   if idx<len(plan)-1:time.sleep(25)
  for block in range(6):assert len({r['canonical_trace_sha256'] for r in rows if r['block']==block})==1
  save(d/'COMPLETE.json',{'utc':stamp(),'trials':len(rows),'valid':sum(r['valid'] for r in rows),'raw_bytes':sum(q['bytes'] for r in rows for q in r['rf']['radios']),'same_canonical_trace_per_block':True,'all_trials_test_only':True})
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
