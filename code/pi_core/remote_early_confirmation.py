"""Read-only early evaluation of one complete family, fixed coefficients only."""
import argparse,hashlib,json,pathlib,time,numpy as np
from scipy.special import expit
from remote_extensions import load_features,stats
from relative_reference_features import feature
from blockwise_comparison import compare
ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--stage',choices=['confirmation','confirmation_partial'],required=True);ap.add_argument('--family',choices=['trace','order'],required=True);a=ap.parse_args();R=pathlib.Path(a.root)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(R/'CONFIRMATION_MODELS.json')=='8ec87a546f008b7778fbf4afdb9cc7d7342c465b8489c80090fbb506b8797f49'
assert sha(R/'RELATIVE_REFERENCE_MODELS.json')=='70d72ecf5321b6ee0a68cce74077fd7e5adc121087efda5ea7868a41a94b071b'
old=json.loads((R/'CONFIRMATION_MODELS.json').read_text())['families'][a.family];relative=json.loads((R/'RELATIVE_REFERENCE_MODELS.json').read_text());assert sha(R/'relative_reference_features.py')==relative['feature_code_sha256']
validated=json.loads((R/('C08_COLLECTION_VALIDATION.json' if a.stage=='confirmation' else 'CONFIRMATION_PARTIAL_COLLECTION_VALIDATION.json')).read_text());assert validated['pass']
rr=[x for x in json.loads((R/'LEDGER.json').read_text())['records'] if x['stage']==a.stage and x['family']==a.family];assert len(rr)==(40 if a.stage=='confirmation' else 21) and all(x['valid'] for x in rr)
sources={x['filename']:x for x in json.loads((R/'SOURCE_RECEIPTS.json').read_text())['files']}
for x in rr:
 ident=x['id']+'_930c';d=json.loads((R/'features'/(ident+'.json')).read_text());s=sources[ident+'.iq'];assert d['full_contiguous'] and d['raw_sha256']==s['sha256'] and d['raw_bytes']==s['bytes']==160000000
assert not set(x['id'] for x in rr).intersection(old['training_ids'])
actual=np.array([x['actual_condition'] for x in rr]);expected=np.array([x['expected_condition'] for x in rr]);y=actual!=expected;truth={x['id']:{'block':x['block'],'actual_active':bool(ac),'expected_active':bool(ex),'violation':bool(v)} for x,ac,ex,v in zip(rr,actual,expected,y)}
def predict(X,m):
 q=expit(((X-np.array(m['mean']))/np.array(m['scale']))@np.array(m['coefficient'])+m['intercept']);return q>.5,q
def evaluate(X,mm):
 p,q=predict(X,mm['physical']);dp,dq=predict(X,mm['direct_violation'])
 return {'physical':stats(actual,p,q),'task_plus_rf':stats(y,p!=expected,np.where(expected,1-q,q)),'rf_direct_violation':stats(y,dp,dq),'predictions':[{'id':x['id'],'block':x['block'],'actual':bool(ac),'expected':bool(ex),'violation':bool(v),'p_actual':float(prob),'alert':bool(al)} for x,ac,ex,v,prob,al in zip(rr,actual,expected,y,q,p!=expected)]}
out={'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'stage':a.stage,'family':a.family,'n_test':len(rr),'primary_raw_hashes_verified':len(rr),'diagnostic_channel_pending_or_not_checked':True,'scope':'one complete family only; all original frozen models and secondary normalized models retained; no fit calls','original':{},'relative_reference':{},'task_only':stats(y,np.zeros(len(rr),dtype=bool))}
for k,mm in old['models'].items():
 X=np.array([load_features(R,x,k=='temporal_260') for x in rr]);out['original'][k]=evaluate(X,mm)
 pairs=[feature(R,x,k=='temporal_260') for x in rr];X=np.array([v for v,q in pairs]);z=evaluate(X,relative['families'][a.family]['models'][k]);z['reference_checks']=[q for v,q in pairs];z['paired_vs_original']=compare(z['predictions'],out['original'][k]['predictions'],truth);out['relative_reference'][k]=z
p,q=predict(np.array([[x['elapsed_s']] for x in rr]),old['elapsed_physical']);out['frozen_elapsed']={'physical':stats(actual,p,q),'task_plus_elapsed':stats(y,p!=expected,np.where(expected,1-q,q))}
name='EARLY_'+a.stage.upper()+'_'+a.family.upper()+'.json';(R/name).write_text(json.dumps(out,indent=2));print(json.dumps({'file':name,'original':{k:v['task_plus_rf'] for k,v in out['original'].items()},'relative':{k:v['task_plus_rf'] for k,v in out['relative_reference'].items()},'elapsed':out['frozen_elapsed']['task_plus_elapsed']}))
