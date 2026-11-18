"""Recompute paper statistics from the frozen per-trial prediction files.

Reads only the stored prediction CSVs produced by the frozen-model evaluations of
session ws_pi; no model is refit and no threshold is changed.  Adds exact
Clopper-Pearson intervals, threshold-free AUCs and block-level summaries.
"""
import csv, json, math, pathlib, collections, sys

A = pathlib.Path(r'<WORKSPACE>/ws_pi\results\scenario_rf_20261104\analysis_extensions')
OUT = pathlib.Path(r'<WORKSPACE>/ws_main\results\sp2027\stats')
OUT.mkdir(parents=True, exist_ok=True)
FILES = {
    'C08_order': A/'early_confirm_20261105/reports/EARLY_CONFIRMATION_ORDER_a27de29479e9/all_predictions.csv',
    'C08_order_window': A/'window_diagnostic_20261105/reports/WINDOW_DIAGNOSTIC_CONFIRMATION_ORDER_b0cc46caada2/all_predictions.csv',
    'C08_activity': A/'early_confirm_20261105/reports/EARLY_CONFIRMATION_TRACE_103f4acc7876/all_predictions.csv',
    'C08_activity_window': A/'window_diagnostic_20261105/reports/WINDOW_DIAGNOSTIC_CONFIRMATION_TRACE_cba94ae5b39e/all_predictions.csv',
    'C09_burst': A/'early_burst_wait_20261105/burst_report_10ca91c73d54/all_predictions.csv',
    'C10_wait': A/'early_burst_wait_20261105/wait_report_5031308add33/all_predictions.csv',
    'C13_untraced': A/'untraced_wait_report_20261105/predictions.csv',
    'C15_sustained': A/'sustained_burst_report_20261105/predictions.csv',
}

def b(x):
    return str(x).strip().lower() == 'true'

def betainc_inv(a, bb, p):
    # inverse regularized incomplete beta by bisection on a continued-fraction betainc
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if betainc(a, bb, mid) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2

def betacf(a, bb, x):
    MAXIT, EPS, FPMIN = 400, 3e-14, 1e-300
    qab, qap, qam = a + bb, a + 1, a - 1
    c, d = 1.0, 1 - qab * x / qap
    d = 1 / (d if abs(d) > FPMIN else FPMIN)
    h = d
    for m in range(1, MAXIT + 1):
        m2 = 2 * m
        aa = m * (bb - m) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d; d = 1 / (d if abs(d) > FPMIN else FPMIN)
        c = 1 + aa / c; c = c if abs(c) > FPMIN else FPMIN
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d; d = 1 / (d if abs(d) > FPMIN else FPMIN)
        c = 1 + aa / c; c = c if abs(c) > FPMIN else FPMIN
        de = d * c; h *= de
        if abs(de - 1) < EPS:
            break
    return h

def betainc(a, bb, x):
    if x <= 0: return 0.0
    if x >= 1: return 1.0
    lbt = math.lgamma(a + bb) - math.lgamma(a) - math.lgamma(bb) + a * math.log(x) + bb * math.log(1 - x)
    bt = math.exp(lbt)
    if x < (a + 1) / (a + bb + 2):
        return bt * betacf(a, bb, x) / a
    return 1 - bt * betacf(bb, a, 1 - x) / bb

def cp(k, n, alpha=0.05):
    lo = 0.0 if k == 0 else betainc_inv(k, n - k + 1, alpha / 2)
    hi = 1.0 if k == n else betainc_inv(k + 1, n - k, 1 - alpha / 2)
    return lo, hi

def auc(pos, neg):
    if not pos or not neg:
        return None
    s = 0.0
    for p in pos:
        for q in neg:
            s += 1.0 if p > q else (0.5 if p == q else 0.0)
    return s / (len(pos) * len(neg))

def vscore(r):
    if r.get('task_conditioned_score') not in (None, ''):
        return float(r['task_conditioned_score'])
    if r.get('conditioned_score') not in (None, ''):
        return float(r['conditioned_score'])
    # C20 transfer rows: 'score' is the contract-conditioned violation score, 'p_target' is P(actual)
    if r.get('score') not in (None, ''):
        return float(r['score'])
    if r.get('p_actual') not in (None, ''):
        pa = float(r['p_actual'])
        return pa if not b(r['expected']) else 1 - pa
    return None

def summarize(rows):
    tp = sum(b(r['violation']) and b(r['alert']) for r in rows)
    fn = sum(b(r['violation']) and not b(r['alert']) for r in rows)
    fp = sum((not b(r['violation'])) and b(r['alert']) for r in rows)
    tn = sum((not b(r['violation'])) and not b(r['alert']) for r in rows)
    n = len(rows); k = tp + tn
    lo, hi = cp(k, n)
    sc = [vscore(r) for r in rows]
    a = None
    if all(s is not None for s in sc):
        a = auc([s for s, r in zip(sc, rows) if b(r['violation'])], [s for s, r in zip(sc, rows) if not b(r['violation'])])
    blocks = collections.defaultdict(list)
    for r in rows:
        blocks[r['block']].append(b(r['violation']) == b(r['alert']))
    return {'n': n, 'correct': k, 'acc': k / n, 'cp95': [lo, hi], 'TP': tp, 'FN': fn, 'FP': fp, 'TN': tn,
            'tpr': tp / (tp + fn) if tp + fn else None, 'fpr': fp / (fp + tn) if fp + tn else None,
            'auc': a, 'blocks': len(blocks), 'perfect_blocks': sum(all(v) for v in blocks.values())}

res = {}
for name, f in FILES.items():
    rows = list(csv.DictReader(f.open(encoding='utf-8-sig')))
    if name in ('C09_burst', 'C15_sustained'):
        groups = collections.defaultdict(list)
        for r in rows:
            groups[(r.get('branch', 'old_threshold'), r['model'])].append(r)
        out = {}
        for (br, m), rs in groups.items():
            cells = collections.defaultdict(lambda: [0, 0])
            for r in rs:
                key = (r['milliseconds'], r['cover'])
                cells[key][0] += b(r['alert']); cells[key][1] += 1
            act = [r for r in rs if b(r['actual'])]; sil = [r for r in rs if not b(r['actual'])]
            tp = sum(b(r['alert']) for r in act); fp = sum(b(r['alert']) for r in sil)
            sc_pos = [float(r['score']) for r in act if r['score'] not in ('', None)]
            sc_neg = [float(r['score']) for r in sil if r['score'] not in ('', None)]
            out[br + '/' + m] = {'TP': tp, 'FN': len(act) - tp, 'FP': fp, 'TN': len(sil) - fp,
                                 'auc_active_vs_silent': auc(sc_pos, sc_neg) if len(sc_pos) == len(act) and len(sc_neg) == len(sil) else None,
                                 'cells': {f'{k[0]}ms|cover={k[1]}': {'alerts': v[0], 'n': v[1]} for k, v in sorted(cells.items(), key=lambda kv: (float(kv[0][0]), kv[0][1]))}}
        res[name] = out
        continue
    key = 'variant' if 'variant' in rows[0] else ('branch' if 'branch' in rows[0] else 'window')
    groups = collections.defaultdict(list)
    for r in rows:
        groups[(r[key], r['model'])].append(r)
    res[name] = {f'{k[0]}/{k[1]}': summarize(v) for k, v in groups.items()}

(OUT/'paper_stats.json').write_text(json.dumps(res, indent=1), encoding='utf-8')
for name, d in res.items():
    print('==', name)
    for k, s in d.items():
        if 'acc' in s:
            print(f"  {k:55s} {s['correct']:3d}/{s['n']:<3d} acc={s['acc']:.3f} CP95=[{s['cp95'][0]:.3f},{s['cp95'][1]:.3f}] TP{s['TP']} FN{s['FN']} FP{s['FP']} TN{s['TN']} AUC={s['auc'] if s['auc'] is None else round(s['auc'],3)} blocks={s['perfect_blocks']}/{s['blocks']}")
        else:
            print(f"  {k:55s} TP{s['TP']} FN{s['FN']} FP{s['FP']} TN{s['TN']} AUC={s['auc_active_vs_silent'] if s['auc_active_vs_silent'] is None else round(s['auc_active_vs_silent'],3)} {s['cells']}")
