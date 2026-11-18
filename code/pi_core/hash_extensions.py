import json,pathlib,time,traceback
from bridge_utils import *
b=pathlib.Path(__file__).resolve().parent;lower_priority();out=b/'extension_transfer';out.mkdir(exist_ok=False);records=[];files=[];stages=[]
for study,stage,n in [('complete_trace_study','trace',20),('order_study','order',20),('burst_study','burst',48)]:
 d=pathlib.Path(json.loads((b/study/'LATEST.json').read_text())['directory']);complete=json.loads((d/'COMPLETE.json').read_text());post=json.loads((d/'POSTFLIGHT.json').read_text());rows=json.loads((d/'RESULTS.json').read_text());assert complete['trials']==complete['valid']==len(rows)==n and all(x['valid'] for x in rows);assert post['restore']['rc']==0 and post['rig']['rc']==0 and post['pi_lock_release']==0;stages.append({'stage':stage,'directory':str(d),'complete_sha256':sha(d/'COMPLETE.json'),'freeze_sha256':sha(d/'FREEZE.json')});records.extend(rows)
for radio in ('930c','16bc'):
 for row in records:
  rf=next(x for x in row['rf']['radios'] if x['radio']==radio);files.append({'id':row['id'],'stage':row['stage'],'radio':radio,'filename':row['id']+'_'+radio+'.iq','source_raw':rf['raw'].replace('\\','/'),'expected_bytes':rf['bytes']})
save(out/'MANIFEST.json',{'files':files,'stages':stages});save(out/'LEDGER.json',{'records':records,'stages':stages});w=connect('192.0.2.4','win');wf=w.open_sftp()
try:
 remote='F:/Data/telltale_ext_hash_'+time.strftime('%Y%m%d_%H%M%S',time.gmtime());wf.mkdir(remote);wf.put(str(b/'source_receipt.py'),remote+'/source_receipt.py');wf.put(str(out/'MANIFEST.json'),remote+'/MANIFEST.json');ret=run(w,'python '+remote+'/source_receipt.py '+remote+'/MANIFEST.json',timeout=650);save(out/'SOURCE_HASH_COMMAND.json',ret);wf.get(remote+'/SOURCE_RECEIPTS.json',str(out/'SOURCE_RECEIPTS.json'));receipts=json.loads((out/'SOURCE_RECEIPTS.json').read_text());assert len(receipts['files'])==176;save(out/'HASH_COMPLETE.json',{'files':176,'bytes':sum(x['bytes'] for x in receipts['files']),'remote_spool':remote,'utc':stamp()});print(json.dumps({'files':176,'bytes':sum(x['bytes'] for x in receipts['files']),'utc':stamp()}))
except Exception:(out/'FAILURE.log').write_text(traceback.format_exc());raise
finally:wf.close();w.close()
