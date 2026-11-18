"""Post-hoc sensitivity on the desktop batches (Appendix C, "Post-hoc sensitivity on the desktop").

No new data; the frozen models and their results are untouched.
(1) Learning curve: refit the phase-resolved model of desktop_analyze.py on k random training runs per
    class (k = 1, 2, 3, 4, 6, 8, 12; 200 draws each) and score the 40 D and 40 D2 runs of each family.
(2) Segment count: refit on all 24 training runs per family with S = 1..8 equal call-window segments.
D2 is scored on the physical bit A; by Proposition 2 the contract-conditioned alert has the same accuracy.

usage: python desktop_sensitivity.py [OUT.json]
       (default OUT: data/pi_adaptive_desktop/desktop_em/runs/SENSITIVITY_posthoc.json)
"""
import json, os, sys
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
ROOT = os.path.join(REPO, 'data', 'pi_adaptive_desktop', 'desktop_em', 'runs')
sys.path.insert(0, HERE)
import desktop_analyze as da  # noqa: E402


def phase_nseg(r, F, nseg):
    good = ~np.all(np.isnan(F[:, :64]), axis=0)
    F = F[:, np.r_[np.where(good)[0], 64]]
    w0 = int(np.ceil(r['mark1_sample'] / da.FRAME)); w1 = int(np.floor(r['mark2_sample'] / da.FRAME))
    ref = da.dbmean(F[5:max(6, w0 - 1)], axis=0)
    W = F[w0:w1] - ref
    segs = np.array_split(W, nseg)
    return np.concatenate([da.dbmean(s + ref, 0) - ref for s in segs])


def table(batch, kind, nseg=4):
    _, data = da.load(ROOT, batch)
    X, y = [], []
    for r, F in data:
        if r['kind'] != kind:
            continue
        if nseg == 4:
            p, _, _ = da.features(r, F)
        else:
            p = phase_nseg(r, F, nseg)
        X.append(p); y.append(int(r['A']))
    return np.array(X), np.array(y)


def correct(model, X, y):
    return int(np.sum((da.predict(model, X) > 0.5) == y))


def main(out):
    rng = np.random.default_rng(20261107)
    res = dict(note=__doc__, learning_curve={}, segments={}, check={})
    frz = json.load(open(os.path.join(ROOT, 'FREEZE.json'), encoding='utf-8'))
    for kind in ('order', 'wait'):
        Xtr, ytr = table('train', kind)
        tests = {b: table(b, kind) for b in ('test', 'd2')}
        full = da.fit_lr(Xtr, ytr)
        res['check'][kind] = {b: dict(frozen=correct(frz['models'][kind]['phase'], *tests[b]),
                                      refit=correct(full, *tests[b]), n=int(len(tests[b][1])))
                              for b in tests}
        pos, neg = np.where(ytr == 1)[0], np.where(ytr == 0)[0]
        lc = {}
        for k in (1, 2, 3, 4, 6, 8, 12):
            draws = 1 if k == 12 else 200
            cnt = {b: [] for b in tests}
            for _ in range(draws):
                idx = np.r_[rng.choice(pos, k, replace=False), rng.choice(neg, k, replace=False)]
                m = da.fit_lr(Xtr[idx], ytr[idx])
                for b in tests:
                    cnt[b].append(correct(m, *tests[b]))
            lc[k] = {b: dict(n=int(len(tests[b][1])), median=float(np.median(v)), p05=float(np.percentile(v, 5)),
                             min=int(np.min(v)), frac_perfect=float(np.mean(np.array(v) == len(tests[b][1]))),
                             draws=draws) for b, v in cnt.items()}
            print(kind, 'k=%d' % k, {b: (lc[k][b]['median'], lc[k][b]['min'], round(lc[k][b]['frac_perfect'], 3)) for b in tests})
        res['learning_curve'][kind] = lc
        seg = {}
        for S in range(1, 9):
            Xs, ys = table('train', kind, S)
            m = da.fit_lr(Xs, ys)
            seg[S] = {b: correct(m, *table(b, kind, S)) for b in tests}
            print(kind, 'segments=%d' % S, seg[S])
        res['segments'][kind] = seg
    print('check (frozen vs. refit on all training runs)', res['check'])
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(res, f, indent=1)
    print('wrote', out)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'SENSITIVITY_posthoc.json'))
