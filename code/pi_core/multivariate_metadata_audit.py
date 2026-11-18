"""Posthoc fixed three-model metadata audit. All fit uses original training IDs only."""
import os
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[key]='1'
from pathlib import Path
import csv,datetime,hashlib,json,pickle
import numpy as np
import sklearn
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score
try:
 import psutil
 psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
except ImportError:pass
B=Path(__file__).resolve().parent
O=B/'analysis_extensions/multivariate_metadata_20261105';assert not O.exists();O.mkdir()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8',newline='')
protocol=B/'MULTIVARIATE_METADATA_PROTOCOL.md'
assert sha(protocol)=='2cea040981f7217fd2be23ff6bf6f6890ea7488ed513384f2526265c92bfe85d'
model=B/'analysis_extensions/CONFIRMATION_MODELS.json'
assert sha(model)=='8ec87a546f008b7778fbf4afdb9cc7d7342c465b8489c80090fbb506b8797f49'
oldpath=B/'analysis_extensions/full_20261105/LEDGER.json';newpath=B/'confirmation_study/confirm_20261105_035739_c92be0/RESULTS.json'
old=read(oldpath)['records'];new=read(newpath);frozen=read(model)
features=['external_request_elapsed_s','win4_local_bracket_elapsed_s','main_bracket_iq_duration_s','diagnostic_bracket_iq_duration_s','main_predispatch_iq_duration_s','diagnostic_predispatch_iq_duration_s','main_minus_diagnostic_bracket_s','main_complete_call_frames','pre_cpu_c','pre_ddr_c']
results=[];flat=[];artifacts=[]
def truth(row,family,isnew):
 key='actual_condition' if isnew else ('actual_active' if family=='trace' else 'actual_order')
 assert isinstance(row[key],bool);return row[key]
def expect(row,family,isnew):
 key='expected_condition' if isnew else ('expected_active' if family=='trace' else 'expected_order')
 assert isinstance(row[key],bool);return row[key]
def count(y,p):
 return dict(TP=int(np.sum(y&p)),FN=int(np.sum(y&~p)),FP=int(np.sum(~y&p)),TN=int(np.sum(~y&~p)),correct=int(np.sum(y==p)),n=len(y))
for family,csvname in [('trace','all_metadata.csv'),('order','all_metadata_order.csv')]:
 csvpath=B/'analysis_extensions/metadata_audit_20261105'/csvname
 entries=list(csv.DictReader(csvpath.open(encoding='utf-8-sig',newline='')));assert len(entries)==60
 oldrows=[r for r in old if r['stage']==family];newrows=[r for r in new if r['family']==family]
 assert len(oldrows)==20 and len(newrows)==40 and all(r['valid'] for r in oldrows+newrows)
 lookups={'old':{r['id']:r for r in oldrows},'new':{r['id']:r for r in newrows}}
 train_ids=frozen['families'][family]['training_ids'];assert len(train_ids)==12 and len(set(train_ids))==12
 source={};groups={}
 for group,n in [('old_training',12),('old_test',8),('new_confirmation',40)]:
  rows=[r for r in entries if r['dataset']==group];assert len(rows)==n and len({r['id'] for r in rows})==n
  isnew=group=='new_confirmation';lookup=lookups['new' if isnew else 'old'];out=[]
  for entry in rows:
   row=lookup[entry['id']];a=truth(row,family,isnew);e=expect(row,family,isnew)
   assert entry['actual'] in ['True','False'] and (entry['actual']=='True')==a
   assert int(entry['block'])==row['block'];assert (row['id'] in train_ids)==(group=='old_training') if not isnew else row['id'] not in lookups['old']
   vals=[float(entry[k]) for k in features];assert np.isfinite(vals).all()
   out.append({'id':row['id'],'block':row['block'],'actual':a,'expected':e,'violation':a!=e,'values':vals})
  groups[group]=out
 assert {r['id'] for r in groups['old_training']}==set(train_ids)
 X=np.array([r['values'] for r in groups['old_training']]);y=np.array([r['actual'] for r in groups['old_training']],dtype=bool);assert np.sum(y)==6
 models={
 'scaled_logistic':Pipeline([('scale',StandardScaler()),('model',LogisticRegression(C=1,max_iter=2000,random_state=1105))]),
 'scaled_rbf_svm':Pipeline([('scale',StandardScaler()),('model',SVC(C=1,kernel='rbf',gamma='scale'))]),
 'random_forest':RandomForestClassifier(n_estimators=200,min_samples_leaf=2,random_state=1105,n_jobs=1),
 }
 for name,est in models.items():
  est.fit(X,y);params={k:v for k,v in est.get_params(deep=True).items() if k not in ['steps','scale','model']}
  blob=O/(family+'_'+name+'.pickle');blob.write_bytes(pickle.dumps(est,protocol=5));artifacts.append({'path':blob.name,'bytes':blob.stat().st_size,'sha256':sha(blob),'only_load_if_trusted':True})
  item={'family':family,'model':name,'training_ids':train_ids,'training_rows':groups['old_training'],'parameters':params,'model_sha256':sha(blob),'datasets':{}}
  for group in ['old_test','new_confirmation']:
   rows=groups[group];Z=np.array([r['values'] for r in rows]);a=np.array([r['actual'] for r in rows],dtype=bool);e=np.array([r['expected'] for r in rows],dtype=bool);v=a!=e
   pred=est.predict(Z).astype(bool);score=est.decision_function(Z) if hasattr(est,'decision_function') else est.predict_proba(Z)[:,1]
   alarms=pred!=e;alert_score=np.where(e,-score,score)
   table=[]
   for i,r in enumerate(rows):
    rr={k:r[k] for k in ['id','block','actual','expected','violation']};rr.update(predicted_actual=bool(pred[i]),physical_score=float(score[i]),alarm=bool(alarms[i]),correct=bool(alarms[i]==v[i]));table.append(rr);flat.append(dict(family=family,model=name,dataset=group,**rr))
   item['datasets'][group]={'physical':count(a,pred),'policy_alarm':count(v,alarms),'physical_auc':float(roc_auc_score(a,score)),'policy_alarm_auc':float(roc_auc_score(v,alert_score)),'blocks':[{'block':block,'correct':sum(r['correct'] for r in table if r['block']==block),'n':sum(r['block']==block for r in table)} for block in sorted({r['block'] for r in table})],'predictions':table}
  results.append(item)
 source[str(csvpath.relative_to(B))]=sha(csvpath)
 sourcepath=O/(family+'_source_receipt.json');put(sourcepath,{'csv_sha256':sha(csvpath),'old_ledger_sha256':sha(oldpath),'new_results_sha256':sha(newpath),'frozen_model_sha256':sha(model),'features':features,'training_ids':train_ids})
 artifacts.append({'path':sourcepath.name,'bytes':sourcepath.stat().st_size,'sha256':sha(sourcepath)})
out={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'posthoc multivariate non-amplitude metadata audit after RF/scalar results; no new-test fit or tuning; not a software upper bound','sklearn':sklearn.__version__,'numpy':np.__version__,'protocol_sha256':sha(protocol),'source_code_sha256':sha(Path(__file__)),'features':features,'rows_per_family':{'old_training':12,'old_test':8,'new_test':40},'results':results}
p=O/'RESULTS.json';put(p,out);artifacts.append({'path':p.name,'bytes':p.stat().st_size,'sha256':sha(p)})
with (O/'all_predictions.csv').open('w',encoding='utf-8',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(flat[0]));w.writeheader();w.writerows(flat)
lines=['# ','','12/840SDR','', '|||8|40|TP/FN/FP/TN|AUC|','|---|---|---:|---:|---|---:|']
for r in results:
 z=r['datasets']['new_confirmation'];c=z['policy_alarm'];c0=r['datasets']['old_test']['policy_alarm'];lines.append('|'+r['family']+'|'+r['model']+'|'+str(c0['correct'])+'/8|'+str(c['correct'])+'/40|'+'/'.join(str(c[k]) for k in ['TP','FN','FP','TN'])+'|'+format(z['physical_auc'],'.4f')+'|')
lines+=['','288288IDRF/','']
(O/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8',newline='')
for n in ['all_predictions.csv','REPORT.md']:
 q=O/n;artifacts.append({'path':n,'bytes':q.stat().st_size,'sha256':sha(q)})
put(O/'ARTIFACT_RECEIPT.json',{'files':artifacts,'predictions':len(flat),'distinct_new_executions':80,'protocol_sha256':sha(protocol),'code_sha256':sha(Path(__file__))})
print(json.dumps({'result_sha256':sha(p),'models':[{'family':r['family'],'model':r['model'],'new':r['datasets']['new_confirmation']['policy_alarm'],'physical_auc':r['datasets']['new_confirmation']['physical_auc']} for r in results]},ensure_ascii=False))
