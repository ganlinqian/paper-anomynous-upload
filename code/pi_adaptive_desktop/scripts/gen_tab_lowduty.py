"""Low-duty mitigation table (C29): the frozen C27 diverse model on C28 vs the frozen C29 low-duty+calibration model
on C29, per condition, from stats/c28_stats.json and stats/c29_stats.json.  Full-width (table*)."""
import json, pathlib
S = pathlib.Path(r'<WORKSPACE>/ws_main\results\sp2027')
c28 = json.loads((S / 'stats/c28_stats.json').read_text(encoding='utf-8'))
c29 = json.loads((S / 'stats/c29_stats.json').read_text(encoding='utf-8'))
G = S / 'paper/generated'; G.mkdir(parents=True, exist_ok=True)
COLS = [('gzip3_d19', '18.75\\%'), ('gzip2_d12', '12.5\\%'), ('gzip1_d06', '6.25\\%'), ('gzip05_d03', '3.125\\%'),
        ('gzip2_d06', '6.25\\%L'), ('gzip1_d03', '3.125\\%L')]
def row(by, sil):
    return ' & '.join('%d/%d' % (by[c]['alerts'], by[c]['n']) for c, _ in COLS) + ' & ' + '%d/%d' % (sil['alerts'], sil['n'])
r28 = row(c28['primary_by_condition'], c28['primary_silent'])
r29 = row(c29['primary_by_condition'], c29['primary_silent_false_alarms'])
B = chr(92)  # backslash
lines = [B + 'begin{table*}[t]', B + 'centering' + B + 'footnotesize',
         B + 'caption{Lowering the throttling frontier (alerts/runs). The frozen C27 diverse model on the C28 runs versus the C29 model, frozen on all C24/C27/C28 runs and applied with per-session calibration, on fresh C29 runs. L: the same duty with twice the work over 2.2' + B + ',s. Last column: false alarms on silent runs.}',
         B + 'label{tab:lowduty}', B + 'setlength{' + B + 'tabcolsep}{3pt}',
         B + 'begin{tabular}{@{}l' + 'c' * len(COLS) + 'c@{}}', B + 'toprule',
         'Model & ' + ' & '.join(h for _, h in COLS) + ' & silent ' + B * 2,
         B + 'midrule',
         'C27 diverse (C28) & ' + r28 + ' ' + B * 2,
         'C29 calibrated (C29) & ' + r29 + ' ' + B * 2,
         B + 'bottomrule', B + 'end{tabular}', B + 'end{table*}', '']
(G / 'tab_lowduty.tex').write_text('\n'.join(lines), encoding='utf-8')
print('wrote', G / 'tab_lowduty.tex'); print('C27/C28:', r28); print('C29/C29:', r29)
