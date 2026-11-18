import tarfile,traceback
from confirmation_pipeline_utils import *
p=Pipe()
try:
 dF=p.wait(lambda:p.study('confirmation_study'),'waiting_C08_complete')
 def c09_started():
  d=p.study('burst_confirmation_study',False)
  return d if d and (d/'RESULTS.json').exists() and len(json.loads((d/'RESULTS.json').read_text()))>0 else None
 p.wait(c09_started,'waiting_C09_preflight_and_first_record')
 # Global preflight rejects other Python workloads. Start F-only hashing after C09 preflight.
 z=subprocess.run([sys.executable,str(B/'validate_confirmation_partial.py')],capture_output=True,text=True,encoding='utf-8',errors='replace');save(p.out/'VALIDATE_PARTIAL_COMMAND.json',{'rc':z.returncode,'stdout':z.stdout,'stderr':z.stderr})
 if z.returncode:raise RuntimeError('Interrupted campaign record verification failed')
 partial=B/'confirmation_study/confirm_20261105_032747_8137bb'
 rowsNew,filesNew=p.manifest(dF,'confirmation');rowsPartial,filesPartial=p.manifest(partial,'confirmation_partial');assert len(rowsNew)==80 and len(rowsPartial)==42
 rowsF=rowsNew+rowsPartial;filesF=filesNew+filesPartial;assert len(filesF)==244;hashF=p.source_hash(filesF,'F')
 def old_cpu_released():
  q=B/'analysis_extensions/full_20261105/RESOURCE_RELEASE.json'
  if (B/'analysis_extensions/full_20261105/FAILURE.log').exists():raise RuntimeError('Previous result retrieval failed')
  return q.exists() and json.loads(q.read_text(encoding='utf-8-sig'))['returncode']==0
 p.wait(old_cpu_released,'waiting_previous_CPU_release');p.allocate();p.sf.put(str(B/'CONFIRMATION_PARTIAL_COLLECTION_VALIDATION.json'),p.root+'/CONFIRMATION_PARTIAL_COLLECTION_VALIDATION.json');p.sf.put(str(partial/'FREEZE.json'),p.root+'/INTERRUPTED_FREEZE.json');p.sf.put(str(partial/'FAILURE.log'),p.root+'/INTERRUPTED_FAILURE.log');p.atomic('SOURCE_RECEIPTS.json',{'files':hashF});p.atomic('LEDGER.json',{'records':rowsF});p.atomic('QUEUE.json',{'files':filesF});p.start();p.transfer(filesF,'F');save(p.out/'F_UPLOAD_COMPLETE.json',{'files':244,'utc':stamp()})
 dB=p.wait(lambda:p.study('burst_confirmation_study'),'waiting_C09_complete')
 z=subprocess.run([sys.executable,str(B/'validate_confirmations.py')],capture_output=True,text=True,encoding='utf-8',errors='replace');save(p.out/'VALIDATE_C08_C09_COMMAND.json',{'rc':z.returncode,'stdout':z.stdout,'stderr':z.stderr})
 if z.returncode:raise RuntimeError('C08/C09 independent validation failed')
 dW=p.wait(lambda:p.study('wait_confirmation_study'),'waiting_C10_complete_no_J_reads')
 z=subprocess.run([sys.executable,str(B/'validate_wait_confirmation.py')],capture_output=True,text=True,encoding='utf-8',errors='replace');save(p.out/'VALIDATE_C10_COMMAND.json',{'rc':z.returncode,'stdout':z.stdout,'stderr':z.stderr})
 if z.returncode:raise RuntimeError('C10 independent archive and record verification failed')
 rowsB,filesB=p.manifest(dB,'burst_confirmation');rowsW,filesW=p.manifest(dW,'wait_confirmation');assert len(rowsB)==72 and len(rowsW)==64;filesJ=filesB+filesW;hashJ=p.source_hash(filesJ,'J');allfiles=filesF+filesJ;allrows=rowsF+rowsB+rowsW;assert len(allfiles)==516 and len(allrows)==258
 p.atomic('SOURCE_RECEIPTS.json',{'files':hashF+hashJ});p.atomic('LEDGER.json',{'records':allrows});p.atomic('QUEUE.json',{'files':allfiles});p.sf.put(str(B/'CONFIRMATION_COLLECTION_VALIDATION.json'),p.root+'/CONFIRMATION_COLLECTION_VALIDATION.json');p.sf.put(str(dW/'WAIT_CONFIRMATION_COLLECTION_VALIDATION.json'),p.root+'/WAIT_CONFIRMATION_COLLECTION_VALIDATION.json');p.transfer(filesJ,'J');p.atomic('UPLOAD_COMPLETE.json',{'expected_files':516,'bytes':sum(x['expected_bytes'] for x in allfiles),'utc':stamp()})
 def extracted():
  try:p.sf.stat(p.root+'/EXTRACTION_FAILURE.log');raise RuntimeError('Remote confirmation extraction failure')
  except FileNotFoundError:pass
  try:p.sf.stat(p.root+'/EXTRACTION_COMPLETE.json');return True
  except FileNotFoundError:return False
 p.wait(extracted,'waiting_516_full_extractions');p.state('evaluating_frozen_models')
 z=run(p.c,'env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 nice -n 10 python '+shlex.quote(p.root+'/remote_package_confirmations.py'),timeout=240,check=False);save(p.out/'PACKAGE_COMMAND.json',z)
 if z['rc']:raise RuntimeError(z['stderr'])
 receipt=json.loads(p.sf.open(p.root+'/RESULT_PACKAGE_RECEIPT.json').read());analysis=p.out/'analysis';analysis.mkdir();archive=analysis/receipt['archive'];p.sf.get(p.root+'/'+receipt['archive'],str(archive));assert sha(archive)==receipt['sha256'] and archive.stat().st_size==receipt['bytes']
 with tarfile.open(archive) as t:
  for member in t.getmembers():
   q=pathlib.PurePosixPath(member.name)
   if q.is_absolute() or '..' in q.parts or not member.isfile():raise RuntimeError('unsafe archive member')
  t.extractall(analysis,filter='data')
 manifest=json.loads((analysis/'RESULT_MANIFEST.json').read_text())
 for item in manifest['files']:
  q=analysis/item['path'];assert q.stat().st_size==item['bytes'] and sha(q)==item['sha256']
 save(p.out/'LOCAL_RESULTS_RECEIPT.json',{'verified':True,'files':len(manifest['files']),'package':receipt,'utc':stamp()})
 save(p.out/'BRIDGE_RELEASE_REQUEST.json',{'node':p.cfg['id'],'utc':stamp(),'reason':'results verified; release through authorized project bridge without copying scoped credentials'})
 def released():
  q=p.out/'RESOURCE_RELEASE.json'
  return q.exists() and json.loads(q.read_text(encoding='utf-8-sig'))['returncode']==0
 p.wait(released,'awaiting_authorized_bridge_release');p.state('complete',verified_files=len(manifest['files']))
except Exception:
 (p.out/'FAILURE.log').write_text(traceback.format_exc(),encoding='utf-8')
 p.state('failed',detail='see preserved FAILURE.log')
 if p.sf and p.root:
  try:
   q=p.out/'STOP_REQUESTED.json';save(q,{'utc':stamp(),'reason':'own controller failed; preserve artifacts'});p.sf.put(str(q),p.root+'/STOP_REQUESTED.json')
  except Exception:pass
 raise
finally:p.close()
