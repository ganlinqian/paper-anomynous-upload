import argparse,hashlib,json,pathlib,time
import numpy as np
from scipy.special import expit
from remote_extensions import load_features,stats
ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);a=ap.parse_args();R=pathlib.Path(a.root)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
p=R/'EARLY_BURST_CONFIRMATION.json';assert sha(p)=='10ca91c73d54730047f5df56703e3a5c4b6d2e5db5adf28fc18a2e9ee827e317';j=json.loads(p.read_text())
f=R/'BURST_EXPLORATORY_FREEZE.json';assert sha(f)=='e43e226984b4034dcd0f86aa3423dcd6a0e1faa88ebc3b4c9449fb23640c1f22'
rows=[x for x in json.loads((R/'LEDGER.json').read_text())['records'] if x['stage']=='burst_confirmation'];assert len(rows)==72 and all(x['valid'] for x in rows)
lookup={x['id']:x for x in j['models']['p99_minus_p50']['predictions']};assert set(lookup)=={x['id'] for x in rows}
X=np.array([load_features(R,r) for r in rows]);m=json.loads(f.read_text())['original_whole_model'];q=expit(((X-np.array(m['mean']))/np.array(m['scale']))@np.array(m['coefficient'])+m['intercept']);y=np.array([r['milliseconds']>0 for r in rows]);s=stats(y,q>.5,q)
for k,v in s.items():assert np.allclose(v,j['original_whole_260'][k],atol=1e-12,rtol=0),k
out=[]
for r,prob in zip(rows,q):
 private=r['private'];wall=(private['burst_end_ns']-private['burst_begin_ns'])/1e6
 row={'id':r['id'],'block':r['block'],'milliseconds':r['milliseconds'],'cover':r['cover'],'actual':r['milliseconds']>0,'actual_c_loop_ms':private['burst_elapsed_s']*1000,'ctypes_call_wall_ms':wall,'operations':private['operations'],'original_whole_probability':float(prob),'original_whole_alert':bool(prob>.5),'external_elapsed_s':r['elapsed_s']}
 if r['cover']:
  c=private['cover'];duration=(c['end_ns']-c['begin_ns'])/1e6;overlap=max(0,min(c['end_ns'],private['burst_end_ns'])-max(c['begin_ns'],private['burst_begin_ns']))/1e6
  row.update(sha_cover_ms=duration,sha_burst_overlap_ms=overlap,sha_overlap_fraction_of_burst_wall=overlap/wall if wall>0 else None)
 assert not row['actual'] or abs(row['actual_c_loop_ms']-row['milliseconds'])<5
 out.append(row)
p=R/'BURST_CONFIRMATION_DETAILS.json';assert not p.exists();p.write_text(json.dumps({'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'scope':'posthoc execution-duration and finite SHA-overlap descriptions; original whole predictions re-evaluated and match early statistics; no new fit or threshold','original_early_result_sha256':sha(R/'EARLY_BURST_CONFIRMATION.json'),'evaluation_code_sha256':sha(pathlib.Path(__file__)),'original_whole_statistics':s,'rows':out},indent=2));print(json.dumps({'sha256':sha(p),'bytes':p.stat().st_size,'n':len(out)}))
