import argparse,json,pathlib
import numpy as np
from remote_extensions import load_features,model,stats
ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);a=ap.parse_args();r=pathlib.Path(a.root)
rows=[x for x in json.loads((r/'LEDGER.json').read_text())['records'] if x['stage']=='wait'];assert len(rows)==32
truth=json.loads((r/'WAIT_COLLECTION_VALIDATION.json').read_text());assert truth['pass'];lookup={x['id']:x for x in truth['rows']}
sources={x['filename']:x for x in json.loads((r/'SOURCE_RECEIPTS.json').read_text())['files']}
for x in rows:
 p=json.loads((r/'features'/(x['id']+'_930c.json')).read_text());s=sources[x['id']+'_930c.iq'];assert p['raw_sha256']==s['sha256'] and p['raw_bytes']==s['bytes'] and p['full_contiguous']
for b in range(8):assert len({x['canonical_trace_sha256'] for x in rows if x['block']==b})==1
actual=np.array([x['actual_active'] for x in rows]);expected=np.array([x['expected_active'] for x in rows]);y=actual!=expected;tr=np.array([x['block']<4 for x in rows]);te=~tr;assert tr.sum()==te.sum()==16
def evaluate(X):
 p=model().fit(X[tr],actual[tr]);pred=p.predict(X[te]);q=p.predict_proba(X[te])[:,1];al=pred!=expected[te];aq=np.where(expected[te],1-q,q)
 return {'physical':stats(actual[te],pred,q),'with_task':stats(y[te],al,aq),'predictions':[{'id':row['id'],'actual':bool(ac),'expected':bool(ex),'attack':bool(at),'pred_actual':bool(pr),'p_actual':float(pp),'alert':bool(aa),'p_attack':float(ap)} for row,ac,ex,at,pr,pp,aa,ap in zip([x for x,t in zip(rows,te) if t],actual[te],expected[te],y[te],pred,q,al,aq)]}
out={'scope':'fixed real gzip within approved network wait; single acquisition session; no autonomous model or OS compromise','n_train':16,'n_test':16,'primary_raw_source_hashes_verified':32,'canonical_content_equal_per_block':True,'task_or_canonical_content_only':stats(y[te],[False]*16),'models':{},'timing':{}}
for k in ('whole_260','temporal_260'):
 X=np.array([load_features(r,x,k=='temporal_260') for x in rows]);z=evaluate(X);d=model().fit(X[tr],y[tr]);z['rf_direct_violation']=stats(y[te],d.predict(X[te]),d.predict_proba(X[te])[:,1]);out['models'][k]=z
for label,cols in [('coordinator_elapsed',['coordinator_elapsed_s']),('gateway_service',['gateway_service_s']),('both_external_times',['coordinator_elapsed_s','gateway_service_s'])]:
 X=np.array([[lookup[x['id']][c] for c in cols] for x in rows]);out['timing'][label]=evaluate(X)
kp=np.array([lookup[x['id']]['kernel_exec_seen'] for x in rows]);out['trusted_kernel_exec_audit']={'physical':stats(actual[te],kp[te]),'with_task':stats(y[te],kp[te]!=expected[te])}
out['all_trial_observations']=truth['rows'];p=r/'WAIT_EARLY.json';p.write_text(json.dumps(out,indent=2))
print(json.dumps({'whole':out['models']['whole_260']['with_task'],'temporal':out['models']['temporal_260']['with_task'],'external_2d':out['timing']['both_external_times']['with_task'],'kernel':out['trusted_kernel_exec_audit']['with_task']}))
