"""Verify the Sec. 6 claim 'a hidden gzip moves total power by only about 0.03 dB but shifts the
spectral shape by about 0.2 dB in several bands' on C13 (untraced wait, 16 gzip16 + 16 silent runs).
Inputs: per-frame power_db / band_db (10.24 ms frames computed from the raw 930c IQ, 1.8 GHz receiver)
and coordinator byte marks from RESULTS.json.  Usage: python3 -I verify_gzip_db.py <validation_dir> <out.json>"""
import json
import sys
from pathlib import Path
import numpy as np

FRAME = 204800          # samples per frame
D = Path(sys.argv[1])
rows = json.load(open(D / 'RESULTS.json'))
out = {'runs': []}
tot_call, tot_ref, band_call, band_ref, act = [], [], [], [], []
for r in rows:
    f = D / 'features' / (r['id'] + '_930c.npz')
    z = np.load(f)
    m0 = [m for m in r['before']['marks'] if m['radio'] == '930c'][0]['bytes'] // 2
    m1 = [m for m in r['after']['marks'] if m['radio'] == '930c'][0]['bytes'] // 2
    f0 = -(-m0 // FRAME)            # first complete frame after b0
    f1 = m1 // FRAME                # frames strictly before b1
    pre1 = m0 // FRAME              # frames ending before b0
    pre0 = max(5, pre1 - 20)        # 0.2 s reference, skip 5 start-up frames
    lin = 10 ** (z['power_db'] / 10)
    blin = 10 ** (z['band_db'] / 10)
    valid = [k for k in range(64) if np.isfinite(z['band_db'][:, k]).all() and z['band_db'][:, k].std() > 0]
    tc = 10 * np.log10(lin[f0:f1].mean()); tr = 10 * np.log10(lin[pre0:pre1].mean())
    bc = 10 * np.log10(blin[f0:f1].mean(0)); br = 10 * np.log10(blin[pre0:pre1].mean(0))
    tot_call.append(tc); tot_ref.append(tr); band_call.append(bc); band_ref.append(br); act.append(bool(r['actual_active']))
    out['runs'].append({'id': r['id'], 'active': bool(r['actual_active']), 'block': r['block'], 'frames_call': int(f1 - f0),
                        'total_call_db': tc, 'total_minus_ref_db': tc - tr})
act = np.array(act); tc = np.array(tot_call); tr = np.array(tot_ref); bc = np.array(band_call); br = np.array(band_ref)
valid = [k for k in range(64) if np.isfinite(bc[:, k]).all() and np.isfinite(br[:, k]).all() and k not in (0, 58, 59, 60, 61, 62, 63)]
d_tot_abs = tc[act].mean() - tc[~act].mean()
d_tot_ref = (tc - tr)[act].mean() - (tc - tr)[~act].mean()
# spectral shape: band level relative to the run's own total power, referenced to the pre-dispatch window
shape = (bc - tc[:, None]) - (br - tr[:, None])
d_shape = shape[act].mean(0) - shape[~act].mean(0)
d_band_ref = ((bc - br)[act].mean(0) - (bc - br)[~act].mean(0))
sv = np.abs(d_shape[valid])
order = np.argsort(-sv)
# per-band consistency: fraction of active runs whose shape value lies beyond the silent median, in the effect's direction
cons = {}
for j in order[:8]:
    k = valid[j]
    med = np.median(shape[~act, k]); sgn = np.sign(d_shape[k])
    cons[int(k)] = float(np.mean(sgn * (shape[act, k] - med) > 0))
def med_iqr(x):
    return [float(np.median(x)), float(np.percentile(x, 25)), float(np.percentile(x, 75))]
out.update({
    'n_active': int(act.sum()), 'n_silent': int((~act).sum()), 'n_valid_bands': len(valid),
    'total_power_diff_db_call_window_mean': float(d_tot_abs),
    'total_power_diff_db_vs_pre_reference_mean': float(d_tot_ref),
    'total_minus_ref_active_median_iqr': med_iqr((tc - tr)[act]), 'total_minus_ref_silent_median_iqr': med_iqr((tc - tr)[~act]),
    'shape_diff_db_abs_top8': {int(valid[j]): float(d_shape[valid[j]]) for j in order[:8]},
    'shape_consistency_top8': cons,
    'n_bands_shape_abs_ge_0.15': int((sv >= 0.15).sum()), 'n_bands_shape_abs_ge_0.2': int((sv >= 0.2).sum()),
    'shape_abs_median_all_bands': float(np.median(sv)),
    'band_minus_ref_diff_db_top8': {int(valid[j]): float(d_band_ref[valid[j]]) for j in np.argsort(-np.abs(d_band_ref[valid]))[:8]},
})
json.dump(out, open(sys.argv[2], 'w'), indent=1)
print(json.dumps({k: v for k, v in out.items() if k != 'runs'}, indent=1))
