"""Bounded resident-workload RF sweep. No models; numerical extraction stays remote."""
import hashlib,json,os,pathlib,random,shlex,sys,time,traceback
B=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(B));from bridge_utils import *
sys.path.insert(1,str(B.parent));from collect import Rig

def main():
 lower_priority();campaign='burst_'+time.strftime('%Y%m%d_%H%M%S',time.gmtime())+'_'+os.urandom(3).hex();d=B/campaign;d.mkdir();save(B/'LATEST.json',{'directory':str(d),'campaign':campaign})
 w=p=wf=pf=rig=li=lo=le=None;changed=False;old=None;pid=None;rows=[]
 pr='/home/pi/telltale_scenarios_rf_20261104/'+campaign;wr='F:/Data/telltale_bursts_20261104/'+campaign;lock='/home/pi/telltale_g1_20261026/controller.lock'
 try:
  assert json.loads((B.parent/'positive_20261104_163253_188606/SIGNAL_GATE.json').read_text())['pass']
  p=connect('192.0.2.60','admin',522);w=connect('192.0.2.4','win');pf=p.open_sftp();wf=w.open_sftp();pre=guard(p);old=pre['state'].splitlines()[:3]
  busy=run(p,"pgrep -af '^(perf|strace|resident_tool|python3.*telltale)' || true")['stdout']
  if busy.strip():raise RuntimeError('Pi occupied '+busy)
  locksrc='import os,fcntl,sys\np='+repr(lock)+'\nfd=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)\ntry:\n fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)\n os.write(fd,'+repr(campaign.encode())+')\n print(\'LOCKED\',flush=True)\n sys.stdin.read()\nfinally:\n os.close(fd)\n if open(p).read()=='+repr(campaign)+':os.unlink(p)\n'
  li,lo,le=p.exec_command('python3 -u -c '+shlex.quote(locksrc),timeout=30)
  if lo.readline().strip()!='LOCKED':raise RuntimeError('Pi lock failed '+le.read().decode())
  run(p,'mkdir -p '+pr)
  for name in ('burst.c','worker.py'):pf.put(str(B/name),pr+'/'+name)
  run(p,'cc -O2 -std=c11 -shared -fPIC '+pr+'/burst.c -o '+pr+'/libburst.so')
  for parent in ('F:/Data','F:/Data/telltale_bursts_20261104'):
   try:wf.mkdir(parent)
   except OSError:pass
  rs='F:/Data/telltale_bursts_20261104/rig_'+campaign+'.py';wf.put(str(B/'rig_capture.py'),rs);rig=Rig(w,rs,wr,campaign)
  plan=[]
  for block in range(4):
   cells=[{'milliseconds':ms,'cover':cover} for ms in (0,10,30,100,300,1000) for cover in (False,True)];random.Random(2026110403+block).shuffle(cells)
   for cfg in cells:cfg.update(id='b'+os.urandom(6).hex(),block=block,stage='burst',values=[11,47,71,83,101]);plan.append(cfg)
  sd=d/'source';sd.mkdir()
  names=['PROTOCOL.md','collect_burst.py','rig_capture.py','bridge_utils.py','worker.py','burst.c']
  for name in names:(sd/name).write_bytes((B/name).read_bytes())
  freeze={'campaign':campaign,'stage':'burst','plan':plan,'seconds':4,'cooldown_s':25,'winroot':wr,'piroot':pr,'pre_state':pre,'rig_preflight':rig.pre,'source_sha256':{name:sha(B/name) for name in names},'utc':stamp(),'worker_contains_trusted_policy':False,'concurrent_transfer':json.loads((B.parent/'transfer/STATUS.json').read_text())}
  save(d/'FREEZE.json',freeze);wf.put(str(d/'FREEZE.json'),wr+'/FREEZE.json')
  run(p,"sudo -n sh -c 'echo performance > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor; echo 1800000 > /sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq'");changed=True
  h=hashlib.sha256();bl=b'C'*1048576
  for _ in range(64):h.update(bl)
  expected_hash=h.hexdigest()
  for idx,cfg in enumerate(plan):
   row=dict(cfg);row['pre']=guard(p);td=d/'records'/cfg['id'];td.mkdir(parents=True);stem=pr+'/'+cfg['id'];inp={k:cfg[k] for k in ('milliseconds','cover','values')};save(td/'input.json',inp);pf.put(str(td/'input.json'),stem+'.json')
   command='nohup env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 nice -n 10 python3 '+pr+'/worker.py --input '+stem+'.json >'+stem+'.out 2>'+stem+'.err </dev/null & echo $!'
   pid=int(run(p,command)['stdout'].strip());row['worker_pid']=pid
   for attempt in range(80):
    check=run(p,'test -f '+stem+'.ready',check=False)
    if check['rc']==0:break
    time.sleep(.05)
   else:raise RuntimeError('worker not ready '+run(p,'cat '+stem+'.err',check=False)['stdout'])
   row['capture_ready']=rig.rpc({'op':'capture','id':cfg['id'],'seconds':4});time.sleep(random.Random(20261104+idx).uniform(.5,.7))
   row['before']=rig.rpc({'op':'mark'});row['dispatch_desktop_ns']=time.perf_counter_ns();run(p,'touch '+stem+'.go');
   until=time.monotonic()+4
   while run(p,'test -f '+stem+'.private.json',check=False)['rc']:
    if time.monotonic()>until:raise RuntimeError('worker timeout')
    time.sleep(.025)
   row['return_desktop_ns']=time.perf_counter_ns();row['after']=rig.rpc({'op':'mark'});row['rf']=rig.rpc({'op':'finish'});pid=None
   for suffix in ('.private.json','.public.json','.err','.out'):pf.get(stem+suffix,str(td/('worker'+suffix)))
   row['private']=json.loads((td/'worker.private.json').read_text());row['public']=json.loads((td/'worker.public.json').read_text());row['post']=guard(p)
   valid=all(r['rc']==0 and r['bytes']==r['expected_bytes']==160000000 for r in row['rf']['radios'])
   valid=valid and all(m['running'] and 0<m['bytes']<160000000 for mark in ('before','after') for m in row[mark]['marks'])
   valid=valid and row['public']=={'tool':'solve_local','status':'ok','answer':sum(cfg['values']),'extra_operations':[]} and not (td/'worker.err').read_text().strip()
   if cfg['cover']:valid=valid and row['private']['cover'].get('sha256')==expected_hash
   valid=valid and ((row['private']['operations']>0)==(cfg['milliseconds']>0))
   row['valid']=bool(valid);save(td/'record.json',row);rows.append(row);save(d/'RESULTS.json',rows)
   for r in row['rf']['radios']:wf.get(r['log'].replace('\\','/'),str(td/(r['radio']+'.rf.log')))
   print(json.dumps({'completed':idx+1,'planned':len(plan),'id':cfg['id'],'ms':cfg['milliseconds'],'cover':cfg['cover'],'valid':valid,'actual_ms':round(row['private']['burst_elapsed_s']*1000,3),'utc':stamp()}),flush=True)
   if not valid:raise RuntimeError('invalid bounded acquisition')
   if idx<len(plan)-1:time.sleep(25)
  save(d/'COMPLETE.json',{'utc':stamp(),'trials':len(rows),'valid':sum(x['valid'] for x in rows),'raw_bytes':sum(r['bytes'] for row in rows for r in row['rf']['radios'])})
 except Exception:(d/'FAILURE.log').write_text(traceback.format_exc(),encoding='utf-8');raise
 finally:
  close={}
  if pid and p:
   cmd=run(p,'cat /proc/'+str(pid)+'/cmdline',check=False)['stdout']
   if pr+'/worker.py' in cmd:close['own_worker_stop']=run(p,'kill -TERM '+str(pid),check=False)
  if rig:
   try:close['rig']=rig.stop()
   except Exception as ex:close['rig_error']=str(ex)
  if changed:
   close['restore']=run(p,"sudo -n sh -c 'echo "+str(int(old[1]))+" > /sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq; echo "+old[0]+" > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor'",check=False);close['pi_state']=snapshot(p)
  if li:li.channel.shutdown_write();close['pi_lock_release']=lo.channel.recv_exit_status()
  save(d/'POSTFLIGHT.json',close)
  for obj in (wf,pf,w,p):
   if obj:obj.close()
  print('ARTIFACT '+str(d),flush=True)
if __name__=='__main__':main()
