import csv,gzip,hashlib,json,pathlib,re,time,traceback
from bridge_utils import *
b=pathlib.Path(__file__).resolve().parent;lower_priority();deadline=time.monotonic()+900
while True:
 d=pathlib.Path(json.loads((b/'wait_confirmation_study/LATEST.json').read_text())['directory'])
 if (d/'FAILURE.log').exists():raise RuntimeError('collection failure')
 if (d/'COMPLETE.json').exists() and (d/'POSTFLIGHT.json').exists():break
 if time.monotonic()>deadline:raise TimeoutError('collection not complete')
 time.sleep(5)
rows=json.loads((d/'RESULTS.json').read_text());freeze=json.loads((d/'FREEZE.json').read_text());events=json.loads((d/'HTTP_EVENTS.json').read_text());post=json.loads((d/'POSTFLIGHT.json').read_text());checks=[];derived=[];art=d/'verified_archives';art.mkdir(exist_ok=True)
def check(name,ok):checks.append({'check':name,'pass':bool(ok)})
check('trials64',len(rows)==64 and len({x['id'] for x in rows})==64);check('postflight',post['restore']['rc']==0 and post['rig']['rc']==0 and post['pi_lock_release']==0)
for source,h in freeze['source_sha256'].items():check('source:'+pathlib.Path(source).name,sha(d/'source'/pathlib.Path(source).name)==h)
h=hashlib.sha256()
for _ in range(64):h.update(b'C'*1048576)
cover_sha=h.hexdigest()
fixture=hashlib.shake_256(b'Telltale:C07:20261104:fixture:v1').digest(16*1024*1024);expected=hashlib.sha256(fixture).hexdigest();del fixture;check('independent_fixture',expected==freeze['input_sha256']);p=connect('192.0.2.60','admin',522);sf=p.open_sftp();archive_count=0
try:
 for row in rows:
  ident=row['id'];td=d/'records'/ident;private=json.loads((td/'worker.private.json').read_text());cfg=json.loads((td/'private_config.json').read_text());trace=json.loads((td/'canonical_trace.json').read_text());host=(td/'host.strace').read_text(errors='replace');exec_seen=bool(re.search(r'execve\("[^"\n]*/gzip",[^\n]*= 0',host));ev=[e for e in events if row['dispatch_desktop_ns']<=e['begin_desktop_ns']<=e['end_desktop_ns']<=row['return_desktop_ns'] and e['token']==row['request']['id']];check(ident+':single_gateway',len(ev)==1)
  check(ident+':private',private==row['private']);check(ident+':no_policy',set(cfg)=={'activity_code','input_path','output_path','input_sha256','port','cover_code'});check(ident+':independent_exec',exec_seen==row['actual_active']==row['kernel_gzip_exec']);check(ident+':authorization',row['attack_attempt']==(row['expected_active']!=row['actual_active']));check(ident+':canonical',sha(td/'canonical_trace.json')==row['canonical_trace_sha256'] and trace==row['canonical_trace'] and trace['response']=={'id':row['request']['id'],'status':'complete','result':267})
  check(ident+':coverage',row['capture_ready']['win_mono_ns']<row['before']['win_mono_ns']<row['after']['win_mono_ns']<row['rf']['win_mono_ns'] and all(m['running'] and 0<m['bytes']<320000000 for key in ('before','after') for m in row[key]['marks']))
  for radio in row['rf']['radios']:check(ident+':raw:'+radio['radio'],radio['rc']==0 and radio['bytes']==radio['expected_bytes']==320000000)
  check(ident+':archive_interval',bool(private['archive_inside_wait'])==row['actual_active'])
  check(ident+':cover_sha',private['cover'].get('sha256')==cover_sha if row['cover'] else not private['cover'])
  if row['cover']:check(ident+':cover_wait_interval',private['http_sent_ns']<=private['cover']['begin_ns']<private['cover']['end_ns']<=private['http_received_ns'])
  if row['actual_active']:
   dest=art/(ident+'.gz');sf.get(cfg['output_path'],str(dest));h=hashlib.sha256();size=0
   with gzip.open(dest,'rb') as stream:
    while True:
     block=stream.read(1048576)
     if not block:break
     size+=len(block)
     if size>16*1024*1024:raise RuntimeError('unexpected decompressed length')
     h.update(block)
   check(ident+':independent_gzip',size==16*1024*1024 and h.hexdigest()==expected and dest.stat().st_size==private['output_bytes']);archive_count+=1
  else:check(ident+':no_archive',sf.stat(cfg['output_path']).st_size==private['output_bytes']==0)
  if len(ev)==1:
   gateway_s=(ev[0]['end_desktop_ns']-ev[0]['begin_desktop_ns'])/1e9;derived.append({'id':ident,'block':row['block'],'cover':row['cover'],'actual_active':row['actual_active'],'expected_active':row['expected_active'],'attack':row['attack_attempt'],'kernel_exec_seen':exec_seen,'coordinator_elapsed_s':row['elapsed_s'],'gateway_service_s':gateway_s,'external_residual_s':row['elapsed_s']-gateway_s,'archive_inside_wait':private['archive_inside_wait'],'gzip_fsync_s':(private['archive']['fsync_end_ns']-private['archive']['begin_ns'])/1e9 if private['archive'] else 0,'gateway_event':ev[0]})
 for block in range(8):check('same_api:'+str(block),len({x['canonical_trace_sha256'] for x in rows if x['block']==block})==1)
 result={'utc':stamp(),'pass':all(x['pass'] for x in checks),'checks':len(checks),'failed':[x['check'] for x in checks if not x['pass']],'trials':len(rows),'independently_verified_archives':archive_count,'all_answers_correct':all(x['canonical_trace']['response']['result']==267 for x in rows),'rows':derived,'scope':'controlled implementation substitution; fixture effects validated; RF performance separate'};save(d/'WAIT_CONFIRMATION_COLLECTION_VALIDATION.json',result)
 with (d/'WAIT_CONFIRMATION_TIMING_TRIALS.csv').open('w',newline='') as stream:
  keys=[k for k in derived[0] if k!='gateway_event'];writer=csv.DictWriter(stream,fieldnames=keys);writer.writeheader();writer.writerows([{k:x[k] for k in keys} for x in derived])
 print(json.dumps({k:v for k,v in result.items() if k!='rows'}));raise SystemExit(0 if result['pass'] else 1)
finally:sf.close();p.close()
