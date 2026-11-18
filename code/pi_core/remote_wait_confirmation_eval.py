"""C10: old frozen models on all 64; new calibration on first 32/last 32 only."""
import argparse,hashlib,json,pathlib,time
import numpy as np
from scipy.special import expit
from remote_extensions import load_features,stats,model
ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);a=ap.parse_args();r=pathlib.Path(a.root)
p=r/'WAIT_CONFIRMATION_MODELS.json';assert hashlib.sha256(p.read_bytes()).hexdigest()=='2c802e7b01ee7b48cf17fee742f033f1267f557b272408db3a29fb1b352460d3';frozen=json.loads(p.read_text())
rows=[x for x in json.loads((r/'LEDGER.json').read_text())['records'] if x['stage']=='wait_confirmation'];assert len(rows)==64
truth=json.loads((r/'WAIT_CONFIRMATION_COLLECTION_VALIDATION.json').read_text());assert truth['pass'];lookup={x['id']:x for x in truth['rows']}
actual=np.array([x['actual_active'] for x in rows]);expected=np.array([x['expected_active'] for x in rows]);cover=np.array([x['cover'] for x in rows]);y=actual!=expected;tr=np.array([x['block']<4 for x in rows]);te=~tr
def predict(X,m):
 q=expit(((X-np.array(m['mean']))/np.array(m['scale']))@np.array(m['coefficient'])+m['intercept']);return q>.5,q
def result(mask,pred,q):
 return {'physical':stats(actual[mask],pred,q),'with_task':stats(y[mask],pred!=expected[mask],np.where(expected[mask],1-q,q)),'predictions':[{'id':x['id'],'block':x['block'],'cover':bool(co),'actual':bool(ac),'expected':bool(ex),'violation':bool(v),'p_actual':float(prob),'alert':bool(al)} for x,co,ac,ex,v,prob,al in zip([x for x,m in zip(rows,mask) if m],cover[mask],actual[mask],expected[mask],y[mask],q,pred!=expected[mask])]}
out={'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'scope':'controlled real gzip under one declared legitimate SHA background; no OS compromise or arbitrary concurrency guarantee','old_models_all64_test':{},'new_calibration_train32_test32':{},'trusted_kernel':{}}
allmask=np.ones(64,dtype=bool)
for k in ('whole_260','temporal_260'):
 X=np.array([load_features(r,x,k=='temporal_260') for x in rows]);pred,q=predict(X,frozen['models'][k]['physical']);out['old_models_all64_test'][k]={'all':result(allmask,pred,q),'by_cover':{str(bool(c)):result(cover==c,pred[cover==c],q[cover==c]) for c in (False,True)}}
 dp,dq=predict(X,frozen['models'][k]['direct_violation']);out['old_models_all64_test'][k]['rf_direct_violation']=stats(y,dp,dq)
 plain=model().fit(X[tr],actual[tr]);pp=plain.predict(X[te]);pq=plain.predict_proba(X[te])[:,1];new={'plain_physical':result(te,pp,pq),'context_specific':{}}
 for c in (False,True):
  train=tr&(cover==c);test=te&(cover==c);assert train.sum()==test.sum()==16;m=model().fit(X[train],actual[train]);new['context_specific'][str(bool(c))]=result(test,m.predict(X[test]),m.predict_proba(X[test])[:,1])
 direct=model().fit(X[tr],y[tr]);new['rf_direct_violation']=stats(y[te],direct.predict(X[te]),direct.predict_proba(X[te])[:,1]);out['new_calibration_train32_test32'][k]=new
out['old_external_times_all64_test']={};out['new_external_times_train32_test32']={}
for label,cols in [('coordinator_elapsed',['coordinator_elapsed_s']),('gateway_service',['gateway_service_s']),('both_external_times',['coordinator_elapsed_s','gateway_service_s'])]:
 X=np.array([[lookup[x['id']][c] for c in cols] for x in rows]);pred,q=predict(X,frozen['timing'][label]['physical']);out['old_external_times_all64_test'][label]={'all':result(allmask,pred,q),'by_cover':{str(bool(c)):result(cover==c,pred[cover==c],q[cover==c]) for c in (False,True)}};out['new_external_times_train32_test32'][label]={}
 for c in (False,True):
  train=tr&(cover==c);test=te&(cover==c);m=model().fit(X[train],actual[train]);out['new_external_times_train32_test32'][label][str(bool(c))]=result(test,m.predict(X[test]),m.predict_proba(X[test])[:,1])
kp=np.array([lookup[x['id']]['kernel_exec_seen'] for x in rows]);out['trusted_kernel']={'all':stats(y,kp!=expected),'new_branch_test32':stats(y[te],kp[te]!=expected[te])};out['task_only_test32']=stats(y[te],np.zeros(int(te.sum()),dtype=bool))
out['note']='Binomial intervals are conditional descriptive summaries; trials share eight acquisition blocks.';(r/'WAIT_CONFIRMATION_EVALUATION.json').write_text(json.dumps(out,indent=2));print(json.dumps({'old':{k:{c:v['with_task'] for c,v in z['by_cover'].items()} for k,z in out['old_models_all64_test'].items()},'new':{k:{c:v['with_task'] for c,v in z['context_specific'].items()} for k,z in out['new_calibration_train32_test32'].items()}}))
