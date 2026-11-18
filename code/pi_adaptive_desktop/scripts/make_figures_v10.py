"""v10 data figures.

fig_contracts: x86 desktop, second session D2 (mixed contracts, models frozen on D-T): the frozen physical score
    P(A=1 | X) of every call, grouped by contract bit E and violation label V; illustrates Proposition 2.
fig_loadpower: exploratory 2025 measurement of an x86 desktop: total received power relative to idle for two
    repetitions each of ALU-, FPU-, and memory-bound load and with the machine switched off.
usage: python -I make_figures_v10.py [contracts] [loadpower]
"""
import json, pathlib, re, sys
import numpy as np
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import figstyle as fs  # noqa: E402
import make_figures as mf  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

S = fs.ROOT
D = S / 'desktop_em'
fs.OUT = fs.FIG_ROOT / 'v10'


def fig_contracts():
    res = json.loads((D / 'runs' / 'RESULTS_d2.json').read_text(encoding='utf-8'))
    rng = np.random.default_rng(3)
    groups = [(0, 0), (0, 1), (1, 0), (1, 1)]
    with fs.ieee_style():
        fig, axs = plt.subplots(1, 2, figsize=(fs.COL_W, 2.05), sharey=True, layout='constrained')
        for ax, kind, title in zip(axs, ('order', 'wait'), ('(a) Order, D2', '(b) Wait, D2')):
            pr = res['fixtures'][kind]['per_run']
            for gi, (e, v) in enumerate(groups):
                ys = np.array([p['p_phase'] for p in pr if p['E'] == e and p['V'] == v])
                xs = gi + rng.uniform(-0.2, 0.2, len(ys))
                if v:
                    ax.scatter(xs, ys, s=10, marker='^', color=fs.VERM, lw=0, label='violating' if gi == 1 else None, zorder=3)
                else:
                    ax.scatter(xs, ys, s=10, marker='o', facecolor='none', edgecolor=fs.BLUE, lw=0.6,
                               label='compliant' if gi == 0 else None, zorder=3)
            ax.axhline(0.5, color='black', lw=0.5, ls=':', label='threshold on P' if kind == 'order' else None, zorder=1)
            ax.axvline(1.5, color=fs.GREY, lw=0.6, zorder=0)
            ax.set_xticks(range(4))
            ax.set_xticklabels(['E=0\nok', 'E=0\nviol.', 'E=1\nok', 'E=1\nviol.'])
            ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
            ax.set_xlim(-0.6, 3.6)
            ax.set_ylim(-0.1, 1.1)
            ax.set_title(title)
        axs[0].set_ylabel('Frozen P(A = 1 | X)')
        fig.legend(loc='outside upper right', ncol=3, frameon=False, handlelength=1.2, columnspacing=0.8)
        mf.finish(fig, 'fig_contracts', {
            'raw_data': [str(D / 'runs/RESULTS_d2.json'), str(D / 'runs/PREREG_d2.json'), str(D / 'runs/FREEZE.json')],
            'transformations': ['p_phase = frozen phase-resolved logistic model of FREEZE.json applied to D2 runs',
                                'groups by contract bit E and violation V = A xor E; horizontal jitter for display only'],
            'uncertainty': 'every run drawn (20 per family per E)'})
    print(json.dumps(mf.REPORT['fig_contracts']['check'], default=str)[:1500])


def fig_loadpower():
    txt = (D / 'early_2025' / 'statistics_20251025_010749.txt').read_text(encoding='utf-8')
    absolute, gains = txt.split('[Relative power gain over idle CPU]')
    pat = re.compile(r'^\s+(\S+)\s*:\s*([+-]?\d+\.\d+) dB', re.M)
    a = dict(pat.findall(absolute))
    g = dict(pat.findall(gains))
    rows = [('ALU, run 1', float(g['ALU1'])), ('ALU, run 2', float(g['ALU2'])),
            ('FPU, run 1', float(g['FPU1'])), ('FPU, run 2', float(g['FPU2'])),
            ('memory, run 1', float(g['RAM1'])), ('memory, run 2', float(g['RAM2'])),
            ('switched off', round(float(a['powered_off']) - float(a['CPU_idle']), 2))]
    with fs.ieee_style():
        fig, ax = plt.subplots(figsize=(fs.COL_W, 1.55), layout='constrained')
        y = np.arange(len(rows))[::-1]
        vals = np.array([v for _, v in rows])
        colors = [fs.BLUE] * 6 + [fs.GREY]
        ax.barh(y, vals, color=colors, height=0.62, edgecolor=fs.EDGE, lw=0.4)
        for yi, v in zip(y, vals):
            ax.text(v - 0.03 if v < 0 else v + 0.03, yi, f'{v:+.2f}', va='center', ha='right' if v < 0 else 'left', fontsize=6.5)
        ax.set_yticks(y)
        ax.set_yticklabels([r for r, _ in rows])
        ax.axvline(0, color='black', lw=0.6)
        ax.set_xlim(-1.75, 0.35)
        ax.set_xlabel('Total received power relative to idle (dB)')
        mf.finish(fig, 'fig_loadpower', {
            'raw_data': [str(D / 'early_2025/statistics_20251025_010749.txt')],
            'transformations': ['load rows: gains relative to idle as reported in the file',
                                'switched off: absolute total power minus the idle value of the same file'],
            'uncertainty': 'single measurement per state (exploratory)'})
    print(json.dumps(mf.REPORT['fig_loadpower']['check'], default=str)[:1500])


if __name__ == '__main__':
    todo = sys.argv[1:] or ['contracts', 'loadpower']
    if 'contracts' in todo:
        fig_contracts()
    if 'loadpower' in todo:
        fig_loadpower()
