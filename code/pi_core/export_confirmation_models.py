import argparse,hashlib,json,pathlib,time
import numpy as np
from remote_extensions import model,load_features
ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);a=ap.parse_args();r=pathlib.Path(a.root)
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def pack(m):
 s=m[0];c=m[1]
 return {'mean':s.mean_.tolist(),'scale':s.scale_.tolist(),'coefficient':c.coef_[0].tolist(),'intercept':float(c.intercept_[0]),'classes':c.classes_.tolist(),'decision_threshold':0.0}
rows=json.loads((r/'LEDGER.json').read_text())['records'];out={'created_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'scope':'Original first three blocks only; never refit on confirmation trials. All declared outputs retained.','evaluation_code_sha256':digest(r/'remote_extensions.py'),'export_code_sha256':digest(pathlib.Path(__file__)),'families':{}}
for stage in ('trace','order'):
 rr=[x for x in rows if x['stage']==stage and x['block']<3];assert len(rr)==12
 y=np.array([x['actual_active' if stage=='trace' else 'actual_order'] for x in rr]);v=y!=np.array([x['expected_active' if stage=='trace' else 'expected_order'] for x in rr])
 item={'training_ids':[x['id'] for x in rr],'training_feature_sha256':{x['id']:digest(r/'features'/(x['id']+'_930c.npz')) for x in rr},'models':{}}
 for kind in (['whole_260'] if stage=='trace' else ['whole_260','temporal_260']):
  X=np.array([load_features(r,x,kind=='temporal_260') for x in rr]);item['models'][kind]={'physical':pack(model().fit(X,y)),'direct_violation':pack(model().fit(X,v))}
 item['elapsed_physical']=pack(model().fit(np.array([[x['elapsed_s']] for x in rr]),y));out['families'][stage]=item
p=r/'CONFIRMATION_MODELS.json'
if p.exists():raise FileExistsError('Frozen models already exist; preserve original')
p.write_text(json.dumps(out,indent=2));print(json.dumps({'path':str(p),'sha256':digest(p),'created_utc':out['created_utc'],'families':list(out['families'])}))
