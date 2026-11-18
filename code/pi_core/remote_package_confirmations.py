import hashlib,json,pathlib,subprocess,sys,tarfile,time
r=pathlib.Path(__file__).resolve().parent
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
for script in ('remote_confirmation_eval.py','remote_wait_confirmation_eval.py','remote_relative_reference_eval.py'):
 z=subprocess.run([sys.executable,str(r/script),'--root',str(r)],capture_output=True,text=True);(r/(script+'.stdout.log')).write_text(z.stdout);(r/(script+'.stderr.log')).write_text(z.stderr)
 if z.returncode:raise RuntimeError(script+' '+z.stderr[-3000:])
files=[p for p in (r/'features').iterdir() if p.suffix in ('.npz','.json')];assert len(files)==1032
for name in ('INDEPENDENT_CONFIRMATION.json','WAIT_CONFIRMATION_EVALUATION.json','EXTRACTION_COMPLETE.json','SOURCE_RECEIPTS.json','LEDGER.json','QUEUE.json','CONFIRMATION_MODELS.json','BURST_EXPLORATORY_FREEZE.json','WAIT_CONFIRMATION_MODELS.json','CONFIRMATION_COLLECTION_VALIDATION.json','WAIT_CONFIRMATION_COLLECTION_VALIDATION.json','remote_confirmation_eval.py','remote_wait_confirmation_eval.py','remote_extract_confirmation.py','CONFIRMATION_PARTIAL_COLLECTION_VALIDATION.json','INTERRUPTED_FREEZE.json','INTERRUPTED_FAILURE.log','RELATIVE_REFERENCE_EVALUATION.json','RELATIVE_REFERENCE_MODELS.json','relative_reference_features.py','remote_relative_reference_eval.py','blockwise_comparison.py','RELATIVE_REFERENCE_PROTOCOL.md','export_relative_reference.py'):files.append(r/name)
manifest={'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'files':[{'path':str(p.relative_to(r)),'sha256':sha(p),'bytes':p.stat().st_size} for p in files]};(r/'RESULT_MANIFEST.json').write_text(json.dumps(manifest,indent=2));a=r/'CONFIRMATION_RESULTS.tar.gz'
with tarfile.open(a,'w:gz',compresslevel=1) as t:
 for p in files+[r/'RESULT_MANIFEST.json']:t.add(p,arcname=str(p.relative_to(r)),recursive=False)
receipt={'archive':a.name,'sha256':sha(a),'bytes':a.stat().st_size,'files':len(files),'raw_source_hashes_verified':516};(r/'RESULT_PACKAGE_RECEIPT.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
