import argparse,json,pathlib,hashlib,time
import numpy as np
from scipy.special import expit
from remote_extensions import load_features,model,stats
ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);a=ap.parse_args();R=pathlib.Path(a.root);sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(R/'COARSE_OBSERVATION_ABLATION_PROTOCOL.md')=='8968fdb123ab28c01d616ab155a75de1943460d717bff34acf26ccd081efbd88'
assert sha(R/'CONFIRMATION_MODELS.json')=='8ec87a546f008b7778fbf4afdb9cc7d7342c465b8489c80090fbb506b8797f49'
assert sha(R/'remote_extensions.py')=='99309e8cf2538dd8a17d1e5a45a373dc497c75b83a0441007cfb94fef15767c0'
original=json.loads((R/'CONFIRMATION_MODELS.json').read_text());inp=json.loads((R/'COARSE_TRAIN_INPUT.json').read_text());rows=json.loads((R/'LEDGER.json').read_text())['records'];sources={x['filename']:x for x in json.loads((R/'SOURCE_RECEIPTS.json').read_text())['files']}
def project(X,key):
 if key=='mean_power_1':return X[:,256:257]
 if key in ['power_stats_4','temporal_power_4']:return X[:,256:260]
 if key in ['spectrum_256','temporal_spectrum_256']:return X[:,:256]
 if key=='early_minus_late_power_1':
  p=10**(X[:,256:260]/10);return (10*np.log10((p[:,0]+p[:,1])/(p[:,2]+p[:,3])))[:,None]
 raise KeyError(key)
variants={'trace':['mean_power_1','power_stats_4','spectrum_256'],'order':['temporal_power_4','early_minus_late_power_1','temporal_spectrum_256']}
models={};live={}
for family,kk in variants.items():
 rr=inp['families'][family];ids=[x['id'] for x in rr];assert ids==original['families'][family]['training_ids'] and len(ids)==12
 for x in rr:assert sha(R/'coarse_training/features'/(x['id']+'_930c.npz'))==x['npz_sha256']==original['families'][family]['training_feature_sha256'][x['id']]
 X=np.array([load_features(R/'coarse_training',x,family=='order') for x in rr]);actual=np.array([x['actual'] for x in rr]);models[family]={};live[family]={}
 for key in kk:
  xx=project(X,key);m=model().fit(xx,actual);sc=m.named_steps['standardscaler'];lr=m.named_steps['logisticregression'];models[family][key]={'n_features':xx.shape[1],'training_ids':ids,'training_npz_sha256':{x['id']:x['npz_sha256'] for x in rr},'mean':sc.mean_.tolist(),'scale':sc.scale_.tolist(),'coefficient':lr.coef_[0].tolist(),'intercept':float(lr.intercept_[0])};live[family][key]=m
mp=R/'COARSE_OBSERVATION_ABLATION_MODELS.json';assert not mp.exists();mp.write_text(json.dumps({'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'scope':'posthoc old12-only fits, all six specified projections, serialized before new predictions; no new-test selection','protocol_sha256':sha(R/'COARSE_OBSERVATION_ABLATION_PROTOCOL.md'),'code_sha256':sha(pathlib.Path(__file__)),'input_sha256':sha(R/'COARSE_TRAIN_INPUT.json'),'families':models},indent=2))
out={'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'scope':'post hoc mechanism ablation; no extra executions; same new40 and interrupted21 per family kept separate; received IQ power is not calibrated device power or a unique process source','models_sha256':sha(mp),'code_sha256':sha(pathlib.Path(__file__)),'raw_primary_hashes_verified':0,'groups':{}}
for stage in ['confirmation','confirmation_partial']:
 out['groups'][stage]={}
 for family,kk in variants.items():
  rr=[x for x in rows if x['stage']==stage and x['family']==family];assert len(rr)==(40 if stage=='confirmation' else 21) and all(x['valid'] for x in rr);assert not {x['id'] for x in rr}&set(models[family][kk[0]]['training_ids'])
  for x in rr:
   name=x['id']+'_930c';meta=json.loads((R/'features'/(name+'.json')).read_text());s=sources[name+'.iq'];assert meta['full_contiguous'] and meta['raw_sha256']==s['sha256'] and meta['raw_bytes']==s['bytes'];out['raw_primary_hashes_verified']+=1
  X=np.array([load_features(R,x,family=='order') for x in rr]);actual=np.array([x['actual_condition'] for x in rr]);policy=np.array([x['expected_condition'] for x in rr]);y=actual!=policy
  def score(p,q):return {'physical':stats(actual,p,q),'task_conditioned':stats(y,p!=policy,np.where(policy,1-q,q)),'predictions':[{'id':x['id'],'block':x['block'],'actual':bool(ac),'expected':bool(ex),'violation':bool(v),'p_actual':float(prob),'alert':bool(al)} for x,ac,ex,v,prob,al in zip(rr,actual,policy,y,q,p!=policy)]}
  z={}
  for key in kk:
   m=live[family][key];xx=project(X,key);q=m.predict_proba(xx)[:,1];z[key]=score(m.predict(xx),q)
  k='whole_260' if family=='trace' else 'temporal_260';m=original['families'][family]['models'][k]['physical'];q=expit(((X-np.array(m['mean']))/np.array(m['scale']))@np.array(m['coefficient'])+m['intercept']);ref=score(q>.5,q);correct=ref['task_conditioned']['tp']+ref['task_conditioned']['tn'];assert correct=={('confirmation','trace'):29,('confirmation','order'):40,('confirmation_partial','trace'):13,('confirmation_partial','order'):21}[(stage,family)]
  out['groups'][stage][family]={'n_test':len(rr),'full_260_reference':ref,'projections':z}
assert out['raw_primary_hashes_verified']==122
p=R/'COARSE_OBSERVATION_ABLATION.json';assert not p.exists();p.write_text(json.dumps(out,indent=2));print(json.dumps({'raw':122,'summary':{s:{f:{k:{t:v['task_conditioned'][t] for t in ['tp','fn','fp','tn','accuracy']} for k,v in z['projections'].items()} for f,z in g.items()} for s,g in out['groups'].items()},'sha256':sha(p)}))
