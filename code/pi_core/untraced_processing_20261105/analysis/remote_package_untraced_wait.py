"""Package C13 complete feature artifacts; raw IQ remains on capture-pc and CPU node."""
import hashlib,json,pathlib,subprocess,sys,tarfile,time
R=pathlib.Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
z=subprocess.run([sys.executable,str(R/'remote_untraced_wait_eval.py'),'--root',str(R)],capture_output=True,text=True)
(R/'EVALUATION_COMMAND.json').write_text(json.dumps({'returncode':z.returncode,'stdout':z.stdout,'stderr':z.stderr},indent=2))
if z.returncode:raise RuntimeError(z.stderr)
features=sorted((R/'features').glob('*.npz'))+sorted((R/'features').glob('*.json'));assert len(features)==128
names=['UNTRACED_WAIT_EVALUATION.json','EVALUATION_COMMAND.json','LEDGER.json','SOURCE_RECEIPTS.json','UNTRACED_WAIT_COLLECTION_VALIDATION.json','COLLECTION_FREEZE.json','COLLECTION_COMPLETE.json','COLLECTION_POSTFLIGHT.json','UNTRACED_WAIT_PROTOCOL.md','WAIT_CONFIRMATION_MODELS.json','RELATIVE_REFERENCE_MODELS.json','EXECUTION_WINDOW_MODELS.json','remote_untraced_wait_eval.py','remote_package_untraced_wait.py','relative_reference_features.py','execution_window_features.py','remote_extract_confirmation.py','remote_extensions.py','remote_evaluate.py','blockwise_comparison.py','collect_untraced_wait.py','pi_api.py','rig_capture_stagger.py','bridge_utils.py']
files=features+[R/n for n in names]
manifest={'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'science_trials':32,'feature_files':128,'raw_source_hashes_verified':64,'files':[{'path':str(p.relative_to(R)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in files]}
(R/'RESULT_MANIFEST.json').write_text(json.dumps(manifest,indent=2))
archive=R/'untraced_wait_results.tar.gz'
with tarfile.open(archive,'w:gz') as t:
 for p in files+[R/'RESULT_MANIFEST.json']:t.add(p,arcname=str(p.relative_to(R)),recursive=False)
receipt={'archive':archive.name,'bytes':archive.stat().st_size,'sha256':sha(archive),'files':len(manifest['files'])}
(R/'RESULT_PACKAGE_RECEIPT.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
