"""CPU-only full contiguous IQ feature extraction. Four workers, no models invoked."""
import argparse, concurrent.futures, hashlib, json, os, pathlib, time, traceback
os.environ["OPENBLAS_NUM_THREADS"]="1";os.environ["OMP_NUM_THREADS"]="1";os.environ["MKL_NUM_THREADS"]="1"
import numpy as np
NFFT=1024;SEG=204800;SR=20000000
def save(p,x):
    tmp=p.with_suffix(p.suffix+".tmp");tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2));tmp.replace(p)
def one(task):
    root=pathlib.Path(task["root"]);raw=root/"raw"/task["filename"];out=root/"features"/(raw.stem+".npz")
    h=hashlib.sha256();band=np.minimum((np.abs(np.fft.fftfreq(NFFT,1/SR))/1e7*64).astype(int),63)
    valid=(np.abs(np.fft.fftfreq(NFFT,1/SR))>.15e6)&(np.abs(np.fft.fftfreq(NFFT,1/SR))<9e6)
    groups=[np.where(valid&(band==j))[0] for j in range(64)];empty=[j for j,g in enumerate(groups) if not len(g)]
    win=np.hanning(NFFT).astype(np.float32);den=float(np.sum(win**2)*NFFT)
    series=[];powers=[];clips=[];counts=[];consumed=0
    with raw.open("rb") as f:
        while True:
            buf=f.read(SEG*2)
            if not buf:break
            h.update(buf);a=np.frombuffer(buf,dtype=np.int8);consumed+=len(a)
            if len(a)%2:raise RuntimeError("odd IQ byte count")
            z=a[0::2].astype(np.float32)+1j*a[1::2].astype(np.float32)
            if len(z)%NFFT:raise RuntimeError("tail not FFT aligned")
            powers.append(float(np.mean(z.real*z.real+z.imag*z.imag)));counts.append(len(z))
            clips.append(float(np.mean((a==-128)|(a==127))))
            frames=z.reshape(-1,NFFT);frames=frames-frames.mean(axis=1,keepdims=True)
            fft=np.fft.fft(frames*win,axis=1);sp=np.mean(fft.real**2+fft.imag**2,axis=0)/den
            series.append(np.array([float(np.mean(sp[g])) if len(g) else 0 for g in groups]))
    if consumed!=raw.stat().st_size or consumed!=task["expected_bytes"]:raise RuntimeError("incomplete extraction")
    psd=np.array(series);pw=np.array(powers);ct=np.array(counts);db=10*np.log10(np.maximum(psd,1e-20));pwdb=10*np.log10(np.maximum(pw,1e-20))
    mean_db=10*np.log10(np.maximum(np.average(psd,axis=0,weights=ct),1e-20))
    feat=np.concatenate([mean_db,np.quantile(db,[.1,.5,.9],axis=0).ravel(),[10*np.log10(np.average(pw,weights=ct))],np.quantile(pwdb,[.1,.5,.9])])
    for j in empty:
        for k in range(4):feat[j+k*64]=0
    np.savez_compressed(out,features=feat,power_db=pwdb,band_db=db,clip_fraction=np.array(clips),sample_counts=ct)
    result={"id":task["id"],"stage":task["stage"],"radio":task["radio"],"filename":task["filename"],"raw_sha256":h.hexdigest(),"raw_bytes":consumed,"feature_path":str(out),"frames":len(pw),"samples_consumed":int(ct.sum()),"full_contiguous":True,"empty_frequency_groups":empty,"feature_dim":len(feat),"mean_power_db":float(10*np.log10(np.average(pw,weights=ct))),"max_clip_fraction":float(max(clips))}
    save(out.with_suffix(".json"),result);return result
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--root",required=True);ap.add_argument("--workers",type=int,default=4);a=ap.parse_args()
    root=pathlib.Path(a.root);(root/"features").mkdir(exist_ok=True);os.nice(10)
    done={};start=time.time()
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers) as ex:
        futures={};queued=set()
        while True:
            if (root/"QUEUE.json").exists():
                queue=json.loads((root/"QUEUE.json").read_text())["files"]
                for row in queue:
                    name=row["filename"]
                    if name in queued or not (root/"raw"/name).exists():continue
                    row["root"]=str(root);futures[ex.submit(one,row)]=name;queued.add(name)
            for fut in list(futures):
                if not fut.done():continue
                result=fut.result();done[result["filename"]]=result;del futures[fut]
                print(json.dumps({"completed":len(done),"filename":result["filename"],"bytes":result["raw_bytes"]}),flush=True)
                save(root/"EXTRACTION_STATUS.json",{"completed":len(done),"elapsed_s":time.time()-start,"receipts":list(done.values())})
            if (root/"UPLOAD_COMPLETE.json").exists() and not futures:
                expected=json.loads((root/"UPLOAD_COMPLETE.json").read_text())["expected_files"]
                if len(done)==expected:break
            if (root/"STOP_REQUESTED.json").exists():raise RuntimeError("own controller requested stop; retain artifacts")
            if time.time()-start>14400:raise RuntimeError("extraction/transfer wait exceeded4h")
            time.sleep(2)
    save(root/"EXTRACTION_COMPLETE.json",{"receipts":list(done.values()),"elapsed_s":time.time()-start,"full_contiguous":True})
if __name__=="__main__":
    try:main()
    except Exception:
        pathlib.Path(__file__).with_name("EXTRACTION_FAILURE.log").write_text(traceback.format_exc());raise
