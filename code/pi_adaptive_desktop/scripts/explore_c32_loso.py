"""EXPLORATORY false-alarm control search for C32 (2026-11-10, after C31; session ws_followup).

Leave-one-session-out over six sessions C24 (s1), C27 (s1b), C28 (s1c), C29 (s1d), C30 (s1e), C31 (s1f).
Every session has been seen; the selected candidate is refit on all six, frozen, and tested prospectively (C32).
Calibration silents per session as before ('silent_cal' if present, else silents of blocks 0-3); false alarms are
counted on the other silents (8+8+8+16+16+16 = 72).  Features are always calibrated by subtracting the mean of the
session's calibration silents (as C29-C31).

Candidate grid:
  rep     W (call-window whole), T (phase-resolved), A = average of P(active) of W and T (= C31 pipeline)
  C       0.1 | 0.03                       (LogisticRegression after StandardScaler)
  weight  bal (class-balanced) | neg2 (class-balanced, negatives x2)
  rule    p50      P > 0.5                                         (C31 rule)
          p70      P > 0.7
          calz3    logit standardised by the session's 8 calibration-silent logits: (l - mean) / max(sd, 0.5) > 3
          offN     l - mean(calibration-silent logits) > tau, tau = 95th percentile of the same offset on the
                   evaluation silents of an inner leave-one-session-out over the training sessions (nested)
          pN       P > max(0.5, tau), tau = 95th percentile of inner out-of-fold P on evaluation silents (nested)
Reference = A/C0.1/bal/p50 (frozen C31 pipeline).

SELECTION RULE (fixed here before the first run):
  1. eligible: pooled detection of held-out hidden runs with duty >= 0.125 >= reference - 10 (about 5% of 216);
  2. minimise pooled false alarms on the 72 evaluation silents;
  3. tie-break: smaller maximum per-session false-alarm rate, then more detections (duty >= 0.125), then more
     detections (all hidden), then rep A before W before T, C 0.1 before 0.03, bal before neg2,
     rule order p50, p70, calz3, offN, pN.
"""
import itertools, json, pathlib, sys
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
E = pathlib.Path(r'<WORKSPACE>/ws_main\results\sp2027\experiments')
sys.path.insert(0, str(E))
import process_sp2027 as ps  # noqa: E402
OUT = E.parent / 'stats'
STAGES = {'C24': 's1', 'C27': 's1b', 'C28': 's1c', 'C29': 's1d', 'C30': 's1e', 'C31': 's1f'}
DUTY = {'gzip16': 1, 'text8': 1, 'json8': 1, 'bzip2_r': 1, 'gzip8_d50': .5, 'gzip6_d37': .375, 'gzip4_d25': .25,
        'gzip3_d19': .1875, 'gzip2_d12': .125, 'gzip1_d06': .0625, 'gzip05_d03': .03125, 'gzip2_d06': .0625, 'gzip1_d03': .03125}
REPS = ['A', 'W', 'T']; CS = [0.1, 0.03]; WTS = ['bal', 'neg2']; RULES = ['p50', 'p70', 'calz3', 'offN', 'pN']

def load():
    data = {}
    for name, stage in STAGES.items():
        d = pathlib.Path(json.loads((E / 'campaigns' / ('LATEST_' + stage + '.json')).read_text(encoding='utf-8-sig'))['directory'])
        rows = ps.rows_of(d); assert all(x['valid'] for x in rows)
        cond = np.array([x['condition'] for x in rows]); block = np.array([int(x['block']) for x in rows])
        cal = cond == 'silent_cal' if (cond == 'silent_cal').any() else (cond == 'silent') & (block <= 3)
        assert cal.sum() == 8
        v = {'cond': cond, 'cal': cal, 'y': np.array([bool(x['actual_active']) for x in rows]),
             'fa_eval': (cond == 'silent') & ~cal, 'duty': np.array([DUTY.get(c, 0.0) for c in cond])}
        for part, temporal in (('W', False), ('T', True)):
            X = np.array([ps.windowed(d, x, 'call_bracket', temporal)[0] for x in rows]); v[part] = X - X[cal].mean(0)
        data[name] = v; print('loaded', name, len(rows), flush=True)
    return data

def fit_predict(data, train, test, part, C, wt):
    X = np.vstack([data[n][part] for n in train]); y = np.concatenate([data[n]['y'] for n in train])
    sw = np.where(y, len(y) / (2 * y.sum()), len(y) / (2 * (~y).sum()))
    if wt == 'neg2':
        sw = np.where(y, sw, 2 * sw)
    m = make_pipeline(StandardScaler(), LogisticRegression(C=C, max_iter=5000, random_state=1110))
    m.fit(X, y, logisticregression__sample_weight=sw)
    return {n: m.predict_proba(data[n][part])[:, 1] for n in test}

def logit(p):
    p = np.clip(p, 1e-9, 1 - 1e-9); return np.log(p / (1 - p))

def part_scores(data, part, C, wt):
    """outer[test] = P on the held-out session; inner[test][i] = P on inner held-out i (training sessions only)."""
    names = list(data); outer = {}; inner = {}
    for test in names:
        tr = [n for n in names if n != test]
        outer[test] = fit_predict(data, tr, [test], part, C, wt)[test]
        inner[test] = {i: fit_predict(data, [n for n in tr if n != i], [i], part, C, wt)[i] for i in tr}
    return outer, inner

def decide(rule, v, q, inner_q, data):
    l = logit(q); lc = l[v['cal']]
    if rule == 'p50':
        return q > .5
    if rule == 'p70':
        return q > .7
    if rule == 'calz3':
        return (l - lc.mean()) / max(lc.std(ddof=1), .5) > 3
    if rule == 'offN':
        off = np.concatenate([logit(qi)[data[i]['fa_eval']] - logit(qi)[data[i]['cal']].mean() for i, qi in inner_q.items()])
        return l - lc.mean() > np.quantile(off, .95)
    if rule == 'pN':
        tau = max(.5, float(np.quantile(np.concatenate([qi[data[i]['fa_eval']] for i, qi in inner_q.items()]), .95)))
        return q > tau
    raise ValueError(rule)

def main():
    data = load(); parts = {}
    for part, C, wt in itertools.product(['W', 'T'], CS, WTS):
        parts[(part, C, wt)] = part_scores(data, part, C, wt); print('scored', part, C, wt, flush=True)
    res = []
    for rep, C, wt in itertools.product(REPS, CS, WTS):
        if rep == 'A':
            (ow, iw), (ot, it) = parts[('W', C, wt)], parts[('T', C, wt)]
            outer = {n: (ow[n] + ot[n]) / 2 for n in data}; inner = {n: {i: (iw[n][i] + it[n][i]) / 2 for i in iw[n]} for n in data}
        else:
            outer, inner = parts[(rep, C, wt)]
        for rule in RULES:
            tot = dict(hi=[0, 0], all=[0, 0], fa=[0, 0]); per = {}
            for n, v in data.items():
                a = decide(rule, v, outer[n], inner[n], data); hid = v['y']; hi = hid & (v['duty'] >= .125)
                s = {'hi': [int(a[hi].sum()), int(hi.sum())], 'all': [int(a[hid].sum()), int(hid.sum())], 'fa': [int(a[v['fa_eval']].sum()), int(v['fa_eval'].sum())]}
                s['by_condition'] = {str(c): '%d/%d' % (a[v['cond'] == c].sum(), (v['cond'] == c).sum()) for c in sorted(set(v['cond'])) if c != 'silent_cal'}
                per[n] = s
                for k in tot:
                    tot[k][0] += s[k][0]; tot[k][1] += s[k][1]
            res.append({'name': '%s/C%g/%s/%s' % (rep, C, wt, rule), 'rep': rep, 'C': C, 'wt': wt, 'rule': rule, **tot,
                        'max_session_fa_rate': max(s['fa'][0] / s['fa'][1] for s in per.values()), 'per_session': per})
    ref = next(r for r in res if r['name'] == 'A/C0.1/bal/p50')
    key = lambda r: (r['fa'][0], r['max_session_fa_rate'], -r['hi'][0], -r['all'][0], REPS.index(r['rep']), -r['C'], WTS.index(r['wt']), RULES.index(r['rule']))
    elig = sorted([r for r in res if r['hi'][0] >= ref['hi'][0] - 10], key=key); sel = elig[0]
    OUT.mkdir(exist_ok=True)
    (OUT / 'explore_c32_loso.json').write_text(json.dumps({'exploratory': True, 'reference': ref['name'], 'rule': 'hi >= ref-10; min FA; tie max session FA rate, hi, all, A<W<T, C0.1, bal, rule order',
                                                          'selected': sel['name'], 'results': res}, indent=1), encoding='utf-8')
    print('%-26s %9s %9s %7s %6s' % ('candidate', 'hi>=.125', 'all', 'FA/72', 'maxFA'))
    for r in sorted(res, key=key):
        print('%-26s %4d/%-4d %4d/%-4d %3d/%-3d %5.2f %s' % (r['name'], *r['hi'], *r['all'], *r['fa'], r['max_session_fa_rate'], '' if r['hi'][0] >= ref['hi'][0] - 10 else 'x'))
    print('REFERENCE', ref['name'], ref['hi'], ref['all'], ref['fa']); print('SELECTED', sel['name'])
    for n, s in sel['per_session'].items():
        print('  ', n, 'hi', s['hi'], 'FA', s['fa'], s['by_condition'])

if __name__ == '__main__':
    main()
