"""Fixed pre-dispatch amplitude reference, separate from original frozen features."""
import numpy as np
FS=20_000_000
REFERENCE_SECONDS=.2
def relative(f,temporal=False):
    w=f['sample_counts'];end=np.cumsum(w)/FS;mask=end<=REFERENCE_SECONDS
    assert mask.sum()>=2 and np.all(w>0)
    bands=f['band_db'];power=f['power_db']
    base=10*np.log10(np.maximum(np.average(10**(bands[mask]/10),axis=0,weights=w[mask]),1e-20))
    bp=float(10*np.log10(np.average(10**(power[mask]/10),weights=w[mask])))
    if not temporal:
        ans=f['features']-np.r_[np.tile(base,4),np.repeat(bp,4)]
    else:
        center=(np.cumsum(w)-w/2)/w.sum();v=[];p=[]
        for k in range(4):
            m=(center>=k/4)&(center<(k+1)/4)
            v.extend((10*np.log10(np.maximum(np.average(10**(bands[m]/10),axis=0,weights=w[m]),1e-20))-base).tolist())
            p.append(float(10*np.log10(np.average(10**(power[m]/10),weights=w[m])))-bp)
        ans=np.array(v+p)
    assert ans.shape==(260,) and np.isfinite(ans).all()
    return ans,float(end[mask][-1])
def feature(root,row,temporal=False):
    p=root/'features'/(row['id']+'_930c.npz')
    with np.load(p) as f:ans,refend=relative(f,temporal)
    before=next(m['bytes'] for m in row['before']['marks'] if m['radio']=='930c')
    assert before>refend*FS*2,'reference not covered by pre-dispatch bytes'
    return ans,{'id':row['id'],'reference_end_seconds':refend,'before_dispatch_bytes':before}
