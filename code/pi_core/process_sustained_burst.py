import json,pathlib,shlex,subprocess,sys,tarfile,traceback
from sustained_pipeline_utils import *
p=SustainedPipe();save(p.out/'CONTROLLER_PID.json',{'pid':__import__('os').getpid(),'script':str(pathlib.Path(__file__).resolve()),'utc':stamp()})
try:
 d=p.wait(lambda:p.study('sustained_burst_study'),'waiting_sustained24_complete')
 z=subprocess.run([sys.executable,'-X','utf8',str(B/'validate_sustained_burst.py')],capture_output=True,text=True,encoding='utf-8',errors='replace');save(p.out/'VALIDATION_COMMAND.json',{'returncode':z.returncode,'stdout':z.stdout,'stderr':z.stderr})
 if z.returncode:raise RuntimeError('C15 independent collection validation failed')
 rows,files=p.manifest(d,'sustained_burst_confirmation');assert len(rows)==24 and len(files)==48;hashes=p.source_hash(files,'F')
 parent=B/'untraced_processing_20261105'
 def released():
  if (parent/'FAILURE.log').exists():raise RuntimeError('C13 failed; inspect before next CPU handoff')
  q=parent/'STATUS.json';r=parent/'RESOURCE_RELEASE.json';v=parent/'LOCAL_RESULTS_RECEIPT.json'
  return all(x.exists() for x in (q,r,v)) and json.loads(q.read_text(encoding='utf-8-sig'))['phase']=='complete' and json.loads(r.read_text(encoding='utf-8-sig'))['returncode']==0 and json.loads(v.read_text(encoding='utf-8-sig'))['verified']
 p.wait(released,'waiting_C13_CPU_results_verified_and_released');p.allocate()
 for src,dest in [('FREEZE.json','COLLECTION_FREEZE.json'),('COMPLETE.json','COLLECTION_COMPLETE.json'),('POSTFLIGHT.json','COLLECTION_POSTFLIGHT.json'),('SUSTAINED_BURST_COLLECTION_VALIDATION.json','SUSTAINED_BURST_COLLECTION_VALIDATION.json')]:p.sf.put(str(d/src),p.root+'/'+dest)
 for n in ['PROTOCOL.md','collect_sustained_burst.py','pi_api.py','rig_capture_stagger.py','burst.c']:p.sf.put(str(d/'source'/n),p.root+'/'+n)
 p.atomic('SOURCE_RECEIPTS.json',{'files':hashes});p.atomic('LEDGER.json',{'records':rows});p.atomic('QUEUE.json',{'files':files});p.start();p.transfer(files,'F');p.atomic('UPLOAD_COMPLETE.json',{'expected_files':48,'bytes':7680000000,'utc':stamp()})
 def extracted():
  try:p.sf.stat(p.root+'/EXTRACTION_FAILURE.log');raise RuntimeError('C15 remote extraction failed')
  except FileNotFoundError:pass
  try:p.sf.stat(p.root+'/EXTRACTION_COMPLETE.json');return True
  except FileNotFoundError:return False
 p.wait(extracted,'waiting_full48_extractions');z=run(p.c,'env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 nice -n 10 python '+shlex.quote(p.root+'/remote_package_sustained_burst.py')+' --root '+shlex.quote(p.root),timeout=180,check=False);save(p.out/'PACKAGE_COMMAND.json',z)
 if z['rc']:raise RuntimeError(z['stderr'])
 receipt=json.loads(p.sf.open(p.root+'/RESULT_PACKAGE_RECEIPT.json').read());out=p.out/'analysis';out.mkdir();archive=out/receipt['archive'];p.sf.get(p.root+'/'+receipt['archive'],str(archive));assert sha(archive)==receipt['sha256'] and archive.stat().st_size==receipt['bytes']
 with tarfile.open(archive) as t:
  for m in t.getmembers():
   q=pathlib.PurePosixPath(m.name);assert m.isfile() and not q.is_absolute() and '..' not in q.parts
  t.extractall(out,filter='data')
 manifest=json.loads((out/'RESULT_MANIFEST.json').read_text(encoding='utf-8-sig'));assert manifest['feature_files']==96 and manifest['raw_source_hashes_verified']==48
 for x in manifest['files']:
  q=out/x['path'];assert q.stat().st_size==x['bytes'] and sha(q)==x['sha256']
 save(p.out/'LOCAL_RESULTS_RECEIPT.json',{'verified':True,'files':len(manifest['files']),'package':receipt,'utc':stamp()});save(p.out/'BRIDGE_RELEASE_REQUEST.json',{'node':p.cfg['id'],'utc':stamp()})
 def own_release():
  q=p.out/'RESOURCE_RELEASE.json';return q.exists() and json.loads(q.read_text(encoding='utf-8-sig'))['returncode']==0
 p.wait(own_release,'awaiting_authorized_bridge_release');p.state('complete',verified_files=len(manifest['files']))
except Exception:
 (p.out/'FAILURE.log').write_text(traceback.format_exc(),encoding='utf-8',newline='');p.state('failed',detail='see preserved FAILURE.log')
 if p.sf and p.root:
  try:
   q=p.out/'STOP_REQUESTED.json';save(q,{'utc':stamp(),'reason':'own C15 controller failed; preserve artifacts'});p.sf.put(str(q),p.root+'/STOP_REQUESTED.json')
  except Exception:pass
 raise
finally:p.close()
