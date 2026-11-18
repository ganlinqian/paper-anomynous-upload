"""Figure (RQ6): adaptive hidden work.  Left: C24, next day, models frozen on one workload.  Right: C27, models frozen
on all C24 variants, new runs incl. unseen variants (marked *).  Reads stats/supp_stats.json only (frozen detectors)."""
import json, pathlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

S = pathlib.Path(r'<WORKSPACE>/ws_main\results\sp2027')
st = json.loads((S / 'stats/supp_stats.json').read_text(encoding='utf-8'))
LAB = {'silent': 'silent\n(FA)', 'gzip2_d12': '12.5%', 'gzip3_d19': '18.75%*', 'gzip4_d25': '25%', 'gzip6_d37': '37.5%*', 'gzip8_d50': '50%',
       'text8': 'text', 'json8': 'JSON*', 'bzip2_r': 'bzip2*', 'gzip16': 'full'}
ORDER = ['silent', 'gzip2_d12', 'gzip3_d19', 'gzip4_d25', 'gzip6_d37', 'gzip8_d50', 'text8', 'json8', 'bzip2_r', 'gzip16']
PANELS = [('s1', 'C24, next day: models frozen on one workload',
           [('C10_transfer/temporal_260/plain', 'C10-calibrated phase (primary)', '#9ecae1'), ('C07_frozen/temporal_260', 'C07 frozen phase', '#bdbdbd')]),
          ('s1b', 'C27, new runs: model frozen on diverse hidden work',
           [('C27_diverse/call_temporal', 'diverse, call-window phase (primary)', '#08306b'), ('C10_transfer/temporal_260/plain', 'C10-calibrated phase', '#9ecae1')])]
panels = [p for p in PANELS if p[0] in st]
plt.rcParams.update({'font.size': 6.8, 'font.family': 'serif', 'axes.linewidth': 0.6, 'legend.fontsize': 5.8, 'pdf.fonttype': 42})
fig, axs = plt.subplots(1, len(panels), figsize=(7.16, 1.75), constrained_layout=True, sharey=True,
                        gridspec_kw={'width_ratios': [len([c for c in ORDER if c in st[p[0]]['primary_by_condition']]) for p in panels]})
axs = axs if len(panels) > 1 else [axs]
for ax, (key, title, dets) in zip(axs, panels):
    b = st[key]; conds = [c for c in ORDER if c in b['primary_by_condition']]
    w = 0.38
    for j, (dk, lab, col) in enumerate(dets):
        by = b['detectors'][dk]['by_condition']
        for i, c in enumerate(conds):
            k, n = by[c]['alerts'], by[c]['n']; x = i + (j - 0.5) * w
            ax.bar(x, k / n, w * 0.92, color=col, edgecolor='black', linewidth=0.3, label=lab if i == 0 else None)
            ax.text(x, k / n + 0.02, '%d/%d' % (k, n), ha='center', va='bottom', fontsize=4.9, rotation=90)
    ax.set_xticks(range(len(conds))); ax.set_xticklabels([LAB[c] for c in conds], fontsize=5.8)
    ax.axvline(0.5, color='0.5', lw=0.4, ls=':')
    ax.set_title(title, fontsize=6.4); ax.set_ylim(0, 1.32); ax.set_yticks([0, .25, .5, .75, 1])
    ax.legend(loc='upper left', frameon=False, ncol=1, handlelength=1.0, borderaxespad=0.1)
    ax.grid(axis='y', alpha=0.25, lw=0.4)
    for s in ('top', 'right'):
        ax.spines[s].set_visible(False)
axs[0].set_ylabel('alert rate')
out = S / 'figures'
fig.savefig(out / 'fig_adaptive.pdf'); fig.savefig(out / 'fig_adaptive.png', dpi=220)
print('wrote fig_adaptive with panels', [p[0] for p in panels])
