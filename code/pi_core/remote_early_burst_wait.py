"""Early complete-family evaluation; identical frozen C09 scores/C10 protocol."""
import argparse,hashlib,json,pathlib,runpy,sys,time
import numpy as np
from scipy.special import expit
from remote_extensions import load_features,stats
ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--family',choices=['burst','wait'],required=True);a=ap.parse_args();R=pathlib.Path(a.root)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def pending(why,**kw):
 print(json.dumps({'ready':False,'why':why,**kw}));raise SystemExit(3)
stage='burst_confirmation' if a.family=='burst' else 'wait_confirmation';n=72 if a.family=='burst' else 64
rows=[r for r in json.loads((R/'LEDGER.json').read_text())['records'] if r['stage']==stage]
if len(rows)!=n:pending('full stage not appended',records=len(rows),expected=n)
vp=R/('CONFIRMATION_COLLECTION_VALIDATION.json' if a.family=='burst' else 'WAIT_CONFIRMATION_COLLECTION_VALIDATION.json')
if not vp.exists():pending('independent validation missing')
assert json.loads(vp.read_text())['pass']
receipts={x['filename']:x for x in json.loads((R/'SOURCE_RECEIPTS.json').read_text())['files']}
done=0
for r in rows:
 p=R/'features'/(r['id']+'_930c.json')
 if p.exists():done+=1
if done!=n:pending('complete primary family features pending',complete=done,expected=n)
assert all(r['valid'] for r in rows) and len({r['id'] for r in rows})==n
for r in rows:
 stem=r['id']+'_930c';d=json.loads((R/'features'/(stem+'.json')).read_text());s=receipts[stem+'.iq']
 assert d['full_contiguous'] and d['raw_sha256']==s['sha256'] and d['raw_bytes']==s['bytes']
base={'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'primary_raw_hashes_verified':n,'diagnostic_channel_pending_or_not_checked':True,'full_family_complete_before_evaluation':True,'no_new_threshold_selection':True,'evaluation_code_sha256':sha(pathlib.Path(__file__)),'validation_sha256':sha(vp),'ledger_sha256':sha(R/'LEDGER.json'),'source_receipts_sha256':sha(R/'SOURCE_RECEIPTS.json')}
if a.family=='burst':
 p=R/'BURST_EXPLORATORY_FREEZE.json';assert sha(p)=='e43e226984b4034dcd0f86aa3423dcd6a0e1faa88ebc3b4c9449fb23640c1f22';f=json.loads(p.read_text())
 actual=np.array([r['milliseconds']>0 for r in rows]);scores={k:[] for k in f['models']}
 assert len(rows)==72 and actual.sum()==60 and (~actual).sum()==12
 for r in rows:
  with np.load(R/'features'/(r['id']+'_930c.npz')) as z:
   pw=z['power_db'];med=float(np.median(pw));v={'p99_minus_p50':float(np.quantile(pw,.99)-med),'max_minus_p50':float(np.max(pw)-med),'top3mean_minus_p50':float(np.mean(np.sort(pw)[-3:])-med)}
  for k in scores:scores[k].append(v[k])
 out={**base,'scope':'C09 all72 new tests; three old exploratory thresholds frozen before new acquisition, original whole baseline retained','n_test':72,'n_active':60,'n_quiet':12,'models':{},'model_sha256':sha(p)}
 for k,ss in scores.items():
  ss=np.array(ss);t=f['models'][k]['threshold'];pred=ss>t;cells=[]
  for ms in (0,10,30,100,300,1000):
   for cover in (False,True):
    mask=np.array([r['milliseconds']==ms and r['cover']==cover for r in rows]);assert mask.sum()==6
    cells.append({'milliseconds':ms,'cover':cover,'n':6,'alerts':int(pred[mask].sum())})
  out['models'][k]={'threshold':t,'activity':stats(actual,pred,ss),'by_duration_cover':cells,'predictions':[{'id':r['id'],'block':r['block'],'milliseconds':r['milliseconds'],'cover':r['cover'],'actual':bool(y),'score':float(s),'alert':bool(p)} for r,y,s,p in zip(rows,actual,ss,pred)]}
 X=np.array([load_features(R,r) for r in rows]);m=f['original_whole_model'];q=expit(((X-np.array(m['mean']))/np.array(m['scale']))@np.array(m['coefficient'])+m['intercept'])
 out['original_whole_260']=stats(actual,q>.5,q);name='EARLY_BURST_CONFIRMATION.json'
else:
 p=R/'remote_wait_confirmation_eval.py';assert sha(p)=='4a39b034928e44fe3b31bb3c1e38ea55a41988eed43ee2bfe0d9521c6ac877c7'
 assert sha(R/'WAIT_CONFIRMATION_MODELS.json')=='2c802e7b01ee7b48cf17fee742f033f1267f557b272408db3a29fb1b352460d3'
 sys.argv=[str(p),'--root',str(R)];runpy.run_path(str(p),run_name='__main__')
 out=json.loads((R/'WAIT_CONFIRMATION_EVALUATION.json').read_text());out.update(base);out['full_original_evaluator_sha256']=sha(p);name='EARLY_WAIT_CONFIRMATION.json'
p=R/name;assert not p.exists(),'preserve previous early family result';p.write_text(json.dumps(out,indent=2))
print(json.dumps({'ready':True,'file':name,'primary_hashes':n,'sha256':sha(p),'bytes':p.stat().st_size}))
