"""Independent confirmation evaluation: fixed exported coefficients, no fit calls."""
import argparse,hashlib,json,pathlib,time
import numpy as np
from scipy.special import expit
from remote_extensions import load_features,stats
ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);a=ap.parse_args();root=pathlib.Path(a.root)
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
models=root/'CONFIRMATION_MODELS.json';burstmodels=root/'BURST_EXPLORATORY_FREEZE.json'
assert digest(models)=='8ec87a546f008b7778fbf4afdb9cc7d7342c465b8489c80090fbb506b8797f49'
assert digest(burstmodels)=='e43e226984b4034dcd0f86aa3423dcd6a0e1faa88ebc3b4c9449fb23640c1f22'
frozen=json.loads(models.read_text());bf=json.loads(burstmodels.read_text());rows=json.loads((root/'LEDGER.json').read_text())['records'];sources={x['filename']:x for x in json.loads((root/'SOURCE_RECEIPTS.json').read_text())['files']}
verified=0
for row in rows:
 for radio in ('930c','16bc'):
  name=row['id']+'_'+radio;d=json.loads((root/'features'/(name+'.json')).read_text());s=sources[name+'.iq'];assert d['full_contiguous'] and d['raw_sha256']==s['sha256'] and d['raw_bytes']==s['bytes'];verified+=1
def predict(X,m):
 X=np.asarray(X);q=expit(((X-np.asarray(m['mean']))/np.asarray(m['scale']))@np.asarray(m['coefficient'])+m['intercept']);return q>.5,q
def conditioned(rr,m):
 actual=np.array([x['actual_condition'] for x in rr]);expected=np.array([x['expected_condition'] for x in rr]);y=actual!=expected;out={'n_test':len(rr),'n_violations':int(y.sum()),'n_legal':int((~y).sum()),'task_only':stats(y,np.zeros(len(rr),dtype=bool)),'models':{}}
 for kind,mm in m['models'].items():
  X=np.array([load_features(root,x,kind=='temporal_260') for x in rr]);pred,q=predict(X,mm['physical']);alert=pred!=expected;aq=np.where(expected,1-q,q);dp,dq=predict(X,mm['direct_violation']);out['models'][kind]={'physical':stats(actual,pred,q),'task_plus_rf':stats(y,alert,aq),'rf_direct_violation':stats(y,dp,dq),'predictions':[{'id':r['id'],'block':r['block'],'actual':bool(ac),'expected':bool(ex),'violation':bool(v),'p_actual':float(prob),'alert':bool(al)} for r,ac,ex,v,prob,al in zip(rr,actual,expected,y,q,alert)]}
 ep,eq=predict(np.array([[r['elapsed_s']] for r in rr]),m['elapsed_physical']);out['frozen_external_elapsed']={'physical':stats(actual,ep,eq),'task_plus_elapsed':stats(y,ep!=expected,np.where(expected,1-eq,eq))}
 return out
out={'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'scope':'new acquisition after model freeze, private diagnostics and buffer release after reception; no refit or threshold selection','raw_source_hashes_verified':verified,'families':{}}
for family in ('trace','order'):
 rr=[x for x in rows if x['stage']=='confirmation' and x['family']==family];assert len(rr)==40 and all(x['valid'] for x in rr)
 for b in range(10):assert len({x['canonical_trace_sha256'] for x in rr if x['block']==b})==1
 out['families'][family]=conditioned(rr,frozen['families'][family])
out['interrupted_confirmation']={'status':'acquisition stopped on trial43 before any RF predictions; 42 valid trials reported separately, never pooled into the new complete confirmation','families':{}}
for family in ('trace','order'):
 rr=[x for x in rows if x['stage']=='confirmation_partial' and x['family']==family];assert len(rr)==21 and all(x['valid'] for x in rr)
 out['interrupted_confirmation']['families'][family]=conditioned(rr,frozen['families'][family])
rr=[x for x in rows if x['stage']=='burst_confirmation'];assert len(rr)==72;actual=np.array([x['milliseconds']>0 for x in rr]);scores={k:[] for k in bf['models']}
for row in rr:
 with np.load(root/'features'/(row['id']+'_930c.npz')) as f:
  pw=f['power_db'];med=float(np.median(pw));v={'p99_minus_p50':float(np.quantile(pw,.99)-med),'max_minus_p50':float(np.max(pw)-med),'top3mean_minus_p50':float(np.mean(np.sort(pw)[-3:])-med)}
 for k in scores:scores[k].append(v[k])
br={'n_test':72,'n_active':int(actual.sum()),'n_quiet':int((~actual).sum()),'models':{}}
for k,ss in scores.items():
 ss=np.array(ss);threshold=bf['models'][k]['threshold'];pred=ss>threshold;cells=[]
 for ms in (0,10,30,100,300,1000):
  for cover in (False,True):
   mask=np.array([r['milliseconds']==ms and r['cover']==cover for r in rr]);cells.append({'milliseconds':ms,'cover':cover,'n':int(mask.sum()),'alerts':int(pred[mask].sum())})
 br['models'][k]={'threshold':threshold,'activity':stats(actual,pred,ss),'by_duration_cover':cells,'predictions':[{'id':r['id'],'milliseconds':r['milliseconds'],'cover':r['cover'],'actual':bool(y),'score':float(s),'alert':bool(p)} for r,y,s,p in zip(rr,actual,ss,pred)]}
X=np.array([load_features(root,x) for x in rr]);pred,q=predict(X,bf['original_whole_model']);br['original_whole_260']=stats(actual,pred,q);out['burst']=br
p=root/'INDEPENDENT_CONFIRMATION.json';p.write_text(json.dumps(out,indent=2));print(json.dumps({'trace':out['families']['trace']['models']['whole_260']['task_plus_rf'],'order':out['families']['order']['models']['temporal_260']['task_plus_rf'],'burst':{k:v['activity'] for k,v in br['models'].items()}}))
