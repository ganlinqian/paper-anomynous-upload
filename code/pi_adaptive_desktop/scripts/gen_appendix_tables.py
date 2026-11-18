"""Generate appendix LaTeX tables directly from stats/paper_stats.json (no hand transcription)."""
import json, pathlib
S = pathlib.Path(r'<WORKSPACE>/ws_main\results\sp2027')
st = json.loads((S/'stats/paper_stats.json').read_text(encoding='utf-8'))
G = S/'paper/generated'; G.mkdir(parents=True, exist_ok=True)

NAMES = {
    'original/whole_260': 'frozen, whole-record', 'original/temporal_260': 'frozen, phase-resolved',
    'relative_reference/whole_260': 'silence ref., whole-record', 'relative_reference/temporal_260': 'silence ref., phase-resolved',
    'prefix_0p2/whole_260': 'pre-dispatch 0.2\\,s, whole', 'prefix_0p2/temporal_260': 'pre-dispatch 0.2\\,s, phase',
    'call_bracket/whole_260': 'call window, whole-record', 'call_bracket/temporal_260': 'call window, phase-resolved',
    'window_prefix_0p2/whole_260': 'pre-dispatch 0.2\\,s, whole', 'window_prefix_0p2/temporal_260': 'pre-dispatch 0.2\\,s, phase',
    'window_call_bracket/whole_260': 'call window, whole-record', 'window_call_bracket/temporal_260': 'call window, phase-resolved',
    'external_timing/coordinator_elapsed': 'timing: coordinator elapsed', 'external_timing/gateway_service': 'timing: gateway service',
    'external_timing/both_external_times': 'timing: both',
    'old_frozen_all64/whole_260': 'frozen C07, whole-record', 'old_frozen_all64/temporal_260': 'frozen C07, phase-resolved',
    'old_frozen_timing_all64/coordinator_elapsed': 'frozen timing: coordinator', 'old_frozen_timing_all64/gateway_service': 'frozen timing: gateway',
    'old_frozen_timing_all64/both_external_times': 'frozen timing: both',
    'new_calibration/whole_260': 'recalibrated, whole-record', 'new_calibration/temporal_260': 'recalibrated, phase-resolved',
    'new_context_calibration/whole_260': 'load-specific recal., whole', 'new_context_calibration/temporal_260': 'load-specific recal., phase',
    'new_context_timing/coordinator_elapsed': 'recal. timing: coordinator', 'new_context_timing/gateway_service': 'recal. timing: gateway',
    'new_context_timing/both_external_times': 'recal. timing: both',
}
def name(k):
    if k in NAMES:
        return NAMES[k]
    if k.startswith('C20_C10_calibration_transfer/'):
        rest = k.split('/', 1)[1].replace('_260', '').replace('_', ' ')
        rest = rest.replace('cover False', 'no-load calib.').replace('cover True', 'load calib.').replace('plain', 'common calib.')
        rest = rest.replace('direct violation', 'direct-violation').replace('timing/', 'timing ').replace('both external times', 'both')
        rest = rest.replace('coordinator elapsed', 'coordinator').replace('gateway service', 'gateway')
        return 'C10 transfer: ' + rest.replace('/', ', ')
    return k.replace('_', '\\_')

def table(exp, keys, caption, label):
    rows = []
    for k in keys:
        s = st[exp][k]
        auc = '--' if s['auc'] is None else f"{s['auc']:.2f}"
        rows.append(f"{name(k)} & {s['correct']}/{s['n']} & {s['cp95'][0]:.2f}--{s['cp95'][1]:.2f} & {s['TP']}/{s['FN']}/{s['FP']}/{s['TN']} & {auc} \\\\")
    body = '\n'.join(rows)
    return (f"\\begin{{table}}[h]\\centering\\scriptsize\\caption{{{caption}}}\\label{{{label}}}\n"
            "\\setlength{\\tabcolsep}{2pt}\\begin{tabular}{@{}p{3.15cm}cccc@{}}\\toprule\n"
            "Branch & Correct & 95\\% CI & TP/FN/FP/TN & AUC \\\\\\midrule\n" + body + "\n\\bottomrule\\end{tabular}\\end{table}\n")

out = []
out.append(table('C08_order', list(st['C08_order']), 'C08 order bit, all frozen branches (40 runs).', 'tab:app-c08o'))
out.append(table('C08_order_window', list(st['C08_order_window']), 'C08 order bit, window branches (40 runs).', 'tab:app-c08ow'))
out.append(table('C08_activity', list(st['C08_activity']) + [], 'C08 presence bit, frozen branches (40 runs).', 'tab:app-c08p'))
out.append(table('C08_activity_window', list(st['C08_activity_window']), 'C08 presence bit, window branches (40 runs).', 'tab:app-c08pw'))
out.append(table('C10_wait', list(st['C10_wait']), 'C10 hidden gzip with and without legitimate load: all branches (64 runs frozen; 32 runs after recalibration).', 'tab:app-c10'))
out.append(table('C13_untraced', list(st['C13_untraced']), 'C13 untraced hidden gzip: all frozen and transferred branches (32 runs).', 'tab:app-c13'))
(G/'app_tables.tex').write_text('\n'.join(out), encoding='utf-8')

# burst cells
def burst_table(exp, caption, label):
    lines = []
    for k, s in st[exp].items():
        cells = s['cells']
        cols = sorted(cells, key=lambda c: (c.split('|')[1], float(c.split('ms')[0])))
        cell_txt = ', '.join(f"{c.split('|')[0]}{'+L' if c.endswith('True') else ''}: {cells[c]['alerts']}/{cells[c]['n']}" for c in cols)
        lines.append(f"{k.split('/')[1].split('_')[0]} & {s['TP']}/{s['FN']}/{s['FP']}/{s['TN']} & \\parbox[t]{{4.6cm}}{{\\raggedright {cell_txt}}} \\\\")
    return (f"\\begin{{table}}[h]\\centering\\scriptsize\\caption{{{caption}}}\\label{{{label}}}\n"
            "\\setlength{\\tabcolsep}{2pt}\\begin{tabular}{@{}llp{4.7cm}@{}}\\toprule\n"
            "Score & TP/FN/FP/TN & Alerts per cell (+L: legitimate load) \\\\\\midrule\n" + '\n'.join(lines) +
            "\n\\bottomrule\\end{tabular}\\end{table}\n")
(G/'app_bursts.tex').write_text(burst_table('C09_burst', 'C09 burst detection, all frozen detectors (72 runs; 6 per cell).', 'tab:app-c09') + '\n' +
                                burst_table('C15_sustained', 'C15 bursts under sustained legitimate load (24 runs; 6 per cell).', 'tab:app-c15'), encoding='utf-8')
print('written', [p.name for p in G.iterdir()])
