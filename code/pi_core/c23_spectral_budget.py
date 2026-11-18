from pathlib import Path
import os
for k in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
if os.name=='nt':
 import ctypes
 ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(),0x4000)
import argparse,datetime,hashlib,json,csv
import numpy as np
from scipy.special import expit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
B=Path(__file__).resolve().parent;A=B/'analysis_extensions';O=A/'spectral_budget_20261105';O.mkdir(exist_ok=True)
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'));sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();stamp=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
ap=argparse.ArgumentParser();ap.add_argument('action',choices=['export','evaluate']);act=ap.parse_args().action
oldp=A/'WAIT_CONFIRMATION_MODELS.json';assert sha(oldp)=='2c802e7b01ee7b48cf17fee742f033f1267f557b272408db3a29fb1b352460d3';old=read(oldp);F=A/'full_20261105';protocol=B/'C23_SPECTRAL_BUDGET_PROTOCOL.md';mp=O/'C23_MODELS.json'
def load(root,rows,manifest):
 known={x['path']:x for x in manifest['files']};X=[];hashes={}
 for r in rows:
  rel='features/'+r['id']+'_930c.npz';p=root/rel;h=sha(p);assert h==known[rel]['sha256'];hashes[r['id']]=h
  with np.load(p) as f:X.append(f['features'].copy())
 return np.array(X),hashes
def stats(y,p,q):
 y=np.array(y,bool);p=np.array(p,bool)
 return {'n':len(y),'tp':int((y&p).sum()),'fn':int((y&~p).sum()),'fp':int((~y&p).sum()),'tn':int((~y&~p).sum()),'accuracy':float((y==p).mean()),'auc':float(roc_auc_score(y,q))}
if act=='export':
 assert not mp.exists();ledger={r['id']:r for r in read(F/'LEDGER.json')['records']};rr=[ledger[i] for i in old['training_ids']];assert len(rr)==16
 X,hs=load(F,rr,read(F/'RESULT_MANIFEST_20261105.json'));assert hs==old['training_feature_sha256'];actual=np.array([r['actual_active'] for r in rr])
 coef=old['models']['whole_260']['physical']['coefficient'];rank=sorted(range(1,58),key=lambda j:(-abs(coef[j]),j))
 out={'utc':stamp(),'scope':'posthoc C10/C13 outcomes already seen; all old16-only fits and all four budgets reported; not new confirmation','code_sha256':sha(Path(__file__)),'protocol_sha256':sha(protocol),'old_model_sha256':sha(oldp),'training_ids':old['training_ids'],'training_feature_sha256':hs,'ranking':rank,'selection_rule':'absolute standardized old full-model coefficients of mean-spectrum columns 1..57 only; index tie-break','models':{}}
 for k in [1,3,8,57]:
  columns=rank[:k];m=make_pipeline(StandardScaler(),LogisticRegression(C=1,max_iter=2000,random_state=1104)).fit(X[:,columns],actual);sc=m.named_steps['standardscaler'];lr=m.named_steps['logisticregression'];assert list(lr.classes_)==[False,True]
  out['models'][str(k)]={'columns':columns,'n_train':16,'mean':sc.mean_.tolist(),'scale':sc.scale_.tolist(),'coefficient':lr.coef_[0].tolist(),'intercept':float(lr.intercept_[0]),'training_accuracy':float(m.score(X[:,columns],actual))}
 mp.write_text(json.dumps(out,indent=2),encoding='utf-8',newline='');print(json.dumps({'models_sha256':sha(mp),'ranking_first8':rank[:8]}));raise SystemExit(0)
models=read(mp);assert models['code_sha256']==sha(Path(__file__)) and models['protocol_sha256']==sha(protocol);p=O/'C23_EVALUATION.json';assert not p.exists();results={};metrics=[];predictions=[]
for ds,folder,stage,N in [('C10','confirmation_processing_20261105','wait_confirmation',64),('C13','untraced_processing_20261105','untraced_wait_confirmation',32)]:
 D=B/folder;assert read(D/'LOCAL_RESULTS_RECEIPT.json')['verified'];R=D/'analysis';rr=[r for r in read(R/'LEDGER.json')['records'] if r['stage']==stage];assert len(rr)==N and not set(models['training_ids'])&{r['id'] for r in rr};X,hs=load(R,rr,read(R/'RESULT_MANIFEST.json'))
 actual=np.array([r['actual_active'] for r in rr],bool);expected=np.array([r['expected_active'] for r in rr],bool);y=actual!=expected
 results[ds]={'n_unique_tests':N,'npz_sha256':hs,'models':{}}
 if ds=='C13':
  m=old['models']['whole_260']['physical'];q0=expit(((X-m['mean'])/m['scale'])@np.array(m['coefficient'])+m['intercept']);ref={x['id']:x['p_actual'] for x in read(R/'UNTRACED_WAIT_EVALUATION.json')['original']['whole_260']['predictions']};difference=max(abs(q-ref[r['id']]) for q,r in zip(q0,rr));assert difference<=1e-12;results[ds]['original_full_probability_rematch_max_difference']=difference
 for k,m in models['models'].items():
  xx=X[:,m['columns']];q=expit(((xx-m['mean'])/m['scale'])@np.array(m['coefficient'])+m['intercept']);pred=q>.5;alert=pred!=expected
  z={'physical':stats(actual,pred,q),'task_conditioned':stats(y,alert,np.where(expected,1-q,q)),'predictions':[{'id':r['id'],'block':r['block'],'cover':bool(r['cover']),'actual':bool(ac),'expected':bool(ex),'violation':bool(yi),'p_actual':float(pr),'alert':bool(al)} for r,ac,ex,yi,pr,al in zip(rr,actual,expected,y,q,alert)]}
  results[ds]['models'][k]=z;metrics.append({'dataset':ds,'budget':int(k),**z['task_conditioned']});predictions.extend({'dataset':ds,'budget':int(k),**r} for r in z['predictions'])
out={'utc':stamp(),'scope':models['scope'],'code_sha256':sha(Path(__file__)),'models_sha256':sha(mp),'protocol_sha256':sha(protocol),'n_existing_test_executions':96,'no_new_acquisition':True,'datasets':results};p.write_text(json.dumps(out,indent=2),encoding='utf-8',newline='')
for name,rr in [('metrics.csv',metrics),('predictions.csv',predictions)]:
 with (O/name).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
fig,ax=plt.subplots(figsize=(5.8,4.0),layout='constrained');mat=np.array([[results[ds]['models'][str(k)]['task_conditioned']['accuracy'] for ds in ['C10','C13']] for k in [1,3,8,57]]);im=ax.imshow(mat,vmin=0,vmax=1,cmap='Blues',aspect='auto');ax.set_xticks([0,1],['C10 / 64 tests','C13 / 32 tests']);ax.set_yticks(range(4),['1 band','3 bands','8 bands','57 bands']);ax.set_title('C23: all old16-trained spectral budgets\nPosthoc exploration; existing test executions')
for iy,k in enumerate([1,3,8,57]):
 for ix,ds in enumerate(['C10','C13']):
  s=results[ds]['models'][str(k)]['task_conditioned'];ax.text(ix,iy,str(s['tp']+s['tn'])+'/'+str(s['n']),ha='center',va='center',color='white' if mat[iy,ix]>.6 else 'black')
fig.colorbar(im,ax=ax,label='Task-conditioned accuracy');fig.savefig(O/'budgets.png',dpi=180);fig.savefig(O/'budgets.pdf');plt.close(fig)
lines=['# C23gzip','',out['scope'],'','16C10/C13','', '|||/N|TP|FN|FP|TN|AUC|','|---|---:|---:|---:|---:|---:|---:|---:|']
for x in metrics:lines.append('|%s|%d|%d/%d|%d|%d|%d|%d|%.4f|'%(x['dataset'],x['budget'],x['tp']+x['tn'],x['n'],x['tp'],x['fn'],x['fp'],x['tn'],x['auc']))
lines+=['','C19256C1053/64C1329/3255/6430/3230/6414/32','','010MHz640.15MHz9MHzFFT1..578'+str(models['ranking'][:8])+'','','FFTFFTgzipC22FFTC08','','![](budgets.png)','','SHA'+sha(mp)+'SHA'+sha(p)+'38496']
(O/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='');(O/'SUMMARY.json').write_text(json.dumps({'models_sha256':sha(mp),'result_sha256':sha(p),'metrics':metrics,'ranking':models['ranking'],'original_probability_rematch':results['C13']['original_full_probability_rematch_max_difference']},indent=2),encoding='utf-8',newline='');print(json.dumps({'result_sha256':sha(p),'metrics':metrics}))
