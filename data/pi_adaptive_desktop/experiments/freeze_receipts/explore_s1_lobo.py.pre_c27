"""EXPLORATORY (post hoc, after the frozen S1/C24 evaluation): is throttled / new-input hidden gzip separable
from silence at all, or are the frozen models just workload-specific?

Leave-one-block-out on C24 only: (i) supervised LR (same pipeline as all models) trained on silent vs any hidden
gzip; (ii) one-class z-score detector fit on the silent runs of the training blocks only.  Nothing here feeds
the frozen results; it only informs the design of a new, separately frozen confirmation batch.
"""
import json, pathlib, sys, collections
import numpy as np
from sklearn.metrics import roc_auc_score
E = pathlib.Path(r'<WORKSPACE>/ws_main\results\sp2027\experiments')
sys.path.insert(0, str(E))
import process_sp2027 as ps  # noqa: E402
OUT = pathlib.Path(r'<WORKSPACE>/ws_main\results\sp2027\stats')
d = pathlib.Path(json.loads((E / 'campaigns' / 'LATEST_s1.json').read_text(encoding='utf-8-sig'))['directory'])
rows = ps.rows_of(d)
REPS = {'call_temporal': lambda x: ps.windowed(d, x, 'call_bracket', True)[0],
        'call_whole': lambda x: ps.windowed(d, x, 'call_bracket', False)[0],
        'ref_temporal': lambda x: ps.referenced(d, x, True)[0],
        'record_temporal': lambda x: ps.load_features(d, x, True)}
y = np.array([bool(x['actual_active']) for x in rows]); blocks = np.array([x['block'] for x in rows]); cond = np.array([x['condition'] for x in rows])
res = {}
for name, f in REPS.items():
    X = np.array([f(x) for x in rows]); keep = np.std(X, axis=0) > 0; X = X[:, keep]
    sup = np.zeros(len(rows)); one = np.zeros(len(rows))
    for b in sorted(set(blocks)):
        tr = blocks != b; te = ~tr
        m = ps.model().fit(X[tr], y[tr]); sup[te] = m.predict_proba(X[te])[:, list(m.classes_).index(True)]
        s = X[tr & ~y]; mu = s.mean(0); sd = s.std(0, ddof=1) + 1e-9
        one[te] = np.mean(((X[te] - mu) / sd) ** 2, axis=1)
    r = {}
    for kind, sc in (('supervised_LR', sup), ('one_class_z2', one)):
        per = {}
        for c in sorted(set(cond) - {'silent'}):
            m = (cond == c) | (cond == 'silent')
            per[c] = {'auc_vs_silent': round(float(roc_auc_score(y[m], sc[m])), 3)}
            if kind == 'supervised_LR':
                per[c]['alerts_at_0.5'] = int(np.sum(sc[cond == c] > .5))
        fa = int(np.sum(sc[cond == 'silent'] > .5)) if kind == 'supervised_LR' else None
        r[kind] = {'per_condition': per, 'silent_alerts_at_0.5': fa, 'auc_all': round(float(roc_auc_score(y, sc)), 3)}
    res[name] = r
    print(name)
    for kind, v in r.items():
        print('  %-14s auc_all %.3f FA %s ' % (kind, v['auc_all'], v['silent_alerts_at_0.5']) + ' '.join('%s:%s' % (c, v['per_condition'][c]) for c in v['per_condition']))
OUT.mkdir(exist_ok=True)
(OUT / 'explore_s1_lobo.json').write_text(json.dumps({'campaign': d.name, 'exploratory': True, 'results': res}, indent=1), encoding='utf-8')
