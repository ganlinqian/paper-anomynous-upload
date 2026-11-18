import argparse,hashlib,json,pathlib,time
import numpy as np
from remote_extensions import stats,model,load_features
ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);a=ap.parse_args();r=pathlib.Path(a.root)
d=json.loads((r/'BURST_EARLY.json').read_text());rr=d['descriptive_fixed_scores'];y=np.array([x['milliseconds']>0 for x in rr]);train=np.array([x['block']<2 for x in rr]);test=~train
out={'created_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'status':'secondary exploratory calibration after inspecting failure of original whole-record model; not new prespecified confirmation','rule':'threshold is max score among four training inactive controls; alert iff greater; all three previously declared descriptive scores retained','n_train':int(train.sum()),'n_test':int(test.sum()),'models':{}}
for k in ('p99_minus_p50','max_minus_p50','top3mean_minus_p50'):
 s=np.array([x[k] for x in rr]);threshold=float(s[train & ~y].max());pred=s>threshold;cells=[]
 for ms in (0,10,30,100,300,1000):
  for cover in (False,True):
   m=np.array([t and x['milliseconds']==ms and x['cover']==cover for x,t in zip(rr,test)]);cells.append({'milliseconds':ms,'cover':cover,'n':int(m.sum()),'alerts':int(pred[m].sum())})
 out['models'][k]={'threshold':threshold,'test':stats(y[test],pred[test],s[test]),'by_duration_cover':cells,'predictions':[{'id':x['id'],'milliseconds':x['milliseconds'],'cover':x['cover'],'actual':bool(yy),'score':float(ss),'alert':bool(pp)} for x,yy,ss,pp,t in zip(rr,y,s,pred,test) if t]}
rows=[x for x in json.loads((r/'LEDGER.json').read_text())['records'] if x['stage']=='burst' and x['block']<2];X=np.array([load_features(r,x) for x in rows]);m=model(True).fit(X,np.array([x['milliseconds']>0 for x in rows]));s=m[0];c=m[1]
out['original_whole_model']={'mean':s.mean_.tolist(),'scale':s.scale_.tolist(),'coefficient':c.coef_[0].tolist(),'intercept':float(c.intercept_[0]),'classes':c.classes_.tolist(),'training_ids':[x['id'] for x in rows]}
p=r/'BURST_EXPLORATORY_FREEZE.json'
if p.exists():raise FileExistsError('preserve frozen exploratory result')
p.write_text(json.dumps(out,indent=2));print(json.dumps({'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'models':{k:{'threshold':x['threshold'],'test':x['test']} for k,x in out['models'].items()}}))
