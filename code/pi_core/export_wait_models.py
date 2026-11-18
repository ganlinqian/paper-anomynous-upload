import argparse,hashlib,json,pathlib,time
import numpy as np
from remote_extensions import load_features,model
ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);a=ap.parse_args();r=pathlib.Path(a.root)
def pack(m):
 s=m[0];c=m[1]
 return {'mean':s.mean_.tolist(),'scale':s.scale_.tolist(),'coefficient':c.coef_[0].tolist(),'intercept':float(c.intercept_[0]),'classes':c.classes_.tolist()}
rows=[x for x in json.loads((r/'LEDGER.json').read_text())['records'] if x['stage']=='wait' and x['block']<4];assert len(rows)==16
lookup={x['id']:x for x in json.loads((r/'WAIT_COLLECTION_VALIDATION.json').read_text())['rows']};actual=np.array([x['actual_active'] for x in rows]);attack=actual!=np.array([x['expected_active'] for x in rows])
out={'created_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'scope':'Original C07 first four blocks only; frozen before C10 acquisition','training_ids':[x['id'] for x in rows],'models':{},'timing':{}}
for k in ('whole_260','temporal_260'):
 X=np.array([load_features(r,x,k=='temporal_260') for x in rows]);out['models'][k]={'physical':pack(model().fit(X,actual)),'direct_violation':pack(model().fit(X,attack))}
for label,cols in [('coordinator_elapsed',['coordinator_elapsed_s']),('gateway_service',['gateway_service_s']),('both_external_times',['coordinator_elapsed_s','gateway_service_s'])]:
 X=np.array([[lookup[x['id']][c] for c in cols] for x in rows]);out['timing'][label]={'columns':cols,'physical':pack(model().fit(X,actual))}
out['training_feature_sha256']={x['id']:hashlib.sha256((r/'features'/(x['id']+'_930c.npz')).read_bytes()).hexdigest() for x in rows}
p=r/'WAIT_CONFIRMATION_MODELS.json'
if p.exists():raise FileExistsError('keep immutable freeze')
p.write_text(json.dumps(out,indent=2));print(json.dumps({'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'created_utc':out['created_utc']}))
