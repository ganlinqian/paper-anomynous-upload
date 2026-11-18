import json,pathlib,subprocess,time,traceback
import paramiko
from bridge_utils import *
b=pathlib.Path(__file__).resolve().parent;lower_priority();out=b/'wait_transfer';out.mkdir(exist_ok=False);deadline=time.monotonic()+3600
while True:
 lp=b/'io_wait_study/LATEST.json'
 if lp.exists():
  d=pathlib.Path(json.loads(lp.read_text())['directory'])
  if (d/'FAILURE.log').exists():raise RuntimeError('wait collection failed; no silent exclusion')
  if (d/'COMPLETE.json').exists() and (d/'POSTFLIGHT.json').exists():break
 if time.monotonic()>deadline:raise TimeoutError('wait collection incomplete')
 time.sleep(5)
comp=json.loads((d/'COMPLETE.json').read_text());post=json.loads((d/'POSTFLIGHT.json').read_text());rows=json.loads((d/'RESULTS.json').read_text());assert comp['trials']==comp['valid']==len(rows)==32;assert post['restore']['rc']==0 and post['rig']['rc']==0 and post['pi_lock_release']==0
files=[]
for radio in ('930c','16bc'):
 for row in rows:
  rf=next(x for x in row['rf']['radios'] if x['radio']==radio);files.append({'id':row['id'],'stage':'wait','radio':radio,'filename':row['id']+'_'+radio+'.iq','source_raw':rf['raw'].replace('\\','/'),'expected_bytes':rf['bytes']})
save(out/'MANIFEST.json',{'files':files,'directory':str(d)});save(out/'LEDGER.json',{'records':rows,'directory':str(d)});w=connect('192.0.2.4','win');wf=w.open_sftp();cfg=json.loads((b/'EXTENSION_REMOTE.json').read_text());root=cfg['remote_root'];c=paramiko.SSHClient();c.load_system_host_keys();c.set_missing_host_key_policy(paramiko.RejectPolicy());c.connect(cfg['host'],port=cfg['port'],username=cfg['user'],key_filename=cfg['key'],timeout=15);sf=c.open_sftp()
try:
 spool='<DATA>/telltale_wait_hash_'+time.strftime('%Y%m%d_%H%M%S',time.gmtime());wf.mkdir(spool);wf.put(str(b/'source_receipt.py'),spool+'/source_receipt.py');wf.put(str(out/'MANIFEST.json'),spool+'/MANIFEST.json');ret=run(w,'python '+spool+'/source_receipt.py '+spool+'/MANIFEST.json',timeout=500);save(out/'HASH_COMMAND.json',ret);wf.get(spool+'/SOURCE_RECEIPTS.json',str(out/'SOURCE_RECEIPTS.json'));newsource=json.loads((out/'SOURCE_RECEIPTS.json').read_text());save(out/'HASH_COMPLETE.json',{'files':64,'utc':stamp()})
 for name,key,newvalues in [('LEDGER.json','records',rows),('QUEUE.json','files',files),('SOURCE_RECEIPTS.json','files',newsource['files'])]:
  current=json.loads(sf.open(root+'/'+name).read().decode());assert not any(x.get('stage')=='wait' for x in current[key]) if name!='SOURCE_RECEIPTS.json' else True;current[key].extend(newvalues);save(out/('MERGED_'+name),current);sf.put(str(out/('MERGED_'+name)),root+'/'+name+'.pending');sf.posix_rename(root+'/'+name+'.pending',root+'/'+name)
 start=time.monotonic();total=0
 with (out/'scp.log').open('wb') as log:
  for i,row in enumerate(files):
   cmd=['scp','-q','-3','-X','nrequests=256','-X','buffer=131072','-o','Compression=no','-F',str(b/'extension_ssh_config'),'claw-rig-ext:'+row['source_raw'],'claw-cpu-ext:'+root+'/raw/'+row['filename']+'.partial'];ret=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,timeout=240)
   if ret.returncode:raise RuntimeError('scp '+row['filename']+' rc='+str(ret.returncode))
   remote=root+'/raw/'+row['filename'];assert sf.stat(remote+'.partial').st_size==row['expected_bytes'];sf.rename(remote+'.partial',remote);total+=row['expected_bytes'];save(out/'STATUS.json',{'completed':i+1,'planned':64,'bytes':total,'elapsed_s':time.monotonic()-start,'utc':stamp()});print(json.dumps({'completed':i+1,'planned':64,'radio':row['radio'],'elapsed_s':time.monotonic()-start}),flush=True)
 marker={'expected_files':64,'bytes':total,'utc':stamp()};save(out/'WAIT_UPLOAD_COMPLETE.json',marker);sf.put(str(out/'WAIT_UPLOAD_COMPLETE.json'),root+'/WAIT_UPLOAD_COMPLETE.json')
 while not (b/'extension_transfer/F_UPLOAD_COMPLETE.json').exists():
  if (b/'extension_transfer/TRANSFER_FAILURE.log').exists():raise RuntimeError('F upload failed')
  if time.monotonic()>deadline+3600:raise TimeoutError('F upload incomplete')
  time.sleep(10)
 queue=json.loads(sf.open(root+'/QUEUE.json').read().decode());assert len(queue['files'])==240;marker={'expected_files':240,'bytes':sum(x['expected_bytes'] for x in queue['files']),'utc':stamp()};save(out/'ALL_UPLOAD_COMPLETE.json',marker);sf.put(str(out/'ALL_UPLOAD_COMPLETE.json'),root+'/UPLOAD_COMPLETE.json');print(json.dumps(marker),flush=True)
except Exception:(out/'FAILURE.log').write_text(traceback.format_exc());raise
finally:wf.close();w.close();sf.close();c.close()
