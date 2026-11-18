"""Supplementary channel audit. Export reads old training only; evaluate never fits."""
import argparse,hashlib,json,pathlib,time
import numpy as np
from scipy.special import expit
from remote_extensions import load_features,model,stats
ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--action',choices=['export','evaluate'],required=True);ap.add_argument('--stage',choices=['confirmation','confirmation_partial','wait_confirmation']);ap.add_argument('--family',choices=['trace','order','wait']);ap.add_argument('--model-sha256');a=ap.parse_args();R=pathlib.Path(a.root)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
stamp=lambda:time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
assert sha(R/'CONFIRMATION_MODELS.json')=='8ec87a546f008b7778fbf4afdb9cc7d7342c465b8489c80090fbb506b8797f49'
assert sha(R/'WAIT_CONFIRMATION_MODELS.json')=='2c802e7b01ee7b48cf17fee742f033f1267f557b272408db3a29fb1b352460d3'
original=json.loads((R/'CONFIRMATION_MODELS.json').read_text())['families'];original['wait']=json.loads((R/'WAIT_CONFIRMATION_MODELS.json').read_text())
def feature(p,temporal):
 with np.load(p) as f:
  if not temporal:return f['features'].copy()
  w=f['sample_counts'];t=(np.cumsum(w)-w/2)/w.sum();v=[];pw=[]
  for k in range(4):
   m=(t>=k/4)&(t<(k+1)/4);assert m.any()
   v.extend((10*np.log10(np.maximum(np.average(10**(f['band_db'][m]/10),axis=0,weights=w[m]),1e-20))).tolist())
   pw.append(float(10*np.log10(np.average(10**(f['power_db'][m]/10),weights=w[m]))))
  return np.array(v+pw)
mp=R/'DIAGNOSTIC_CHANNEL_MODELS.json'
if a.action=='export':
 assert not mp.exists(),'never refit or silently replace prior diagnostic models'
 inp=json.loads((R/'DIAGNOSTIC_TRAIN_INPUT.json').read_text());assert inp['protocol_sha256']==sha(R/'DIAGNOSTIC_CHANNEL_PROTOCOL.md')
 out={'created_utc':stamp(),'scope':'supplementary old-only diagnostic model export after main outcomes, before new diagnostic prediction inspection','protocol_sha256':sha(R/'DIAGNOSTIC_CHANNEL_PROTOCOL.md'),'input_sha256':sha(R/'DIAGNOSTIC_TRAIN_INPUT.json'),'code_sha256':sha(pathlib.Path(__file__)),'families':{}}
 for family,rows in inp['families'].items():
  ids=[r['id'] for r in rows];assert ids==original[family]['training_ids'] and len(ids)==(16 if family=='wait' else 12)
  for r in rows:assert sha(R/'diagnostic_training_features'/(r['id']+'_16bc.npz'))==r['npz_sha256']
  y=np.array([r['actual'] for r in rows]);assert y.sum()*2==len(rows)
  z={'training_ids':ids,'training_feature_sha256':{r['id']:r['npz_sha256'] for r in rows},'models':{}}
  for kind in original[family]['models']:
   X=np.array([feature(R/'diagnostic_training_features'/(r['id']+'_16bc.npz'),kind=='temporal_260') for r in rows]);m=model().fit(X,y);sc=m.named_steps['standardscaler'];lr=m.named_steps['logisticregression']
   z['models'][kind]={'mean':sc.mean_.tolist(),'scale':sc.scale_.tolist(),'coefficient':lr.coef_[0].tolist(),'intercept':float(lr.intercept_[0]),'C':1,'max_iter':2000,'random_state':1104,'class_weight':None}
  out['families'][family]=z
 mp.write_text(json.dumps(out,indent=2));print(json.dumps({'models':str(mp),'sha256':sha(mp),'families':{k:len(v['training_ids']) for k,v in out['families'].items()}}));raise SystemExit(0)
assert a.stage and a.family and a.model_sha256 and sha(mp)==a.model_sha256
frozen=json.loads(mp.read_text());assert frozen['code_sha256']==sha(pathlib.Path(__file__)) and frozen['protocol_sha256']==sha(R/'DIAGNOSTIC_CHANNEL_PROTOCOL.md')
rows=[r for r in json.loads((R/'LEDGER.json').read_text())['records'] if r['stage']==a.stage and (a.family=='wait' or r['family']==a.family)]
n={'confirmation':40,'confirmation_partial':21,'wait_confirmation':64}[a.stage];assert len(rows)==n and all(r['valid'] for r in rows);assert (a.stage=='wait_confirmation')==(a.family=='wait')
vp=R/({'confirmation':'C08_COLLECTION_VALIDATION.json','confirmation_partial':'CONFIRMATION_PARTIAL_COLLECTION_VALIDATION.json','wait_confirmation':'WAIT_CONFIRMATION_COLLECTION_VALIDATION.json'}[a.stage]);assert json.loads(vp.read_text())['pass']
src={r['filename']:r for r in json.loads((R/'SOURCE_RECEIPTS.json').read_text())['files']}
missing=[r['id']+'_'+radio for r in rows for radio in ['930c','16bc'] if not (R/'features'/(r['id']+'_'+radio+'.json')).exists()]
if missing:print(json.dumps({'ready':False,'missing':len(missing)}));raise SystemExit(3)
for r in rows:
 for radio in ['930c','16bc']:
  stem=r['id']+'_'+radio;d=json.loads((R/'features'/(stem+'.json')).read_text());s=src[stem+'.iq'];assert d['full_contiguous'] and d['raw_sha256']==s['sha256'] and d['raw_bytes']==s['bytes']
assert set(r['id'] for r in rows).isdisjoint(frozen['families'][a.family]['training_ids'])
actual=np.array([r['actual_active' if a.family=='wait' else 'actual_condition'] for r in rows]);expected=np.array([r['expected_active' if a.family=='wait' else 'expected_condition'] for r in rows]);y=actual!=expected
out={'utc':stamp(),'scope':'post hoc supplementary diagnostic comparison; 105MHz is not a physical null; all fixed combinations, no new fit','family':a.family,'stage':a.stage,'n_test':n,'raw_source_hashes_verified':n*2,'diagnostic_models_sha256':sha(mp),'validation_sha256':sha(vp),'channels':{}}
for radio in ['930c','16bc']:
 z={};mods=original[a.family]['models'] if radio=='930c' else frozen['families'][a.family]['models']
 for kind,mm in mods.items():
  mm=mm['physical'] if radio=='930c' else mm
  X=np.array([feature(R/'features'/(r['id']+'_'+radio+'.npz'),kind=='temporal_260') for r in rows]);q=expit(((X-np.array(mm['mean']))/np.array(mm['scale']))@np.array(mm['coefficient'])+mm['intercept']);p=q>.5
  z[kind]={'physical':stats(actual,p,q),'task_conditioned':stats(y,p!=expected,np.where(expected,1-q,q)),'predictions':[{'id':r['id'],'block':r['block'],'actual':bool(ac),'expected':bool(ex),'violation':bool(v),'p_actual':float(prob),'alert':bool(al)} for r,ac,ex,v,prob,al in zip(rows,actual,expected,y,q,p!=expected)]}
 out['channels'][radio]=z
name='DIAGNOSTIC_'+a.stage.upper()+'_'+a.family.upper()+'.json';p=R/name;assert not p.exists();p.write_text(json.dumps(out,indent=2));print(json.dumps({'ready':True,'file':name,'sha256':sha(p),'scores':{ch:{k:{t:v['task_conditioned'][t] for t in ['tp','fn','fp','tn','balanced_accuracy']} for k,v in z.items()} for ch,z in out['channels'].items()}}))
