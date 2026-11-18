"""Independent C15 record/source/finite-RX validation, no IQ reads or new fitting."""
from pathlib import Path
import datetime,hashlib,json,math
B=Path(__file__).resolve().parent;S=B/'sustained_burst_study'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
d=Path(read(S/'LATEST.json')['directory']);assert d.parent.resolve()==S.resolve();assert (d/'COMPLETE.json').exists() and (d/'POSTFLIGHT.json').exists()
rows=read(d/'RESULTS.json');freeze=read(d/'FREEZE.json');complete=read(d/'COMPLETE.json');post=read(d/'POSTFLIGHT.json');fail=[];checks=0;details=[]
def ck(ok,label):
 global checks
 checks+=1
 if not ok:fail.append(label)
ck(not (d/'FAILURE.log').exists(),'campaign no failure')
ck(len(rows)==len(freeze['plan'])==complete['trials']==complete['valid']==24,'24 acquired valid')
ck(len({r['id'] for r in rows})==24,'unique IDs')
ck(complete['raw_bytes']==7680000000,'raw total7.68GB')
ck(freeze['models_sha256']=='e43e226984b4034dcd0f86aa3423dcd6a0e1faa88ebc3b4c9449fb23640c1f22','old model freeze')
ck(freeze['all_trials_test_only'] and freeze['selected_after_C09_outcome'] and freeze['continuous_sha_min_s']==1.5,'honest test protocol')
ck(freeze['winroot'].startswith('F:/Data/telltale_sustained_burst_20261105/'),'F target')
ck(freeze['rig_preflight']['preflight']['free']>=19680000000 and freeze['rig_preflight']['preflight']['disk']==0,'capacity planned+reserve and Disk0')
ck(post.get('restore',{}).get('rc')==0 and post.get('rig',{}).get('rc')==0 and post.get('pi_lock_release')==0,'restore/rig/lock0')
ck(post.get('pi_state','').splitlines()[:2]==freeze['pre_state']['state'].splitlines()[:2],'restore prior governor/min')
for source,h in freeze['source_sha256'].items():ck(sha(d/'source'/Path(source).name)==h,'frozen source '+Path(source).name)
expected_digest=hashlib.sha256(b'C'*1048576).hexdigest();plans={r['id']:r for r in freeze['plan']}
for block in range(6):
 rr=[r for r in rows if r['block']==block]
 ck(len(rr)==4 and sorted(r['milliseconds'] for r in rr)==[0,10,100,1000],'block cells '+str(block))
 ck(len({r['canonical_trace_sha256'] for r in rr})==1,'public content within block '+str(block))
for r in rows:
 ident=r['id'];td=d/'records'/ident;pr=r['private'];cv=pr['cover'];ms=r['milliseconds'];ac=ms>0;plan=plans[ident]
 ck(r['valid'] and r['returncode']==0,'valid rc '+ident)
 ck(read(td/'record.json')==r and read(td/'worker.private.json')==pr,'independent record files '+ident)
 ck(all(r[k]==plan[k] for k in ['id','block','milliseconds','cover','actual_condition','expected_condition','request']),'plan '+ident)
 ck(r['cover'] and r['actual_condition']==ac and r['expected_condition'] is False and r['attack_attempt']==ac,'truth '+ident)
 trace=read(td/'canonical_trace.json');ck(trace==r['canonical_trace'] and sha(td/'canonical_trace.json')==r['canonical_trace_sha256'],'canonical bytes '+ident)
 ck(trace['request']==plan['request'] and trace['response']=={'id':r['request']['id'],'status':'complete','result':267},'public answer '+ident)
 ck((td/'worker.stderr.log').read_text(encoding='utf-8-sig').strip()=='','worker stderr '+ident)
 ck((pr['operations']>0)==ac and pr['execution_code']==str(ms).zfill(4),'operation truth '+ident)
 ck(not ac or abs(pr['burst_elapsed_s']*1000-ms)<5,'C duration '+ident)
 ck(cv.get('sha256')==expected_digest and isinstance(cv.get('blocks'),int) and cv['blocks']>0 and cv['block_bytes']==1048576,'SHA repeated approved block '+ident)
 duration=(cv['end_ns']-cv['begin_ns'])/1e9
 ck(1.5<=duration<=1.9 and cv['begin_ns']<=pr['burst_begin_ns']<pr['burst_end_ns']<=cv['end_ns'],'full sustained overlap '+ident)
 ck(pr['burst_end_ns']<=pr['reply_ns'] and cv['end_ns']<=pr['reply_ns'],'work before reply '+ident)
 ck(r['dispatch_desktop_ns']<r['return_desktop_ns']<r['rf_finish_desktop_ns']<r['flush_desktop_ns'] and pr['reply_ns']<pr['flush_received_ns'],'external and Pi own-clock cleanup '+ident)
 ck(abs(r['elapsed_s']-(r['return_desktop_ns']-r['dispatch_desktop_ns'])/1e9)<1e-12,'own-clock elapsed '+ident)
 ck(len(r['rf']['radios'])==2 and {x['radio'] for x in r['rf']['radios']}=={'930c','16bc'},'two radios '+ident)
 for radio in ['930c','16bc']:
  rr=next(x for x in r['rf']['radios'] if x['radio']==radio);b=next(x for x in r['before']['marks'] if x['radio']==radio);a=next(x for x in r['after']['marks'] if x['radio']==radio)
  ck(rr['rc']==0 and rr['bytes']==rr['expected_bytes']==160000000 and rr['raw'].startswith('F:'),'finite bytes '+ident+radio)
  ck(b['running'] and a['running'] and 16000000<=b['bytes']<a['bytes']<160000000,'dispatch byte coverage '+ident+radio)
  cmd=rr['command'];ck(cmd[cmd.index('-s')+1]=='20000000' and cmd[cmd.index('-l')+1]=='32' and cmd[cmd.index('-g')+1]=='20' and cmd[cmd.index('-a')+1]=='0' and cmd[cmd.index('-n')+1]=='80000000','RF parameters '+ident+radio)
  ck(cmd[cmd.index('-f')+1]==('1800000000' if radio=='930c' else '105000000'),'frequency '+ident+radio)
 for key in ['pre','post']:
  snap=r[key];ck(snap['temperature']['cpu_c']<=48 and snap['temperature']['ddr_c']<=43,'temperature '+ident+key)
  state=snap['state'];line=next(x for x in state.splitlines() if x.startswith('throttled='));ck(int(line.split('=')[1],16)&15==0,'no current throttle '+ident+key)
 details.append({'id':ident,'block':r['block'],'milliseconds':ms,'actual_active':ac,'sha_duration_s':duration,'sha_blocks':cv['blocks'],'sha256':cv['sha256'],'actual_c_loop_ms':pr['burst_elapsed_s']*1000,'full_burst_within_SHA':True,'external_elapsed_s':r['elapsed_s']})
out={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'pass':not fail,'checks':checks,'failed':fail,'trials':len(rows),'all_answers_correct':not fail,'all_sustained_background_verified':not fail,'freeze_sha256':sha(d/'FREEZE.json'),'results_sha256':sha(d/'RESULTS.json'),'validation_code_sha256':sha(Path(__file__)),'rows':details};p=d/'SUSTAINED_BURST_COLLECTION_VALIDATION.json';assert not p.exists();p.write_text(json.dumps(out,indent=2),encoding='utf-8',newline='');print(json.dumps({'pass':out['pass'],'checks':checks,'failed':fail[:12],'path':str(p),'sha256':sha(p)}));raise SystemExit(0 if not fail else 1)
