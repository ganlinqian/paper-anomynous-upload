"""EXPLORATORY (post hoc, after the frozen C28 evaluation): is gzip throttled to 6.25 / 3.125% duty separable from
silence at all with our features, or did the frozen C27 model merely not learn it?

Leave-one-block-out on C28: (a) 'c28_only' trains on the other 7 C28 blocks; (b) 'pooled' additionally trains on all
C24 and C27 runs (three sessions).  Same pipeline as every model (StandardScaler + LR(C=1), balanced classes), plus a
one-class z-score detector fit on silent training runs.  Per condition: AUC against the held-out silent runs (pooled
over folds) and alerts at P > 0.5.  Nothing feeds any frozen result; it only informs the discussion.
"""
import json, pathlib, sys
import numpy as np
from sklearn.metrics import roc_auc_score
E = pathlib.Path(r'<WORKSPACE>/ws_main\results\sp2027\experiments')
sys.path.insert(0, str(E))
import process_sp2027 as ps  # noqa: E402
OUT = pathlib.Path(r'<WORKSPACE>/ws_main\results\sp2027\stats')

def campaign(stage):
    return pathlib.Path(json.loads((E / 'campaigns' / ('LATEST_' + stage + '.json')).read_text(encoding='utf-8-sig'))['directory'])

REPS = {'call_temporal': lambda d, x: ps.windowed(d, x, 'call_bracket', True)[0],
        'call_whole': lambda d, x: ps.windowed(d, x, 'call_bracket', False)[0],
        'ref_temporal': lambda d, x: ps.referenced(d, x, True)[0],
        'record_temporal': lambda d, x: ps.load_features(d, x, True)}
data = {}
for stage in ('s1', 's1b', 's1c'):
    d = campaign(stage); rows = ps.rows_of(d); data[stage] = (d, rows)
d28, r28 = data['s1c']
y28 = np.array([bool(x['actual_active']) for x in r28]); b28 = np.array([x['block'] for x in r28]); c28 = np.array([x['condition'] for x in r28])
res = {}
for name, f in REPS.items():
    X = {s: np.array([f(d, x) for x in rows]) for s, (d, rows) in data.items()}
    yo = np.concatenate([np.array([bool(x['actual_active']) for x in data[s][1]]) for s in ('s1', 's1b')])
    Xo = np.vstack([X['s1'], X['s1b']])
    keep = np.std(np.vstack([Xo, X['s1c']]), axis=0) > 0
    out = {}
    for mode in ('c28_only', 'pooled'):
        sup = np.zeros(len(r28)); one = np.zeros(len(r28))
        for b in sorted(set(b28)):
            tr = b28 != b; te = ~tr
            Xtr = X['s1c'][tr][:, keep]; ytr = y28[tr]
            if mode == 'pooled':
                Xtr = np.vstack([Xtr, Xo[:, keep]]); ytr = np.concatenate([ytr, yo])
            m = ps.model(balanced=True).fit(Xtr, ytr); sup[te] = m.predict_proba(X['s1c'][te][:, keep])[:, list(m.classes_).index(True)]
            s = Xtr[~ytr]; mu = s.mean(0); sd = s.std(0, ddof=1) + 1e-9
            one[te] = np.mean(((X['s1c'][te][:, keep] - mu) / sd) ** 2, axis=1)
        r = {}
        for kind, sc in (('supervised_LR', sup), ('one_class_z2', one)):
            per = {}
            for c in sorted(set(c28) - {'silent'}):
                m = (c28 == c) | (c28 == 'silent')
                per[c] = {'auc_vs_silent': round(float(roc_auc_score(y28[m], sc[m])), 3)}
                if kind == 'supervised_LR':
                    per[c]['alerts_at_0.5'] = int(np.sum(sc[c28 == c] > .5))
            r[kind] = {'per_condition': per, 'silent_alerts_at_0.5': int(np.sum(sc[c28 == 'silent'] > .5)) if kind == 'supervised_LR' else None}
        out[mode] = r
        print(name, mode)
        for kind, v in r.items():
            print('  %-14s FA %s ' % (kind, v['silent_alerts_at_0.5']) + ' '.join('%s:%s' % (c, '/'.join(str(z) for z in v['per_condition'][c].values())) for c in v['per_condition']))
    res[name] = out
OUT.mkdir(exist_ok=True)
(OUT / 'explore_c28_lobo.json').write_text(json.dumps({'campaign': d28.name, 'exploratory': True, 'results': res}, indent=1), encoding='utf-8')
