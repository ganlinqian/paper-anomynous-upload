"""Exact block-level sign-flip tests for paired detector comparisons on the same runs.

Per block, d_b = acc(A) - acc(B).  Under H0 (exchangeable labels within block), signs of d_b
are symmetric; p = fraction of 2^B sign assignments with |sum| >= observed.  Descriptive:
blocks are the randomization units of each batch; no multiplicity correction claimed.
"""
import csv, itertools, json, pathlib, collections
A = pathlib.Path(r'<WORKSPACE>/ws_pi\results\scenario_rf_20261104\analysis_extensions')
OUT = pathlib.Path(r'<WORKSPACE>/ws_main\results\sp2027\stats')
def load(f):
    return list(csv.DictReader(f.open(encoding='utf-8-sig')))
def b(x): return str(x).strip().lower() == 'true'
def per_block(rows, key, val, model):
    d = collections.defaultdict(list)
    for r in rows:
        if r[key] == val and r['model'] == model:
            d[r['block']].append(b(r['alert']) == b(r['violation']))
    return {k: sum(v) / len(v) for k, v in d.items()}
def signflip(da, db):
    blocks = sorted(set(da) & set(db))
    diffs = [da[k] - db[k] for k in blocks]
    obs = abs(sum(diffs)); cnt = 0; tot = 0
    for s in itertools.product([1, -1], repeat=len(diffs)):
        tot += 1; cnt += abs(sum(x * y for x, y in zip(diffs, s))) >= obs - 1e-12
    return {'blocks': len(blocks), 'mean_diff': sum(diffs) / len(diffs), 'p_two_sided': cnt / tot}
def timing_from(rows, key, val, model):
    return per_block(rows, key, val, model)
res = {}
o = load(A/'early_confirm_20261105/reports/EARLY_CONFIRMATION_ORDER_a27de29479e9/all_predictions.csv')
ow = load(A/'window_diagnostic_20261105/reports/WINDOW_DIAGNOSTIC_CONFIRMATION_ORDER_b0cc46caada2/all_predictions.csv')
res['C08_order temporal vs whole'] = signflip(per_block(o, 'variant', 'original', 'temporal_260'), per_block(o, 'variant', 'original', 'whole_260'))
res['C08_order call-window vs pre-dispatch (temporal)'] = signflip(per_block(ow, 'window', 'call_bracket', 'temporal_260'), per_block(ow, 'window', 'prefix_0p2', 'temporal_260'))
t = load(A/'early_confirm_20261105/reports/EARLY_CONFIRMATION_TRACE_103f4acc7876/all_predictions.csv')
res['C08_presence relative-ref vs original (whole)'] = signflip(per_block(t, 'variant', 'relative_reference', 'whole_260'), per_block(t, 'variant', 'original', 'whole_260'))
w = load(A/'early_burst_wait_20261105/wait_report_5031308add33/all_predictions.csv')
res['C10 temporal vs best timing (coordinator)'] = signflip(per_block(w, 'branch', 'old_frozen_all64', 'temporal_260'), per_block(w, 'branch', 'old_frozen_timing_all64', 'coordinator_elapsed'))
u = load(A/'untraced_wait_report_20261105/predictions.csv')
res['C13 temporal vs timing (both)'] = signflip(per_block(u, 'branch', 'original', 'temporal_260'), per_block(u, 'branch', 'external_timing', 'both_external_times'))
res['C13 calib-transfer temporal vs timing (both)'] = signflip(per_block(u, 'branch', 'C20_C10_calibration_transfer', 'temporal_260/plain'), per_block(u, 'branch', 'external_timing', 'both_external_times'))
OUT.mkdir(parents=True, exist_ok=True)
(OUT/'block_tests.json').write_text(json.dumps(res, indent=1), encoding='utf-8')
for k, v in res.items():
    print(f"{k:50s} blocks={v['blocks']} mean_diff={v['mean_diff']:+.3f} p={v['p_two_sided']:.4f}")
