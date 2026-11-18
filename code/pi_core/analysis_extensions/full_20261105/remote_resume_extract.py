import concurrent.futures,hashlib,json,os,pathlib,time,traceback
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1';os.environ['MKL_NUM_THREADS']='1'
import numpy as np
from remote_extract import one,save
root=pathlib.Path(__file__).resolve().parent;os.nice(10);start=time.time();done={}
try:
 assert hashlib.sha256((root/'remote_extract.py').read_bytes()).hexdigest()=='0b67c178a5bf7a01b93f6d0cff9d799857923ba1c4e9b956c921881782e0b69a'
 sources={x['filename']:x for x in json.loads((root/'SOURCE_RECEIPTS.json').read_text())['files']}
 for p in (root/'features').glob('*.json'):
  d=json.loads(p.read_text());s=sources[d['filename']];assert d['raw_sha256']==s['sha256'] and d['raw_bytes']==s['bytes'] and d['full_contiguous']
  with np.load(p.with_suffix('.npz')) as f:
   assert f['features'].shape==(260,) and np.isfinite(f['features']).all() and int(f['sample_counts'].sum())*2==d['raw_bytes']
  done[d['filename']]=d
 cached=len(done);save(root/'RESUME_CACHE_VALIDATION.json',{'cached_files':cached,'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'scope':'original full-raw SHA receipts against source SHA and numeric NPZ shape; skipped raw files are not rehashed'})
 with concurrent.futures.ProcessPoolExecutor(max_workers=4) as ex:
  queued=set(done);pending={}
  while True:
   queue=json.loads((root/'QUEUE.json').read_text())['files'];assert len(queue)==240
   for row in queue:
    if row['filename'] in queued or not (root/'raw'/row['filename']).exists():continue
    row=dict(row,root=str(root));pending[ex.submit(one,row)]=row['filename'];queued.add(row['filename'])
   for future in list(pending):
    if not future.done():continue
    d=future.result();s=sources[d['filename']];assert d['raw_sha256']==s['sha256'] and d['raw_bytes']==s['bytes'];done[d['filename']]=d;del pending[future]
    save(root/'RESUME_EXTRACTION_STATUS.json',{'completed':len(done),'cached':cached,'planned':240,'elapsed_s':time.time()-start});print(json.dumps({'completed':len(done),'file':d['filename']}),flush=True)
   if (root/'UPLOAD_COMPLETE.json').exists() and len(done)==240 and not pending:break
   if time.time()-start>10800:raise TimeoutError('3h resume limit')
   time.sleep(2)
 save(root/'EXTRACTION_COMPLETE_RESUMED.json',{'receipts':list(done.values()),'cached_original_features':cached,'full_contiguous':True,'elapsed_s':time.time()-start});print('EXTRACTION COMPLETE',flush=True)
except Exception:(root/'RESUME_EXTRACTION_FAILURE.log').write_text(traceback.format_exc());raise
