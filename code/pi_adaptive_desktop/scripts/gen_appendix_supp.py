"""Appendix tables for the supplementary batches C24-C27, generated from stats/supp_stats.json (no hand transcription)."""
import json, pathlib
S = pathlib.Path(r'<WORKSPACE>/ws_main\results\sp2027')
st = json.loads((S / 'stats/supp_stats.json').read_text(encoding='utf-8'))
G = S / 'paper/generated'; G.mkdir(parents=True, exist_ok=True)
COND = {'silent': 'silent', 'gzip16': '16\\,MiB', 'text8': 'text', 'gzip8_d50': '50\\%', 'gzip4_d25': '25\\%', 'gzip2_d12': '12.5\\%',
        'gzip16_cap': '16\\,MiB cap', 'silent_cap': 'silent cap', 'gzip6_d37': '37.5\\%', 'gzip3_d19': '18.75\\%', 'json8': 'JSON', 'bzip2_r': 'bzip2',
        'gzip1_d06': '6.25\\%', 'gzip05_d03': '3.125\\%', 'gzip2_d06': '6.25L', 'gzip1_d03': '3.125L'}
ORDER = ['silent', 'silent_cap', 'gzip16', 'gzip16_cap', 'text8', 'json8', 'bzip2_r', 'gzip8_d50', 'gzip6_d37', 'gzip4_d25', 'gzip3_d19', 'gzip2_d12',
         'gzip1_d06', 'gzip05_d03', 'gzip2_d06', 'gzip1_d03']
DET = [('C27_diverse/call_temporal', 'diverse, call window, phase'), ('C27_diverse/call_whole', 'diverse, call window, whole'),
       ('C27_diverse/record_temporal', 'diverse, record, phase'),
       ('C10_transfer/temporal_260/plain', 'C10 calib., phase'), ('C10_transfer/whole_260/plain', 'C10 calib., whole'),
       ('C10_transfer/temporal_260/cover_False', 'C10 no-load calib., phase'), ('C10_transfer/whole_260/cover_False', 'C10 no-load calib., whole'),
       ('C07_frozen/temporal_260', 'C07 frozen, phase'), ('C07_frozen/whole_260', 'C07 frozen, whole'),
       ('relative_ref/temporal_260', 'silence ref., phase'), ('relative_ref/whole_260', 'silence ref., whole'),
       ('window_call_bracket/temporal_260', 'call window, phase'), ('window_call_bracket/whole_260', 'call window, whole'),
       ('window_prefix_0p2/temporal_260', 'pre-dispatch 0.2\\,s, phase'), ('window_prefix_0p2/whole_260', 'pre-dispatch 0.2\\,s, whole'),
       ('burst/top3mean_minus_p50', 'burst top-3'), ('burst/p99_minus_p50', 'burst p99'), ('burst/max_minus_p50', 'burst max')]

def wait_table(key, caption, label, clock=False):
    b = st[key]; conds = [c for c in ORDER if c in b['primary_by_condition']]
    head = ' & '.join(COND[c] for c in conds)
    lines = ['\\begin{table*}[t]', '\\centering\\scriptsize', '\\caption{' + caption + '}', '\\label{' + label + '}', '\\setlength{\\tabcolsep}{3pt}',
             '\\begin{tabular}{@{}l' + 'c' * len(conds) + '@{}}', '\\toprule', 'Detector (alerts/runs) & ' + head + ' \\\\', '\\midrule']
    for k, nm in DET:
        if k not in b['detectors']:
            continue
        by = b['detectors'][k]['by_condition']
        cells = ['%d/%d' % (by[c]['alerts'], by[c]['n']) for c in conds]
        if k == b['primary']:
            nm = '\\textbf{' + nm + ' (primary)}'; cells = ['\\textbf{' + x + '}' for x in cells]
        lines.append(nm + ' & ' + ' & '.join(cells) + ' \\\\')
    if clock and 'clock_check' in b:
        by = b['clock_check']['by_condition']
        lines.append('\\midrule')
        lines.append('clock check (flags) & ' + ' & '.join('%d/%d' % (by[c]['clock_flags'], by[c]['n']) for c in conds) + ' \\\\')
        lines.append('activity or clock & ' + ' & '.join('%d/%d' % (by[c]['combined_alerts'], by[c]['n']) for c in conds) + ' \\\\')
    lines += ['\\bottomrule', '\\end{tabular}', '\\end{table*}', '']
    return '\n'.join(lines)

def multi_wait_table(keys, names, caption, label):
    """Several batches side by side (same detectors as rows), e.g. C27 and C28 for the diverse-workload models."""
    bs = [st[k] for k in keys]; conds = [[c for c in ORDER if c in b['primary_by_condition']] for b in bs]
    spans, pos = [], 2
    for nm, cc in zip(names, conds):
        spans.append('\\multicolumn{%d}{c}{%s}' % (len(cc), nm)); pos += len(cc)
    rules, start = [], 2
    for cc in conds:
        rules.append('\\cmidrule(lr){%d-%d}' % (start, start + len(cc) - 1)); start += len(cc)
    lines = ['\\begin{table*}[t]', '\\centering\\scriptsize', '\\caption{' + caption + '}', '\\label{' + label + '}', '\\setlength{\\tabcolsep}{2.4pt}',
             '\\begin{tabular}{@{}l' + 'c' * sum(len(c) for c in conds) + '@{}}', '\\toprule', ' & ' + ' & '.join(spans) + ' \\\\', ''.join(rules),
             'Detector (alerts/runs) & ' + ' & '.join(COND[c] for cc in conds for c in cc) + ' \\\\', '\\midrule']
    for k, nm in DET:
        if not all(k in b['detectors'] for b in bs):
            continue
        cells = ['%d/%d' % (b['detectors'][k]['by_condition'][c]['alerts'], b['detectors'][k]['by_condition'][c]['n']) for b, cc in zip(bs, conds) for c in cc]
        if all(k == b['primary'] for b in bs):
            nm = '\\textbf{' + nm + ' (primary)}'; cells = ['\\textbf{' + x + '}' for x in cells]
        lines.append(nm + ' & ' + ' & '.join(cells) + ' \\\\')
    lines += ['\\bottomrule', '\\end{tabular}', '\\end{table*}', '']
    return '\n'.join(lines)

def order_table():
    b = st['s2']
    NM = {'call_temporal': '\\textbf{call window, phase (primary)}', 'record_temporal': 'record, phase', 'record_whole': 'record, whole',
          'elapsed': 'timing (elapsed)'}
    lines = ['\\begin{table}[h]', '\\centering\\scriptsize',
             '\\caption{C26: real verify-then-extract, 40 test runs in 10 blocks; models trained on the 16 runs of C26-T and frozen before C26 was collected. Transcript bound 20/40.}',
             '\\label{tab:app-c26}', '\\setlength{\\tabcolsep}{2.5pt}', '\\begin{tabular}{@{}lccccc@{}}', '\\toprule',
             'Model & Correct & 95\\% CI & TP/FN/FP/TN & AUC & Blk \\\\', '\\midrule']
    for k in ('call_temporal', 'record_temporal', 'record_whole', 'elapsed'):
        if k not in b['models']:
            continue
        m = b['models'][k]; auc = '--' if m.get('auc') is None else '%.2f' % m['auc']
        lines.append('%s & %d/%d & %.2f--%.2f & %d/%d/%d/%d & %s & %d/%d \\\\' % (NM[k], m['correct'], b['n'], m['cp95'][0], m['cp95'][1], m['tp'], m['fn'], m['fp'], m['tn'],
                                                                                auc, m['perfect_blocks'], m['blocks']))
    lines += ['\\bottomrule', '\\end{tabular}', '\\end{table}', '']
    return '\n'.join(lines)

out = []
if 's1' in st:
    out.append(wait_table('s1', 'C24: adaptive hidden work the next day (8 blocks; 16 silent runs, 8 runs per variant). All models frozen before collection; percentages are duty cycles of throttled gzip on 8, 4, and 2\\,MiB.', 'tab:app-c24'))
if 's3' in st:
    out.append(wait_table('s3', 'C25: clock capping to 1.2\\,GHz during the call (6 blocks, 6 runs per cell). The clock-check rule was fixed before collection; its reference statistics come from the six uncapped silent runs.', 'tab:app-c25', clock=True))
if 's1b' in st and 's1c' in st:
    out.append(multi_wait_table(['s1b', 's1c'], ['C27', 'C28'], 'C27 and C28: prospective tests of the diverse-workload models frozen on all C24 runs (8 blocks each; 16 silent runs, 8 runs per variant). Duty-cycled runs spread their work over 1.1\\,s; L: twice the work at the same duty over 2.2\\,s. Of these variants, only 25 and 12.5\\% duty and 16\\,MiB at full speed were seen in training.', 'tab:app-c27'))
elif 's1b' in st:
    out.append(wait_table('s1b', 'C27: prospective test of the diverse-workload models frozen on all C24 runs (8 blocks; 16 silent runs, 8 runs per variant). 37.5 and 18.75\\% duty, JSON input, and bzip2 were never seen in training.', 'tab:app-c27'))
if 's2' in st:
    out.append(order_table())
(G / 'app_supp.tex').write_text('\n'.join(out), encoding='utf-8')
print('wrote', G / 'app_supp.tex', len(out), 'tables')
