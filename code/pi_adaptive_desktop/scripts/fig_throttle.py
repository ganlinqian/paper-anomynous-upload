"""Figure: detection of throttled / new-input hidden gzip (C24 = supplement S1) vs. the adversary's hidden throughput.

Reads stats/supp_stats.json (frozen detectors only, written by supp_stats.py).  Error bars are exact
Clopper-Pearson 95% intervals; the shaded band is the false-alarm rate on the silent runs of the same batch.
"""
import json, pathlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

S = pathlib.Path(r'<WORKSPACE>/ws_main\results\sp2027')
st = json.loads((S / 'stats/supp_stats.json').read_text(encoding='utf-8'))['s1']
DET = [('C10_transfer/temporal_260/plain', 'Telltale phase-resolved (C10 calib., primary)', '#08306b', 'o'),
       ('C10_transfer/whole_260/plain', 'RF whole-record (C10 calib.)', '#6baed6', 's'),
       ('C07_frozen/temporal_260', 'phase-resolved, C07 frozen', '#969696', '^')]
RANDOM = ['gzip2_d12', 'gzip4_d25', 'gzip8_d50', 'gzip16']
LABEL = {'gzip2_d12': '2 MiB\n12.5%', 'gzip4_d25': '4 MiB\n25%', 'gzip8_d50': '8 MiB\n50%', 'gzip16': '16 MiB\n100%', 'text8': 'text\n8 MiB'}

plt.rcParams.update({'font.size': 7, 'font.family': 'serif', 'axes.linewidth': 0.6, 'legend.fontsize': 5.8, 'pdf.fonttype': 42})
fig, ax = plt.subplots(figsize=(3.45, 1.75), constrained_layout=True)
order = RANDOM + ['text8']
xs = {c: i for i, c in enumerate(order)}
for j, (key, lab, col, mk) in enumerate(DET):
    by = st['detectors'][key]['by_condition']
    off = (j - 1) * 0.18
    for c in order:
        v = by[c]; r = v['alerts'] / v['n']; lo, hi = v['cp95']
        ax.errorbar(xs[c] + off, r, yerr=[[r - lo], [hi - r]], fmt=mk, ms=3.2, color=col, mfc=col if j == 0 else 'white', lw=0.6, capsize=1.5,
                    label=lab if c == order[0] else None)
    fa = by['silent']; f = fa['alerts'] / fa['n']
    ax.axhline(f, color=col, lw=0.6, ls=(0, (2, 2)) if j else '--', alpha=0.9)
ax.text(len(order) - 0.55, st['detectors'][DET[0][0]]['by_condition']['silent']['alerts'] / st['detectors'][DET[0][0]]['by_condition']['silent']['n'] + 0.03,
        'false alarms\n(%d silent)' % st['detectors'][DET[0][0]]['by_condition']['silent']['n'], fontsize=5.5, ha='right', va='bottom', color=DET[0][2])
tim = st['hidden_work']
ax.set_xticks(range(len(order)))
ax.set_xticklabels([LABEL[c] + '\n%.1f MiB/s' % tim[c]['mib_per_s_median'] for c in order], fontsize=5.6)
ax.set_xlim(-0.5, len(order) - 0.5); ax.set_ylim(-0.04, 1.08)
ax.set_ylabel('alert rate (n=8 per cell)')
ax.axvline(len(RANDOM) - 0.5, color='k', lw=0.4, ls=':')
ax.legend(loc='lower left', frameon=False, handletextpad=0.3, borderaxespad=0.2)
for spine in ('top', 'right'):
    ax.spines[spine].set_visible(False)
out = S / 'figures'; out.mkdir(exist_ok=True)
fig.savefig(out / 'fig_throttle.pdf'); fig.savefig(out / 'fig_throttle.png', dpi=220)
print('wrote', out / 'fig_throttle.pdf')
