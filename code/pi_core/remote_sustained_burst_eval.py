import argparse,hashlib,json,pathlib,time
import numpy as np
from scipy.special import expit
from remote_extensions import load_features,stats
ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);a=ap.parse_args();R=pathlib.Path(a.root)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
fpath=R/'BURST_EXPLORATORY_FREEZE.json';assert sha(fpath)=='e43e226984b4034dcd0f86aa3423dcd6a0e1faa88ebc3b4c9449fb23640c1f22';f=json.loads(fpath.read_text());rows=json.loads((R/'LEDGER.json').read_text())['records'];sources={r['filename']:r for r in json.loads((R/'SOURCE_RECEIPTS.json').read_text())['files']};v=json.loads((R/'SUSTAINED_BURST_COLLECTION_VALIDATION.json').read_text());assert v['pass'] and v['trials']==24
assert len(rows)==24 and len({r['id'] for r in rows})==24 and all(r['valid'] and r['stage']=='sustained_burst_confirmation' and r['cover'] for r in rows)
verified=0
for r in rows:
 for radio in ['930c','16bc']:
  d=json.loads((R/'features'/(r['id']+'_'+radio+'.json')).read_text());s=sources[r['id']+'_'+radio+'.iq'];assert d['full_contiguous'] and d['raw_sha256']==s['sha256'] and d['raw_bytes']==s['bytes'];verified+=1
assert verified==48
y=np.array([r['milliseconds']>0 for r in rows]);assert y.sum()==18 and (~y).sum()==6
base=[];scores={k:[] for k in f['models']}
for r in rows:
 with np.load(R/'features'/(r['id']+'_930c.npz')) as z:
  pw=z['power_db'];med=float(np.median(pw));ss={'p99_minus_p50':float(np.quantile(pw,.99)-med),'max_minus_p50':float(np.max(pw)-med),'top3mean_minus_p50':float(np.mean(np.sort(pw)[-3:])-med)}
 for k in scores:scores[k].append(ss[k])
 cv=r['private']['cover'];base.append({'id':r['id'],'block':r['block'],'milliseconds':r['milliseconds'],'cover':True,'actual':r['milliseconds']>0,'actual_c_loop_ms':r['private']['burst_elapsed_s']*1000,'sha_duration_s':(cv['end_ns']-cv['begin_ns'])/1e9,'sha_blocks':cv['blocks'],'full_SHA_overlap':cv['begin_ns']<=r['private']['burst_begin_ns']<r['private']['burst_end_ns']<=cv['end_ns']})
out={'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'scope':'C15 new24 tests after seeing C09; sustained1.5s SHA benchmark background; fixed original three thresholds and whole model; no tuning/fitting','raw_source_hashes_verified':48,'n_test':24,'n_active':18,'n_quiet':6,'source_model_sha256':sha(fpath),'validation_sha256':sha(R/'SUSTAINED_BURST_COLLECTION_VALIDATION.json'),'code_sha256':sha(pathlib.Path(__file__)),'models':{}}
for k,ss in scores.items():
 ss=np.array(ss);t=f['models'][k]['threshold'];pred=ss>t;cells=[]
 for ms in [0,10,100,1000]:
  mask=np.array([r['milliseconds']==ms for r in rows]);assert mask.sum()==6;cells.append({'milliseconds':ms,'n':6,'alerts':int(pred[mask].sum())})
 out['models'][k]={'threshold':t,'activity':stats(y,pred,ss),'by_duration':cells,'predictions':[dict(r,score=float(s),alert=bool(p)) for r,s,p in zip(base,ss,pred)]}
X=np.array([load_features(R,r) for r in rows]);m=f['original_whole_model'];q=expit(((X-np.array(m['mean']))/np.array(m['scale']))@np.array(m['coefficient'])+m['intercept']);out['original_whole_260']={'activity':stats(y,q>.5,q),'predictions':[dict(r,p_actual=float(s),alert=bool(s>.5)) for r,s in zip(base,q)]}
p=R/'SUSTAINED_BURST_EVALUATION.json';assert not p.exists();p.write_text(json.dumps(out,indent=2));print(json.dumps({'raw_verified':48,'models':{k:z['activity'] for k,z in out['models'].items()},'whole':out['original_whole_260']['activity']}))
