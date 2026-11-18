"""Same frozen matrix estimator; availability-only early run before unrelated boundary files finish."""
import argparse,json,pathlib
import numpy as np
from remote_evaluate import model,score
ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);a=ap.parse_args();r=pathlib.Path(a.root);ledger=json.loads((r/'LEDGER.json').read_text())['records'];matrix=[x for x in ledger if x['stage']=='matrix'];source={x['filename']:x for x in json.loads((r/'SOURCE_RECEIPTS.json').read_text())['files']}
for row in matrix:
 name=row['id']+'_930c.iq';receipt=json.loads((r/'features'/(row['id']+'_930c.json')).read_text());assert receipt['raw_sha256']==source[name]['sha256'];assert receipt['raw_bytes']==source[name]['bytes']
X=np.array([np.load(r/'features'/(x['id']+'_930c.npz'))['features'] for x in matrix]);op=np.array([x['kind']=='helper' for x in matrix]);y=np.array([x['attack_attempt'] for x in matrix]);train=np.array([x['block']<3 for x in matrix]);test=~train;assert train.sum()==12 and test.sum()==8 and op[train].sum()==6 and op[test].sum()==4
physical=model().fit(X[train],op[train]);pred_op=physical.predict(X[test]);rf=model().fit(X[train],y[train]);pred_rf=rf.predict(X[test]);rows=[x for x,t in zip(matrix,test) if t];fused=[not x['policy']['allow_helper' if po else 'allow_dns'] for x,po in zip(rows,pred_op)]
result={'scope':'frozen matrix only; unrelated boundary transfer incomplete; exploratory one-session forward-block holdout','n_train':12,'n_test':8,'n_features':int(X.shape[1]),'raw_source_hashes_verified':True,'physical_operation':score(op[test],pred_op),'task_only':score(y[test],[False]*8),'rf_only':score(y[test],pred_rf),'task_plus_rf':score(y[test],fused),'strong_content_audit':score(y[test],[x['strong_software']['alert'] for x in rows]),'predictions':[]}
for row,po,pr,pf in zip(rows,pred_op,pred_rf,fused):result['predictions'].append({'id':row['id'],'block':row['block'],'kind':row['kind'],'policy':row['policy'],'attack':row['attack_attempt'],'predicted_operation':'helper' if po else 'dns','rf_only_alert':bool(pr),'fused_alert':bool(pf),'independent_unauthorized_effect':row['unauthorized_effect']})
(r/'MATRIX_EARLY.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='predictions'}))
