"""Session drift of the idle reference level (first 0.2 s of each recording, before dispatch).

Descriptive only: uses stored frame powers and the controller's thermometer readings; no model.
"""
import json, pathlib, statistics
import numpy as np
R = pathlib.Path(r'<WORKSPACE>/ws_pi\results\scenario_rf_20261104')
OUT = pathlib.Path(r'<WORKSPACE>/ws_main\results\sp2027\stats')
BATCHES = [
    ('C08', R/'confirmation_study/confirm_20261105_035739_c92be0', R/'confirmation_processing_20261105/analysis/features'),
    ('C09', R/'burst_confirmation_study/burstconfirm_20261105_043818_8bdb76', R/'confirmation_processing_20261105/analysis/features'),
    ('C10', R/'wait_confirmation_study/waitconfirm_20261105_051433_3df228', R/'confirmation_processing_20261105/analysis/features'),
    ('C13', R/'untraced_wait_study/untracedwait_20261105_061041_b80fac', R/'untraced_processing_20261105/analysis/features'),
    ('C15', R/'sustained_burst_study/sustainedburst_20261105_063509_c737ee', None),
]
def feat_dir_for(name, default):
    if default is not None:
        return default
    cands = list((R/'sustained_processing_20261105').rglob('*_930c.npz'))
    return cands[0].parent if cands else None
res = {}; allref = []; alltemp = []
for name, d, fd in BATCHES:
    fd = feat_dir_for(name, fd)
    rows = json.loads((d/'RESULTS.json').read_text(encoding='utf-8-sig'))
    rows = rows if isinstance(rows, list) else rows.get('records', [])
    utc = json.loads((d/'FREEZE.json').read_text(encoding='utf-8-sig')).get('utc')
    refs = []; temps = []
    for r in rows:
        f = fd/(r['id'] + '_930c.npz')
        if not f.exists():
            continue
        z = np.load(f); w = z['sample_counts']; end = np.cumsum(w)/20e6; m = end <= 0.2
        ref = 10*np.log10(np.average(10**(z['power_db'][m]/10), weights=w[m])); refs.append(float(ref))
        t = r.get('pre', {}).get('temperature', {}); temps.append((t.get('cpu_c'), t.get('ddr_c')))
    if not refs:
        continue
    res[name] = {'utc_freeze': utc, 'n': len(refs), 'ref_db_median': statistics.median(refs), 'ref_db_p10': float(np.percentile(refs, 10)), 'ref_db_p90': float(np.percentile(refs, 90)),
                 'cpu_c_median': statistics.median([a for a, b in temps if a is not None]), 'ddr_c_median': statistics.median([b for a, b in temps if b is not None])}
    allref += refs; alltemp += [a for a, b in temps]
meds = [v['ref_db_median'] for v in res.values()]
res['_across_batches'] = {'range_of_batch_medians_db': max(meds) - min(meds), 'pooled_p10_p90_db': [float(np.percentile(allref, 10)), float(np.percentile(allref, 90))],
                          'corr_ref_vs_cpu_temp': float(np.corrcoef(allref[:len(alltemp)], alltemp)[0, 1]) if len(alltemp) == len(allref) else None}
OUT.mkdir(parents=True, exist_ok=True); (OUT/'drift_stats.json').write_text(json.dumps(res, indent=1), encoding='utf-8')
print(json.dumps(res, indent=1))
