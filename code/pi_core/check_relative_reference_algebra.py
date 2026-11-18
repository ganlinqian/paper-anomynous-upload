"""Small old-feature algebra check, not a detection experiment or robustness guarantee."""
import hashlib,json,pathlib,time,numpy as np
from relative_reference_features import relative,feature
B=pathlib.Path(__file__).resolve().parent;src=B/'analysis_extensions/full_20261105';m=json.loads((B/'analysis_extensions/RELATIVE_REFERENCE_MODELS.json').read_text());ident=m['families']['trace']['training_ids'][0];rows=json.loads((src/'LEDGER.json').read_text())['records'];row=next(x for x in rows if x['id']==ident)
with np.load(src/'features'/(ident+'_930c.npz')) as f:orig={k:f[k].copy() for k in f.files}
offset=np.linspace(-2,3,64);offset[np.max(orig['band_db'],axis=0)<-199]=0;synthetic={k:v.copy() for k,v in orig.items()};synthetic['band_db']+=offset;synthetic['power_db']+=3;synthetic['features']+=np.r_[np.tile(offset,4),np.repeat(3,4)]
result={'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'training_id':ident,'scope':'synthetic fixed dB offsets only; verifies the intended algebra, not accuracy under real drift, new RF data, frequency shift, noise, or camouflage','kinds':{}}
for kind in ('whole_260','temporal_260'):
 temporal=kind=='temporal_260';a,end=relative(orig,temporal);b,_=relative(synthetic,temporal);err=float(np.max(np.abs(a-b)));assert err<1e-10;real,guard=feature(src,row,temporal);assert np.array_equal(real,a);result['kinds'][kind]={'max_absolute_error':err,'pass':True,'reference_end_seconds':end,'before_dispatch_bytes':guard['before_dispatch_bytes']}
(B/'analysis_extensions/RELATIVE_REFERENCE_ALGEBRA_CHECK.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
