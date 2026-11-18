"""Secondary fixed models: no fitting or tuning on any new acquisition."""
import hashlib,json,pathlib,time,numpy as np
from scipy.special import expit
from remote_extensions import stats
from relative_reference_features import feature
from blockwise_comparison import compare
R=pathlib.Path(__file__).resolve().parent;sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(R/'RELATIVE_REFERENCE_MODELS.json')=='70d72ecf5321b6ee0a68cce74077fd7e5adc121087efda5ea7868a41a94b071b'
m=json.loads((R/'RELATIVE_REFERENCE_MODELS.json').read_text());assert m['feature_code_sha256']==sha(R/'relative_reference_features.py') and m['protocol_sha256']==sha(R/'RELATIVE_REFERENCE_PROTOCOL.md')
rows=json.loads((R/'LEDGER.json').read_text())['records'];primary=json.loads((R/'INDEPENDENT_CONFIRMATION.json').read_text());wait=json.loads((R/'WAIT_CONFIRMATION_EVALUATION.json').read_text());assert primary['raw_source_hashes_verified']==516
training=set(x for f in m['families'].values() for x in f['training_ids']);assert not training.intersection(x['id'] for x in rows)
def predict(X,z):
 q=expit(((X-np.array(z['mean']))/np.array(z['scale']))@np.array(z['coefficient'])+z['intercept']);return q>.5,q
def evaluate(rr,family,original):
 ac=np.array([x['actual_active'] if family=='wait' else x['actual_condition'] for x in rr]);ex=np.array([x['expected_active'] if family=='wait' else x['expected_condition'] for x in rr]);y=ac!=ex
 truth={x['id']:{'block':x['block'],'actual_active':bool(a),'expected_active':bool(e),'violation':bool(v)} for x,a,e,v in zip(rr,ac,ex,y)}
 out={'n_test':len(rr),'models':{}}
 for kind,mm in m['families'][family]['models'].items():
  pairs=[feature(R,x,kind=='temporal_260') for x in rr];X=np.array([x for x,q in pairs]);pred,q=predict(X,mm['physical']);dp,dq=predict(X,mm['direct_violation'])
  predictions=[{'id':x['id'],'block':x['block'],'cover':x.get('cover'),'actual':bool(a),'expected':bool(e),'violation':bool(v),'p_actual':float(p),'alert':bool(al),'p_direct_violation':float(dprob)} for x,a,e,v,p,al,dprob in zip(rr,ac,ex,y,q,pred!=ex,dq)]
  z={'physical':stats(ac,pred,q),'task_plus_rf':stats(y,pred!=ex,np.where(ex,1-q,q)),'rf_direct_violation':stats(y,dp,dq),'reference_checks':[v for x,v in pairs],'predictions':predictions,'paired_vs_original':compare(predictions,original[kind],truth)}
  if family=='wait':
   z['by_cover']={}
   for c in (False,True):
    mask=np.array([x['cover']==c for x in rr]);ids={x['id'] for x,k in zip(rr,mask) if k};z['by_cover'][str(c)]={'task_plus_rf':stats(y[mask],pred[mask]!=ex[mask],np.where(ex[mask],1-q[mask],q[mask])),'paired_vs_original':compare([x for x in predictions if x['id'] in ids],[x for x in original[kind] if x['id'] in ids],truth)}
  out['models'][kind]=z
 return out
out={'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'scope':m['scope'],'models_sha256':sha(R/'RELATIVE_REFERENCE_MODELS.json'),'no_refit_on_new_data':True,'groups':{}}
for stage,name,key in [('confirmation','complete_C08','families'),('confirmation_partial','interrupted_C08','interrupted_confirmation')]:
 out['groups'][name]={}
 for family in ('trace','order'):
  rr=[x for x in rows if x['stage']==stage and x['family']==family];assert len(rr)==(40 if stage=='confirmation' else 21)
  src=primary['families'][family] if stage=='confirmation' else primary['interrupted_confirmation']['families'][family]
  orig={k:v['predictions'] for k,v in src['models'].items()};out['groups'][name][family]=evaluate(rr,family,orig)
rr=[x for x in rows if x['stage']=='wait_confirmation'];assert len(rr)==64;orig={k:v['all']['predictions'] for k,v in wait['old_models_all64_test'].items()};out['groups']['all_C10']=evaluate(rr,'wait',orig)
(R/'RELATIVE_REFERENCE_EVALUATION.json').write_text(json.dumps(out,indent=2));print(json.dumps({'complete_C08':{f:{k:v['task_plus_rf'] for k,v in z['models'].items()} for f,z in out['groups']['complete_C08'].items()},'C10':{k:{c:v['task_plus_rf'] for c,v in z['by_cover'].items()} for k,z in out['groups']['all_C10']['models'].items()}}))
