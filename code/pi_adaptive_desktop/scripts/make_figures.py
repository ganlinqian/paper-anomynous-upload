"""Paper figures for the S&P submission (v7), redrawn with the scientific-visualization skill (see figstyle.py).

Data are exactly those of the v6 figures (fig_results.py, fig_traces.py): stats/paper_stats.json and
stats/supp_stats.json, recomputed from stored per-trial predictions of frozen models, and the stored per-frame
features of the C08/C13 test runs.  Nothing is refit.  Changes from v6 are presentational: drawn at final size and
included at 100 %, Arial 6.5-8 pt, Okabe-Ito colours with line-style/marker/hatch redundancy, legends off the data,
exact 95 % Clopper-Pearson intervals on measured accuracies, and PDFs without dates or producer strings.
Usage: python -I make_figures.py [results] [budget] [traces]      (default: all three)
"""
import json, os, pathlib, sys
import numpy as np
from scipy.stats import beta
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import figstyle as fs  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

S = fs.ROOT
R = pathlib.Path(os.environ.get('TELLTALE_SCENARIO', str(fs.REPOSITORY / 'data/pi_core')))
REPORT = {}


def cp(k, n):
    lo = 0.0 if k == 0 else float(beta.ppf(.025, k, n - k + 1))
    hi = 1.0 if k == n else float(beta.ppf(.975, k + 1, n - k))
    return lo, hi


def finish(fig, name, provenance):
    chk = fs.check_layout(fig)
    rep = fs.save(fig, name, {**provenance, 'layout_check': chk})
    png = next(o['path'] for o in rep['outputs'] if o['format'] == 'png')
    REPORT[name] = {'check': chk, 'outputs': [(pathlib.Path(o['path']).name, o['size_bytes']) for o in rep['outputs']],
                    'preview': fs.ascii_preview(png, cols=150)}
    plt.close(fig)


# ---------------------------------------------------------------- Fig. results: accuracy vs. baselines
def fig_results():
    st = json.loads((S / 'stats/paper_stats.json').read_text(encoding='utf-8'))

    def g(exp, key):
        s = st[exp][key]
        return s['correct'], s['n']
    groups = [
        ('Order bit\n(C08, n=40)', [(20, 40), (24, 40), g('C08_order', 'original/whole_260'), g('C08_order', 'original/temporal_260'), g('C08_order_window', 'call_bracket/temporal_260')]),
        ('Presence bit\n(C08, n=40)', [(20, 40), (23, 40), g('C08_activity', 'original/whole_260'), g('C08_activity', 'relative_reference/whole_260'), g('C08_activity_window', 'call_bracket/whole_260')]),
        ('gzip + legit. load\n(C10, n=64/32)', [(32, 64), g('C10_wait', 'old_frozen_timing_all64/coordinator_elapsed'), g('C10_wait', 'old_frozen_all64/whole_260'), g('C10_wait', 'old_frozen_all64/temporal_260'), g('C10_wait', 'new_calibration/temporal_260')]),
        ('gzip, untraced\n(C13, n=32)', [(16, 32), g('C13_untraced', 'external_timing/both_external_times'), g('C13_untraced', 'original/whole_260'), g('C13_untraced', 'original/temporal_260'), g('C13_untraced', 'C20_C10_calibration_transfer/temporal_260/plain')]),
    ]
    s2 = json.loads((S / 'stats/supp_stats.json').read_text(encoding='utf-8'))['s2']
    m, n2 = s2['models'], s2['n']
    groups.append(('Order, real tools\n(C26, n=%d)' % n2, [(s2['transcript_bound_correct'], n2), (m['elapsed']['correct'], n2), (m['record_whole']['correct'], n2),
                                                            (m['record_temporal']['correct'], n2), (m['call_temporal']['correct'], n2)]))
    methods = [('Transcript-only bound', dict(facecolor='white', hatch='/////', edgecolor='#777777'), False, 'black'),
               ('External timing', dict(facecolor=fs.GREY, edgecolor=fs.EDGE), True, 'black'),
               ('RF whole-record', dict(facecolor=fs.SKY, edgecolor=fs.EDGE), True, 'black'),
               (fs.SYS, dict(facecolor=fs.BLUE, edgecolor=fs.EDGE), True, 'white'),
               (fs.SYS + ' + reference/calibration', dict(facecolor=fs.NAVY, edgecolor=fs.EDGE), True, 'white')]
    with fs.ieee_style():
        fig, ax = plt.subplots(figsize=(fs.FULL_W, 1.62), layout='constrained')
        x = np.arange(len(groups))
        w = 0.155
        values = {}
        for j, (lab, sty, has_ci, tcol) in enumerate(methods):
            xs = x + (j - 2) * w
            ks = np.array([gr[1][j][0] for gr in groups])
            ns = np.array([gr[1][j][1] for gr in groups])
            p = ks / ns
            ax.bar(xs, p, w * 0.9, label=lab, linewidth=0.4, zorder=2, **sty)
            if has_ci:
                lo, hi = np.array([cp(k, n) for k, n in zip(ks, ns)]).T
                ax.errorbar(xs, p, yerr=[p - lo, hi - p], fmt='none', ecolor='black', elinewidth=0.6, capsize=1.6, capthick=0.6, zorder=3)
            for xi, k, n in zip(xs, ks, ns):
                t = ax.text(xi, 0.03, f'{k}/{n}', rotation=90, ha='center', va='bottom', fontsize=6.5, color=tcol, zorder=4)
                if j == 0:
                    t.set_bbox(dict(facecolor='white', edgecolor='none', pad=0.4))
            values[lab] = [f'{k}/{n}' for k, n in zip(ks, ns)]
        ax.axhline(0.5, color='black', lw=0.6, ls=(0, (1, 1.5)), zorder=1)
        ax.set_xticks(x, [gr[0] for gr in groups], fontsize=7.5)
        ax.tick_params(axis='x', length=0)
        ax.set_xlim(-0.55, len(groups) - 0.45)
        ax.set_ylim(0, 1.04)
        ax.set_yticks([0, .25, .5, .75, 1], ['0%', '25%', '50%', '75%', '100%'])
        ax.set_ylabel('Accuracy on new runs')
        fig.legend(loc='outside upper center', ncol=5, frameon=False)
        REPORT['fig_results_values'] = values
        finish(fig, 'fig_results', {
            'raw_data': ['stats/paper_stats.json', 'stats/supp_stats.json (s2)'],
            'transformations': ['correct/total of frozen models on new runs; transcript-only = exact bound of Prop. 1'],
            'uncertainty': 'exact 95% Clopper-Pearson interval on each measured accuracy (none on the transcript bound)'})


# ---------------------------------------------------------------- Fig. budget: hidden-work budget
def fig_budget():
    st = json.loads((S / 'stats/paper_stats.json').read_text(encoding='utf-8'))
    det = [('top3mean_minus_p50', 'top-3 mean', fs.BLUE, 'o', '-'), ('p99_minus_p50', 'p99', fs.VERM, 's', '--'),
           ('max_minus_p50', 'max', fs.GREEN, '^', '-.')]
    durs = [10, 30, 100, 300, 1000]
    panels = [('C09_burst', 'False', 'No load (C09)'), ('C09_burst', 'True', 'Short load (C09)'), ('C15_sustained', 'True', 'Sustained (C15)')]
    fa_x = 2.8
    series = {}
    with fs.ieee_style():
        fig, axs = plt.subplots(1, 3, figsize=(fs.COL_W, 1.58), layout='constrained', sharey=True)
        for ax, (exp, cover, title) in zip(axs, panels):
            for j, (key, lab, col, mk, ls) in enumerate(det):
                c = st[exp]['old_threshold/' + key]['cells']
                xs = [d for d in durs if f'{d}ms|cover={cover}' in c]
                ys = [c[f'{d}ms|cover={cover}']['alerts'] / c[f'{d}ms|cover={cover}']['n'] for d in xs]
                ax.plot(xs, ys, color=col, ls=ls, lw=0.9, marker=mk, ms=3.2, mfc='white', mew=0.8, label=lab, zorder=3)
                fa = c.get(f'0ms|cover={cover}')
                if fa:
                    ax.plot([fa_x * (1 + 0.2 * (j - 1))], [fa['alerts'] / fa['n']], marker='x', ms=3.6, mew=0.9, color=col, ls='none', zorder=4)
                series[f'{title}|{lab}'] = {'ms': xs, 'alert_rate': [round(v, 3) for v in ys],
                                            'false_alarm': (f"{fa['alerts']}/{fa['n']}" if fa else None)}
            ax.set_xscale('log')
            ax.set_xlim(1.8, 1800)
            ax.set_xticks([fa_x, 10, 100, 1000], ['FA', '10', '100', '1k'])
            ax.minorticks_off()
            ax.axvline(5.0, color='0.6', lw=0.5, ls=':')
            ax.set_title(title, fontsize=7.5)
            ax.set_ylim(-0.06, 1.08)
            ax.set_yticks([0, 0.5, 1])
        axs[0].set_ylabel('Alert rate')
        fig.supxlabel('Hidden work per call (ms)', fontsize=8)
        handles = [Line2D([], [], color=col, ls=ls, lw=0.9, marker=mk, ms=3.2, mfc='white', mew=0.8) for _, _, col, mk, ls in det]
        handles.append(Line2D([], [], color='0.25', marker='x', ms=3.6, mew=0.9, ls='none'))
        fig.legend(handles, [d[1] for d in det] + ['false alarm (silent)'], loc='outside upper center', ncol=4, frameon=False)
        REPORT['fig_budget_series'] = series
        finish(fig, 'fig_budget', {
            'raw_data': ['stats/paper_stats.json (C09_burst, C15_sustained; old_threshold/*)'],
            'transformations': ['alert rate per hidden-work duration with thresholds frozen from 4 silent runs of an earlier session'],
            'uncertainty': 'none drawn; n=6 runs per cell (stated in caption)'})


# ---------------------------------------------------------------- Fig. traces: what the witness sees
FRAME_S = 204800 / 20e6
BYTES_PER_FRAME = 2 * 204800


def load_rows(p):
    rows = json.loads(pathlib.Path(p).read_text(encoding='utf-8-sig'))
    return rows if isinstance(rows, list) else rows.get('records', rows)


def mark_frame(row, key):
    return next(x for x in row[key]['marks'] if x['radio'] == '930c')['bytes'] / BYTES_PER_FRAME


def aligned(rows, feat_dir, sel, pre_s=0.5, post_s=None):
    out, bands = [], []
    for r in rows:
        f = pathlib.Path(feat_dir) / f"{r['id']}_930c.npz"
        if not sel(r) or not f.exists():
            continue
        z = np.load(f)
        p, bd = z['power_db'], z['band_db']
        d0, d1 = mark_frame(r, 'before'), mark_frame(r, 'after')
        i0, pre = int(round(d0)), int(round(pre_s / FRAME_S))
        span = int(round((post_s if post_s else (d1 - d0) * FRAME_S + 0.6) / FRAME_S))
        lo, hi = i0 - pre, i0 + span
        if lo < 0 or hi > len(p):
            continue
        out.append(p[lo:hi] - np.median(p[lo:i0]))
        bands.append(bd[lo:hi] - np.median(bd[lo:i0], axis=0))
    return np.arange(-pre, span) * FRAME_S, np.array(out), np.array(bands)


def fig_traces():
    rows08 = load_rows(R / 'confirmation_study/confirm_20261105_035739_c92be0/RESULTS.json')
    f08 = R / 'confirmation_processing_20261105/analysis/features'
    post08 = min(2.75, 4.0 - max(mark_frame(r, 'before') * FRAME_S for r in rows08) - 0.02)
    tOa, Oa, _ = aligned(rows08, f08, lambda r: r.get('family') == 'order' and r['actual_condition'], post_s=post08)
    tOb, Ob, _ = aligned(rows08, f08, lambda r: r.get('family') == 'order' and not r['actual_condition'], post_s=post08)
    tPa, Pa, _ = aligned(rows08, f08, lambda r: r.get('family') == 'trace' and r['actual_condition'], post_s=post08)
    tPb, Pb, _ = aligned(rows08, f08, lambda r: r.get('family') == 'trace' and not r['actual_condition'], post_s=post08)
    rows13 = load_rows(R / 'untraced_wait_study/untracedwait_20261105_061041_b80fac/RESULTS.json')
    f13 = R / 'untraced_processing_20261105/analysis/features'
    tGa, _, GBa = aligned(rows13, f13, lambda r: r['actual_active'], post_s=4.8)
    tGb, _, GBb = aligned(rows13, f13, lambda r: not r['actual_active'], post_s=4.8)
    freqs = (np.arange(64) + 0.5) * (10.0 / 64)
    valid = [i for i in range(64) if i not in (0, 58, 59, 60, 61, 62, 63)]
    ia, ib = np.searchsorted(tGa, 0.05), np.searchsorted(tGa, 2.25)
    sig_a = np.median(GBa[:, ia:ib, :], axis=1)[:, valid]
    sig_b = np.median(GBb[:, ia:ib, :], axis=1)[:, valid]

    # same probes as fig_traces_summary.json of v6, to confirm the redraw uses identical data
    def probe(t, arr, pts):
        med = np.median(arr, axis=0)
        return {f'{x:.2f}s': round(float(med[np.searchsorted(t, x)]), 3) for x in pts}
    new = {'order_MC': probe(tOa, Oa, [-0.2, 0.3, 0.8, 1.3, 1.8, 2.3]), 'order_CM': probe(tOb, Ob, [-0.2, 0.3, 0.8, 1.3, 1.8, 2.3]),
           'pres_active': probe(tPa, Pa, [-0.2, 0.3, 0.8, 1.3, 1.8]), 'pres_silent': probe(tPb, Pb, [-0.2, 0.3, 0.8, 1.3, 1.8])}
    old = json.loads((S / 'figures/fig_traces_summary.json').read_text(encoding='utf-8'))
    diff = max(abs(new[k][q] - old['median_probe'][k][q]) for k in new for q in new[k])
    gz_old = np.array(old['gzip_band_sig_median_db']['active'])
    gz_diff = float(np.max(np.abs(np.round(np.median(sig_a, axis=0), 3) - gz_old)))
    REPORT['fig_traces_data_check'] = {'n': {'order_MC': len(Oa), 'order_CM': len(Ob), 'pres_active': len(Pa), 'pres_silent': len(Pb),
                                             'gzip_active': len(sig_a), 'gzip_silent': len(sig_b)},
                                       'max_abs_diff_vs_v6_median_probes_db': diff, 'max_abs_diff_vs_v6_gzip_signature_db': gz_diff}
    with fs.ieee_style():
        fig, axs = plt.subplots(1, 3, figsize=(fs.FULL_W, 1.70), layout='constrained')

        def band(ax, x, arr, color, ls, label):
            med = np.median(arr, axis=0)
            q1, q3 = np.percentile(arr, [25, 75], axis=0)
            ax.fill_between(x, q1, q3, color=color, alpha=0.2, lw=0)
            ax.plot(x, med, color=color, ls=ls, lw=1.0, label=label)
        band(axs[0], tOa, Oa, fs.VERM, '-', 'memory \u2192 CPU')
        band(axs[0], tOb, Ob, fs.BLUE, '--', 'CPU \u2192 memory')
        band(axs[1], tPa, Pa, fs.VERM, '-', 'hidden 1 s burst')
        band(axs[1], tPb, Pb, fs.BLUE, '--', 'no burst')
        band(axs[2], freqs[valid], sig_a, fs.VERM, '-', 'hidden gzip')
        band(axs[2], freqs[valid], sig_b, fs.BLUE, '--', 'no archiving')
        titles = [f'(a) Order bit (C08, {len(Oa) + len(Ob)} runs)', f'(b) Presence bit (C08, {len(Pa) + len(Pb)} runs)',
                  f'(c) gzip, untraced (C13, {len(sig_a) + len(sig_b)} runs)']
        for ax in axs[:2]:
            ax.axvline(0, color='black', lw=0.5, ls=':')
            ax.set_xlabel('Time since dispatch (s)')
        axs[0].set_ylabel('Rel. received power (dB)')
        axs[2].set_xlabel('|Offset from 1.8 GHz| (MHz)')
        axs[2].set_ylabel('Band power change (dB)')
        # panel title + key as one header block above each panel, so no key sits on the traces
        for ax, title in zip(axs, titles):
            ax.legend(title=title, title_fontsize=8, loc='lower left', bbox_to_anchor=(0, 1.0), ncol=2, alignment='left',
                      frameon=False, borderaxespad=0.2, borderpad=0.1)
        finish(fig, 'fig_traces', {
            'raw_data': [str(R / 'confirmation_study/confirm_20261105_035739_c92be0/RESULTS.json'), str(f08),
                         str(R / 'untraced_wait_study/untracedwait_20261105_061041_b80fac/RESULTS.json'), str(f13)],
            'transformations': ['per-run reference = median of the 0.5 s pre-dispatch window (power and each band)',
                                'dispatch alignment by receiver byte marks; (c) per-run median band change over 0.05-2.25 s after dispatch',
                                'bands 0 and 58-63 excluded as in v6'],
            'uncertainty': 'median and interquartile band across runs'})


if __name__ == '__main__':
    todo = sys.argv[1:] or ['results', 'budget', 'traces']
    for name in todo:
        {'results': fig_results, 'budget': fig_budget, 'traces': fig_traces}[name]()
    out = {k: v for k, v in REPORT.items()}
    (fs.OUT / 'make_figures_report.json').write_text(json.dumps({k: (v if not isinstance(v, dict) else {kk: vv for kk, vv in v.items() if kk != 'preview'})
                                                                  for k, v in out.items()}, indent=1, default=str), encoding='utf-8')
    for k, v in REPORT.items():
        if isinstance(v, dict) and 'preview' in v:
            print(f'===== {k}: outputs {v["outputs"]}')
            print(json.dumps(v['check'], indent=None, default=str))
            print(v['preview'])
        else:
            print(f'===== {k}:', json.dumps(v, default=str))
