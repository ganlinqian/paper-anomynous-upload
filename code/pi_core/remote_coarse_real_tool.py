import argparse,pathlib,hashlib,json,time
import numpy as np
from scipy.special import expit
from remote_extensions import load_features,model,stats
ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--action',choices=['export','evaluate'],required=True);ap.add_argument('--dataset',choices=['C10','C13']);a=ap.parse_args();R=pathlib.Path(a.root);sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();code=sha(pathlib.Path(__file__))
assert sha(R/'COARSE_REAL_TOOL_PROTOCOL.md')=='7f02ddfb5f002972014ca52b79d675e7dee28dc1ee36dd1a768eb54fd756732d';assert sha(R/'WAIT_CONFIRMATION_MODELS.json')=='2c802e7b01ee7b48cf17fee742f033f1267f557b272408db3a29fb1b352460d3';assert sha(R/'remote_extensions.py')=='99309e8cf2538dd8a17d1e5a45a373dc497c75b83a0441007cfb94fef15767c0';original=json.loads((R/'WAIT_CONFIRMATION_MODELS.json').read_text())
keys={'mean_power_1':False,'power_stats_4':False,'spectrum_256':False,'temporal_power_4':True,'early_minus_late_power_1':True,'temporal_spectrum_256':True}
def project(X,key):
 if key=='mean_power_1':return X[:,256:257]
 if key in ['power_stats_4','temporal_power_4']:return X[:,256:260]
 if key in ['spectrum_256','temporal_spectrum_256']:return X[:,:256]
 if key=='early_minus_late_power_1':
  p=10**(X[:,256:260]/10);return (10*np.log10((p[:,0]+p[:,1])/(p[:,2]+p[:,3])))[:,None]
 raise KeyError(key)
mp=R/'COARSE_REAL_TOOL_MODELS.json'
if a.action=='export':
 inp=json.loads((R/'COARSE_REAL_TOOL_TRAIN_INPUT.json').read_text());rr=inp['rows'];assert len(rr)==16 and [x['id'] for x in rr]==original['training_ids']
 for x in rr:assert sha(R/'coarse_real_training/features'/(x['id']+'_930c.npz'))==x['npz_sha256']==original['training_feature_sha256'][x['id']]
 out={'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'scope':'C19 six specified old16-only fits; C10 outcomes already seen; C13 collection already completed but no RF result seen and CPU not yet allocated at model specification','code_sha256':code,'protocol_sha256':sha(R/'COARSE_REAL_TOOL_PROTOCOL.md'),'original_models_sha256':sha(R/'WAIT_CONFIRMATION_MODELS.json'),'training_ids':original['training_ids'],'training_feature_sha256':original['training_feature_sha256'],'models':{}}
 for key,temp in keys.items():
  X=np.array([load_features(R/'coarse_real_training',x,temp) for x in rr]);xx=project(X,key);m=model().fit(xx,np.array([x['actual'] for x in rr]));sc=m.named_steps['standardscaler'];lr=m.named_steps['logisticregression'];out['models'][key]={'temporal':temp,'n_features':xx.shape[1],'mean':sc.mean_.tolist(),'scale':sc.scale_.tolist(),'coefficient':lr.coef_[0].tolist(),'intercept':float(lr.intercept_[0])}
 assert not mp.exists();mp.write_text(json.dumps(out,indent=2));print(json.dumps({'models':6,'sha256':sha(mp),'utc':out['utc']}));raise SystemExit(0)
assert a.dataset
models=json.loads(mp.read_text());assert models['code_sha256']==code and models['protocol_sha256']==sha(R/'COARSE_REAL_TOOL_PROTOCOL.md') and models['training_ids']==original['training_ids']
stage='wait_confirmation' if a.dataset=='C10' else 'untraced_wait_confirmation';n=64 if a.dataset=='C10' else 32
rr=[x for x in json.loads((R/'LEDGER.json').read_text())['records'] if x['stage']==stage];assert len(rr)==n and all(x['valid'] for x in rr);assert not {x['id'] for x in rr}&set(models['training_ids'])
vp=R/('WAIT_CONFIRMATION_COLLECTION_VALIDATION.json' if a.dataset=='C10' else 'UNTRACED_WAIT_COLLECTION_VALIDATION.json');assert json.loads(vp.read_text())['pass'];ss={x['filename']:x for x in json.loads((R/'SOURCE_RECEIPTS.json').read_text())['files']}
for x in rr:
 name=x['id']+'_930c';p=R/'features'/(name+'.json')
 if not p.exists():print(json.dumps({'ready':False,'missing':name}));raise SystemExit(3)
 j=json.loads(p.read_text());s=ss[name+'.iq'];assert j['full_contiguous'] and j['raw_sha256']==s['sha256'] and j['raw_bytes']==s['bytes']
actual=np.array([x['actual_active'] for x in rr]);policy=np.array([x['expected_active'] for x in rr]);y=actual!=policy
out={'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'dataset':a.dataset,'n_test':n,'n_blocks':len({x['block'] for x in rr}),'models_sha256':sha(mp),'code_sha256':code,'primary_raw_hashes_verified':n,'scope':'all six fixed old16-only projections; C10 posthoc, C13 specified before RF results but after collection; no new-test model or threshold selection','models':{},'original_full':{}}
def result(X,m):
 q=expit(((X-np.array(m['mean']))/np.array(m['scale']))@np.array(m['coefficient'])+m['intercept']);p=q>.5
 z={'physical':stats(actual,p,q),'task_conditioned':stats(y,p!=policy,np.where(policy,1-q,q)),'predictions':[{'id':x['id'],'block':x['block'],'cover':bool(x['cover']),'actual':bool(ac),'expected':bool(ex),'violation':bool(v),'p_actual':float(prob),'alert':bool(al),'scalar_input':float(xx[0]) if len(xx)==1 else None} for x,ac,ex,v,prob,al,xx in zip(rr,actual,policy,y,q,p!=policy,X)]}
 z['by_cover']={str(c):stats(y[mask],p[mask]!=policy[mask],np.where(policy[mask],1-q[mask],q[mask])) for c in [False,True] if (mask:=np.array([bool(x['cover'])==c for x in rr])).any()};return z
for key,m in models['models'].items():
 X=np.array([load_features(R,x,m['temporal']) for x in rr]);out['models'][key]=result(project(X,key),m)
for k,m in original['models'].items():out['original_full'][k]=result(np.array([load_features(R,x,k=='temporal_260') for x in rr]),m['physical'])
p=R/('COARSE_REAL_TOOL_'+a.dataset+'.json');assert not p.exists();p.write_text(json.dumps(out,indent=2));print(json.dumps({'dataset':a.dataset,'sha256':sha(p),'scores':{k:{t:v['task_conditioned'][t] for t in ['tp','fn','fp','tn','accuracy']} for k,v in out['models'].items()}}))
