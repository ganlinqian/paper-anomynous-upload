import os
for k in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
import argparse,pathlib,hashlib,json,time,concurrent.futures,importlib.util
import numpy as np
ap=argparse.ArgumentParser();ap.add_argument('--data-root',required=True);ap.add_argument('--output-root',required=True);a=ap.parse_args();R=pathlib.Path(a.data_root);O=pathlib.Path(a.output_root);O.mkdir(exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
models=json.loads((O/'MODELS.json').read_text());scalars=json.loads((O/'SCALARS.json').read_text())
assert sha(O/'MODELS.json')=='5dc5b97501c2fa372c93080602c2575a78369ed9389741558fcb8d9a94897765'
assert sha(O/'SCALARS.json')=='0737b0303781b8268fcbefe4f51f209e938f26bd2f0650d178d65323ca9a91bb'
rows=[r for r in json.loads((R/'LEDGER.json').read_text())['records'] if r['stage']=='confirmation'];assert len(rows)==80 and all(r['valid'] for r in rows)
sources={s['filename']:s for s in json.loads((R/'SOURCE_RECEIPTS.json').read_text())['files']}
expected={f:{x['id']:x for x in s['rows'] if x['group']=='confirmation'} for f,s in scalars['families'].items()};assert all(len(v)==40 for v in expected.values())
def scalar(path):
 t=time.perf_counter();cpu=time.process_time();h=hashlib.sha256();pw=[];ct=[];nb=0
 with path.open('rb') as f:
  while True:
   buf=f.read(409600)
   if not buf:break
   h.update(buf);nb+=len(buf);assert len(buf)%2==0
   iq=np.frombuffer(buf,dtype=np.int8);z=iq[::2].astype(np.float32)+1j*iq[1::2].astype(np.float32)
   pw.append(float(np.mean(z.real*z.real+z.imag*z.imag)));ct.append(len(z))
 p=np.array(pw);w=np.array(ct);power_db=10*np.log10(np.maximum(p,1e-20));center=(np.cumsum(w)-w/2)/w.sum();quarter=[]
 for k in range(4):
  m=(center>=k/4)&(center<(k+1)/4);assert m.any();quarter.append(float(10*np.log10(np.average(10**(power_db[m]/10),weights=w[m]))))
 v=10**(np.array(quarter)/10)
 return {'mean_power_1':float(10*np.log10(np.average(p,weights=w))),'early_minus_late_power_1':float(10*np.log10((v[0]+v[1])/(v[2]+v[3]))),'bytes':nb,'raw_sha256':h.hexdigest(),'frames':len(p),'samples_consumed':int(w.sum()),'wall_s':time.perf_counter()-t,'cpu_s':time.process_time()-cpu}
def one(row):
 f=row['family'];key='mean_power_1' if f=='trace' else 'early_minus_late_power_1';name=row['id']+'_930c.iq';s=scalar(R/'raw'/name);src=sources[name];assert s['raw_sha256']==src['sha256'] and s['bytes']==src['bytes'] and s['samples_consumed']*2==s['bytes']
 ref=expected[f][row['id']];m=models['families'][f][key];x=s[key];logit=float(((np.array([x])-m['mean'])/m['scale'])@np.array(m['coefficient'])+m['intercept']);q=float(1/(1+np.exp(-logit)));pred=q>.5
 assert row['actual_condition']==ref['actual'] and pred==ref['prediction'];dv=abs(x-ref['value']);dq=abs(q-ref['p_actual']);assert dv<=1e-10 and dq<=1e-10
 return {'id':row['id'],'family':f,'block':row['block'],'actual':row['actual_condition'],'expected':row['expected_condition'],'violation':row['actual_condition']!=row['expected_condition'],'prediction':bool(pred),'alert':bool(pred!=row['expected_condition']),'feature':key,'value':x,'reference_value':ref['value'],'p_actual':q,'reference_p_actual':ref['p_actual'],'absolute_feature_difference':dv,'absolute_probability_difference':dq,**s}
def main():
 out=O/'C22_STREAMING_REPLAY.json';assert not out.exists();t=time.perf_counter()
 with concurrent.futures.ProcessPoolExecutor(max_workers=2) as ex:rr=list(ex.map(one,rows))
 total=time.perf_counter()-t
 # Small same-file warm-cache comparison. Existing full extractor writes into a new benchmark tree only.
 bench=O/'benchmark';(bench/'raw').mkdir(parents=True,exist_ok=True);(bench/'features').mkdir(exist_ok=True)
 row=rows[0];name=row['id']+'_930c.iq';link=bench/'raw'/name
 if not link.exists():link.symlink_to(R/'raw'/name)
 spec=importlib.util.spec_from_file_location('original_extractor',R/'remote_extract_confirmation.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 assert sha(R/'remote_extract_confirmation.py')=='c387e3c74a88bfbc77b1f9d5b0df7bf03361944a20c84fb4db28f2a1f8e1aef7'
 benchmark=[]
 for repeat,sequence in enumerate([['scalar','full_fft'],['full_fft','scalar']]):
  for method in sequence:
   t0=time.perf_counter();c0=time.process_time()
   if method=='scalar':v=scalar(link)
   else:v=module.one({'root':str(bench),'filename':name,'id':row['id'],'stage':'C22_replay_benchmark','radio':'930c','expected_bytes':sources[name]['bytes']})
   assert v['raw_sha256']==sources[name]['sha256']
   benchmark.append({'repeat':repeat,'method':method,'wall_s':time.perf_counter()-t0,'cpu_s':time.process_time()-c0,'bytes':sources[name]['bytes'],'same_file':name,'cache_policy':'uncontrolled warm cache; alternating order; full SHA in both'})
 result={'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'scope':'posthoc implementation replay of existing C08; no additional independent executions; not online deployment','code_sha256':sha(pathlib.Path(__file__)),'models_sha256':sha(O/'MODELS.json'),'scalars_sha256':sha(O/'SCALARS.json'),'protocol_sha256':sha(O/'PROTOCOL.md'),'raw_files':80,'raw_bytes':sum(r['bytes'] for r in rr),'workers':2,'streaming_wall_s':total,'aggregate_cpu_s':sum(r['cpu_s'] for r in rr),'maximum_feature_difference':max(r['absolute_feature_difference'] for r in rr),'maximum_probability_difference':max(r['absolute_probability_difference'] for r in rr),'prediction_agreement':sum(r['prediction']==expected[r['family']][r['id']]['prediction'] for r in rr),'predictions':rr,'benchmark':benchmark}
 out.write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k not in ['predictions','benchmark']}))
if __name__=='__main__':main()
