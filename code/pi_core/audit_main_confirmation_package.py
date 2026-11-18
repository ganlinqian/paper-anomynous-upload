from pathlib import Path
import datetime, hashlib, json, math
B=Path(__file__).resolve().parent; A=B/'analysis_extensions'; D=B/'confirmation_processing_20261105'; P=D/'analysis'
O=A/'final_integrity_20261105';O.mkdir(exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
sources={}; checks=[]; leaves=0; maximum=0.0
def get(p):
 sources[str(p.relative_to(B))]={'sha256':sha(p),'bytes':p.stat().st_size}
 return read(p)
def cmp(a,b,label):
 global leaves,maximum
 if isinstance(a,dict):
  assert isinstance(b,dict),label
  for k in a: assert k in b,(label,k);cmp(a[k],b[k],label+'/'+k)
 elif isinstance(a,list):
  assert isinstance(b,list) and len(a)==len(b),(label,len(a),len(b))
  for i,(x,y) in enumerate(zip(a,b)):cmp(x,y,label+'/'+str(i))
 elif isinstance(a,(int,float)) and not isinstance(a,bool):
  assert isinstance(b,(int,float)) and not isinstance(b,bool),(label,a,b)
  delta=abs(a-b);assert math.isfinite(delta) and delta<=1e-12,(label,a,b,delta)
  maximum=max(maximum,delta);leaves+=1
 else:assert a==b,(label,a,b);leaves+=1
def done(label):checks.append(label)
receipt=get(D/'LOCAL_RESULTS_RECEIPT.json');assert receipt['verified'] and receipt['files']==1056
manifest=get(P/'RESULT_MANIFEST.json');assert len(manifest['files'])==1056
assert len([x for x in manifest['files'] if x['path'].startswith('features/')])==1032
archive=P/receipt['package']['archive'];assert archive.stat().st_size==receipt['package']['bytes'] and sha(archive)==receipt['package']['sha256']
done('Controller verified all 1056 returned files; archive SHA independently rematched')
src=get(P/'SOURCE_RECEIPTS.json')['files']; ext=get(P/'EXTRACTION_COMPLETE.json');assert ext['full_contiguous'] and len(src)==len(ext['receipts'])==516
sm={x['filename']:x for x in src};assert len(sm)==516
for x in ext['receipts']:
 y=sm[x['filename']]
 assert x['raw_sha256']==y['sha256'] and x['raw_bytes']==y['bytes'] and x['samples_consumed']*2==y['bytes'] and x['full_contiguous'] and x['feature_dim']==260
done('All 516 full contiguous raw extraction receipts match original source SHA/bytes and all samples')
for name in ['CONFIRMATION_MODELS.json','BURST_EXPLORATORY_FREEZE.json','WAIT_CONFIRMATION_MODELS.json','RELATIVE_REFERENCE_MODELS.json']:
 assert sha(P/name)==sha(A/name);get(P/name);get(A/name)
done('Four packaged frozen model files identical to original desktop freezes')
full=get(P/'INDEPENDENT_CONFIRMATION.json'); rel=get(P/'RELATIVE_REFERENCE_EVALUATION.json')
for partial in [False,True]:
 for family in ['trace','order']:
  name='EARLY_CONFIRMATION_'+('PARTIAL_' if partial else '')+family.upper()+'.json'
  e=get(A/'early_confirm_20261105'/name)
  f=(full['interrupted_confirmation']['families'] if partial else full['families'])[family]
  cmp(e['original'],f['models'],name+'/original')
  cmp(e['task_only'],f['task_only'],name+'/task')
  cmp(e['frozen_elapsed'],f['frozen_external_elapsed'],name+'/elapsed')
  rr=rel['groups']['interrupted_C08' if partial else 'complete_C08'][family]['models']
  for k,v in e['relative_reference'].items():
   cmp({z:q for z,q in v.items() if z!='paired_vs_original'},rr[k],name+'/relative/'+k)
  done(name+' original, elapsed and relative predictions/statistics identical')
eb=get(A/'early_burst_wait_20261105/EARLY_BURST_CONFIRMATION.json')
for k,v in eb['models'].items():
 q={z:t for z,t in v.items() if z!='predictions'}
 cmp(q,full['burst']['models'][k],'C09/'+k+'/statistics')
 cmp([{z:t for z,t in p.items() if z!='block'} for p in v['predictions']],full['burst']['models'][k]['predictions'],'C09/'+k+'/predictions')
cmp(eb['original_whole_260'],full['burst']['original_whole_260'],'C09/original_whole')
done('C09 all three thresholds, 216 scores/predictions and original whole metrics identical')
ew=get(A/'early_burst_wait_20261105/EARLY_WAIT_CONFIRMATION.json');fw=get(P/'WAIT_CONFIRMATION_EVALUATION.json')
for k in ['old_models_all64_test','new_calibration_train32_test32','trusted_kernel','old_external_times_all64_test','new_external_times_train32_test32','task_only_test32']:
 cmp(ew[k],fw[k],'C10/'+k)
done('C10 original and all prespecified new calibration, timing, kernel predictions/statistics identical')
diag=get(A/'diagnostic_confirm_20261105/DIAGNOSTIC_WAIT_CONFIRMATION_WAIT.json'); assert diag['raw_source_hashes_verified']==128
for k,v in fw['old_models_all64_test'].items():
 d=diag['channels']['930c'][k]
 cmp(v['all']['with_task'],d['task_conditioned'],'C10diag/main/'+k)
done('C10 paired diagnostic supplementary main statistics match independent full evaluation')
result={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'verified':True,'scope':'Metadata and independently repeated predictions; no raw-IQ reread, no new fit or threshold choice. Controller receipt supplies 1056 per-file local SHA verifications. This audit additionally hashes the 107MB archive and binds 516 source hashes to contiguous extraction receipts.','raw_files':516,'feature_files':1032,'returned_files':1056,'numeric_tolerance':1e-12,'compared_leaves':leaves,'maximum_numeric_difference':maximum,'checks':checks,'sources':sources}
p=O/'MAIN_PACKAGE_REMATCH.json'; assert not p.exists();p.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8',newline='')
print(json.dumps({'path':str(p),'sha256':sha(p),'checks':len(checks),'leaves':leaves,'maximum_numeric_difference':maximum,'verified':True}))
