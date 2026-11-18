import hashlib,json,pathlib,subprocess,sys,tarfile,time
root=pathlib.Path(__file__).resolve().parent
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
assert (root/'EXTRACTION_COMPLETE_RESUMED.json').exists()
for name in ('remote_extensions.py','remote_wait_eval.py'):
 ret=subprocess.run([sys.executable,str(root/name),'--root',str(root)],capture_output=True,text=True);(root/(name+'.resume.stdout.log')).write_text(ret.stdout);(root/(name+'.resume.stderr.log')).write_text(ret.stderr)
 if ret.returncode:raise RuntimeError(name+' rc='+str(ret.returncode)+' '+ret.stderr[-2000:])
files=[p for p in (root/'features').iterdir() if p.suffix in ('.npz','.json')]
assert len(files)==480
for name in ('EXTENSION_EVALUATION.json','WAIT_EARLY.json','EXTRACTION_COMPLETE_RESUMED.json','RESUME_CACHE_VALIDATION.json','SOURCE_RECEIPTS.json','LEDGER.json','QUEUE.json','CONFIRMATION_MODELS.json','BURST_EXPLORATORY_FREEZE.json','WAIT_COLLECTION_VALIDATION.json','remote_extract.py','remote_extensions.py','remote_wait_eval.py','remote_resume_extract.py'):
 files.append(root/name)
manifest={'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'files':[{'path':str(p.relative_to(root)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in files]};(root/'RESULT_MANIFEST_20261105.json').write_text(json.dumps(manifest,indent=2));archive=root/'EXTENSION_RESULTS_20261105.tar.gz'
with tarfile.open(archive,'w:gz',compresslevel=1) as t:
 for p in files+[root/'RESULT_MANIFEST_20261105.json']:t.add(p,arcname=str(p.relative_to(root)),recursive=False)
receipt={'archive':archive.name,'sha256':sha(archive),'bytes':archive.stat().st_size,'files':len(files),'utc':manifest['utc'],'raw_files_verified':240};(root/'RESULT_PACKAGE_RECEIPT_20261105.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
