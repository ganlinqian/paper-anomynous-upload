"""Windowed diagnostic features from existing contiguous frame arrays."""
import numpy as np
FS=20_000_000
NFFT=1024
freq=np.abs(np.fft.fftfreq(NFFT,1/FS))
groups=np.minimum((freq/1e7*64).astype(int),63)
valid=(freq>.15e6)&(freq<9e6)
EMPTY=[j for j in range(64) if not np.any(valid&(groups==j))]
def feature(root,row,window,temporal=False):
    with np.load(root/'features'/(row['id']+'_930c.npz')) as f:
        w=f['sample_counts'].copy();bands=f['band_db'].copy();power=f['power_db'].copy()
    end=np.cumsum(w);start=end-w
    before=next(m['bytes'] for m in row['before']['marks'] if m['radio']=='930c')
    after=next(m['bytes'] for m in row['after']['marks'] if m['radio']=='930c')
    if window=='prefix_0p2':
        mask=end<=.2*FS
        assert end[mask][-1]*2<before
    elif window=='call_bracket':
        mask=(start*2>=before)&(end*2<=after)
    else: raise ValueError(window)
    assert mask.sum()>=8,'too few complete frames; retain failure without choosing a new window'
    ww=w[mask];bb=bands[mask];pp=power[mask]
    if not temporal:
        mean=10*np.log10(np.maximum(np.average(10**(bb/10),axis=0,weights=ww),1e-20))
        bp=10*np.log10(np.maximum(np.average(10**(pp/10),weights=ww),1e-20))
        ans=np.r_[mean,np.quantile(bb,[.1,.5,.9],axis=0).ravel(),bp,np.quantile(pp,[.1,.5,.9])]
    else:
        center=(np.cumsum(ww)-ww/2)/ww.sum();v=[];pw=[]
        for k in range(4):
            m=(center>=k/4)&(center<(k+1)/4)
            assert m.any()
            v.extend((10*np.log10(np.maximum(np.average(10**(bb[m]/10),axis=0,weights=ww[m]),1e-20))).tolist())
            pw.append(float(10*np.log10(np.maximum(np.average(10**(pp[m]/10),weights=ww[m]),1e-20))))
        ans=np.array(v+pw)
    for j in EMPTY:
        for k in range(4):ans[j+k*64]=0
    assert ans.shape==(260,) and np.isfinite(ans).all()
    return ans,{'id':row['id'],'window':window,'frames':int(mask.sum()),'samples':int(ww.sum()),'frame_start_bytes':int(start[mask][0]*2),'frame_end_bytes':int(end[mask][-1]*2),'before_dispatch_bytes':before,'after_return_bytes':after}
