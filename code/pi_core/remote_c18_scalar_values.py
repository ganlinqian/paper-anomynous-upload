import argparse,pathlib,json,hashlib,time
import numpy as np
from scipy.special import expit
from remote_extensions import load_features
ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);a=ap.parse_args();R=pathlib.Path(a.root);sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(R/'COARSE_OBSERVATION_ABLATION_MODELS.json')=='5dc5b97501c2fa372c93080602c2575a78369ed9389741558fcb8d9a94897765';assert sha(R/'COARSE_OBSERVATION_ABLATION.json')=='ac44bdd9962c5b0b77c6a3c78c82fec8b14eaf752e13dc7b11076c45d754957a'
models=json.loads((R/'COARSE_OBSERVATION_ABLATION_MODELS.json').read_text());prior=json.loads((R/'COARSE_OBSERVATION_ABLATION.json').read_text());training=json.loads((R/'COARSE_TRAIN_INPUT.json').read_text())['families'];ledger=json.loads((R/'LEDGER.json').read_text())['records'];out={'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'scope':'posthoc interpretation of the same C18 fits and samples, no new trials or model fitting; received power units not calibrated dBm','models_sha256':sha(R/'COARSE_OBSERVATION_ABLATION_MODELS.json'),'result_sha256':sha(R/'COARSE_OBSERVATION_ABLATION.json'),'code_sha256':sha(pathlib.Path(__file__)),'families':{}}
for fam,key in [('trace','mean_power_1'),('order','early_minus_late_power_1')]:
 m=models['families'][fam][key];beta=m['coefficient'][0];mu=m['mean'][0];scale=m['scale'][0];intercept=m['intercept'];threshold=mu-intercept*scale/beta;rows=[]
 for group in ['old_training','confirmation','confirmation_partial']:
  rr=training[fam] if group=='old_training' else [x for x in ledger if x['stage']==group and x['family']==fam]
  root=R/'coarse_training' if group=='old_training' else R
  for x in rr:
   xx=load_features(root,x,fam=='order')
   if fam=='trace':value=float(xx[256])
   else:
    pw=10**(xx[256:260]/10);value=float(10*np.log10((pw[0]+pw[1])/(pw[2]+pw[3])))
   prob=float(expit((value-mu)/scale*beta+intercept));actual=x['actual'] if group=='old_training' else x['actual_condition']
   if group!='old_training':
    ref=next(p for p in prior['groups'][group][fam]['projections'][key]['predictions'] if p['id']==x['id']);assert abs(prob-ref['p_actual'])<1e-12
   rows.append({'id':x['id'],'group':group,'actual':bool(actual),'value':value,'p_actual':prob,'prediction':prob>.5,'absolute_feature_margin':abs(value-threshold)})
 out['families'][fam]={'projection':key,'threshold':threshold,'positive_if_above_threshold':beta>0,'rows':rows,'new40_minimum_absolute_feature_margin':min(x['absolute_feature_margin'] for x in rows if x['group']=='confirmation')}
p=R/'C18_SCALAR_VALUES.json';assert not p.exists();p.write_text(json.dumps(out,indent=2));print(json.dumps({'file':p.name,'sha256':sha(p),'thresholds_and_feature_margins':{k:{q:v[q] for q in ['threshold','new40_minimum_absolute_feature_margin']} for k,v in out['families'].items()}}))
