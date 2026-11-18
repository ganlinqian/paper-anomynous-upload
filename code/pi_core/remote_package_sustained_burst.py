import argparse,hashlib,json,pathlib,subprocess,sys,tarfile,time
ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);a=ap.parse_args();R=pathlib.Path(a.root)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
subprocess.run([sys.executable,str(R/'remote_sustained_burst_eval.py'),'--root',str(R)],check=True)
result=json.loads((R/'SUSTAINED_BURST_EVALUATION.json').read_text());assert result['raw_source_hashes_verified']==48
features=sorted((R/'features').glob('*.npz'))+sorted((R/'features').glob('*.json'));assert len(features)==96
names=['SUSTAINED_BURST_EVALUATION.json','SOURCE_RECEIPTS.json','LEDGER.json','COLLECTION_FREEZE.json','COLLECTION_COMPLETE.json','COLLECTION_POSTFLIGHT.json','SUSTAINED_BURST_COLLECTION_VALIDATION.json','PROTOCOL.md','BURST_EXPLORATORY_FREEZE.json','remote_sustained_burst_eval.py','remote_extract_confirmation.py','remote_extensions.py','remote_evaluate.py','collect_sustained_burst.py','pi_api.py','rig_capture_stagger.py','burst.c']
paths=features+[R/n for n in names];assert all(p.is_file() for p in paths);records=[{'path':p.relative_to(R).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in paths]
manifest=R/'RESULT_MANIFEST.json';manifest.write_text(json.dumps({'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'raw_source_hashes_verified':48,'feature_files':96,'files':records},indent=2));archive=R/'SUSTAINED_BURST_RESULTS.tar.gz';assert not archive.exists()
with tarfile.open(archive,'w:gz') as t:
 for p in paths+[manifest]:t.add(p,arcname=p.relative_to(R).as_posix(),recursive=False)
receipt={'archive':archive.name,'bytes':archive.stat().st_size,'sha256':sha(archive),'files':len(records),'feature_files':96,'raw_source_hashes_verified':48};(R/'RESULT_PACKAGE_RECEIPT.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
