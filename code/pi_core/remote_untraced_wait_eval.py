"""Untraced C13: old frozen models only, all32 new tests, no fit calls."""
import argparse,hashlib,json,pathlib,time,numpy as np
from scipy.special import expit
from remote_extensions import load_features,stats
from relative_reference_features import feature as referenced
from execution_window_features import feature as windowed
from blockwise_comparison import compare
ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);a=ap.parse_args();R=pathlib.Path(a.root)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
expected={'WAIT_CONFIRMATION_MODELS.json':'2c802e7b01ee7b48cf17fee742f033f1267f557b272408db3a29fb1b352460d3','RELATIVE_REFERENCE_MODELS.json':'70d72ecf5321b6ee0a68cce74077fd7e5adc121087efda5ea7868a41a94b071b','EXECUTION_WINDOW_MODELS.json':'f238ff8e1a3f73a9d2fa29f0495a4d30cc36c5e255b02cb714a48432614e4224'}
for n,h in expected.items():assert sha(R/n)==h
original=json.loads((R/'WAIT_CONFIRMATION_MODELS.json').read_text())
relative=json.loads((R/'RELATIVE_REFERENCE_MODELS.json').read_text())
windows=json.loads((R/'EXECUTION_WINDOW_MODELS.json').read_text())
assert sha(R/'relative_reference_features.py')==relative['feature_code_sha256']
assert sha(R/'execution_window_features.py')==windows['feature_code_sha256']
validation=json.loads((R/'UNTRACED_WAIT_COLLECTION_VALIDATION.json').read_text());assert validation['pass'] and validation['trials']==32 and validation['independently_verified_archives']==16
freeze=json.loads((R/'COLLECTION_FREEZE.json').read_text());assert freeze['syscall_tracing'] is False and freeze['all_trials_test_only']
protocol_h=next(h for p,h in freeze['source_sha256'].items() if pathlib.PureWindowsPath(p).name=='PROTOCOL.md');assert sha(R/'UNTRACED_WAIT_PROTOCOL.md')==protocol_h
rr=json.loads((R/'LEDGER.json').read_text())['records'];assert len(rr)==32 and all(x['stage']=='untraced_wait_confirmation' and x['valid'] and not x['cover'] and x['kernel_exec_audit_measured'] is False for x in rr)
assert not {x['id'] for x in rr}&set(original['training_ids'])
assert set(original['training_ids'])==set(relative['families']['wait']['training_ids'])==set(windows['families']['wait']['training_ids'])
sources={x['filename']:x for x in json.loads((R/'SOURCE_RECEIPTS.json').read_text())['files']};verified=0
for x in rr:
 for radio in ('930c','16bc'):
  name=x['id']+'_'+radio;meta=json.loads((R/'features'/(name+'.json')).read_text());s=sources[name+'.iq'];assert meta['full_contiguous'] and meta['raw_sha256']==s['sha256'] and meta['raw_bytes']==s['bytes']==320000000;verified+=1
actual=np.array([x['actual_active'] for x in rr]);policy=np.array([x['expected_active'] for x in rr]);y=actual!=policy
truth={x['id']:{'block':x['block'],'actual_active':bool(ac),'expected_active':bool(ex),'violation':bool(v)} for x,ac,ex,v in zip(rr,actual,policy,y)}
def predict(X,m):
 q=expit(((X-np.array(m['mean']))/np.array(m['scale']))@np.array(m['coefficient'])+m['intercept']);return q>.5,q
def result(X,m):
 p,q=predict(X,m)
 return {'physical':stats(actual,p,q),'task_plus_rf':stats(y,p!=policy,np.where(policy,1-q,q)),'predictions':[{'id':x['id'],'block':x['block'],'actual':bool(ac),'expected':bool(ex),'violation':bool(v),'p_actual':float(prob),'alert':bool(al)} for x,ac,ex,v,prob,al in zip(rr,actual,policy,y,q,p!=policy)]}
out={'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'n_test':32,'n_train_old':16,'raw_source_hashes_verified':verified,'scope':'untraced controlled implementation substitution, one device, no SHA cover, all frozen models reported; no arbitrary OS-compromise or causal tracing-overhead claim','model_sha256':expected,'original':{},'relative_reference':{},'windows':{},'external_timing':{},'task_only':stats(y,np.zeros(32,dtype=bool)),'trusted_kernel_exec_audit':{'status':'not_measured_in_C13','reason':'system-call tracing deliberately disabled as an instrumentation control; earlier C07/C10 measured successes remain valid, absence is not failure'}}
for k,mm in original['models'].items():
 X=np.array([load_features(R,x,k=='temporal_260') for x in rr]);z=result(X,mm['physical']);p,q=predict(X,mm['direct_violation']);z['rf_direct_violation']=stats(y,p,q);out['original'][k]=z
 pairs=[referenced(R,x,k=='temporal_260') for x in rr];X=np.array([v for v,q in pairs]);mm=relative['families']['wait']['models'][k];z=result(X,mm['physical']);p,q=predict(X,mm['direct_violation']);z['rf_direct_violation']=stats(y,p,q);z['reference_checks']=[q for v,q in pairs];z['paired_vs_original']=compare(z['predictions'],out['original'][k]['predictions'],truth);out['relative_reference'][k]=z
for w,kk in windows['families']['wait']['windows'].items():
 out['windows'][w]={}
 for k,mm in kk.items():
  pairs=[windowed(R,x,w,k=='temporal_260') for x in rr];z=result(np.array([v for v,q in pairs]),mm['physical']);z['frame_checks']=[q for v,q in pairs];z['paired_vs_original']=compare(z['predictions'],out['original'][k]['predictions'],truth);out['windows'][w][k]=z
lookup={x['id']:x for x in validation['rows']}
for label,cols in [('coordinator_elapsed',['coordinator_elapsed_s']),('gateway_service',['gateway_service_s']),('both_external_times',['coordinator_elapsed_s','gateway_service_s'])]:
 X=np.array([[lookup[x['id']][c] for c in cols] for x in rr]);z=result(X,original['timing'][label]['physical']);out['external_timing'][label]=z
out['all_trial_observations']=validation['rows'];(R/'UNTRACED_WAIT_EVALUATION.json').write_text(json.dumps(out,indent=2))
print(json.dumps({'old_RF':{k:v['task_plus_rf'] for k,v in out['original'].items()},'relative':{k:v['task_plus_rf'] for k,v in out['relative_reference'].items()},'external_timing':{k:v['task_plus_rf'] for k,v in out['external_timing'].items()}}))
