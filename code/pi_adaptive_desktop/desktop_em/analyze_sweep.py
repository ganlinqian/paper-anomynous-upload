"""Find desktop EM bands that respond to load: compare each load sweep with the idle sweeps
that bracket it. A band (or a 64-bin sub-band) is a candidate when every load sweep of a
kind exceeds both neighbouring idle sweeps by more than the idle-to-idle drift + 1 dB.

usage: python -I analyze_sweep.py <sweep_dir>
"""
import json, os, sys
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')
d = sys.argv[1]
meta = json.load(open(os.path.join(d, 'meta.json'), encoding='utf-8'))
los = np.array(meta['los_hz']) / 1e6
sw = meta['sweeps']
P = {s['k']: np.load(os.path.join(d, f"sweep_{s['k']:02d}_{s['cond']}.npy")) for s in sw}
cond = {s['k']: s['cond'] for s in sw}
NF = 1024
# drop DC +-8 bins and 64 bins at each edge (anti-alias roll-off)
keep = np.ones(NF, bool); keep[NF // 2 - 8: NF // 2 + 8] = False; keep[:64] = False; keep[-64:] = False
SUB = 64
nsub = NF // SUB


def lin(db):
    return 10 ** (db / 10)


def subband_db(p):
    # p: (nbands, NF) dB -> (nbands, nsub) mean linear power in dB over kept bins
    out = np.full((p.shape[0], nsub), np.nan)
    for j in range(nsub):
        m = keep[j * SUB:(j + 1) * SUB]
        if m.sum() < SUB // 2:
            continue
        out[:, j] = 10 * np.log10(np.nanmean(lin(p[:, j * SUB:(j + 1) * SUB][:, m]), axis=1))
    return out


S = {k: subband_db(v) for k, v in P.items()}
ks = sorted(S)
idle = [k for k in ks if cond[k] == 'i']
res = {}
for kind in ('m', 'c'):
    loads = [k for k in ks if cond[k] == kind]
    deltas, margins = [], []
    for k in loads:
        nb = [i for i in idle if abs(i - k) == 1]
        ref = np.nanmean(np.stack([S[i] for i in nb]), axis=0)
        drift = np.abs(S[nb[0]] - S[nb[-1]]) if len(nb) > 1 else np.zeros_like(ref)
        deltas.append(S[k] - ref)
        margins.append(S[k] - np.maximum(S[nb[0]], S[nb[-1]]) - drift - 1.0)
    deltas = np.stack(deltas); margins = np.stack(margins)
    cand = np.all(margins > 0, axis=0)
    idx = np.argwhere(cand)
    rows = []
    for b, j in idx:
        f_lo = los[b] - 10 + j * SUB * 20 / NF
        rows.append(dict(band_lo_mhz=float(los[b]), sub=int(j), f_mhz=round(float(f_lo + SUB * 20 / NF / 2), 3),
                         delta_db=[round(float(x), 2) for x in deltas[:, b, j]],
                         min_margin_db=round(float(margins[:, b, j].min()), 2)))
    rows.sort(key=lambda r: -min(r['delta_db']))
    # band-level summary (whole 20 MHz)
    band_delta = np.nanmean(deltas, axis=2)  # (nload, nbands)
    order = np.argsort(-np.nanmin(band_delta, axis=0))[:15]
    res[kind] = dict(n_candidates=len(rows), top_subbands=rows[:40],
                     top_bands=[dict(lo_mhz=float(los[b]), mean_delta_db=[round(float(x), 2) for x in band_delta[:, b]]) for b in order])
# idle stability
idle_drift = [float(np.nanmedian(np.abs(S[a] - S[b]))) for a, b in zip(idle[:-1], idle[1:])]
res['idle_median_abs_drift_db'] = [round(x, 3) for x in idle_drift]
json.dump(res, open(os.path.join(d, 'analysis.json'), 'w', encoding='utf-8'), indent=1)
for kind in ('m', 'c'):
    r = res[kind]
    print(f"== {kind}: {r['n_candidates']} candidate sub-bands")
    for row in r['top_subbands'][:15]:
        print('  ', row)
    print('  top 20-MHz bands by min mean delta:', [(t['lo_mhz'], t['mean_delta_db']) for t in r['top_bands'][:8]])
print('idle drift (median |dB|):', res['idle_median_abs_drift_db'])
