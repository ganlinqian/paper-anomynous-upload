"""EXPLORATORY false-alarm control search for C35 (2026-11-11, after C34; session ws_followup).

Motivation (C34): the frozen C31 ensemble kept 48/48 detection (AUC 0.990) but false-alarmed on 16/40 negatives,
with more alarms in the second half of the session -> the reference (mean of 8 calibration silents at session start)
goes stale both across sessions and within a session.

Data: stats/c35_cache.npz (scripts/c35_cache.py), nine Pi sessions in time order
  C24 C27 C28 C29 (UTC 11-06) | C30 C31 C32 C33 (UTC 11-10) | C34 (UTC 11-11).
Exclusions: 'bg_download' (legal download; contract-dependent, C33) is removed from training and evaluation.
Calibration rows: 'silent_cal' if present, else silents of blocks 0-3 (as C29-C34); never evaluated.
Evaluation negatives: other 'silent' runs + 'bg_log'.  Hidden 'hi' set: actual_active, duty >= 0.125, not 'gzip1_full'
(sub-budget, C33).  Model: StandardScaler + LogisticRegression(C=0.1), class balanced ('bal') or negatives x2 ('neg2');
the score is the mean P(active) of the whole (W) and phase-resolved (T) models (C31/C32 ensemble).

Reference schemes (a deterministic per-session transformation applied identically to training and test sessions;
'reference pool' = calibration silents + silents, in time order; only STRICTLY EARLIER pool runs are used, so every
evaluated run is scored causally; calibration rows themselves always use the calibration mean):
  sess        subtract the mean of the 8 calibration silents (deployed C29-C34)
  cum         subtract the mean of all earlier pool runs (calibration + every earlier silent)
  roll4/roll2 subtract the mean of the last 4 / 2 earlier pool runs
  mix4        subtract 0.5*calibration mean + 0.5*mean of last 4 earlier pool runs
  self        subtract the run's own pre-dispatch reference (64-band mean, total power; same record, < 1.3 s earlier)
  self_sess   self, then subtract the calibration mean of the self features
  self_roll4  self, then subtract the mean of the last 4 earlier pool runs' self features
Rules: p50 (P > 0.5), p70 (P > 0.7).   32 candidates.  Reference candidate = sess/bal/p50 (frozen C31 pipeline).

Evaluations
  FWD  forward chaining (primary): test C30, C31, C32, C33, C34, each trained on all strictly earlier sessions.
  LOSO leave-one-session-out over all nine (secondary).
SELECTION RULE (fixed here before the first run):
  1. eligible: FWD hi detections >= reference FWD hi - 12  (about 5 % of 232);
  2. minimise FWD pooled false alarms on evaluation negatives;
  3. tie-break: smaller maximum per-session FWD false-alarm rate, then fewer LOSO false alarms, then more FWD hi,
     then more FWD all-hidden, then scheme order as listed, bal before neg2, p50 before p70.
Smoke check: sess/bal trained on C24 C27 C28 C29 C30 and tested on C34 must reproduce the frozen C31 result on C34
(hidden 48/48, negatives 16/40).
"""
import itertools, json, pathlib, sys
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
sys.stdout.reconfigure(encoding='utf-8')
S = pathlib.Path(r'<WORKSPACE>/ws_main\results\sp2027\stats')
NAMES = ['C24', 'C27', 'C28', 'C29', 'C30', 'C31', 'C32', 'C33', 'C34']
FWD_TESTS = ['C30', 'C31', 'C32', 'C33', 'C34']
DUTY = {'gzip16': 1, 'text8': 1, 'json8': 1, 'bzip2_r': 1, 'gzip8_d50': .5, 'gzip6_d37': .375, 'gzip4_d25': .25,
        'gzip3_d19': .1875, 'gzip2_d12': .125, 'gzip1_d06': .0625, 'gzip05_d03': .03125, 'gzip2_d06': .0625, 'gzip1_d03': .03125,
        'zstd16': 1, 'xz2': 1, 'ossl16': 1, 'sha32': 1, 'gziptxt32': 1, 'gzip1_full': 1}
SCHEMES = ['sess', 'cum', 'roll4', 'roll2', 'mix4', 'self', 'self_sess', 'self_roll4']
WTS = ['bal', 'neg2']; RULES = ['p50', 'p70']; THR = {'p50': .5, 'p70': .7}


def expand(base):
    """(n, 65) pre-dispatch reference -> (n, 260) in the W/T layout (4 x 64 bands, then 4 power values)."""
    return np.hstack([np.tile(base[:, :64], 4), np.repeat(base[:, 64:65], 4, axis=1)])


def load():
    z = np.load(S / 'c35_cache.npz'); data = {}
    for n in NAMES:
        cond = z[n + '/cond']; keep = cond != 'bg_download'
        cond = cond[keep]; block = z[n + '/block'][keep]; y = z[n + '/y'][keep]
        cal = cond == 'silent_cal' if (cond == 'silent_cal').any() else (cond == 'silent') & (block <= 3)
        assert cal.sum() == 8, n
        v = {'cond': cond, 'block': block, 'y': y, 'cal': cal,
             'neg_eval': ((cond == 'silent') & ~cal) | (cond == 'bg_log'),
             'hi': y & (np.array([DUTY[c] if c in DUTY else 0.0 for c in cond]) >= .125) & (cond != 'gzip1_full'),
             'pool': (cond == 'silent') | (cond == 'silent_cal'),
             'Wr': z[n + '/W'][keep], 'Tr': z[n + '/T'][keep], 'base': expand(z[n + '/base'][keep])}
        data[n] = v
    return data


def transform(v, X, scheme):
    from execution_window_features import EMPTY  # noqa
    if scheme.startswith('self'):
        X = X - v['base']
        for j in EMPTY:
            for k in range(4):
                X[:, j + k * 64] = 0
        scheme = {'self': 'none', 'self_sess': 'sess', 'self_roll4': 'roll4'}[scheme]
    if scheme == 'none':
        return X
    calmean = X[v['cal']].mean(0); out = np.empty_like(X); pool = np.where(v['pool'])[0]
    for i in range(len(X)):
        prev = pool[pool < i]
        if v['cal'][i] or scheme == 'sess' or len(prev) == 0:
            ref = calmean
        elif scheme == 'cum':
            ref = X[prev].mean(0)
        elif scheme in ('roll4', 'roll2'):
            ref = X[prev[-int(scheme[-1]):]].mean(0)
        elif scheme == 'mix4':
            ref = .5 * calmean + .5 * X[prev[-4:]].mean(0)
        else:
            raise ValueError(scheme)
        out[i] = X[i] - ref
    return out


def fit_score(feats, data, train, test, wt):
    q = np.zeros(len(data[test]['y']))
    for p in ('W', 'T'):
        X = np.vstack([feats[n][p] for n in train]); y = np.concatenate([data[n]['y'] for n in train])
        sw = np.where(y, len(y) / (2 * y.sum()), len(y) / (2 * (~y).sum()))
        if wt == 'neg2':
            sw = np.where(y, sw, 2 * sw)
        m = make_pipeline(StandardScaler(), LogisticRegression(C=0.1, max_iter=5000, random_state=1111))
        m.fit(X, y, logisticregression__sample_weight=sw)
        q += m.predict_proba(feats[test][p])[:, 1] / 2
    return q


def counts(v, a):
    return {'hi': [int(a[v['hi']].sum()), int(v['hi'].sum())], 'all': [int(a[v['y']].sum()), int(v['y'].sum())],
            'fa': [int(a[v['neg_eval']].sum()), int(v['neg_eval'].sum())]}


def main():
    sys.path.insert(0, r'<WORKSPACE>/ws_pi\results\scenario_rf_20261104')
    data = load(); scores = {}
    for scheme in SCHEMES:
        feats = {n: {'W': transform(v, v['Wr'].copy(), scheme), 'T': transform(v, v['Tr'].copy(), scheme)} for n, v in data.items()}
        for wt in WTS:
            if scheme == 'sess' and wt == 'bal':
                q = fit_score(feats, data, ['C24', 'C27', 'C28', 'C29', 'C30'], 'C34', wt); v = data['C34']; a = q > .5
                smoke = counts(v, a); print('SMOKE C31-equivalent on C34:', smoke, flush=True)
            fwd = {t: fit_score(feats, data, NAMES[:NAMES.index(t)], t, wt) for t in FWD_TESTS}
            loso = {t: fit_score(feats, data, [n for n in NAMES if n != t], t, wt) for t in NAMES}
            scores[(scheme, wt)] = (fwd, loso); print('scored', scheme, wt, flush=True)
    res = []
    for scheme, wt, rule in itertools.product(SCHEMES, WTS, RULES):
        fwd, loso = scores[(scheme, wt)]; r = {'name': '%s/%s/%s' % (scheme, wt, rule), 'scheme': scheme, 'wt': wt, 'rule': rule}
        for tag, sc in (('fwd', fwd), ('loso', loso)):
            tot = {'hi': [0, 0], 'all': [0, 0], 'fa': [0, 0]}; per = {}
            for t, q in sc.items():
                v = data[t]; a = q > THR[rule]; c = counts(v, a)
                negb = v['neg_eval']; c['fa_by_block'] = {int(b): '%d/%d' % (a[negb & (v['block'] == b)].sum(), (negb & (v['block'] == b)).sum()) for b in sorted(set(v['block'][negb]))}
                c['by_condition'] = {str(k): '%d/%d' % (a[v['cond'] == k].sum(), (v['cond'] == k).sum()) for k in sorted(set(v['cond'])) if k != 'silent_cal'}
                c['neg_scores'] = [round(float(x), 3) for x in q[negb]]
                per[t] = c
                for k in tot:
                    tot[k][0] += c[k][0]; tot[k][1] += c[k][1]
            r[tag] = tot; r[tag + '_per'] = per
        r['fwd_max_fa_rate'] = max(p['fa'][0] / p['fa'][1] for p in r['fwd_per'].values())
        res.append(r)
    ref = next(r for r in res if r['name'] == 'sess/bal/p50')
    key = lambda r: (r['fwd']['fa'][0], r['fwd_max_fa_rate'], r['loso']['fa'][0], -r['fwd']['hi'][0], -r['fwd']['all'][0],
                     SCHEMES.index(r['scheme']), WTS.index(r['wt']), RULES.index(r['rule']))
    elig = sorted([r for r in res if r['fwd']['hi'][0] >= ref['fwd']['hi'][0] - 12], key=key); sel = elig[0]
    (S / 'explore_c35_fa.json').write_text(json.dumps({'exploratory': True, 'smoke_c34': smoke, 'reference': ref['name'], 'selected': sel['name'],
                                                      'rule': 'FWD hi >= ref-12; min FWD FA; tie max session FA rate, LOSO FA, hi, all, order', 'results': res}, indent=1), encoding='utf-8')
    print('%-22s %10s %10s %9s %6s | %10s %9s' % ('candidate', 'FWD hi', 'FWD all', 'FWD FA', 'maxFA', 'LOSO hi', 'LOSO FA'))
    for r in sorted(res, key=key):
        print('%-22s %4d/%-5d %4d/%-5d %3d/%-5d %5.2f | %4d/%-5d %3d/%-4d %s' % (r['name'], *r['fwd']['hi'], *r['fwd']['all'], *r['fwd']['fa'], r['fwd_max_fa_rate'],
                                                                       *r['loso']['hi'], *r['loso']['fa'], '' if r['fwd']['hi'][0] >= ref['fwd']['hi'][0] - 12 else 'x'))
    for r in (ref, sel):
        print('==', r['name'])
        for t, p in r['fwd_per'].items():
            print('   FWD', t, 'hi', p['hi'], 'FA', p['fa'], 'blocks', p['fa_by_block'])
    print('REFERENCE', ref['name'], 'SELECTED', sel['name'])


if __name__ == '__main__':
    main()
