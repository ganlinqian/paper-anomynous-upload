"""Median per-quarter band-average change (dB re. pre-dispatch) by condition, for the paper text."""
import json, os, sys
import numpy as np
sys.stdout.reconfigure(encoding='utf-8')
root, batch = sys.argv[1], sys.argv[2]
m = json.load(open(os.path.join(root, batch, 'manifest.json'), encoding='utf-8'))
acc = {}
for r in m['runs']:
    F = np.load(os.path.join(root, batch, r['run'] + '.npy'))
    w0 = r['mark1_sample'] // 204800 + 1; w1 = r['mark2_sample'] // 204800
    good = ~np.all(np.isnan(F[:, :64]), 0)
    B = 10 * np.log10(np.nanmean(10 ** (F[:, :64][:, good] / 10), 1))
    ref = np.median(B[5:w0 - 1])
    q = [float(s.mean()) for s in np.array_split(B[w0:w1] - ref, 4)]
    acc.setdefault((r['kind'], r['variant']), []).append(q)
out = {}
for k, v in acc.items():
    a = np.array(v)
    out[f'{k[0]}/{k[1]}'] = dict(n=len(a), median=[round(float(x), 2) for x in np.median(a, 0)],
                                 iqr=[[round(float(x), 2) for x in np.percentile(a, 25, 0)], [round(float(x), 2) for x in np.percentile(a, 75, 0)]])
    print(k, out[f'{k[0]}/{k[1]}'])
json.dump(out, open(os.path.join(root, f'QUARTERS_{batch}.json'), 'w', encoding='utf-8'), indent=1)
