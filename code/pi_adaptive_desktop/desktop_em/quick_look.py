"""Preliminary look at a partial sweep: load sweep k vs. the two bracketing idle sweeps."""
import sys, os
import numpy as np
sys.stdout.reconfigure(encoding='utf-8')
d, k = sys.argv[1], int(sys.argv[2])
f = {int(n[6:8]): n for n in os.listdir(d) if n.startswith('sweep_') and n.endswith('.npy')}
P = {i: np.load(os.path.join(d, n)) for i, n in f.items()}
NF = P[k].shape[1]
keep = np.ones(NF, bool); keep[NF//2-8:NF//2+8] = False; keep[:64] = False; keep[-64:] = False
los = np.arange(10, 2510, 20) + 10
def sub(p, w=64):
    out = []
    for j in range(NF // w):
        m = keep[j*w:(j+1)*w]
        out.append(10*np.log10(np.nanmean(10**(p[:, j*w:(j+1)*w][:, m]/10), axis=1)) if m.sum() else np.full(p.shape[0], np.nan))
    return np.stack(out, 1)
S = {i: sub(v) for i, v in P.items()}
a, b = S[k-1], S[k+1]
drift = np.abs(a - b)
margin = S[k] - np.maximum(a, b) - drift
delta = S[k] - (a + b) / 2
idx = np.dstack(np.unravel_index(np.argsort(-np.nan_to_num(margin, nan=-99), axis=None), margin.shape))[0][:25]
print('median idle drift', float(np.nanmedian(drift)))
for bi, j in idx:
    print(f'lo={los[bi]:5d} MHz sub={j:2d} f~{los[bi]-10+j*1.25+0.625:8.2f} MHz delta={delta[bi,j]:+6.2f} dB margin={margin[bi,j]:+6.2f} drift={drift[bi,j]:.2f}')
bd = np.nanmean(delta, axis=1)
o = np.argsort(-bd)[:10]
print('top bands mean delta:', [(int(los[i]), round(float(bd[i]), 2)) for i in o])
