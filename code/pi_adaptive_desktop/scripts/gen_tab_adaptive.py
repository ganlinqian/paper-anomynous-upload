"""Main-text table for RQ6 (adaptive hidden work), generated from stats/supp_stats.json (frozen detectors only)."""
import json, pathlib
S = pathlib.Path(r'<WORKSPACE>/ws_main\results\sp2027')
st = json.loads((S / 'stats/supp_stats.json').read_text(encoding='utf-8'))
G = S / 'paper/generated'; G.mkdir(parents=True, exist_ok=True)
ONE = 'C10_transfer/temporal_260/plain'; DIV = 'C27_diverse/call_temporal'
ROWS = [('silent', 'silent (false alarms)'), ('gzip16', 'full speed, 16\\,MiB'), ('text8', 'text input, 8\\,MiB'), ('json8', 'JSON input, 8\\,MiB$^*$'),
        ('bzip2_r', '\\texttt{bzip2}, 4\\,MiB$^*$'), ('gzip8_d50', '50\\% duty, 8\\,MiB'), ('gzip6_d37', '37.5\\% duty, 6\\,MiB$^*$'),
        ('gzip4_d25', '25\\% duty, 4\\,MiB'), ('gzip3_d19', '18.75\\% duty, 3\\,MiB$^*$'), ('gzip2_d12', '12.5\\% duty, 2\\,MiB'),
        ('gzip1_d06', '6.25\\% duty, 1\\,MiB$^*$'), ('gzip05_d03', '3.125\\% duty, 0.5\\,MiB$^*$'),
        ('gzip2_d06', '6.25\\%, 2\\,MiB over 2.2\\,s$^*$'), ('gzip1_d03', '3.125\\%, 1\\,MiB over 2.2\\,s$^*$')]
c24 = st['s1']['detectors'][ONE]['by_condition']
c27 = st['s1b']['detectors'] if 's1b' in st else None
c28 = st['s1c']['detectors'] if 's1c' in st else None
def cell(by, c, bold=False):
    if by is None or c not in by:
        return '--'
    s = '%d/%d' % (by[c]['alerts'], by[c]['n'])
    return '\\textbf{' + s + '}' if bold else s
cols = 'lccc' + ('c' if c28 else '')
cap = ("\\caption{Adaptive hidden work: alerts/runs of frozen models. `Single' is the C10-calibrated phase-resolved model, trained on full-speed gzip only; "
       "`diverse' is the call-window model frozen on all C24 runs" + (" before C27 and C28 were collected" if c28 else '') + ". Throttled runs spread their work over 1.1\\,s"
       + ("; the last two rows double the work at the same duty" if c28 else '') + ". $^*$Not in the diverse model's training data.}")
head1 = ' & C24 (next day) & \\multicolumn{2}{c}{C27 (new runs)}' + (' & C28 (new) ' if c28 else '') + ' \\\\'
rule = '\\cmidrule(lr){2-2}\\cmidrule(lr){3-4}' + ('\\cmidrule(l){5-5}' if c28 else '')
head2 = 'Hidden work & single & single & \\textbf{diverse}' + (' & \\textbf{diverse}' if c28 else '') + ' \\\\'
lines = ['\\begin{table}[t]', '\\centering\\footnotesize', cap, '\\label{tab:adaptive}', '\\setlength{\\tabcolsep}{3pt}', '\\begin{tabular}{@{}' + cols + '@{}}', '\\toprule',
         head1, rule, head2, '\\midrule']
for c, nm in ROWS:
    if not any(by is not None and c in by for by in (c24, c27[ONE]['by_condition'] if c27 else None, c27[DIV]['by_condition'] if c27 else None,
                                                    c28[DIV]['by_condition'] if c28 else None)):
        continue
    row = [nm, cell(c24, c), cell(c27[ONE]['by_condition'] if c27 else None, c), cell(c27[DIV]['by_condition'] if c27 else None, c, True)]
    if c28:
        row.append(cell(c28[DIV]['by_condition'], c, True))
    lines.append(' & '.join(row) + ' \\\\')
    if c == 'silent' or (c28 and c == 'gzip05_d03'):
        lines.append('\\midrule')
lines += ['\\bottomrule', '\\end{tabular}', '\\end{table}', '']
(G / 'tab_adaptive.tex').write_text('\n'.join(lines), encoding='utf-8')
print('wrote', G / 'tab_adaptive.tex', 'with C27' if c27 else 'without C27', 'with C28' if c28 else 'without C28')
