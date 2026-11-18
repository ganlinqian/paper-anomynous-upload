"""Paper figures: (1) frozen-model results vs. baselines, (2) hidden-work evasion budget.

All numbers are read from stats/paper_stats.json, which is recomputed from stored per-trial
predictions of frozen models (no refit).  Transcript-only values are the content-equivalence
upper bound (each public-content class holds one compliant and one violating run).
"""
import json, pathlib
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

S = pathlib.Path(r'<WORKSPACE>/ws_main\results\sp2027')
st = json.loads((S/'stats/paper_stats.json').read_text(encoding='utf-8'))
OUT = S/'figures'

def g(exp, key):
    s = st[exp][key]; return s['correct'], s['n']

# best frozen external-timing baseline per experiment (reported values from frozen baselines)
groups = [
    ('Order bit\n(C08, n=40)', [(20, 40), (24, 40), g('C08_order', 'original/whole_260'), g('C08_order', 'original/temporal_260'), g('C08_order_window', 'call_bracket/temporal_260')]),
    ('Presence bit\n(C08, n=40)', [(20, 40), (23, 40), g('C08_activity', 'original/whole_260'), g('C08_activity', 'relative_reference/whole_260'), g('C08_activity_window', 'call_bracket/whole_260')]),
    ('gzip + legit. load\n(C10, n=64/32)', [(32, 64), g('C10_wait', 'old_frozen_timing_all64/coordinator_elapsed'), g('C10_wait', 'old_frozen_all64/whole_260'), g('C10_wait', 'old_frozen_all64/temporal_260'), g('C10_wait', 'new_calibration/temporal_260')]),
    ('gzip, untraced\n(C13, n=32)', [(16, 32), g('C13_untraced', 'external_timing/both_external_times'), g('C13_untraced', 'original/whole_260'), g('C13_untraced', 'original/temporal_260'), g('C13_untraced', 'C20_C10_calibration_transfer/temporal_260/plain')]),
]
# real-tool order (C26, supplement S2): frozen on C26-T; the rightmost bar is the call-window model (primary)
_sp = S / 'stats/supp_stats.json'
if _sp.exists() and 's2' in json.loads(_sp.read_text(encoding='utf-8')):
    _s2 = json.loads(_sp.read_text(encoding='utf-8'))['s2']; _m = _s2['models']; _n = _s2['n']
    groups.append(('Order, real tools\n(C26, n=%d)' % _n, [(_s2['transcript_bound_correct'], _n), (_m['elapsed']['correct'], _n), (_m['record_whole']['correct'], _n),
                                                        (_m['record_temporal']['correct'], _n), (_m['call_temporal']['correct'], _n)]))
labels = ['transcript-only (upper bound)', 'external timing (frozen)', 'RF whole-record (frozen)', 'Telltale phase-resolved (frozen)', 'Telltale + reference/calibration']
colors = ['#bdbdbd', '#8c8c8c', '#9ecae1', '#2171b5', '#08306b']

def cp(k, n):
    from math import lgamma, log, exp
    import importlib.util, sys
    spec = importlib.util.spec_from_file_location('ps', str(S/'scripts/paper_stats.py'))
    return None

plt.rcParams.update({'font.size': 7.5, 'font.family': 'serif', 'axes.linewidth': 0.6, 'legend.fontsize': 6.5, 'pdf.fonttype': 42})
fig, ax = plt.subplots(figsize=(7.16, 1.9), constrained_layout=True)
x = np.arange(len(groups)); w = 0.16
for j in range(5):
    vals = [gr[1][j][0] / gr[1][j][1] for gr in groups]
    bars = ax.bar(x + (j - 2) * w, vals, w * 0.92, color=colors[j], label=labels[j], edgecolor='black', linewidth=0.3)
    for xi, (k, n) in zip(x + (j - 2) * w, [gr[1][j] for gr in groups]):
        ax.text(xi, k / n + 0.015, f'{k}/{n}', ha='center', va='bottom', fontsize=5.2, rotation=90)
ax.axhline(0.5, color='k', lw=0.5, ls=':')
ax.set_xticks(x); ax.set_xticklabels([gr[0] for gr in groups])
ax.set_ylim(0, 1.32); ax.set_yticks([0, .25, .5, .75, 1.0]); ax.set_ylabel('accuracy on new runs')
ax.legend(ncol=3, loc='upper center', frameon=False, bbox_to_anchor=(0.5, 1.02), columnspacing=1.0, handlelength=1.2)
ax.grid(axis='y', alpha=0.25, lw=0.4)
fig.savefig(OUT/'fig_results.pdf'); fig.savefig(OUT/'fig_results.png', dpi=220)

# ---- evasion budget: alerts per duration cell, top-3 detector (frozen threshold), and silent false alarms
def cells(exp, key):
    return st[exp][key]['cells']
DET = [('top3mean_minus_p50', 'top-3', '#2171b5'), ('p99_minus_p50', 'p99', '#e6550d'), ('max_minus_p50', 'max', '#31a354')]
durs = [10, 30, 100, 300, 1000]
def series(c, cover):
    xs, ys = [], []
    for d in durs:
        k = f'{d}ms|cover={cover}'
        if k in c:
            xs.append(d); ys.append(c[k]['alerts'] / c[k]['n'])
    fa = c.get(f'0ms|cover={cover}')
    return xs, ys, (fa['alerts'] / fa['n'] if fa else None)
fig, axs = plt.subplots(1, 3, figsize=(3.45, 1.75), constrained_layout=True, sharey=True)
panels = [('C09_burst', 'False', 'no load (C09)'), ('C09_burst', 'True', 'short load (C09)'), ('C15_sustained', 'True', 'sustained load (C15)')]
for ax, (exp, cover, title) in zip(axs, panels):
    for j, (key, lab, col) in enumerate(DET):
        xs, ys, fa = series(cells(exp, 'old_threshold/' + key), cover)
        ax.plot(xs, ys, marker='o', ms=2.4, lw=0.8, color=col, label=lab)
        if fa is not None:
            ax.scatter([3.2 * (1 + 0.15 * (j - 1))], [fa], marker='x', s=12, color=col, zorder=5, lw=0.8)
    ax.set_xscale('log'); ax.set_xlim(2.2, 1600); ax.set_xticks([3.2, 10, 100, 1000]); ax.set_xticklabels(['FA', '10', '100', '1k'])
    ax.axvline(5.6, color='0.6', lw=0.4, ls=':')
    ax.minorticks_off()
    ax.set_title(title, fontsize=6.2); ax.grid(alpha=0.25, lw=0.4); ax.set_ylim(-0.05, 1.08)
axs[1].set_xlabel('hidden work per call (ms); FA = alerts on silent runs')
axs[0].set_ylabel('alert rate (n=6/cell)')
axs[0].legend(frameon=False, fontsize=5.3, loc='center right')
fig.savefig(OUT/'fig_budget.pdf'); fig.savefig(OUT/'fig_budget.png', dpi=220)
print('ok', [gr[0].split(chr(10))[0] for gr in groups])
