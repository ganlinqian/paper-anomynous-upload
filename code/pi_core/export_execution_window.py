"""Fit fixed windows using original 40 training cases only."""
import hashlib,json,pathlib,time,numpy as np
from execution_window_features import feature
from remote_extensions import model
R=pathlib.Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(R/'CONFIRMATION_MODELS.json')=='8ec87a546f008b7778fbf4afdb9cc7d7342c465b8489c80090fbb506b8797f49'
assert sha(R/'WAIT_CONFIRMATION_MODELS.json')=='2c802e7b01ee7b48cf17fee742f033f1267f557b272408db3a29fb1b352460d3'
old=json.loads((R/'CONFIRMATION_MODELS.json').read_text());wait=json.loads((R/'WAIT_CONFIRMATION_MODELS.json').read_text())
rows=json.loads((R/'LEDGER.json').read_text())['records']
out={'created_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'scope':'secondary outcome-blind window diagnostic; acquisition already underway; not original confirmation','feature_code_sha256':sha(R/'execution_window_features.py'),'export_code_sha256':sha(pathlib.Path(__file__)),'protocol_sha256':sha(R/'EXECUTION_WINDOW_PROTOCOL.md'),'families':{}}
def export(m):
 a,b=m.steps[0][1],m.steps[1][1]
 return {'mean':a.mean_.tolist(),'scale':a.scale_.tolist(),'coefficient':b.coef_[0].tolist(),'intercept':float(b.intercept_[0]),'classes':b.classes_.tolist()}
for family,oldm in [('trace',old['families']['trace']),('order',old['families']['order']),('wait',wait)]:
 rr=[x for x in rows if x['id'] in oldm['training_ids']]
 assert len(rr)==len(oldm['training_ids']) and {x['id'] for x in rr}==set(oldm['training_ids'])
 hashes={x['id']:sha(R/'features'/(x['id']+'_930c.npz')) for x in rr};assert hashes==oldm['training_feature_sha256']
 actual=np.array([x['actual_order' if family=='order' else 'actual_active'] for x in rr])
 z={'training_ids':[x['id'] for x in rr],'training_feature_sha256':hashes,'windows':{}}
 for window in ('prefix_0p2','call_bracket'):
  z['windows'][window]={}
  for kind in oldm['models']:
   pairs=[feature(R,x,window,kind=='temporal_260') for x in rr];X=np.array([v for v,q in pairs])
   z['windows'][window][kind]={'physical':export(model().fit(X,actual)),'frame_checks':[q for v,q in pairs]}
 out['families'][family]=z
(R/'EXECUTION_WINDOW_MODELS.json').write_text(json.dumps(out,indent=2))
print(json.dumps({'sha256':sha(R/'EXECUTION_WINDOW_MODELS.json'),'created_utc':out['created_utc'],'training_n':sum(len(z['training_ids']) for z in out['families'].values())}))
