"""C20 fixed parameters, no training."""
from pathlib import Path
import argparse,datetime,hashlib,json,numpy as np
from scipy.special import expit
from remote_extensions import load_features,stats
a=argparse.ArgumentParser();a.add_argument('--root',required=True);args=a.parse_args();R=Path(args.root)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
MODEL='C10_CALIBRATION_MODELS_RECONSTRUCTED.json';MH='ec83b153b44292f7b506f110ef6a6850bd8575e5128f23629b17aa75d9914f1a'
assert sha(R/MODEL)==MH and sha(R/'remote_extensions.py')=='99309e8cf2538dd8a17d1e5a45a373dc497c75b83a0441007cfb94fef15767c0'
freeze=read(R/'C20_FREEZE.json');assert freeze['models_sha256']==MH and freeze['protocol_sha256']==sha(R/'C20_CALIBRATION_TRANSFER_PROTOCOL.md') and freeze['code_sha256']==sha(Path(__file__))
j=read(R/MODEL);assert len(j['models'])==14 and j['max_heldout_probability_difference']==0
rows=read(R/'LEDGER.json')['records'];assert len(rows)==32 and all(x['valid'] and not x['cover'] and x['stage']=='untraced_wait_confirmation' for x in rows)
sources={x['filename']:x for x in read(R/'SOURCE_RECEIPTS.json')['files']};assert len(sources)==64
for x in rows:
 for radio in ['930c','16bc']:
  n=x['id']+'_'+radio;m=read(R/'features'/(n+'.json'));s=sources[n+'.iq'];assert m['full_contiguous'] and m['raw_sha256']==s['sha256'] and m['raw_bytes']==s['bytes']==320000000
validation=read(R/'UNTRACED_WAIT_COLLECTION_VALIDATION.json');assert validation['pass'] and validation['trials']==32
vl={x['id']:x for x in validation['rows']};actual=np.array([x['actual_active'] for x in rows],bool);expected=np.array([x['expected_active'] for x in rows],bool);y=actual!=expected
out={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'C20 fixed C10-calibrated parameters transferred to independent untraced C13; no fit/threshold selection; outcome-blind supplementary protocol after collection','n_test':32,'n_blocks':8,'raw_source_hashes_verified':64,'models_sha256':MH,'freeze_sha256':sha(R/'C20_FREEZE.json'),'code_sha256':sha(Path(__file__)),'models':{}}
timing={'coordinator_elapsed':['coordinator_elapsed_s'],'gateway_service':['gateway_service_s'],'both_external_times':['coordinator_elapsed_s','gateway_service_s']}
for name,m in j['models'].items():
 assert not set(m['training_ids'])&{x['id'] for x in rows};assert m['classes']==[False,True] and m['target'] in ['actual_activity','violation']
 if name.startswith('timing/'):
  cols=timing[name.split('/')[1]];X=np.array([[vl[x['id']][k] for k in cols] for x in rows])
 else:X=np.array([load_features(R,x,name.startswith('temporal_260/')) for x in rows])
 q=expit(((X-np.array(m['mean']))/np.array(m['scale']))@np.array(m['coefficient'])+m['intercept']);p=q>.5
 direct=m['target']=='violation';alert=p if direct else p!=expected;vscore=q if direct else np.where(expected,1-q,q)
 z={'target':m['target'],'n_train':m['n_train'],'training_ids':m['training_ids'],'task_conditioned':stats(y,alert,vscore),'predictions':[{'id':x['id'],'block':x['block'],'actual':bool(ac),'expected':bool(ex),'violation':bool(v),'score':float(vs),'p_target':float(prob),'alert':bool(al)} for x,ac,ex,v,vs,prob,al in zip(rows,actual,expected,y,vscore,q,alert)]}
 if not direct:z['physical']=stats(actual,p,q)
 out['models'][name]=z
p=R/'C20_CALIBRATION_TRANSFER_C13.json';assert not p.exists();p.write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps({'models':{k:{t:v['task_conditioned'][t] for t in ['tp','fn','fp','tn']} for k,v in out['models'].items()},'n':32,'raw':64}))
