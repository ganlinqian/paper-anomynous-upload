"""Fixed old-training window models on new records; no fit calls."""
import argparse,hashlib,json,pathlib,time,numpy as np
from scipy.special import expit
from execution_window_features import feature
from remote_extensions import load_features,stats
from blockwise_comparison import compare
ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--stage',choices=['confirmation','confirmation_partial','wait_confirmation'],required=True);ap.add_argument('--family',choices=['trace','order','wait'],required=True);a=ap.parse_args();R=pathlib.Path(a.root)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(R/'EXECUTION_WINDOW_MODELS.json')=='f238ff8e1a3f73a9d2fa29f0495a4d30cc36c5e255b02cb714a48432614e4224'
frozen=json.loads((R/'EXECUTION_WINDOW_MODELS.json').read_text());assert sha(R/'execution_window_features.py')==frozen['feature_code_sha256'];assert sha(R/'EXECUTION_WINDOW_PROTOCOL.md')==frozen['protocol_sha256']
validation={'confirmation':'C08_COLLECTION_VALIDATION.json','confirmation_partial':'CONFIRMATION_PARTIAL_COLLECTION_VALIDATION.json','wait_confirmation':'WAIT_CONFIRMATION_COLLECTION_VALIDATION.json'}[a.stage]
assert json.loads((R/validation).read_text())['pass']
rr=[x for x in json.loads((R/'LEDGER.json').read_text())['records'] if x['stage']==a.stage and (a.family=='wait' or x.get('family')==a.family)]
assert len(rr)=={'confirmation':40,'confirmation_partial':21,'wait_confirmation':64}[a.stage] and all(x['valid'] for x in rr)
assert (a.stage=='wait_confirmation')==(a.family=='wait')
sources={x['filename']:x for x in json.loads((R/'SOURCE_RECEIPTS.json').read_text())['files']}
for x in rr:
 name=x['id']+'_930c';d=json.loads((R/'features'/(name+'.json')).read_text());s=sources[name+'.iq'];assert d['full_contiguous'] and d['raw_sha256']==s['sha256'] and d['raw_bytes']==s['bytes']
m=frozen['families'][a.family];assert not set(x['id'] for x in rr)&set(m['training_ids'])
if a.family=='wait':
 assert sha(R/'WAIT_CONFIRMATION_MODELS.json')=='2c802e7b01ee7b48cf17fee742f033f1267f557b272408db3a29fb1b352460d3'
 original=json.loads((R/'WAIT_CONFIRMATION_MODELS.json').read_text())
else:
 assert sha(R/'CONFIRMATION_MODELS.json')=='8ec87a546f008b7778fbf4afdb9cc7d7342c465b8489c80090fbb506b8797f49'
 original=json.loads((R/'CONFIRMATION_MODELS.json').read_text())['families'][a.family]
assert set(m['training_ids'])==set(original['training_ids'])
actual=np.array([x['actual_active' if a.family=='wait' else 'actual_condition'] for x in rr])
expected=np.array([x['expected_active' if a.family=='wait' else 'expected_condition'] for x in rr]);y=actual!=expected
truth={x['id']:{'block':x['block'],'actual_active':bool(ac),'expected_active':bool(ex),'violation':bool(v)} for x,ac,ex,v in zip(rr,actual,expected,y)}
def result(X,mm):
 q=expit(((X-np.array(mm['mean']))/np.array(mm['scale']))@np.array(mm['coefficient'])+mm['intercept']);p=q>.5
 def subset(mask):
  return {'physical':stats(actual[mask],p[mask],q[mask]),'task_plus_rf':stats(y[mask],p[mask]!=expected[mask],np.where(expected[mask],1-q[mask],q[mask]))}
 z=subset(np.ones(len(rr),dtype=bool));z['predictions']=[{'id':x['id'],'block':x['block'],'actual':bool(ac),'expected':bool(ex),'violation':bool(v),'p_actual':float(prob),'alert':bool(al)} for x,ac,ex,v,prob,al in zip(rr,actual,expected,y,q,p!=expected)]
 if a.family=='wait':z['by_cover']={str(c):subset(np.array([bool(x['cover'])==c for x in rr])) for c in (False,True)}
 return z
out={'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'family':a.family,'stage':a.stage,'n_test':len(rr),'primary_raw_source_hashes_verified':len(rr),'diagnostic_channel_not_checked':True,'model_sha256':sha(R/'EXECUTION_WINDOW_MODELS.json'),'scope':'secondary window localization only; new acquisition already underway when specified; all frozen window/kind combinations reported; no causal identification or new detector claim','original_full':{},'windows':{}}
for kind,mm in original['models'].items():
 X=np.array([load_features(R,x,kind=='temporal_260') for x in rr]);out['original_full'][kind]=result(X,mm['physical'])
for window,kinds in m['windows'].items():
 out['windows'][window]={}
 for kind,mm in kinds.items():
  pairs=[feature(R,x,window,kind=='temporal_260') for x in rr];X=np.array([v for v,q in pairs]);z=result(X,mm['physical']);z['frame_checks']=[q for v,q in pairs];z['paired_vs_original_full']=compare(z['predictions'],out['original_full'][kind]['predictions'],truth);out['windows'][window][kind]=z
out['paired_call_minus_prefix']={k:compare(out['windows']['call_bracket'][k]['predictions'],out['windows']['prefix_0p2'][k]['predictions'],truth) for k in original['models']}
name='WINDOW_DIAGNOSTIC_'+a.stage.upper()+'_'+a.family.upper()+'.json';(R/name).write_text(json.dumps(out,indent=2))
print(json.dumps({'file':name,'windows':{w:{k:z['task_plus_rf'] for k,z in kk.items()} for w,kk in out['windows'].items()}}))
