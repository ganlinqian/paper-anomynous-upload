"""Confusion counts, AUCs, and exact block-level sign-flip tests for the desktop test batch."""
import itertools, json, os, sys
import numpy as np
sys.stdout.reconfigure(encoding='utf-8')
runs = sys.argv[1] if len(sys.argv) > 1 else 'runs'
res = json.load(open(os.path.join(runs, 'RESULTS_test.json'), encoding='utf-8'))
man = json.load(open(os.path.join(runs, 'test', 'manifest.json'), encoding='utf-8'))
block_of = {r['run']: r['block'] for r in man['runs']}
frz = json.load(open(os.path.join(runs, 'FREEZE.json'), encoding='utf-8'))


def auc(y, s):
    y = np.asarray(y); s = np.asarray(s)
    pos, neg = s[y == 1], s[y == 0]
    return float(np.mean([(p > n) + 0.5 * (p == n) for p in pos for n in neg]))


def signflip(d):
    d = np.asarray([x for x in d if x != 0])
    if len(d) == 0:
        return 1.0
    obs = abs(d.sum()); n = len(d)
    if n <= 20:
        cnt = sum(1 for signs in itertools.product((1, -1), repeat=n) if abs(np.dot(signs, d)) >= obs - 1e-12)
        return cnt / 2 ** n
    rng = np.random.default_rng(0)
    sims = np.abs((rng.choice((1, -1), size=(200000, n)) * d).sum(1))
    return float(np.mean(sims >= obs - 1e-12))


out = {}
for kind, f in res['fixtures'].items():
    pr = f['per_run']
    y = np.array([p['A'] for p in pr]); pp = np.array([p['p_phase'] for p in pr]); pw = np.array([p['p_whole'] for p in pr])
    dt = np.array([p['dt'] for p in pr])
    tm = frz['models'][kind]['timing']
    pt = ((np.sign(dt - tm['threshold']) * tm['sign']) > 0).astype(int)
    yhat = (pp > 0.5).astype(int)
    tp = int(np.sum((yhat == 1) & (y == 1))); fn = int(np.sum((yhat == 0) & (y == 1)))
    fp = int(np.sum((yhat == 1) & (y == 0))); tn = int(np.sum((yhat == 0) & (y == 0)))
    blocks = sorted({block_of[p['run']] for p in pr})
    cph = {b: 0 for b in blocks}; cwh = {b: 0 for b in blocks}; cti = {b: 0 for b in blocks}
    for p, a, b_, c_ in zip(pr, y, (pw > 0.5).astype(int), pt):
        b = block_of[p['run']]
        cph[b] += int((p['p_phase'] > 0.5) == a); cwh[b] += int(b_ == a); cti[b] += int(c_ == a)
    out[kind] = dict(n=len(y), TP=tp, FN=fn, FP=fp, TN=tn,
                     auc_phase=round(auc(y, pp), 3), auc_whole=round(auc(y, pw), 3),
                     auc_timing=round(auc(y, dt * tm['sign']), 3),
                     p_phase_vs_whole=signflip([cph[b] - cwh[b] for b in blocks]),
                     p_phase_vs_timing=signflip([cph[b] - cti[b] for b in blocks]),
                     n_blocks=len(blocks),
                     dt_range=[round(float(dt.min()), 4), round(float(dt.max()), 4)])
    print(kind, out[kind])
json.dump(out, open(os.path.join(runs, 'STATS_test.json'), 'w', encoding='utf-8'), indent=1)
