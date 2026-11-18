"""EXPLORATORY model selection for C29, before any C29 run: leave-one-session-out over C24, C27, C28.

Question: does per-session calibration from a few silent calls make a diverse-workload model robust to the session
drift that broke the fixed threshold between C27 and C28?  Only C28 contains duty cycles below 12.5%, so this
analysis cannot test low-duty transfer (C29 does that prospectively); it tests drift handling on the conditions that
the training sessions share with the held-out one.

Calibration runs: the silent runs of blocks 0-3 of a session (8 runs); false alarms are counted only on the silent
runs of blocks 4-7.  Methods (StandardScaler + LR(C=1, balanced), trained on all runs of the two other sessions):
  raw      features as they are; alert if P > 0.5
  sesscal  features minus the mean of the session's calibration silents (training sessions and test session alike)
  thrcal   raw model; alert if the score exceeds the maximum score of the test session's calibration silents
  both     sesscal features and the calibration-silent maximum as threshold
Representations: call_whole, call_temporal.  Nothing feeds a frozen result.
"""
import collections, json, pathlib, sys
import numpy as np
from sklearn.metrics import roc_auc_score
E = pathlib.Path(r'<WORKSPACE>/ws_main\results\sp2027\experiments')
sys.path.insert(0, str(E))
import process_sp2027 as ps  # noqa: E402
OUT = pathlib.Path(r'<WORKSPACE>/ws_main\results\sp2027\stats')
STAGES = {'C24': 's1', 'C27': 's1b', 'C28': 's1c'}
REPS = {'call_whole': False, 'call_temporal': True}

def campaign(stage):
    return pathlib.Path(json.loads((E / 'campaigns' / ('LATEST_' + stage + '.json')).read_text(encoding='utf-8-sig'))['directory'])

data = {}
for name, stage in STAGES.items():
    d = campaign(stage); rows = ps.rows_of(d)
    data[name] = {'d': d, 'rows': rows, 'y': np.array([bool(x['actual_active']) for x in rows]),
                  'cond': np.array([x['condition'] for x in rows]), 'block': np.array([int(x['block']) for x in rows])}
    data[name]['cal'] = (data[name]['cond'] == 'silent') & (data[name]['block'] <= 3)
    data[name]['fa_eval'] = (data[name]['cond'] == 'silent') & (data[name]['block'] >= 4)

res = {}
for rep, temporal in REPS.items():
    X = {n: np.array([ps.windowed(v['d'], x, 'call_bracket', temporal)[0] for x in v['rows']]) for n, v in data.items()}
    keep = np.std(np.vstack(list(X.values())), axis=0) > 0
    X = {n: v[:, keep] for n, v in X.items()}
    Xc = {n: X[n] - X[n][data[n]['cal']].mean(0) for n in X}
    out = {}
    for test in data:
        train = [n for n in data if n != test]; t = data[test]; r = {}
        for method in ('raw', 'sesscal', 'thrcal', 'both'):
            src = Xc if method in ('sesscal', 'both') else X
            m = ps.model(balanced=True).fit(np.vstack([src[n] for n in train]), np.concatenate([data[n]['y'] for n in train]))
            q = m.predict_proba(src[test])[:, list(m.classes_).index(True)]
            thr = 0.5 if method in ('raw', 'sesscal') else float(q[t['cal']].max())
            alert = q > thr
            by = {}
            for c in sorted(set(t['cond']) - {'silent'}):
                mk = t['cond'] == c; by[c] = '%d/%d' % (alert[mk].sum(), mk.sum())
            ev = t['fa_eval'] | t['y']
            r[method] = {'threshold': round(thr, 4), 'false_alarms_blocks4_7': '%d/%d' % (alert[t['fa_eval']].sum(), t['fa_eval'].sum()),
                         'auc_vs_heldout_silent': round(float(roc_auc_score(t['y'][ev], q[ev])), 3), 'by_condition': by}
        out[test] = r
        print(rep, 'held out', test)
        for method, v in r.items():
            print('   %-8s thr %-7s FA %s AUC %s  %s' % (method, v['threshold'], v['false_alarms_blocks4_7'], v['auc_vs_heldout_silent'],
                                                       ' '.join('%s:%s' % kv for kv in v['by_condition'].items())))
    res[rep] = out
OUT.mkdir(exist_ok=True)
(OUT / 'explore_c29_loso.json').write_text(json.dumps({'exploratory': True, 'calibration': 'silent runs of blocks 0-3', 'results': res}, indent=1), encoding='utf-8')
