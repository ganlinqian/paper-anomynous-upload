"""v9 figure: Observations across two hosts (Fig. obs).

(a) Raspberry Pi 4, order fixture (C08 test runs), total received power at the 1.8 GHz CPU clock.
(b) x86 desktop (i7-11700), order fixture (desktop test batch), band-average power at 1.38 GHz.
(c) x86 desktop, hidden 1 GiB staging with the system tar during a 3 s wait vs. an idle wait (test batch).
(d) x86 desktop sweep: per-band change under memory-streaming and compute loads relative to the
    bracketing idle sweeps (two repetitions each), 10-2510 MHz.
Every run is referenced to its own pre-dispatch window; alignment uses coordinator byte marks.
usage: python -I make_figures_v9.py
"""
import json, pathlib, sys
import numpy as np
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import figstyle as fs  # noqa: E402
import make_figures as mf  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

S = fs.ROOT
D = S / 'desktop_em'
fs.OUT = fs.FIG_ROOT / 'v9'
FRAME = 204_800
FRAME_S = FRAME / 20e6


def desktop_traces(batch, kind, variant, pre_s=0.5, post_s=None):
    man = json.loads((D / 'runs' / batch / 'manifest.json').read_text(encoding='utf-8'))
    out = []
    for r in man['runs']:
        if r['kind'] != kind or r['variant'] != variant:
            continue
        F = np.load(D / 'runs' / batch / (r['run'] + '.npy'))
        good = ~np.all(np.isnan(F[:, :64]), 0)
        B = 10 * np.log10(np.nanmean(10 ** (F[:, :64][:, good] / 10), 1))
        i0 = int(round(r['mark1_sample'] / FRAME))
        pre = int(round(pre_s / FRAME_S))
        span = int(round((post_s or ((r['mark2_sample'] - r['mark1_sample']) / 20e6 + 0.3)) / FRAME_S))
        lo, hi = i0 - pre, min(i0 + span, len(B))
        out.append(B[lo:hi] - np.median(B[lo:i0]))
    n = min(len(x) for x in out)
    arr = np.array([x[:n] for x in out])
    return (np.arange(n) - pre) * FRAME_S, arr


def sweep_deltas():
    d = D / 'sweep_20261106'
    meta = json.loads((d / 'meta.json').read_text(encoding='utf-8'))
    los = np.array(meta['los_hz']) / 1e6
    NF = 1024
    keep = np.ones(NF, bool); keep[NF // 2 - 8: NF // 2 + 8] = False; keep[:64] = False; keep[-64:] = False
    P = {s['k']: np.load(d / f"sweep_{s['k']:02d}_{s['cond']}.npy") for s in meta['sweeps']}
    cond = {s['k']: s['cond'] for s in meta['sweeps']}
    band = {k: 10 * np.log10(np.nanmean(10 ** (v[:, keep] / 10), axis=1)) for k, v in P.items()}
    res = {}
    for kind in ('m', 'c'):
        res[kind] = [band[k] - (band[k - 1] + band[k + 1]) / 2 for k in sorted(band) if cond[k] == kind]
    idle = [k for k in sorted(band) if cond[k] == 'i']
    drift = [band[b] - band[a] for a, b in zip(idle[:-1], idle[1:])]
    return los, res, drift


def fig_obs():
    rows08 = mf.load_rows(mf.R / 'confirmation_study/confirm_20261105_035739_c92be0/RESULTS.json')
    f08 = mf.R / 'confirmation_processing_20261105/analysis/features'
    post08 = min(2.75, 4.0 - max(mf.mark_frame(r, 'before') * mf.FRAME_S for r in rows08) - 0.02)
    tOa, Oa, _ = mf.aligned(rows08, f08, lambda r: r.get('family') == 'order' and r['actual_condition'], post_s=post08)
    tOb, Ob, _ = mf.aligned(rows08, f08, lambda r: r.get('family') == 'order' and not r['actual_condition'], post_s=post08)
    tDa, Da = desktop_traces('test', 'order', 'MC', post_s=2.3)
    tDb, Db = desktop_traces('test', 'order', 'CM', post_s=2.3)
    tHa, Ha = desktop_traces('test', 'wait', 'hidden', post_s=3.3)
    tHb, Hb = desktop_traces('test', 'wait', 'silent', post_s=3.3)
    los, dl, drift = sweep_deltas()
    with fs.ieee_style():
        fig, axs = plt.subplots(1, 4, figsize=(fs.FULL_W, 1.78), layout='constrained')

        def band(ax, x, arr, color, ls, label):
            med = np.median(arr, axis=0)
            q1, q3 = np.percentile(arr, [25, 75], axis=0)
            ax.fill_between(x, q1, q3, color=color, alpha=0.2, lw=0)
            ax.plot(x, med, color=color, ls=ls, lw=1.0, label=label)
        band(axs[0], tOa, Oa, fs.VERM, '-', 'mem \u2192 CPU')
        band(axs[0], tOb, Ob, fs.BLUE, '--', 'CPU \u2192 mem')
        band(axs[1], tDa, Da, fs.VERM, '-', 'mem \u2192 CPU')
        band(axs[1], tDb, Db, fs.BLUE, '--', 'CPU \u2192 mem')
        band(axs[2], tHa, Ha, fs.VERM, '-', 'hidden tar')
        band(axs[2], tHb, Hb, fs.BLUE, '--', 'idle wait')
        x = los
        ism = (x >= 2390) & (x <= 2500)          # 2.4 GHz ISM band: the desktop's own Wi-Fi link, not shown
        for i, dm in enumerate(dl['m']):
            axs[3].plot(x, np.where(ism, np.nan, dm), color=fs.VERM, lw=0.6, ls='-' if i == 0 else ':', label='memory' if i == 0 else None)
        for i, dc in enumerate(dl['c']):
            axs[3].plot(x, np.where(ism, np.nan, dc), color=fs.BLUE, lw=0.6, ls='--' if i == 0 else '-.', label='compute' if i == 0 else None)
        axs[3].set_xlim(0, 2400)
        axs[3].axvspan(1370, 1490, color=fs.GREY, alpha=0.18, lw=0)
        axs[3].set_ylim(-3.0, 6.0)
        titles = [f'(a) Pi 4, order ({len(Oa) + len(Ob)} runs)', f'(b) x86 desktop, order ({len(Da) + len(Db)})',
                  f'(c) x86, hidden staging ({len(Ha) + len(Hb)})', '(d) x86 sweep: load \u2212 idle']
        for ax in axs[:3]:
            ax.axvline(0, color='black', lw=0.5, ls=':')
            ax.set_xlabel('Time since dispatch (s)')
        axs[0].set_ylabel('Rel. power (dB)')
        axs[3].set_xlabel('Frequency (MHz)')
        axs[3].set_ylabel('\u0394 band power (dB)')
        for ax, title in zip(axs, titles):
            ax.legend(title=title, title_fontsize=7.5, loc='lower left', bbox_to_anchor=(0, 1.0), ncol=2, alignment='left',
                      frameon=False, borderaxespad=0.2, borderpad=0.1, handlelength=1.6, columnspacing=0.8)
        mf.finish(fig, 'fig_obs', {
            'raw_data': [str(mf.R / 'confirmation_study/confirm_20261105_035739_c92be0/RESULTS.json'), str(f08),
                         str(D / 'runs/test/manifest.json'), str(D / 'sweep_20261106/meta.json')],
            'transformations': ['per-run reference = median of the 0.5 s pre-dispatch window',
                                'desktop: band-average of 57 valid 156-kHz bands at 1.38 GHz; alignment by byte marks',
                                'sweep: 20-MHz band mean (excl. DC and edges) of each load sweep minus mean of the two bracketing idle sweeps'],
            'uncertainty': 'median and interquartile band across runs; (d) each repetition drawn separately'})
    print(json.dumps({k: v.get('check', v) if isinstance(v, dict) else v for k, v in mf.REPORT.items() if k == 'fig_obs'}, default=str)[:2000])


def regen_named():
    # Regenerate the submission figures whose labels carry the system name, into figures/v9.
    import make_figures_submission as m8
    fs.OUT = fs.FIG_ROOT / 'v9'
    for name in ('results', 'roc', 'inserts'):
        m8.BUILDERS[name]()
        print('regenerated', name, flush=True)


if __name__ == '__main__':
    todo = sys.argv[1:] or ['obs']
    if 'obs' in todo:
        fig_obs()
    if 'named' in todo:
        regen_named()
