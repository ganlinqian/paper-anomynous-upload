"""EXPLORATORY reference-cadence check for the C35 pipeline (2026-11-11, written while C35 was collecting and before any
C35 result was seen; uses only C24..C34 from stats/c35_cache.npz; session ws_followup).

Question: the C35 pipeline references the last 4 earlier no-work calls; in C24..C34 every 'silent' is such a call
(2-4 per block of 7-11 calls).  How much does it degrade if the verifier issues only ONE reference call per block?
  dense   pool = calibration silents + every silent (as frozen C35)
  sparse  pool = calibration silents + the FIRST silent of each block (in time order)
For a fair comparison both are scored on the same runs: silents that are not the first of their block + bg_log
(negatives), and all hidden runs.  Features for training sessions are built with the same cadence.
Forward chaining (C30..C34, train on strictly earlier sessions); p70 and p50; self_roll4 and self_roll1 (last
1 reference instead of 4, the natural choice when references are sparse).  Descriptive only.
"""
import json, pathlib, sys
import numpy as np
sys.stdout.reconfigure(encoding='utf-8')
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, r'<WORKSPACE>/ws_pi\results\scenario_rf_20261104')
import explore_c35_fa as X  # noqa: E402
from execution_window_features import EMPTY  # noqa: E402


def feats(v, Xr, cadence, k):
    Xs = Xr - v['base']
    for j in EMPTY:
        for q in range(4):
            Xs[:, j + q * 64] = 0
    calmean = Xs[v['cal']].mean(0); cond = v['cond']; block = v['block']
    first = np.zeros(len(cond), bool)
    for b in sorted(set(block)):
        idx = np.where((cond == 'silent') & (block == b) & ~v['cal'])[0]
        if len(idx):
            first[idx[0]] = True
    pool_mask = v['pool'] if cadence == 'dense' else (v['cal'] | first)
    pool = np.where(pool_mask)[0]; out = np.empty_like(Xs)
    for i in range(len(Xs)):
        prev = pool[pool < i]
        out[i] = Xs[i] - (calmean if (v['cal'][i] or len(prev) == 0) else Xs[prev[-k:]].mean(0))
    return out, first


def main():
    data = X.load(); res = {}
    for cadence in ('dense', 'sparse'):
        for k in (4, 1):
            F = {}; firsts = {}
            for n, v in data.items():
                W, f1 = feats(v, v['Wr'].copy(), cadence, k); T, _ = feats(v, v['Tr'].copy(), cadence, k); F[n] = {'W': W, 'T': T}; firsts[n] = f1
            for rule in ('p70', 'p50'):
                tot = np.zeros(4, int); per = {}
                for t in X.FWD_TESTS:
                    q = X.fit_score(F, data, X.NAMES[:X.NAMES.index(t)], t, 'bal'); v = data[t]; a = q > X.THR[rule]
                    neg = v['neg_eval'] & ~firsts[t]
                    c = [int(a[v['hi']].sum()), int(v['hi'].sum()), int(a[neg].sum()), int(neg.sum())]; per[t] = c; tot += c
                name = '%s/self_roll%d/%s' % (cadence, k, rule); res[name] = {'total': tot.tolist(), 'per_session': per}
                print('%-24s hi %d/%d  FA %d/%d  | %s' % (name, *tot, ' '.join('%s:%d/%d' % (t, c[2], c[3]) for t, c in per.items())), flush=True)
    (X.S / 'explore_c35_cadence.json').write_text(json.dumps({'exploratory': True, 'results': res}, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
