"""Small fixed-feature replay for review; no training and no raw-IQ processing."""
import os
for k in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS"): os.environ[k]="4"
import csv,json,hashlib,sys
from pathlib import Path
import numpy as np
try: os.nice(10)
except OSError: pass
ROOT=Path(__file__).resolve().parents[2]
B=ROOT/'data/pi_adaptive_desktop/experiments'
OUT=ROOT/'outputs/replay'
OUT.mkdir(parents=True,exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def original_hash_verified(name,v):
 rows=json.loads((ROOT/'ORIGINAL_HASHES.json').read_text())
 return any(Path(x['path']).name==name and x['original_sha256']==v and sha(ROOT/x['path'])==x['artifact_sha256'] for x in rows)
def truth(x):return str(x).lower()=="true"
def sigmoid(x):return 1/(1+np.exp(-x))
def score(X,m):
 return sigmoid(((X-np.array(m["mean"]))/np.array(m["scale"]))@np.array(m["coefficient"])+m["intercept"])
def reference(X,rows,cal):
 cm=X[cal].mean(0);pool=np.array([i for i,r in enumerate(rows) if r["condition"] in ("silent","silent_cal")]);Y=np.empty_like(X)
 for i in range(len(X)):
  prev=pool[pool<i];Y[i]=X[i]-(cm if cal[i] or len(prev)==0 else X[prev[-4:]].mean(0))
 return Y
d=next((B/"campaigns").glob("s1p_*"))
rows=json.loads((d/"RESULTS.json").read_text());cal=np.array([r["condition"]=="silent_cal" for r in rows])
env=[]
for r in rows:
 with np.load(d/"env"/(r["id"]+"_930c_env.npz")) as z:
  g=[z[k][:64].reshape(16,4,9).mean(1).ravel() for k in ("mod_call","mod_pre")]
  env.append(np.r_[g[0],g[1],z["mod_call"][64],z["mod_pre"][64]])
env=reference(np.array(env),rows,cal)
m38=json.loads((B/"models/C38_ENV_MODELS.json").read_text());q38=score(env,m38["models"]["roll4"])
freq=np.abs(np.fft.fftfreq(1024,1/20000000));gr=np.minimum((freq/1e7*64).astype(int),63)
valid=(freq>.15e6)&(freq<9e6);empty=[j for j in range(64) if not np.any(valid&(gr==j))]
XX={False:[],True:[]};pre=[]
for r in rows:
 with np.load(d/"features"/(r["id"]+"_930c.npz")) as z:
  w=z["sample_counts"];bb=z["band_db"];pp=z["power_db"]
 end=np.cumsum(w);start=end-w
 before=next(m["bytes"] for m in r["before"]["marks"] if m["radio"]=="930c")
 after=next(m["bytes"] for m in r["after"]["marks"] if m["radio"]=="930c")
 pm=(end*2<=before)&(w>0)
 b=10*np.log10(np.maximum(np.average(10**(bb[pm]/10),axis=0,weights=w[pm]),1e-20))
 p=10*np.log10(np.maximum(np.average(10**(pp[pm]/10),weights=w[pm]),1e-20));b[empty]=0
 pre.append(np.r_[np.tile(b,4),np.repeat(p,4)])
 mask=(start*2>=before)&(end*2<=after);ww=w[mask];bands=bb[mask];power=pp[mask]
 mean=10*np.log10(np.maximum(np.average(10**(bands/10),axis=0,weights=ww),1e-20))
 bp=10*np.log10(np.maximum(np.average(10**(power/10),weights=ww),1e-20))
 whole=np.r_[mean,np.quantile(bands,[.1,.5,.9],axis=0).ravel(),bp,np.quantile(power,[.1,.5,.9])]
 center=(np.cumsum(ww)-ww/2)/ww.sum();v=[];pw=[]
 for k in range(4):
  mk=(center>=k/4)&(center<(k+1)/4)
  v.extend((10*np.log10(np.maximum(np.average(10**(bands[mk]/10),axis=0,weights=ww[mk]),1e-20))).tolist())
  pw.append(float(10*np.log10(np.maximum(np.average(10**(power[mk]/10),weights=ww[mk]),1e-20))))
 temporal=np.array(v+pw)
 for vec in (whole,temporal):
  for j in empty:
   for k in range(4):vec[j+k*64]=0
 XX[False].append(whole);XX[True].append(temporal)
m35=json.loads((B/"models/C35_SELFROLL_MODELS.json").read_text())
q35=np.mean([score(reference(np.array(XX[m["temporal"]])-np.array(pre),rows,cal),m)
             for m in m35["variants"]["self_roll4"]["models"].values()],axis=0)
saved35={r["id"]:float(r["score"]) for r in csv.DictReader((d/"predictions_c35.csv").open()) if r["detector"]=="C35/self_roll4_p70"}
saved38={r["id"]:float(r["score"]) for r in csv.DictReader((d/"predictions_c38.csv").open()) if r["detector"]=="C38/roll4"}
delta35=max(abs(float(s)-saved35[r["id"]]) for r,s in zip(rows,q35));delta38=max(abs(float(s)-saved38[r["id"]]) for r,s in zip(rows,q38))
assert delta35<1e-10 and delta38<1e-10,(delta35,delta38)
a35=q35>.7;a38=q38>.5;out={"scope":"Stored feature replay only; no new independent runs, no retraining, no raw-IQ validation",
 "C35_max_abs_score_difference":delta35,"C38_max_abs_score_difference":delta38,"by_condition":{}}
for c in sorted({r["condition"] for r in rows if r["condition"]!="silent_cal"}):
 mk=np.array([r["condition"]==c for r in rows])
 out["by_condition"][c]={"n":int(mk.sum()),"C35":int(a35[mk].sum()),"C38":int(a38[mk].sum()),"OR":int((a35|a38)[mk].sum())}
freeze=json.loads((d/"FREEZE.json").read_text())
out["frozen_model_hash_matches"]={name:any(k.replace(chr(92),"/").rsplit("/",1)[-1]==name and original_hash_verified(name,v) for k,v in freeze["source_sha256"].items()) for name in ["C35_SELFROLL_MODELS.json","C38_ENV_MODELS.json"]}
out["feature_code_hash_matches"]={name:original_hash_verified(name,v) for name,v in m38["feature_code_sha256"].items()}
out["pre_capture_duration_s"]={"min":min(next(m["bytes"] for m in r["before"]["marks"] if m["radio"]=="930c")/40000000 for r in rows),"max":max(next(m["bytes"] for m in r["before"]["marks"] if m["radio"]=="930c")/40000000 for r in rows)}
(OUT/"fixed_feature_replay.json").write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(json.dumps(out,ensure_ascii=False,indent=2))
