import hashlib,json,pathlib,re,time
B=pathlib.Path(__file__).resolve().parent;checks=[];summaries=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def ck(name,ok):checks.append({'name':name,'pass':bool(ok)})
h=hashlib.sha256()
for _ in range(64):h.update(b'C'*1048576)
cover_sha=h.hexdigest()
for study,n,blocks in [('confirmation_study',80,10),('burst_confirmation_study',72,6)]:
 d=pathlib.Path(json.loads((B/study/'LATEST.json').read_text())['directory']);frozen=json.loads((d/'FREEZE.json').read_text());rows=json.loads((d/'RESULTS.json').read_text());post=json.loads((d/'POSTFLIGHT.json').read_text());ck(study+':complete',(d/'COMPLETE.json').exists() and len(rows)==n and len({r['id'] for r in rows})==n)
 for path,hs in frozen['source_sha256'].items():ck(study+':source:'+pathlib.Path(path).name,sha(d/'source'/pathlib.Path(path).name)==hs)
 for row in rows:
  ident=row['id'];td=d/'records'/ident;cfg=json.loads((td/'private_config.json').read_text());private=json.loads((td/'worker.private.json').read_text());plan=next(x for x in frozen['plan'] if x['id']==ident);ck(ident+':plan',all(row[k]==plan[k] for k in plan));ck(ident+':truth',private==row['private']);ck(ident+':valid',row['valid'])
  ck(ident+':canonical',sha(td/'canonical_trace.json')==row['canonical_trace_sha256'] and json.loads((td/'canonical_trace.json').read_text())==row['canonical_trace'] and row['canonical_trace']['response']=={'id':row['request']['id'],'status':'complete','result':267})
  ck(ident+':coverage',row['capture_ready']['win_mono_ns']<row['before']['win_mono_ns']<row['after']['win_mono_ns']<row['rf']['win_mono_ns'] and all(m['running'] and 0<m['bytes']<160000000 for key in ('before','after') for m in row[key]['marks']))
  ck(ident+':flush_after_rx',row['flush_desktop_ns']>row['rf_finish_desktop_ns']>row['return_desktop_ns'] and private['flush_received_ns']>private['reply_ns'])
  for rf in row['rf']['radios']:
   ck(ident+':rx:'+rf['radio'],rf['rc']==0 and rf['bytes']==rf['expected_bytes']==160000000)
   log=(td/(rf['radio']+'.rf.log')).read_text(errors='replace');ck(ident+':rxlog:'+rf['radio'],not re.search(r'not found|LIBUSB_ERROR|hackrf_start_rx.*failed|buffer overflow',log,re.I))
  for key in ('pre','post'):
   t=row[key]['temperature'];ck(ident+':thermal:'+key,t['cpu_c']<=48 and t['ddr_c']<=43 and (int(row[key]['state'].split('throttled=')[1].splitlines()[0],16)&15)==0)
  ck(ident+':authorization',row['attack_attempt']==(row['actual_condition']!=row['expected_condition']))
  if study=='confirmation_study':
   ck(ident+':no_policy',set(cfg)=={'family_code','execution_code'})
   if row['family']=='trace':ck(ident+':memory',(private['operations']>0)==row['actual_condition'] and private['envelope_s']>=2.0)
   else:ck(ident+':order',[x['kind'] for x in private['phases']]==(['memory','cpu'] if row['actual_condition'] else ['cpu','memory']) and all(x['operations']>0 and .99<x['elapsed_s']<1.1 for x in private['phases']) and private['envelope_s']>=2.5)
  else:
   ck(ident+':no_policy',set(cfg)=={'cover_code','execution_code'});ck(ident+':memory',(private['operations']>0)==(row['milliseconds']>0) and abs(private['burst_elapsed_s']*1000-row['milliseconds'])<5)
   ck(ident+':cover',(private['cover'].get('sha256')==cover_sha) if row['cover'] else not private['cover'])
 for block in range(blocks):ck(study+':same_api:'+str(block),len({x['canonical_trace_sha256'] for x in rows if x['block']==block})==1)
 ck(study+':restore',post['restore']['rc']==post['rig']['rc']==post['pi_lock_release']==0 and post['pi_state'].splitlines()[:2]==frozen['pre_state']['state'].splitlines()[:2])
 summaries.append({'study':study,'directory':str(d),'trials':len(rows),'raw_bytes':sum(q['bytes'] for row in rows for q in row['rf']['radios'])})
result={'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'pass':all(x['pass'] for x in checks),'checks':len(checks),'failed':[x['name'] for x in checks if not x['pass']],'stages':summaries,'scope':'record and source consistency; not security sample count'};(B/'CONFIRMATION_COLLECTION_VALIDATION.json').write_text(json.dumps(result,indent=2));print(json.dumps(result));raise SystemExit(0 if result['pass'] else 1)
