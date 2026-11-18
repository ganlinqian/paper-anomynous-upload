"""Independent small-record consistency verification; never counts checks as scientific trials."""
import hashlib,json,pathlib,re,time
B=pathlib.Path(__file__).resolve().parent;checks=[];summaries=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def check(name,ok):checks.append({'check':name,'pass':bool(ok)})
for study,stage,n in [('burst_study','burst',48),('complete_trace_study','trace',20),('order_study','order',20)]:
 lp=B/study/'LATEST.json'
 if not lp.exists():summaries.append({'stage':stage,'status':'not_started'});continue
 d=pathlib.Path(json.loads(lp.read_text())['directory'])
 if not (d/'FREEZE.json').exists():summaries.append({'stage':stage,'status':'not_frozen'});continue
 frozen=json.loads((d/'FREEZE.json').read_text());rows=json.loads((d/'RESULTS.json').read_text()) if (d/'RESULTS.json').exists() else [];complete=(d/'COMPLETE.json').exists()
 if complete:check(stage+':trial_count',len(rows)==n)
 check(stage+':unique_ids',len({x['id'] for x in rows})==len(rows))
 for source,h in frozen['source_sha256'].items():check(stage+':source:'+pathlib.Path(source).name,sha(d/'source'/pathlib.Path(source).name)==h)
 for row in rows:
  ident=row['id'];td=d/'records'/ident;plan=next(x for x in frozen['plan'] if x['id']==ident);private=json.loads((td/('worker.private.json')).read_text());check(ident+':valid',row['valid'])
  check(ident+':truth_receipt',private==row['private']);check(ident+':coverage_order',row['capture_ready']['win_mono_ns']<row['before']['win_mono_ns']<row['after']['win_mono_ns']<row['rf']['win_mono_ns'])
  for key in ('before','after'):check(ident+':coverage:'+key,all(m['running'] and 0<m['bytes']<160000000 for m in row[key]['marks']))
  for radio in row['rf']['radios']:
   check(ident+':raw:'+radio['radio'],radio['rc']==0 and radio['bytes']==radio['expected_bytes']==160000000)
   log=(td/(radio['radio']+'.rf.log')).read_text(errors='replace');check(ident+':rf_errors:'+radio['radio'],not re.search(r'not found|LIBUSB_ERROR|hackrf_start_rx.*failed|buffer overflow',log,re.I))
  for key in ('pre','post'):
   t=row[key]['temperature'];check(ident+':thermal:'+key,t['cpu_c']<=48 and t['ddr_c']<=43 and int(row[key]['state'].split('throttled=')[1].splitlines()[0],16)&15==0)
  if stage=='burst':
   cfg=json.loads((td/'input.json').read_text());check(ident+':no_policy_in_worker',set(cfg)=={'milliseconds','cover','values'});check(ident+':planned_input',all(cfg[k]==plan[k] for k in cfg));public=json.loads((td/'worker.public.json').read_text());check(ident+':public',public=={'tool':'solve_local','status':'ok','answer':sum(cfg['values']),'extra_operations':[]});check(ident+':actual_memory',(private['operations']>0)==(cfg['milliseconds']>0))
   if cfg['cover']:check(ident+':cover_interval',private['start_ns']<=private['cover']['begin_ns']<private['cover']['end_ns']<=private['end_ns'])
  else:
   cfg=json.loads((td/'private_config.json').read_text());check(ident+':no_policy_in_worker',set(cfg)==({'duration_code'} if stage=='trace' else {'order_code'}));tr=json.loads((td/'canonical_trace.json').read_text());check(ident+':protected_content_sha',sha(td/'canonical_trace.json')==row['canonical_trace_sha256']);check(ident+':protected_content',tr==row['canonical_trace'] and tr['request']==plan['request'] and tr['response']=={'id':plan['request']['id'],'status':'complete','result':sum(plan['request']['params']['values'])});check(ident+':external_duration',abs(row['elapsed_s']-(row['return_desktop_ns']-row['dispatch_desktop_ns'])/1e9)<1e-12)
   actual=plan['actual_active' if stage=='trace' else 'actual_order'];expected=plan['expected_active' if stage=='trace' else 'expected_order'];check(ident+':authorization',row['attack_attempt']==(actual!=expected))
   if stage=='trace':check(ident+':actual_memory',(private['operations']>0)==actual);check(ident+':response_padding',private['envelope_s']>=2.0)
   else:check(ident+':phase_order',[x['kind'] for x in private['phases']]==(['memory','cpu'] if actual else ['cpu','memory']));check(ident+':same_work_amount',all(x['operations']>0 and .99<=x['elapsed_s']<=1.1 for x in private['phases']));check(ident+':response_padding',private['envelope_s']>=2.5)
 if stage!='burst' and complete:
  for block in range(5):check(stage+':identical_api:'+str(block),len({x['canonical_trace_sha256'] for x in rows if x['block']==block})==1)
 if (d/'POSTFLIGHT.json').exists():
  p=json.loads((d/'POSTFLIGHT.json').read_text());check(stage+':rig_release',p.get('rig',{}).get('rc')==0);check(stage+':pi_lock_release',p.get('pi_lock_release')==0);check(stage+':settings_restore',p.get('restore',{}).get('rc')==0 and p.get('pi_state','').splitlines()[:2]==frozen['pre_state']['state'].splitlines()[:2])
 summaries.append({'stage':stage,'status':'complete' if complete else 'collecting','directory':str(d),'records':len(rows),'raw_bytes':sum(r['bytes'] for x in rows for r in x['rf']['radios'])})
result={'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'checks':len(checks),'failed':[x['check'] for x in checks if not x['pass']],'pass':all(x['pass'] for x in checks),'stages':summaries,'scope':'consistency only; no RF security conclusion'};(B/'EXTENSION_COLLECTION_VALIDATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False));raise SystemExit(0 if result['pass'] else 1)
