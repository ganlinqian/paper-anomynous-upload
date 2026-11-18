import argparse,hashlib,itertools,json,pathlib,time
import numpy as np
from scipy.special import expit
from remote_extensions import load_features,stats
from relative_reference_features import feature as relative_feature
from execution_window_features import feature as window_feature,EMPTY
ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);a=ap.parse_args();R=pathlib.Path(a.root);sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(R/'CONFIRMATION_MODELS.json')=='8ec87a546f008b7778fbf4afdb9cc7d7342c465b8489c80090fbb506b8797f49';assert sha(R/'RELATIVE_REFERENCE_MODELS.json')=='70d72ecf5321b6ee0a68cce74077fd7e5adc121087efda5ea7868a41a94b071b';assert sha(R/'EXECUTION_WINDOW_MODELS.json')=='f238ff8e1a3f73a9d2fa29f0495a4d30cc36c5e255b02cb714a48432614e4224'
assert sha(R/'MODEL_RESPONSE_AUDIT_PROTOCOL.md')=='fd8005ad19f9da0cc085ea7782bc70d72f7fefbfb86222b2f85f12ac01856f56'
for name,h in [('relative_reference_features.py','17d6d034fc3e3ed85c993449a79bf20c5afdc6dd6dc8ec89a96ce96ba6930527'),('execution_window_features.py','aa2d8ea85bc2fb68ec338fe7e703c95c47659c09773a61b7543c72cfce132bb1'),('remote_extensions.py','99309e8cf2538dd8a17d1e5a45a373dc497c75b83a0441007cfb94fef15767c0')]:assert sha(R/name)==h,name
assert json.loads((R/'C08_COLLECTION_VALIDATION.json').read_text())['pass'];rows=[r for r in json.loads((R/'LEDGER.json').read_text())['records'] if r['stage']=='confirmation' and r['family']=='order'];assert len(rows)==40 and all(r['valid'] for r in rows)
sources={r['filename']:r for r in json.loads((R/'SOURCE_RECEIPTS.json').read_text())['files']}
for r in rows:
 stem=r['id']+'_930c';d=json.loads((R/'features'/(stem+'.json')).read_text());s=sources[stem+'.iq'];assert d['full_contiguous'] and d['raw_sha256']==s['sha256'] and d['raw_bytes']==s['bytes']
f=json.loads((R/'CONFIRMATION_MODELS.json').read_text())['families']['order'];rel=json.loads((R/'RELATIVE_REFERENCE_MODELS.json').read_text())['families']['order'];window=json.loads((R/'EXECUTION_WINDOW_MODELS.json').read_text())['families']['order'];assert set(f['training_ids'])==set(rel['training_ids'])==set(window['training_ids']);assert not set(r['id'] for r in rows)&set(f['training_ids'])
y=np.array([r['actual_condition'] for r in rows]);e=np.array([r['expected_condition'] for r in rows]);v=y!=e
models={'original_full':(f['models']['temporal_260']['physical'],np.array([load_features(R,r,True) for r in rows])),'relative_full':(rel['models']['temporal_260']['physical'],np.array([relative_feature(R,r,True)[0] for r in rows])),'call_bracket':(window['windows']['call_bracket']['temporal_260']['physical'],np.array([window_feature(R,r,'call_bracket',True)[0] for r in rows]))}
perms=list(itertools.permutations(range(4)));out={'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'scope':'posthoc feature-vector response analysis only; not new executions or physical/causal evidence','code_sha256':sha(pathlib.Path(__file__)),'protocol_sha256':sha(R/'MODEL_RESPONSE_AUDIT_PROTOCOL.md'),'raw_sources_verified':40,'n_executions':40,'n_permutations':24,'models':{},'uniform_db_direction_slope':{}}
for name,(m,X) in models.items():
 assert X.shape==(40,260);beta=np.array(m['coefficient'])/np.array(m['scale']);intercept=m['intercept']-float(np.array(m['mean'])@beta);pp=[];identity_q=expit(X@beta+intercept);identity=identity_q>.5
 for perm in perms:
  ix=np.r_[np.concatenate([np.arange(k*64,(k+1)*64) for k in perm]),256+np.array(perm)];Z=X[:,ix];q=expit(Z@beta+intercept);pred=q>.5
  pp.append({'permutation':list(perm),'physical_correct':int(np.sum(pred==y)),'policy_correct':int(np.sum((pred!=e)==v)),'bit_flips_from_identity':int(np.sum(pred!=identity)),'predictions':[{'id':r['id'],'block':r['block'],'actual':bool(a),'expected':bool(ex),'violation':bool(vi),'p_actual':float(pr),'predicted_actual':bool(hat),'alarm':bool(hat!=ex)} for r,a,ex,vi,pr,hat in zip(rows,y,e,v,q,pred)]})
 identity_record=next(x for x in pp if x['permutation']==[0,1,2,3]);reverse_record=next(x for x in pp if x['permutation']==[3,2,1,0]);assert identity_record['physical_correct']==40
 out['models'][name]={'identity':{k:x for k,x in identity_record.items() if k!='predictions'},'reverse':{k:x for k,x in reverse_record.items() if k!='predictions'},'all_permutations':pp,'correct_count_distribution':{str(k):sum(x['physical_correct']==k for x in pp) for k in sorted({x['physical_correct'] for x in pp})},'effective_weight_sum_by_quarter':[float(sum(beta[k*64+j] for j in range(64) if j not in EMPTY)+beta[256+k]) for k in range(4)]}
g=np.ones(260)
for j in EMPTY:
 for k in range(4):g[k*64+j]=0
for kind,z in f['models'].items():
 m=z['physical'];beta=np.array(m['coefficient'])/np.array(m['scale']);slope=float(beta@g);out['uniform_db_direction_slope'][kind]={'logit_change_per_one_db':slope,'effective_weight_l2':float(np.linalg.norm(beta)),'absolute_direction_cosine':float(abs(slope)/(np.linalg.norm(beta)*np.linalg.norm(g))),'not_an_observed_gain_change':True}
p=R/'MODEL_RESPONSE_AUDIT.json';assert not p.exists();p.write_text(json.dumps(out,indent=2));print(json.dumps({'sha256':sha(p),'bytes':p.stat().st_size,'models':{k:{'identity':z['identity'],'reverse':z['reverse'],'distribution':z['correct_count_distribution']} for k,z in out['models'].items()},'gain_slopes':out['uniform_db_direction_slope']}))
