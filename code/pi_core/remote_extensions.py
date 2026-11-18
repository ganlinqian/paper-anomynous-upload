"""Frozen extension analyses. CPU only. All fits use preceding blocks only."""
import argparse,json,pathlib
import numpy as np
from scipy.stats import beta
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score,balanced_accuracy_score
from remote_evaluate import score

def model(balanced=False):return make_pipeline(StandardScaler(),LogisticRegression(C=1,max_iter=2000,random_state=1104,class_weight='balanced' if balanced else None))
def stats(y,p,q=None):
 d=score(y,p);d['balanced_accuracy']=float(balanced_accuracy_score(y,p))
 if q is not None and len(set(y))==2:d['auc']=float(roc_auc_score(y,q))
 return d

def load_features(root,row,temporal=False):
 with np.load(root/'features'/(row['id']+'_930c.npz')) as f:
  if not temporal:return f['features'].copy()
  weights=f['sample_counts'];center=(np.cumsum(weights)-weights/2)/weights.sum();bands=f['band_db'];power=f['power_db'];values=[];pw=[]
  for k in range(4):
   mask=(center>=k/4)&(center<(k+1)/4);assert mask.any()
   values.extend((10*np.log10(np.maximum(np.average(10**(bands[mask]/10),axis=0,weights=weights[mask]),1e-20))).tolist());pw.append(float(10*np.log10(np.average(10**(power[mask]/10),weights=weights[mask]))))
  return np.array(values+pw)

def conditioned(root,rows,order=False):
 actual=np.array([x['actual_order' if order else 'actual_active'] for x in rows]);expected=np.array([x['expected_order' if order else 'expected_active'] for x in rows]);y=actual!=expected;train=np.array([x['block']<3 for x in rows]);test=~train;assert train.sum()==12 and test.sum()==8
 for block in range(5):assert len({x['canonical_trace_sha256'] for x in rows if x['block']==block})==1
 result={'n_train':12,'n_test':8,'scope':'one-session controlled implementation substitution; not OS compromise or autonomous-agent rate','canonical_content_equal_per_block':True,'task_only':stats(y[test],[False]*int(test.sum())),'content_plus_task_upper_accuracy_on_paired_test':0.5,'models':{}}
 kinds=['whole_260','temporal_260'] if order else ['whole_260']
 for kind in kinds:
  X=np.array([load_features(root,x,kind=='temporal_260') for x in rows]);physical=model().fit(X[train],actual[train]);po=physical.predict(X[test]);q=physical.predict_proba(X[test])[:,1];fused=po!=expected[test];fq=np.where(expected[test],1-q,q);direct=model().fit(X[train],y[train]);dr=direct.predict(X[test]);dq=direct.predict_proba(X[test])[:,1]
  result['models'][kind]={'physical':stats(actual[test],po,q),'rf_direct_violation':stats(y[test],dr,dq),'task_plus_rf':stats(y[test],fused,fq),'predictions':[{'id':row['id'],'actual':bool(act),'expected':bool(exp),'attack':bool(atk),'pred_actual':bool(pred),'p_actual':float(prob),'alert':bool(al),'p_attack':float(pa)} for row,act,exp,atk,pred,prob,al,pa in zip([x for x,t in zip(rows,test) if t],actual[test],expected[test],y[test],po,q,fused,fq)]}
 elapsed=np.array([[x['elapsed_s']] for x in rows]);tm=model().fit(elapsed[train],actual[train]);tp=tm.predict(elapsed[test]);tq=tm.predict_proba(elapsed[test])[:,1];tf=tp!=expected[test];tfq=np.where(expected[test],1-tq,tq)
 result['external_elapsed_time']={'physical':stats(actual[test],tp,tq),'with_task':stats(y[test],tf,tfq),'all_trials':[{'id':x['id'],'block':x['block'],'actual':bool(a),'elapsed_s':x['elapsed_s']} for x,a in zip(rows,actual)]}
 return result

def burst(root,rows):
 X=np.array([load_features(root,x) for x in rows]);y=np.array([x['milliseconds']>0 for x in rows]);train=np.array([x['block']<2 for x in rows]);test=~train;assert train.sum()==24 and test.sum()==24
 m=model(True).fit(X[train],y[train]);pred=m.predict(X[test]);q=m.predict_proba(X[test])[:,1];ids=[x for x,t in zip(rows,test) if t];result={'n_train':24,'n_test':24,'scope':'single engineered memory burst; not original network event','activity':stats(y[test],pred,q),'predictions':[],'by_duration_cover':[],'descriptive_fixed_scores':[]}
 for row,p,prob in zip(ids,pred,q):result['predictions'].append({'id':row['id'],'milliseconds':row['milliseconds'],'cover':row['cover'],'active':row['milliseconds']>0,'pred_active':bool(p),'p_active':float(prob),'actual_elapsed_ms':row['private']['burst_elapsed_s']*1000})
 for ms in (0,10,30,100,300,1000):
  for cover in (False,True):
   mask=np.array([x['milliseconds']==ms and x['cover']==cover for x in ids]);result['by_duration_cover'].append({'milliseconds':ms,'cover':cover,'n':int(mask.sum()),'correct':int(np.sum(pred[mask]==y[test][mask])),'predicted_active':int(pred[mask].sum())})
 for row in rows:
  with np.load(root/'features'/(row['id']+'_930c.npz')) as f:
   pw=f['power_db'];med=float(np.median(pw));ss={'p99_minus_p50':float(np.quantile(pw,.99)-med),'max_minus_p50':float(np.max(pw)-med),'top3mean_minus_p50':float(np.mean(np.sort(pw)[-3:])-med)}
  result['descriptive_fixed_scores'].append({'id':row['id'],'block':row['block'],'milliseconds':row['milliseconds'],'cover':row['cover'],**ss})
 return result

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);a=ap.parse_args();root=pathlib.Path(a.root);records=json.loads((root/'LEDGER.json').read_text())['records'];sources={x['filename']:x for x in json.loads((root/'SOURCE_RECEIPTS.json').read_text())['files']};verified=0
 for row in records:
  for rf in row['rf']['radios']:
   name=row['id']+'_'+rf['radio']+'.iq';receipt=json.loads((root/'features'/(row['id']+'_'+rf['radio']+'.json')).read_text());assert receipt['raw_sha256']==sources[name]['sha256'];assert receipt['raw_bytes']==sources[name]['bytes'];assert receipt['full_contiguous'];verified+=1
 result={'raw_source_hashes_verified':verified,'burst':burst(root,[x for x in records if x['stage']=='burst']),'complete_trace':conditioned(root,[x for x in records if x['stage']=='trace']),'order':conditioned(root,[x for x in records if x['stage']=='order'],True)}
 (root/'EXTENSION_EVALUATION.json').write_text(json.dumps(result,indent=2));print(json.dumps({'verified':verified,'burst':result['burst']['activity'],'trace':result['complete_trace']['models']['whole_260']['task_plus_rf'],'order_whole':result['order']['models']['whole_260']['task_plus_rf'],'order_temporal':result['order']['models']['temporal_260']['task_plus_rf']}))
if __name__=='__main__':main()
