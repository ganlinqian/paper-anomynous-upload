"""E-D2 analysis: freeze models on the training batch, then evaluate the frozen models on a
new test batch that is collected only after the freeze.

  python -I desktop_analyze.py freeze   --runs runs --train train
  python -I desktop_analyze.py evaluate --runs runs --test test

Features mirror the Pi pipeline: per 10.24 ms frame, 64 band powers over |f| in [0.15, 9] MHz
and the total power; every run is referenced to its own pre-dispatch window; the call window
is delimited by the coordinator's byte marks. Phase-resolved = 4 equal call-window segments x
(64 bands + total); whole-call = per band mean/p10/p50/p90 + the same four of total power.
"""
import hashlib, json, os, sys, datetime
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')
FRAME = 204_800
HERE = os.path.dirname(os.path.abspath(__file__))


def load(runs, batch):
    man = json.load(open(os.path.join(runs, batch, 'manifest.json'), encoding='utf-8'))
    out = []
    for r in man['runs']:
        F = np.load(os.path.join(runs, batch, r['run'] + '.npy'))
        out.append((r, F))
    return man, out


def lin(db):
    return 10 ** (db / 10)


def dbmean(x, axis=0):
    return 10 * np.log10(np.nanmean(lin(x), axis=axis))


def features(r, F):
    good = ~np.all(np.isnan(F[:, :64]), axis=0)
    F = F[:, np.r_[np.where(good)[0], 64]]
    w0 = int(np.ceil(r['mark1_sample'] / FRAME)); w1 = int(np.floor(r['mark2_sample'] / FRAME))
    ref = dbmean(F[5:max(6, w0 - 1)], axis=0)
    W = F[w0:w1] - ref
    segs = np.array_split(W, 4)
    phase = np.concatenate([dbmean(s + ref, 0) - ref for s in segs])
    whole = np.concatenate([dbmean(W + ref, 0) - ref, np.nanpercentile(W, 10, 0), np.nanpercentile(W, 50, 0), np.nanpercentile(W, 90, 0)])
    timing = np.array([r['coord_dt'], (r['mark2_sample'] - r['mark1_sample']) / 20e6])
    return phase, whole, timing


def build(runs, batch, kind):
    man, data = load(runs, batch)
    rows = [(r, F) for r, F in data if r['kind'] == kind]
    P, Wh, T, y, ids, digests = [], [], [], [], [], []
    for r, F in rows:
        p, w, t = features(r, F)
        P.append(p); Wh.append(w); T.append(t); y.append(r['A']); ids.append(r['run'])
        digests.append(hashlib.sha256(np.ascontiguousarray(F).tobytes()).hexdigest()[:16])
    return np.array(P), np.array(Wh), np.array(T), np.array(y), ids, digests, rows


def fit_lr(X, y):
    from sklearn.linear_model import LogisticRegression
    mu, sd = X.mean(0), X.std(0) + 1e-9
    m = LogisticRegression(C=1.0, max_iter=5000).fit((X - mu) / sd, y)
    return dict(mu=mu.tolist(), sd=sd.tolist(), coef=m.coef_[0].tolist(), intercept=float(m.intercept_[0]))


def predict(model, X):
    z = ((X - np.array(model['mu'])) / np.array(model['sd'])) @ np.array(model['coef']) + model['intercept']
    return 1 / (1 + np.exp(-z))


def cp(k, n, a=0.05):
    from scipy.stats import beta
    lo = 0.0 if k == 0 else beta.ppf(a / 2, k, n - k + 1)
    hi = 1.0 if k == n else beta.ppf(1 - a / 2, k + 1, n - k)
    return round(float(lo), 3), round(float(hi), 3)


def cmd_freeze(runs, train):
    code = hashlib.sha256(open(__file__, 'rb').read()).hexdigest()
    frz = dict(frozen_at=datetime.datetime.now().astimezone().isoformat(), code_sha256=code, train_batch=train, models={})
    for kind in ('order', 'wait'):
        P, Wh, T, y, ids, dig, _ = build(runs, train, kind)
        frz['models'][kind] = dict(
            phase=fit_lr(P, y), whole=fit_lr(Wh, y),
            timing=dict(threshold=float(np.median(T[:, 0])), sign=int(np.sign(np.mean(T[y == 1, 0]) - np.mean(T[y == 0, 0])) or 1)),
            n_train=int(len(y)), n_pos=int(y.sum()), train_ids=ids, train_feature_digests=dig)
        acc_tr = float(np.mean((predict(frz['models'][kind]['phase'], P) > 0.5) == y))
        print(f'{kind}: n={len(y)} train acc (phase, resubstitution) = {acc_tr:.3f}')
    path = os.path.join(runs, 'FREEZE.json')
    json.dump(frz, open(path, 'w', encoding='utf-8'), indent=1)
    print('frozen ->', path, hashlib.sha256(open(path, 'rb').read()).hexdigest())


def cmd_evaluate(runs, test):
    frz = json.load(open(os.path.join(runs, 'FREEZE.json'), encoding='utf-8'))
    man = json.load(open(os.path.join(runs, test, 'manifest.json'), encoding='utf-8'))
    assert man['started'] > frz['frozen_at'], 'test batch must start after the freeze'
    res = dict(freeze_sha256=hashlib.sha256(open(os.path.join(runs, 'FREEZE.json'), 'rb').read()).hexdigest(),
               test_batch=test, test_started=man['started'], frozen_at=frz['frozen_at'], fixtures={})
    for kind in ('order', 'wait'):
        P, Wh, T, y, ids, dig, rows = build(runs, test, kind)
        M = frz['models'][kind]
        pp = predict(M['phase'], P); pw = predict(M['whole'], Wh)
        tm = M['timing']; pt = (np.sign(T[:, 0] - tm['threshold']) * tm['sign'] > 0).astype(int)
        n = len(y)
        resp_identical = len({r['response'] for r, _ in rows}) == 1
        k_phase = int(np.sum((pp > 0.5) == y)); k_whole = int(np.sum((pw > 0.5) == y)); k_time = int(np.sum(pt == y))
        res['fixtures'][kind] = dict(
            n=n, n_pos=int(y.sum()), responses_identical=resp_identical, transcript_bound=n // 2,
            phase=dict(correct=k_phase, ci95=cp(k_phase, n)), whole=dict(correct=k_whole, ci95=cp(k_whole, n)),
            timing=dict(correct=k_time, ci95=cp(k_time, n)),
            per_run=[dict(run=i, A=int(a), p_phase=round(float(p), 4), p_whole=round(float(q), 4), dt=round(float(t), 4))
                     for i, a, p, q, t in zip(ids, y, pp, pw, T[:, 0])])
        print(f"{kind}: n={n} phase {k_phase}/{n} {cp(k_phase, n)} | whole {k_whole}/{n} | timing {k_time}/{n} | transcript bound {n // 2}/{n} (responses identical={resp_identical})")
    json.dump(res, open(os.path.join(runs, f'RESULTS_{test}.json'), 'w', encoding='utf-8'), indent=1)


if __name__ == '__main__':
    cmd = sys.argv[1]
    args = dict(zip(sys.argv[2::2], sys.argv[3::2]))
    if cmd == 'freeze':
        cmd_freeze(args.get('--runs', 'runs'), args.get('--train', 'train'))
    else:
        cmd_evaluate(args.get('--runs', 'runs'), args.get('--test', 'test'))
