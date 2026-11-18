"""EXPLORATORY (post hoc, after the C28 primary analysis): score distributions of the frozen diverse models on C27/C28.

For each frozen representation, per condition: median P(active), and AUC of the score against the same batch's silent
runs (threshold-free separability).  Also an exploratory multi-call aggregation: if an adversary hides the same work
in every call, the mean score over k calls is compared with the mean over k silent calls (exact enumeration over
k-subsets is too large, so a fixed-seed resampling with 20000 draws per k is used; threshold = 95th percentile of
silent k-means, i.e. 5% false alarms per k-call window).  Nothing is refit; labelled exploratory everywhere.
"""
import collections, csv, json, pathlib, random
import numpy as np
from sklearn.metrics import roc_auc_score
E = pathlib.Path(r'<WORKSPACE>/ws_main\results\sp2027\experiments')
OUT = pathlib.Path(r'<WORKSPACE>/ws_main\results\sp2027\stats')

def campaign(stage):
    return pathlib.Path(json.loads((E / 'campaigns' / ('LATEST_' + stage + '.json')).read_text(encoding='utf-8-sig'))['directory'])

def scores(d):
    by = collections.defaultdict(lambda: collections.defaultdict(list))
    with (d / 'predictions_diverse.csv').open(encoding='utf-8') as f:
        for r in csv.DictReader(f):
            by[r['detector']][r['condition']].append(float(r['score']))
    return by

out = {'note': 'exploratory, post hoc; frozen C27 diverse models; no refit', 'batches': {}}
for stage, name in (('s1b', 'C27'), ('s1c', 'C28')):
    by = scores(campaign(stage)); res = {}
    for det, cc in by.items():
        sil = cc['silent']; r = {}
        for c, v in cc.items():
            row = {'n': len(v), 'median': round(float(np.median(v)), 3), 'min': round(min(v), 3), 'max': round(max(v), 3)}
            if c != 'silent':
                row['auc_vs_silent'] = round(float(roc_auc_score([0] * len(sil) + [1] * len(v), sil + v)), 3)
            r[c] = row
        res[det] = r
    out['batches'][name] = res

# multi-call aggregation for the primary representation, C28, silent pooled over C27 + C28 for the threshold
rng = random.Random(20261106)
p27 = scores(campaign('s1b'))['C27_diverse/call_temporal']; p28 = scores(campaign('s1c'))['C27_diverse/call_temporal']
sil = p27['silent'] + p28['silent']; agg = {}
for k in (1, 2, 4, 8):
    sk = sorted(np.mean([rng.choice(sil) for _ in range(k)]) for _ in range(20000)); thr = sk[int(0.95 * len(sk))]
    row = {'threshold_mean_score': round(float(thr), 4)}
    for c in ('gzip3_d19', 'gzip2_d12', 'gzip1_d06', 'gzip05_d03', 'gzip2_d06', 'gzip1_d03'):
        v = p28[c]; hits = sum(np.mean([rng.choice(v) for _ in range(k)]) > thr for _ in range(20000))
        row[c] = round(hits / 20000, 3)
    agg[k] = row
out['aggregation_primary_c28'] = {'method': 'resampled mean of k call scores vs 95th percentile of resampled mean of k silent scores (32 silent runs, C27+C28)',
                                  'by_k': agg}
OUT.mkdir(exist_ok=True); (OUT / 'explore_c28_scores.json').write_text(json.dumps(out, indent=1), encoding='utf-8')
for name, res in out['batches'].items():
    for det, r in res.items():
        print(name, det.split('/')[-1], ' '.join('%s:%s/%s' % (c, v['median'], v.get('auc_vs_silent', '-')) for c, v in sorted(r.items())))
for k, row in agg.items():
    print('k=%d' % k, row)
