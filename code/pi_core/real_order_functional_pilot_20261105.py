"""Functional research pilot only: real file operations, no RF or new classification data."""
from pathlib import Path
import os,time,json,gzip,hashlib,datetime
if os.name=='nt':
 import ctypes
 ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(),0x4000)
B=Path(__file__).resolve().parent;O=B/'candidate_real_order_20261105';O.mkdir(exist_ok=False);sha=lambda b:hashlib.sha256(b).hexdigest()
data=hashlib.shake_256(b'Telltale:real-order-functional-pilot:20261105:v1').digest(16*1024*1024);archive=gzip.compress(data,compresslevel=6,mtime=0);(O/'fixture.bin').write_bytes(data);(O/'fixture.bin.gz').write_bytes(archive);input_sha=sha(archive);output_sha=sha(data);assert input_sha!='0'*64
records=[]
for valid_digest in [True,False]:
 expected=input_sha if valid_digest else '0'*64
 for legal_order in [True,False]:
  rid=('valid' if valid_digest else 'mismatch')+('_verify_first' if legal_order else '_extract_first');d=O/rid;d.mkdir();out=d/'decoded.bin';events=[]
  def check():
   t=time.perf_counter_ns();got=sha((O/'fixture.bin.gz').read_bytes());events.append({'operation':'verify_compressed_sha256','begin_ns':t,'end_ns':time.perf_counter_ns(),'matches':got==expected})
   if got!=expected:raise ValueError('integrity mismatch')
  def extract():
   t=time.perf_counter_ns();decoded=gzip.decompress((O/'fixture.bin.gz').read_bytes());assert sha(decoded)==output_sha;out.write_bytes(decoded);events.append({'operation':'decompress_and_write','begin_ns':t,'end_ns':time.perf_counter_ns(),'bytes':len(decoded)})
  cleanup=False;pre_cleanup_exists=False;t0=time.perf_counter_ns()
  try:
   for fn in ([check,extract] if legal_order else [extract,check]):fn()
   response={'status':'complete','result':{'decoded_bytes':len(data),'sha256':output_sha}}
  except ValueError:
   pre_cleanup_exists=out.exists()
   if pre_cleanup_exists:out.unlink();cleanup=True
   response={'status':'integrity_error','result':None}
  t1=time.perf_counter_ns()
  request={'id':'candidate-'+str(valid_digest),'method':'verified_extract','params':{'compressed_input_sha256':expected,'output_id':'artifact'}}
  canonical={'trusted_requirement':'verify_input_before_decompression','request':request,'response':response}
  sequence=[e['operation'] for e in events];violation=sequence[0]=='decompress_and_write';assert violation==(not legal_order)
  final_files=[{'name':'decoded.bin','bytes':out.stat().st_size,'sha256':sha(out.read_bytes())}] if out.exists() else []
  records.append({'id':rid,'valid_digest':valid_digest,'actual_verify_first':legal_order,'violation':violation,'public_projection':canonical,'canonical_sha256':sha(json.dumps(canonical,sort_keys=True,separators=(',',':')).encode()),'private_events':events,'wall_s':(t1-t0)/1e9,'pre_cleanup_output_existed_on_error':pre_cleanup_exists,'own_sandbox_cleanup_on_error':cleanup,'final_files':final_files})
pairs=[]
for valid_digest in [True,False]:
 pp=[r for r in records if r['valid_digest']==valid_digest];assert len(pp)==2 and pp[0]['canonical_sha256']==pp[1]['canonical_sha256'] and pp[0]['violation']!=pp[1]['violation'] and pp[0]['final_files']==pp[1]['final_files'];pairs.append({'valid_digest':valid_digest,'ids':[r['id'] for r in pp],'same_public_projection':True,'same_final_output_inventory':True,'opposing_order_compliance':True,'canonical_sha256':pp[0]['canonical_sha256']})
result={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'data-desktop functional pilot; four operation runs, no RF capture or classifier evaluation; does not change 472-record/944-IQ dataset','code_sha256':sha(Path(__file__).read_bytes()),'fixture_bytes':len(data),'fixture_sha256':output_sha,'gzip_bytes':len(archive),'gzip_sha256':input_sha,'records':records,'pairs':pairs,'counterexample':'Final public response and output inventory do not determine whether decompression occurred before successful input verification. Trusted intermediate file/syscall instrumentation can distinguish operations. RF observability on Pi is not measured.'}
(O/'RESULTS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8',newline='')
lines=['# /','',result['scope'],'','SHA256gzip16MiBRF472RF','', '|||||||','|---|---|---|---|---|---:|']
for r in records:lines.append('|%s|%s|%s|%s|%s|%.5f|'%(str(r['valid_digest']),','.join(e['operation'] for e in r['private_events']),r['public_projection']['response']['status'],'1' if r['final_files'] else '',r['violation'],r['wall_s']))
lines+=['','//','', 'PiEMPiRF','', 'SHA'+result['code_sha256']+'RESULTS.json“error”']
(O/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='');print(json.dumps({'out':str(O),'result_sha256':sha((O/'RESULTS.json').read_bytes()),'pairs':pairs,'wall_s':[r['wall_s'] for r in records]},ensure_ascii=False))
