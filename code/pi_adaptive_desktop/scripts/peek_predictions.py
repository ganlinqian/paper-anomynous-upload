import csv, pathlib, collections, sys
A = pathlib.Path(r'<WORKSPACE>/ws_pi\results\scenario_rf_20261104\analysis_extensions')
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
for name, f in FILES.items():
    rows = list(csv.DictReader(f.open(encoding='utf-8-sig')))
    print('==', name, len(rows), 'cols:', list(rows[0].keys()))
    keycols = [c for c in ('variant', 'branch', 'model', 'cover', 'milliseconds', 'stage', 'split') if c in rows[0]]
    cnt = collections.Counter(tuple(r[c] for c in keycols if c not in ('milliseconds', 'cover')) for r in rows)
    for k, v in sorted(cnt.items()):
        print('  ', k, v)
