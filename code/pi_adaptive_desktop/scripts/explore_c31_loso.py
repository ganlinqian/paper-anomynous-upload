"""EXPLORATORY algorithm search for C31 (2026-11-10, after C30; session ws_followup).

Leave-one-session-out over the five supplement sessions C24 (s1), C27 (s1b), C28 (s1c), C29 (s1d), C30 (s1e).
Nothing here is confirmatory: every session has been seen.  The selected candidate is refit on all five sessions,
frozen, and tested prospectively on a new session (C31).

Calibration silents per session: the 8 'silent_cal' runs when present (C29, C30), else the silents of blocks 0-3
(C24, C27, C28; as train-c29/train-c30).  False alarms are counted on the other silents only (8+8+8+16+16 = 56).
Training of each fold: all runs of the other four sessions, each calibrated with its own calibration silents.

Candidates (feature representation x calibration x LR strength x threshold, plus two probability-average ensembles):
  W  call-window whole features (260; = C29 primary representation)
  T  call-window phase-resolved features (260)
  K  NEW position-invariant contrast: for sliding windows of 0.5 s and 1.0 s inside the call window, per band and total
     power, max over positions of the window mean (dB) minus the whole-call mean (dB): 2 x 65 = 130.  A contiguous
     hidden burst raises it wherever it starts; a session-wide gain change cancels.
  W+K, T+K concatenations
  cal: none | mean (subtract the mean of the session's calibration silents)
  C: 1 | 0.1 (LogisticRegression, class_weight balanced, after StandardScaler)
  thr: p50 (P > 0.5) | calmax (score above the maximum score of the held-out session's own calibration silents)

SELECTION RULE (fixed in this docstring before the first run):
  1. eligible: pooled false alarms on the 56 held-out evaluation silents <= 3 (about 5%);
  2. maximise pooled detection on held-out hidden runs with duty >= 0.125 (the range the paper claims);
  3. tie-break: pooled detection on all hidden runs, then fewer features, then C=1 before C=0.1, p50 before calmax.
Reference point = W/mean/C1/p50 (the C29 primary pipeline).
"""
import itertools, json, pathlib, sys
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
E = pathlib.Path(r'<WORKSPACE>/ws_main\results\sp2027\experiments')
sys.path.insert(0, str(E))
import process_sp2027 as ps  # noqa: E402
from execution_window_features import EMPTY  # noqa: E402
OUT = E.parent / 'stats'
STAGES = {'C24': 's1', 'C27': 's1b', 'C28': 's1c', 'C29': 's1d', 'C30': 's1e'}
DUTY = {'gzip16': 1, 'text8': 1, 'json8': 1, 'bzip2_r': 1, 'gzip8_d50': .5, 'gzip6_d37': .375, 'gzip4_d25': .25,
        'gzip3_d19': .1875, 'gzip2_d12': .125, 'gzip1_d06': .0625, 'gzip05_d03': .03125, 'gzip2_d06': .0625, 'gzip1_d03': .03125}
FS = 20_000_000

def contrast(d, x, wins=(0.5, 1.0)):
    with np.load(d / 'features' / (x['id'] + '_930c.npz')) as f:
        w = f['sample_counts'].astype(float); bands = f['band_db']; power = f['power_db']
    end = np.cumsum(w); start = end - w
    before = next(m['bytes'] for m in x['before']['marks'] if m['radio'] == '930c')
    after = next(m['bytes'] for m in x['after']['marks'] if m['radio'] == '930c')
    mask = (start * 2 >= before) & (end * 2 <= after); assert mask.sum() >= 8
    ww = w[mask]; lin = np.c_[10 ** (bands[mask] / 10), 10 ** (power[mask] / 10)] * ww[:, None]
    cw = np.r_[0, np.cumsum(ww)]; cl = np.vstack([np.zeros(lin.shape[1]), np.cumsum(lin, 0)])
    whole = 10 * np.log10(np.maximum(cl[-1] / cw[-1], 1e-20)); out = []
    for sec in wins:
        L = sec * FS; best = np.full(lin.shape[1], -np.inf)
        for i in range(len(ww)):
            j = int(np.searchsorted(cw, cw[i] + L))
            if j >= len(cw):
                break
            best = np.maximum(best, 10 * np.log10(np.maximum((cl[j] - cl[i]) / (cw[j] - cw[i]), 1e-20)))
        if not np.isfinite(best).all():          # call shorter than the window: use the whole call
            best = whole.copy()
        v = best - whole; v[EMPTY] = 0; out.append(v)
    return np.concatenate(out)

def load():
    data = {}
    for name, stage in STAGES.items():
        d = pathlib.Path(json.loads((E / 'campaigns' / ('LATEST_' + stage + '.json')).read_text(encoding='utf-8-sig'))['directory'])
        rows = ps.rows_of(d); assert all(x['valid'] for x in rows)
        cond = np.array([x['condition'] for x in rows]); block = np.array([int(x['block']) for x in rows])
        cal = cond == 'silent_cal' if (cond == 'silent_cal').any() else (cond == 'silent') & (block <= 3)
        assert cal.sum() == 8
        data[name] = {'cond': cond, 'cal': cal, 'y': np.array([bool(x['actual_active']) for x in rows]),
                      'fa_eval': (cond == 'silent') & ~cal, 'duty': np.array([DUTY.get(c, 0.0) for c in cond]),
                      'W': np.array([ps.windowed(d, x, 'call_bracket', False)[0] for x in rows]),
                      'T': np.array([ps.windowed(d, x, 'call_bracket', True)[0] for x in rows]),
                      'K': np.array([contrast(d, x) for x in rows])}
        print('loaded', name, len(rows), flush=True)
    return data

def feats(v, rep):
    return np.hstack([v[r] for r in rep.split('+')])

def fold_scores(data, rep, cal, C):
    """Held-out probabilities for every session (calibration silents included, used only for calmax)."""
    X = {n: feats(v, rep) for n, v in data.items()}
    if cal == 'mean':
        X = {n: X[n] - X[n][data[n]['cal']].mean(0) for n in X}
    keep = np.std(np.vstack(list(X.values())), axis=0) > 0
    q = {}
    for test in data:
        tr = [n for n in data if n != test]
        m = make_pipeline(StandardScaler(), LogisticRegression(C=C, max_iter=5000, class_weight='balanced', random_state=1110))
        m.fit(np.vstack([X[n][:, keep] for n in tr]), np.concatenate([data[n]['y'] for n in tr]))
        q[test] = m.predict_proba(X[test][:, keep])[:, list(m.classes_).index(True)]
    return q, int(keep.sum())

def evaluate(data, q, thr):
    per = {}; tot = dict(hi=[0, 0], all=[0, 0], fa=[0, 0])
    for n, v in data.items():
        t = 0.5 if thr == 'p50' else float(q[n][v['cal']].max())
        a = q[n] > t; hid = v['y']; hi = hid & (v['duty'] >= .125)
        s = {'hi': [int(a[hi].sum()), int(hi.sum())], 'all': [int(a[hid].sum()), int(hid.sum())], 'fa': [int(a[v['fa_eval']].sum()), int(v['fa_eval'].sum())]}
        s['by_condition'] = {c: '%d/%d' % (a[v['cond'] == c].sum(), (v['cond'] == c).sum()) for c in sorted(set(v['cond'])) if c != 'silent_cal'}
        per[n] = s
        for k in tot:
            tot[k][0] += s[k][0]; tot[k][1] += s[k][1]
    return tot, per

def main():
    data = load(); res = []
    cache = {}
    for rep, cal, C in itertools.product(['W', 'T', 'K', 'W+K', 'T+K'], ['none', 'mean'], [1.0, 0.1]):
        q, nf = fold_scores(data, rep, cal, C); cache[(rep, cal, C)] = q
        for thr in ('p50', 'calmax'):
            tot, per = evaluate(data, q, thr)
            res.append({'name': '%s/%s/C%g/%s' % (rep, cal, C, thr), 'n_features': nf, 'C': C, 'thr': thr, **tot, 'per_session': per})
    for a, b in (('W', 'T'), ('W', 'K')):
        for C in (1.0, 0.1):
            q = {n: (cache[(a, 'mean', C)][n] + cache[(b, 'mean', C)][n]) / 2 for n in data}
            for thr in ('p50', 'calmax'):
                tot, per = evaluate(data, q, thr)
                res.append({'name': 'avg(%s,%s)/mean/C%g/%s' % (a, b, C, thr), 'n_features': 520 if b == 'T' else 390, 'C': C, 'thr': thr, **tot, 'per_session': per})
    key = lambda r: (-r['hi'][0], -r['all'][0], r['n_features'], -r['C'], r['thr'] != 'p50')
    elig = sorted([r for r in res if r['fa'][0] <= 3], key=key)
    sel = elig[0] if elig else None
    OUT.mkdir(exist_ok=True)
    (OUT / 'explore_c31_loso.json').write_text(json.dumps({'exploratory': True, 'rule': 'FA<=3/56; max hidden duty>=0.125; tie: all hidden, fewer features, C=1, p50',
                                                          'selected': sel['name'] if sel else None, 'results': res}, indent=1), encoding='utf-8')
    print('%-30s %5s %9s %9s %7s' % ('candidate', 'nf', 'hi>=.125', 'all', 'FA'))
    for r in sorted(res, key=lambda r: (r['fa'][0] > 3,) + key(r)):
        print('%-30s %5d %4d/%-4d %4d/%-4d %3d/%-3d' % (r['name'], r['n_features'], *r['hi'], *r['all'], *r['fa']))
    print('SELECTED', sel['name'] if sel else None)
    if sel:
        for n, s in sel['per_session'].items():
            print('  ', n, 'hi', s['hi'], 'FA', s['fa'], s['by_condition'])

if __name__ == '__main__':
    main()
