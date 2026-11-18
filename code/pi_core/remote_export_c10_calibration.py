"""Reconstruct only C10 prespecified fits for parameter provenance; no selection.
Every available original heldout prediction must agree to 1e-12.
"""
import argparse,hashlib,json,pathlib,time,platform
import numpy as np,sklearn
from remote_extensions import model,load_features,stats
ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);a=ap.parse_args();R=pathlib.Path(a.root)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
pins={'remote_wait_confirmation_eval.py':'4a39b034928e44fe3b31bb3c1e38ea55a41988eed43ee2bfe0d9521c6ac877c7','remote_extensions.py':'99309e8cf2538dd8a17d1e5a45a373dc497c75b83a0441007cfb94fef15767c0','WAIT_CONFIRMATION_MODELS.json':'2c802e7b01ee7b48cf17fee742f033f1267f557b272408db3a29fb1b352460d3'}
for n,h in pins.items():assert sha(R/n)==h
source=R/'EARLY_WAIT_CONFIRMATION.json';base=json.loads(source.read_text());assert base['primary_raw_hashes_verified']==64 and base['full_original_evaluator_sha256']==pins['remote_wait_confirmation_eval.py']
rr=[x for x in json.loads((R/'LEDGER.json').read_text())['records'] if x['stage']=='wait_confirmation'];assert len(rr)==64
actual=np.array([x['actual_active'] for x in rr]);policy=np.array([x['expected_active'] for x in rr]);y=actual!=policy;cover=np.array([x['cover'] for x in rr]);tr=np.array([x['block']<4 for x in rr]);te=~tr
assert tr.sum()==te.sum()==32
validation=R/'WAIT_CONFIRMATION_COLLECTION_VALIDATION.json';v=json.loads(validation.read_text());assert v['pass'];lookup={x['id']:x for x in v['rows']}
out={'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'scope':'post-result deterministic reconstruction of prespecified C10 calibration fits for parameter artifacts only; not a new prospective model freeze; no model or threshold selection','source_evaluation_sha256':sha(source),'original_evaluator_sha256':pins['remote_wait_confirmation_eval.py'],'feature_code_sha256':pins['remote_extensions.py'],'code_sha256':sha(pathlib.Path(__file__)),'python':platform.python_version(),'sklearn':sklearn.__version__,'models':{},'max_heldout_probability_difference':0.0}
def export(label,X,train,test,target,direct=False):
 assert train.sum() in [16,32] and test.sum() in [16,32] and not (train&test).any()
 m=model().fit(X[train],y[train] if direct else actual[train]);q=m.predict_proba(X[test])[:,1];p=m.predict(X[test]);rows=[r for r,z in zip(rr,test) if z];delta=0.0
 if direct:
  got=stats(y[test],p,q)
  for k,z in target.items():
   if isinstance(z,(int,float)) and z is not None:assert abs(got[k]-z)<1e-12,(label,k)
 else:
  expected={r['id']:r for r in target['predictions']};assert set(expected)=={r['id'] for r in rows}
  delta=max(abs(float(prob)-expected[r['id']]['p_actual']) for r,prob in zip(rows,q));assert delta<1e-12,(label,delta)
  for r,pred,e in zip(rows,p,policy[test]):assert (bool(pred)!=bool(e))==bool(expected[r['id']]['alert'])
 sc=m.named_steps['standardscaler'];lr=m.named_steps['logisticregression'];out['models'][label]={'target':'violation' if direct else 'actual_activity','n_train':int(train.sum()),'n_test':int(test.sum()),'training_ids':[r['id'] for r,z in zip(rr,train) if z],'test_ids':[r['id'] for r in rows],'mean':sc.mean_.tolist(),'scale':sc.scale_.tolist(),'coefficient':lr.coef_[0].tolist(),'intercept':float(lr.intercept_[0]),'classes':lr.classes_.tolist(),'parameters':{k:z for k,z in lr.get_params().items() if k in ['C','max_iter','random_state','solver','class_weight']},'max_probability_difference':delta,'predictions':[{'id':r['id'],'probability':float(prob),'predicted_target':bool(pred)} for r,prob,pred in zip(rows,q,p)]};out['max_heldout_probability_difference']=max(out['max_heldout_probability_difference'],delta)
for k,z in base['new_calibration_train32_test32'].items():
 X=np.array([load_features(R,x,k=='temporal_260') for x in rr]);export(k+'/plain',X,tr,te,z['plain_physical'])
 for c in [False,True]:export(k+'/cover_'+str(c),X,tr&(cover==c),te&(cover==c),z['context_specific'][str(c)])
 export(k+'/direct_violation',X,tr,te,z['rf_direct_violation'],True)
for label,cols in [('coordinator_elapsed',['coordinator_elapsed_s']),('gateway_service',['gateway_service_s']),('both_external_times',['coordinator_elapsed_s','gateway_service_s'])]:
 X=np.array([[lookup[x['id']][c] for c in cols] for x in rr])
 for c in [False,True]:export('timing/'+label+'/cover_'+str(c),X,tr&(cover==c),te&(cover==c),base['new_external_times_train32_test32'][label][str(c)])
assert len(out['models'])==14
out['training_primary_feature_sha256']={x['id']:sha(R/'features'/(x['id']+'_930c.npz')) for x,t in zip(rr,tr) if t};out['timing_validation_sha256']=sha(validation)
p=R/'C10_CALIBRATION_MODELS_RECONSTRUCTED.json';assert not p.exists();p.write_text(json.dumps(out,indent=2));print(json.dumps({'models':14,'max_heldout_probability_difference':out['max_heldout_probability_difference'],'sha256':sha(p)}))
