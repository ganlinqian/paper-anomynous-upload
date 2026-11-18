"""Submission figures from frozen measurements, same style and checks (figstyle.py).

New: throttling frontier (RQ6), ROC curves (RQ1/RQ2/RQ6), session drift (RQ3), band-resolved maps (Sec. 4),
prospective-protocol timeline (Sec. 5), and the measured mini-plots embedded in the teaser and system figures.
All inputs are stored statistics, per-run prediction files of frozen models, frame features, and the batch/freeze
receipts; nothing is refit.  Usage: python -I make_figures_submission.py [name ...]   (default: all)
"""
import csv, datetime as dt, json, pathlib, sys
import numpy as np
from scipy.stats import beta
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import figstyle as fs  # noqa: E402
import make_figures as mf  # noqa: E402  (v7 builders: results, budget, traces)
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

S = mf.S
R = mf.R
E = S / 'experiments' / 'campaigns'
A = R / 'analysis_extensions'
fs.OUT = fs.FIG_ROOT / 'submission'
REPORT = mf.REPORT
GREY_D = '#7A7A7A'


def b(x):
    return str(x).strip().lower() == 'true'


def rows_of(p):
    with open(p, encoding='utf-8-sig') as fh:
        return list(csv.DictReader(fh))


def cp(k, n):
    return mf.cp(k, n)


def auc(pos, neg):
    s = sum(1.0 if p > q else (0.5 if p == q else 0.0) for p in pos for q in neg)
    return s / (len(pos) * len(neg))


def roc(pos, neg):
    th = sorted(set(pos) | set(neg), reverse=True)
    fpr, tpr = [0.0], [0.0]
    for t in th:
        fpr.append(sum(q >= t for q in neg) / len(neg))
        tpr.append(sum(p >= t for p in pos) / len(pos))
    return np.array(fpr), np.array(tpr)


def vscore(r):
    for k in ('task_conditioned_score', 'conditioned_score', 'score'):
        if r.get(k) not in (None, ''):
            return float(r[k])
    pa = float(r['p_actual'])
    return pa if not b(r['expected']) else 1 - pa


# ---------------------------------------------------------------- RQ6: throttling frontier
DUTY = {'gzip16': (1.0, False), 'gzip8_d50': (0.5, False), 'gzip6_d37': (0.375, False), 'gzip4_d25': (0.25, False),
        'gzip3_d19': (0.1875, False), 'gzip2_d12': (0.125, False), 'gzip1_d06': (0.0625, False), 'gzip05_d03': (0.03125, False),
        'gzip2_d06': (0.0625, True), 'gzip1_d03': (0.03125, True)}


def _kn(v):
    return (v['alerts'], v['n']) if isinstance(v, dict) else (v[0], v[1])


def fig_frontier():
    supp = json.loads((S / 'stats/supp_stats.json').read_text(encoding='utf-8'))
    c29 = json.loads((S / 'stats/c29_stats.json').read_text(encoding='utf-8'))
    single, diverse, low = 'C10_transfer/temporal_260/plain', 'C27_diverse/call_temporal', 'C29/call_whole_sesscal'
    by = {  # model -> list of (batch, by_condition) for batches collected after the model was frozen
        'single': [('C24', supp['s1']['detectors'][single]['by_condition']), ('C27', supp['s1b']['detectors'][single]['by_condition']),
                   ('C28', supp['s1c']['detectors'][single]['by_condition']), ('C29', c29['all_detectors'][single])],
        'diverse': [('C27', supp['s1b']['detectors'][diverse]['by_condition']), ('C28', supp['s1c']['detectors'][diverse]['by_condition']),
                    ('C29', c29['all_detectors'][diverse])],
        'low': [('C29', c29['all_detectors'][low])]}
    style = {'single': ('Single-workload model', fs.GREEN, 'v', ':'), 'diverse': ('Diverse model (C27)', fs.BLUE, 'o', '-'),
             'low': ('Low-duty model + session calibration (C29)', fs.VERM, 's', '--')}
    rate = {}
    with fs.ieee_style():
        fig, (ax, bx) = plt.subplots(1, 2, figsize=(fs.FULL_W, 2.25), layout='constrained', gridspec_kw={'width_ratios': [3.3, 1.0]})
        xs_all = sorted({d for d, _ in DUTY.values()})
        for j, m in enumerate(('single', 'diverse', 'low')):
            lab, col, mk, ls = style[m]
            pooled, per_batch = {}, []
            fa = [0, 0]
            for batch, cond in by[m]:
                k, n = _kn(cond['silent'])
                fa[0] += k; fa[1] += n
                for c, v in cond.items():
                    if c not in DUTY:
                        continue
                    k, n = _kn(v)
                    key = DUTY[c]
                    pooled.setdefault(key, [0, 0]); pooled[key][0] += k; pooled[key][1] += n
                    per_batch.append((key, k / n, batch))
            off = 1 + 0.035 * (j - 1)
            for stretched in (False, True):
                pts = sorted((d, kn) for (d, s), kn in pooled.items() if s == stretched)
                if not pts:
                    continue
                xd = np.array([d for d, _ in pts]) * off * (1.06 if stretched else 1.0)
                p = np.array([k / n for _, (k, n) in pts])
                lo, hi = np.array([cp(k, n) for _, (k, n) in pts]).T
                if not stretched:
                    ax.plot(xd, p, color=col, ls=ls, lw=1.1, marker=mk, ms=4, mfc=col, mec=col, zorder=4,
                            label=f'{lab}; false alarms {fa[0]}/{fa[1]}')
                else:
                    ax.plot(xd, p, ls='none', marker=mk, ms=4, mfc='white', mec=col, mew=0.9, zorder=4)
                ax.errorbar(xd, p, yerr=[p - lo, hi - p], fmt='none', ecolor=col, elinewidth=0.6, capsize=1.4, capthick=0.6, zorder=3)
            for (d, s), r, batch in per_batch:
                ax.plot([d * off * (1.06 if s else 1.0)], [r], ls='none', marker='.', ms=2.2, color=col, alpha=0.5, zorder=2)
            rate[m] = {f'{d * 100:g}%' + (' stretched' if s else ''): f'{k}/{n}' for (d, s), (k, n) in sorted(pooled.items())}
            rate[m]['false_alarms'] = f'{fa[0]}/{fa[1]}'
        mibs = {}
        for st in ('s1', 's1b', 's1c'):
            for c, v in supp[st]['hidden_work'].items():
                if c in DUTY and not DUTY[c][1]:
                    mibs.setdefault(DUTY[c][0], []).append(v['mib_per_s_median'])
        ax.set_xscale('log', base=2)
        ticks = [d for d in xs_all]
        ax.set_xticks(ticks, [f'{d * 100:g}%\n{np.median(mibs[d]):.1f}' if d in mibs else f'{d * 100:g}%' for d in ticks])
        ax.minorticks_off()
        ax.set_xlim(0.025, 1.25)
        ax.set_ylim(-0.04, 1.06)
        ax.set_yticks([0, .25, .5, .75, 1], ['0%', '25%', '50%', '75%', '100%'])
        ax.set_ylabel('Hidden-work runs detected')
        ax.set_xlabel('Duty cycle of hidden gzip (top line) and median throughput in MiB/s (bottom line)')
        handles, labels = ax.get_legend_handles_labels()
        handles.append(Line2D([], [], ls='none', marker='o', mfc='white', mec='0.3', ms=4))
        labels.append('hollow: twice the work stretched over 2.2 s')
        fig.legend(handles, labels, loc='outside upper center', ncol=2, frameon=False, fontsize=6.5)
        ax.set_title('(a) Throttled hidden work', fontsize=8)
        # (b) input and tool changes at full speed
        cats = [('text8', 'text, 8 MiB', 's1'), ('json8', 'JSON, 8 MiB', 's1b'), ('bzip2_r', 'bzip2, 4 MiB', 's1b')]
        yb = np.arange(len(cats))
        vals = {}
        for i, (c, lab, st) in enumerate(cats):
            for j, (m, det, col) in enumerate((('single', single, fs.GREEN), ('diverse', diverse, fs.BLUE))):
                d = supp[st]['detectors'].get(det, {}).get('by_condition', {})
                if c not in d:
                    continue
                k, n = _kn(d[c])
                lo, hi = cp(k, n)
                y = i + (j - 0.5) * 0.36
                bx.barh(y, k / n, 0.32, color=col if m == 'diverse' else 'white', edgecolor=col, hatch=None if m == 'diverse' else '////', lw=0.8)
                bx.errorbar([k / n], [y], xerr=[[k / n - lo], [hi - k / n]], fmt='none', ecolor='black', elinewidth=0.6, capsize=1.4, capthick=0.6)
                bx.text(1.04, y, f'{k}/{n}', va='center', ha='left', fontsize=6.5)
                vals[f'{lab}|{m}'] = f'{k}/{n}'
        bx.set_yticks(yb, [c[1] for c in cats])
        bx.invert_yaxis()
        bx.set_xlim(0, 1.0)
        bx.set_xticks([0, .5, 1], ['0%', '50%', '100%'])
        bx.set_xlabel('Detected')
        bx.set_title('(b) New input or tool', fontsize=8)
        REPORT['fig_frontier_values'] = {'pooled': rate, 'inputs_tools': vals}
        mf.finish(fig, 'fig_frontier', {
            'raw_data': ['stats/supp_stats.json (s1=C24, s1b=C27, s1c=C28)', 'stats/c29_stats.json (C29)'],
            'transformations': ['alerts/runs of frozen models, pooled per duty cycle over all batches collected after the model was frozen'],
            'uncertainty': 'exact 95% Clopper-Pearson intervals on pooled rates; small dots are individual batches (n=8 each)'})


# ---------------------------------------------------------------- ROC curves
def fig_roc():
    c08 = rows_of(A / 'early_confirm_20261105/reports/EARLY_CONFIRMATION_ORDER_a27de29479e9/all_predictions.csv')
    c13 = rows_of(A / 'untraced_wait_report_20261105/predictions.csv')
    c26 = rows_of(E / 's2test_20261106_032920_dddf78/predictions.csv')
    c27s = rows_of(E / 's1b_20261106_035740_995bcb/predictions.csv')
    c27d = rows_of(E / 's1b_20261106_035740_995bcb/predictions_diverse.csv')

    def sel(rows, **kw):
        return [r for r in rows if all(r.get(k) == v for k, v in kw.items())]

    def pv(rows, score=vscore, viol=lambda r: b(r['violation'])):
        return [score(r) for r in rows if viol(r)], [score(r) for r in rows if not viol(r)]

    act = lambda r: b(r['actual_active'])  # noqa: E731  (wait contract forbids side work: violation = activity)
    sc = lambda r: float(r['score'])  # noqa: E731
    panels = [
        ('(a) Order bit (C08)', [(fs.SYS, fs.BLUE, '-', pv(sel(c08, variant='original', model='temporal_260'))),
                                 ('RF whole-record', fs.SKY, '--', pv(sel(c08, variant='original', model='whole_260')))]),
        ('(b) Real installer (C26)', [(fs.SYS + ' (call window)', fs.BLUE, '-', pv(sel(c26, model='call_temporal'), score=sc)),
                                      ('RF whole-record', fs.SKY, '--', pv(sel(c26, model='record_whole'), score=sc)),
                                      ('External timing', fs.VERM, '-.', pv(sel(c26, model='elapsed'), score=sc))]),
        ('(c) Untraced gzip (C13)', [(fs.SYS + ' + C10 calib.', fs.NAVY, '-', pv(sel(c13, branch='C20_C10_calibration_transfer', model='temporal_260/plain'))),
                                     (fs.SYS + ' (C07 frozen)', fs.BLUE, '-', pv(sel(c13, branch='original', model='temporal_260'))),
                                     ('RF whole-record', fs.SKY, '--', pv(sel(c13, branch='original', model='whole_260'))),
                                     ('External timing', fs.VERM, '-.', pv(sel(c13, branch='external_timing', model='both_external_times')))]),
        ('(d) Adaptive hidden work (C27)', [('Diverse model', fs.BLUE, '-', pv(sel(c27d, detector='C27_diverse/call_temporal'), score=sc, viol=act)),
                                            ('Single-workload model', fs.GREEN, ':', pv(sel(c27s, detector='C10_transfer/temporal_260/plain'), score=sc, viol=act))]),
    ]
    aucs = {}
    with fs.ieee_style():
        fig, axs = plt.subplots(1, 4, figsize=(fs.FULL_W, 2.7), layout='constrained', sharey=True)
        for ax, (title, curves) in zip(axs, panels):
            ax.plot([0, 1], [0, 1], color='0.6', lw=0.6, ls=(0, (1, 1.5)), zorder=1)
            for lab, col, ls, (pos, neg) in curves:
                f, t = roc(pos, neg)
                a = auc(pos, neg)
                aucs[f'{title}|{lab}'] = {'auc': round(a, 3), 'n_pos': len(pos), 'n_neg': len(neg)}
                ax.step(f, t, where='post', color=col, ls=ls, lw=1.1, label=f'{lab}, {a:.2f}', zorder=3)
            ax.set_xlim(-0.02, 1.02); ax.set_ylim(-0.02, 1.02)
            ax.set_xticks([0, .5, 1], ['0', '0.5', '1']); ax.set_yticks([0, .5, 1], ['0', '0.5', '1'])
            ax.set_xlabel('False-positive rate')
            ax.set_title(title, fontsize=8)
            ax.legend(loc='upper left', bbox_to_anchor=(-0.02, -0.25), frameon=False, fontsize=6.5, handlelength=1.6, borderaxespad=0.1,
                      labelspacing=0.25, title='curve, AUC', title_fontsize=6.5, alignment='left')
        axs[0].set_ylabel('True-positive rate')
        REPORT['fig_roc_auc'] = aucs
        mf.finish(fig, 'fig_roc', {
            'raw_data': ['C08/C13 all_predictions.csv (ws_pi analysis_extensions)', 'C26/C27 predictions*.csv (experiments/campaigns)'],
            'transformations': ['ROC of frozen-model scores on new runs; violation = positive class'],
            'uncertainty': 'none drawn; n per panel in caption'})


# ---------------------------------------------------------------- RQ3: drift
FRAME_S = mf.FRAME_S


def _ref_levels(results_json, feat_dir):
    rows = mf.load_rows(results_json)
    out = []
    for r in rows:
        f = pathlib.Path(feat_dir) / f"{r['id']}_930c.npz"
        if not f.exists():
            continue
        z = np.load(f)
        w = z['sample_counts']
        end = np.cumsum(w) / 20e6
        m = end <= 0.2
        if m.sum() < 3:
            continue
        out.append(float(10 * np.log10(np.average(10 ** (z['power_db'][m] / 10), weights=w[m]))))
    return out


def fig_drift():
    sus = next((R / 'sustained_processing_20261105').rglob('*_930c.npz')).parent
    batches = [
        ('C08', R / 'confirmation_study/confirm_20261105_035739_c92be0/RESULTS.json', R / 'confirmation_processing_20261105/analysis/features', 1),
        ('C09', R / 'burst_confirmation_study/burstconfirm_20261105_043818_8bdb76/RESULTS.json', R / 'confirmation_processing_20261105/analysis/features', 1),
        ('C10', R / 'wait_confirmation_study/waitconfirm_20261105_051433_3df228/RESULTS.json', R / 'confirmation_processing_20261105/analysis/features', 1),
        ('C13', R / 'untraced_wait_study/untracedwait_20261105_061041_b80fac/RESULTS.json', R / 'untraced_processing_20261105/analysis/features', 1),
        ('C15', R / 'sustained_burst_study/sustainedburst_20261105_063509_c737ee/RESULTS.json', sus, 1),
        ('C24', E / 's1_20261106_021046_a5bd83/RESULTS.json', E / 's1_20261106_021046_a5bd83/features', 2),
        ('C25', E / 's3_20261106_024815_0b8db7/RESULTS.json', E / 's3_20261106_024815_0b8db7/features', 2),
        ('C26', E / 's2test_20261106_032920_dddf78/RESULTS.json', E / 's2test_20261106_032920_dddf78/features', 2),
        ('C27', E / 's1b_20261106_035740_995bcb/RESULTS.json', E / 's1b_20261106_035740_995bcb/features', 2),
        ('C28', E / 's1c_20261106_065736_99d08a/RESULTS.json', E / 's1c_20261106_065736_99d08a/features', 2),
        ('C29', E / 's1d_20261106_083646_2fa3ac/RESULTS.json', E / 's1d_20261106_083646_2fa3ac/features', 2)]
    lv = {name: _ref_levels(rj, fd) for name, rj, fd, _ in batches}
    base = float(np.median(lv['C08']))
    med = {k: float(np.median(v)) - base for k, v in lv.items()}
    day1 = [k for k, _, _, d in batches if d == 1]
    stats = {'n': {k: len(v) for k, v in lv.items()}, 'median_rel_c08_db': {k: round(v, 3) for k, v in med.items()},
             'range_day1_medians_db': round(max(med[k] for k in day1) - min(med[k] for k in day1), 3),
             'range_all_medians_db': round(max(med.values()) - min(med.values()), 3)}
    pres = rows_of(A / 'early_confirm_20261105/reports/EARLY_CONFIRMATION_TRACE_103f4acc7876/all_predictions.csv')
    rng = np.random.default_rng(20261106)
    with fs.ieee_style():
        fig, (ax, bx) = plt.subplots(1, 2, figsize=(fs.FULL_W, 1.95), layout='constrained', gridspec_kw={'width_ratios': [2.3, 1.0]})
        for i, (name, _, _, day) in enumerate(batches):
            y = np.array(lv[name]) - base
            x = i + rng.uniform(-0.22, 0.22, len(y))
            ax.plot(x, y, ls='none', marker='o', ms=2.0, mfc='none', mec=fs.BLUE if day == 1 else fs.VERM, mew=0.5, alpha=0.75, zorder=2)
            ax.plot([i - 0.32, i + 0.32], [med[name]] * 2, color='black', lw=1.2, zorder=3)
        ax.axvline(len(day1) - 0.5, color='0.5', lw=0.6, ls=':')
        ax.text(len(day1) / 2 - 0.5, 0.98, 'Nov 5, 03:57-06:47 UTC', transform=ax.get_xaxis_transform(), ha='center', va='top', fontsize=6.5)
        ax.text(len(day1) + (len(batches) - len(day1)) / 2 - 0.5, 0.98, 'Nov 6, 02:10-09:18 UTC', transform=ax.get_xaxis_transform(),
                ha='center', va='top', fontsize=6.5)
        ax.set_xticks(range(len(batches)), [n for n, *_ in batches])
        ax.set_xlim(-0.6, len(batches) - 0.4)
        lo, hi = min(min(np.array(v) - base) for v in lv.values()), max(max(np.array(v) - base) for v in lv.values())
        ax.set_ylim(lo - 0.05, hi + 0.22 * (hi - lo))
        ax.set_ylabel('Idle level vs. C08 median (dB)')
        ax.set_title('(a) Pre-dispatch idle level per run (bar: batch median)', fontsize=8)
        # (b) C08 presence bit: frozen scores before/after silence referencing
        cols = [('original', 'frozen'), ('relative_reference', '+ silence ref.')]
        acc = {}
        for i, (var, lab) in enumerate(cols):
            rs = [r for r in pres if r['variant'] == var and r['model'] == 'whole_260']
            for r in rs:
                a_ = b(r['actual'])
                x = i + (0.16 if a_ else -0.16) + rng.uniform(-0.09, 0.09)
                bx.plot([x], [float(r['p_actual'])], ls='none', marker='^' if a_ else 'o', ms=2.6, mfc='none',
                        mec=fs.VERM if a_ else fs.BLUE, mew=0.6, zorder=3)
            acc[lab] = f"{sum(b(r['violation']) == b(r['alert']) for r in rs)}/{len(rs)}"
        bx.axhline(0.5, color='black', lw=0.6, ls='--', zorder=1)
        bx.set_xticks([0, 1], [f'{lab}\n({acc[lab]} correct)' for _, lab in cols])
        bx.set_xlim(-0.55, 1.55); bx.set_ylim(-0.04, 1.04)
        bx.set_yticks([0, .5, 1])
        bx.set_ylabel('P(activity) of frozen model')
        bx.set_title('(b) C08 presence bit', fontsize=8)
        stats['presence_accuracy'] = acc
        REPORT['fig_drift_stats'] = stats
        mf.finish(fig, 'fig_drift', {
            'raw_data': ['frame features (power_db, sample_counts) of all runs of the listed test batches', 'C08 presence all_predictions.csv'],
            'transformations': ['idle level = power-weighted mean frame power over the first 0.2 s of each recording, minus the C08 median'],
            'uncertainty': 'all runs shown; bars are batch medians'})


# ---------------------------------------------------------------- band-resolved maps
def _order_aligned_bands(rows, fd, sel, pre_s=0.5, post_s=2.6):
    _, _, B = mf.aligned(rows, fd, sel, pre_s=pre_s, post_s=post_s)
    return B


def fig_spectro():
    rows08 = mf.load_rows(R / 'confirmation_study/confirm_20261105_035739_c92be0/RESULTS.json')
    f08 = R / 'confirmation_processing_20261105/analysis/features'
    post08 = min(2.75, 4.0 - max(mf.mark_frame(r, 'before') * FRAME_S for r in rows08) - 0.02)
    t, _, Ba = mf.aligned(rows08, f08, lambda r: r.get('family') == 'order' and r['actual_condition'], post_s=post08)
    _, _, Bb = mf.aligned(rows08, f08, lambda r: r.get('family') == 'order' and not r['actual_condition'], post_s=post08)
    rows13 = mf.load_rows(R / 'untraced_wait_study/untracedwait_20261105_061041_b80fac/RESULTS.json')
    f13 = R / 'untraced_processing_20261105/analysis/features'
    tg, _, Ga = mf.aligned(rows13, f13, lambda r: r['actual_active'], post_s=4.8)
    _, _, Gb = mf.aligned(rows13, f13, lambda r: not r['actual_active'], post_s=4.8)
    valid = [i for i in range(64) if i not in (0, 58, 59, 60, 61, 62, 63)]
    freqs = (np.arange(64) + 0.5) * (10.0 / 64)
    ma, mb = np.median(Ba, axis=0)[:, valid], np.median(Bb, axis=0)[:, valid]
    dg = (np.median(Ga, axis=0) - np.median(Gb, axis=0))[:, valid]
    # smooth the gzip difference over 5 frames (51 ms) for display only
    k = np.ones(5) / 5
    dgs = np.apply_along_axis(lambda c: np.convolve(c, k, mode='same'), 0, dg)
    v1 = float(np.ceil(np.percentile(np.abs(np.r_[ma.ravel(), mb.ravel()]), 99) * 2) / 2)
    v2 = float(np.ceil(np.percentile(np.abs(dgs), 99) * 20) / 20)
    ext = lambda tt: [tt[0], tt[-1] + FRAME_S, freqs[valid][0] - 10 / 128, freqs[valid][-1] + 10 / 128]  # noqa: E731
    with fs.ieee_style():
        fig, axs = plt.subplots(1, 3, figsize=(fs.FULL_W, 1.85), layout='constrained', gridspec_kw={'width_ratios': [1, 1, 1.35]})
        im1 = None
        for ax, m, title in ((axs[0], mb, '(a) CPU → memory (compliant)'), (axs[1], ma, '(b) memory → CPU (violating)')):
            im1 = ax.imshow(m.T, aspect='auto', origin='lower', extent=ext(t), cmap='RdBu_r', vmin=-v1, vmax=v1, interpolation='nearest')
            ax.axvline(0, color='black', lw=0.5, ls=':')
            ax.set_title(title, fontsize=8)
            ax.set_xlabel('Time since dispatch (s)')
        axs[0].set_ylabel('|Offset from 1.8 GHz| (MHz)')
        cb1 = fig.colorbar(im1, ax=axs[:2], shrink=0.95, pad=0.01, aspect=22)
        cb1.set_label('Band power change (dB)')
        im2 = axs[2].imshow(dgs.T, aspect='auto', origin='lower', extent=ext(tg), cmap='RdBu_r', vmin=-v2, vmax=v2, interpolation='nearest')
        axs[2].axvline(0, color='black', lw=0.5, ls=':')
        axs[2].set_title('(c) Hidden gzip minus no archiving (C13)', fontsize=8)
        axs[2].set_xlabel('Time since dispatch (s)')
        cb2 = fig.colorbar(im2, ax=axs[2], shrink=0.95, pad=0.01, aspect=22)
        cb2.set_label('Difference of medians (dB)')
        REPORT['fig_spectro_stats'] = {'order_colour_limit_db': v1, 'gzip_colour_limit_db': v2, 'n_order': [len(Bb), len(Ba)], 'n_gzip': [len(Ga), len(Gb)],
                                       'gzip_diff_max_abs_db': round(float(np.abs(dgs).max()), 3),
                                       'order_first_second_mean_db': {'mem_cpu': [round(float(ma[(t >= 0) & (t < 1)].mean()), 2), round(float(ma[(t >= 1) & (t < 2)].mean()), 2)],
                                                                      'cpu_mem': [round(float(mb[(t >= 0) & (t < 1)].mean()), 2), round(float(mb[(t >= 1) & (t < 2)].mean()), 2)]}}
        mf.finish(fig, 'fig_spectro', {
            'raw_data': ['C08 and C13 frame features (band_db) of all test runs'],
            'transformations': ['per-run reference = median of 0.5 s pre-dispatch window per band', 'median over runs; (c) difference of medians smoothed over 5 frames for display'],
            'uncertainty': 'medians over 20 (order) and 16 (gzip) runs per condition'})


# ---------------------------------------------------------------- protocol timeline
def _utc(s):
    return dt.datetime.fromisoformat(s.replace('Z', '+00:00')).replace(tzinfo=None)


def _span(d):
    fz = json.loads((d / 'FREEZE.json').read_text(encoding='utf-8-sig'))['utc']
    c = d / 'COMPLETE.json'
    if c.exists():
        end = json.loads(c.read_text(encoding='utf-8-sig'))['utc']
        return _utc(fz), _utc(end)
    # interrupted batch: last write of RESULTS.json (local clock UTC-8 on the desktop)
    m = dt.datetime.fromtimestamp((d / 'RESULTS.json').stat().st_mtime, dt.timezone.utc).replace(tzinfo=None)
    return _utc(fz), m


def fig_timeline():
    lanes = ['Training / development', 'Order / presence', 'Hidden bursts', 'Hidden gzip', 'Adaptive / clock', 'Real installer']
    ylane = {l: len(lanes) - 1 - i for i, l in enumerate(lanes)}
    bars = [  # (lane, label, dirs, kind, label placement)
        ('Training / development', 'training (158)', [R / 'positive_20261104_163253_188606', R / 'io_wait_study/wait_20261104_180736_75e384'], 'dev', 'in'),
        ('Order / presence', '', [R / 'confirmation_study/confirm_20261105_032747_8137bb'], 'int', None),
        ('Order / presence', 'C08', [R / 'confirmation_study/confirm_20261105_035739_c92be0'], 'test', 'in'),
        ('Hidden bursts', 'C09', [R / 'burst_confirmation_study/burstconfirm_20261105_043818_8bdb76'], 'test', 'in'),
        ('Hidden bursts', 'C15', [R / 'sustained_burst_study/sustainedburst_20261105_063509_c737ee'], 'test', 'right'),
        ('Hidden gzip', 'C10', [R / 'wait_confirmation_study/waitconfirm_20261105_051433_3df228'], 'test', 'in'),
        ('Hidden gzip', 'C13', [R / 'untraced_wait_study/untracedwait_20261105_061041_b80fac'], 'test', 'right'),
        ('Adaptive / clock', 'C24', [E / 's1_20261106_021046_a5bd83'], 'test', 'in'),
        ('Adaptive / clock', 'C25', [E / 's3_20261106_024815_0b8db7'], 'test', 'right'),
        ('Adaptive / clock', 'C27', [E / 's1b_20261106_035740_995bcb'], 'test', 'in'),
        ('Adaptive / clock', 'C28', [E / 's1c_20261106_065736_99d08a'], 'test', 'in'),
        ('Adaptive / clock', 'C29', [E / 's1d_20261106_083646_2fa3ac'], 'test', 'in'),
        ('Real installer', '', [E / 's2train_20261106_030428_10f38e'], 'dev', None),
        ('Real installer', '', [E / 's2test_20261106_031520_1af941'], 'int', None),
        ('Real installer', 'C26', [E / 's2test_20261106_032920_dddf78'], 'test', 'right')]
    freezes = [  # (lane, utc, primary): every test bar in a lane starts after that lane's primary freeze
        ('Order / presence', '2026-11-04T18:31:01Z', True), ('Hidden bursts', '2026-11-04T18:35:44Z', True),
        ('Hidden gzip', '2026-11-05T03:14:26Z', True), ('Order / presence', '2026-11-05T04:08:51Z', False),
        ('Order / presence', '2026-11-05T04:33:27Z', False), ('Hidden gzip', '2026-11-05T07:09:49Z', True),
        ('Hidden gzip', '2026-11-05T07:57:39Z', False), ('Adaptive / clock', '2026-11-05T07:09:49Z', True),
        ('Adaptive / clock', '2026-11-06T02:16:39Z', True),
        ('Adaptive / clock', '2026-11-06T02:55:38Z', True), ('Real installer', '2026-11-06T03:15:20Z', True),
        ('Adaptive / clock', '2026-11-06T08:28:54Z', True)]
    segs = [(dt.datetime(2026, 11, 4, 16, 25), dt.datetime(2026, 11, 4, 18, 45)),
            (dt.datetime(2026, 11, 5, 3, 5), dt.datetime(2026, 11, 5, 8, 10)),
            (dt.datetime(2026, 11, 6, 1, 55), dt.datetime(2026, 11, 6, 9, 30))]
    hours = [(e - s).total_seconds() / 3600 for s, e in segs]
    spans, order_ok = {}, {}
    with fs.ieee_style():
        fig, axs = plt.subplots(1, 3, figsize=(fs.FULL_W, 2.1), layout='constrained', sharey=True,
                                gridspec_kw={'width_ratios': hours, 'wspace': 0.02})
        for si, (ax, (s0, s1)) in enumerate(zip(axs, segs)):
            hrs = lambda x: (x - s0).total_seconds() / 3600  # noqa: E731
            for lane, lab, ds, kind, pos in bars:
                t0 = min(_span(d)[0] for d in ds); t1 = max(_span(d)[1] for d in ds)
                if t1 < s0 or t0 > s1:
                    continue
                spans[lab or kind + ':' + ds[0].name] = [t0.strftime('%m-%d %H:%M'), t1.strftime('%H:%M')]
                y = ylane[lane]
                fc = {'dev': '#D9D9D9', 'test': fs.BLUE, 'int': 'white'}[kind]
                ax.barh(y, hrs(t1) - hrs(t0), left=hrs(t0), height=0.42, color=fc, edgecolor=fs.BLUE if kind != 'dev' else '#8C8C8C',
                        hatch='////' if kind == 'int' else None, lw=0.6, zorder=2)
                if pos == 'in':
                    ax.text(hrs(t0) + (hrs(t1) - hrs(t0)) / 2, y, lab, ha='center', va='center', fontsize=6.5,
                            color='white' if kind == 'test' else 'black', zorder=4)
                elif pos == 'right':
                    ax.text(hrs(t1) + 0.04, y, lab, ha='left', va='center', fontsize=6.5, color='black', zorder=4)
                if kind == 'test':
                    prior = [_utc(ts) for ln, ts, p in freezes if ln == lane and p and _utc(ts) <= t0]
                    order_ok[lab] = bool(prior)
            for lane, ts, prim in freezes:
                tt = _utc(ts)
                if s0 <= tt <= s1:
                    ax.plot([hrs(tt)], [ylane[lane] + 0.33], marker='D', ms=3.6 if prim else 3.0, mfc=fs.VERM if prim else 'white',
                            mec=fs.VERM, mew=0.7, ls='none', zorder=5)
            ax.set_xlim(0, hours[si])
            first_full = s0.replace(minute=0) + dt.timedelta(hours=1)
            hticks = [first_full + dt.timedelta(hours=h) for h in range(0, 12) if first_full + dt.timedelta(hours=h) <= s1]
            ax.set_xticks([hrs(h) for h in hticks], [h.strftime('%H') for h in hticks])
            ax.set_xlabel('Hour (UTC)')
            ax.set_title(s0.strftime('Nov %d'), fontsize=7.5)
            ax.spines['left'].set_visible(si == 0)
            if si:
                ax.tick_params(axis='y', length=0)
            ax.grid(axis='x', color='0.9', lw=0.5, zorder=0)
        axs[0].set_yticks([ylane[l] for l in lanes], lanes)
        axs[0].set_ylim(-0.6, len(lanes) - 0.35)
        fig.legend([Patch(facecolor=fs.BLUE, edgecolor=fs.BLUE), Patch(facecolor='#D9D9D9', edgecolor='#8C8C8C'),
                    Patch(facecolor='white', edgecolor=fs.BLUE, hatch='////'),
                    Line2D([], [], ls='none', marker='D', mfc=fs.VERM, mec=fs.VERM, ms=3.6),
                    Line2D([], [], ls='none', marker='D', mfc='white', mec=fs.VERM, ms=3.0)],
                   ['test batch (new runs)', 'training / development', 'interrupted (reported apart)', 'primary model frozen',
                    'secondary rule fixed'], loc='outside upper center', ncol=5, frameon=False, fontsize=6.5)
        REPORT['fig_timeline_spans'] = spans
        REPORT['fig_timeline_frozen_before_test'] = order_ok
        mf.finish(fig, 'fig_timeline', {
            'raw_data': ['FREEZE.json/COMPLETE.json of every batch', 'model receipts: CONFIRMATION_MODELS, BURST_RECEIPT, WAIT_CONFIRMATION_MODELS, '
                         'RELATIVE_REFERENCE/EXECUTION_WINDOW receipts, C20_FREEZE, PRE_S3_FREEZE, C27/S2/C29 model files'],
            'transformations': ['UTC start = batch FREEZE time, end = COMPLETE time (interrupted batches: last RESULTS write)'],
            'uncertainty': 'none'})


# ---------------------------------------------------------------- teaser and system-figure inserts
def fig_inserts():
    rows08 = mf.load_rows(R / 'confirmation_study/confirm_20261105_035739_c92be0/RESULTS.json')
    f08 = R / 'confirmation_processing_20261105/analysis/features'
    post08 = min(2.75, 4.0 - max(mf.mark_frame(r, 'before') * FRAME_S for r in rows08) - 0.02)
    t, MC, BMC = mf.aligned(rows08, f08, lambda r: r.get('family') == 'order' and r['actual_condition'], post_s=post08)
    _, CM, _ = mf.aligned(rows08, f08, lambda r: r.get('family') == 'order' and not r['actual_condition'], post_s=post08)
    with fs.ieee_style(**{'xtick.labelsize': 6.5, 'ytick.labelsize': 6.5, 'axes.labelsize': 6.5}):
        fig, ax = plt.subplots(figsize=(1.6, 1.32), layout='constrained')
        for arr, col, ls, lab in ((CM, fs.BLUE, '--', 'compliant'), (MC, fs.VERM, '-', 'violating')):
            med = np.median(arr, axis=0); q1, q3 = np.percentile(arr, [25, 75], axis=0)
            ax.fill_between(t, q1, q3, color=col, alpha=0.2, lw=0)
            ax.plot(t, med, color=col, ls=ls, lw=1.0, label=lab)
        ax.axvline(0, color='black', lw=0.5, ls=':')
        ax.set_xlim(-0.5, 2.6); ax.set_xticks([0, 1, 2]); ax.set_yticks([0, 1, 2])
        ax.set_xlabel('Time since dispatch (s)', labelpad=1)
        ax.set_ylabel('Rel. power (dB)', labelpad=1)
        fig.legend(loc='outside upper center', ncol=2, frameon=False, fontsize=6.5, handlelength=1.5, columnspacing=0.8)
        mf.finish(fig, 'ins_teaser_traces', {'raw_data': ['C08 order test runs (frame features)'], 'transformations': ['as fig_traces (a)'],
                                             'uncertainty': 'median and IQR over 20 runs per order'})
    st = json.loads((S / 'stats/paper_stats.json').read_text(encoding='utf-8'))
    s2 = json.loads((S / 'stats/supp_stats.json').read_text(encoding='utf-8'))['s2']
    g = lambda e, k: st[e][k]['correct'] / st[e][k]['n']  # noqa: E731
    cats = ['Transcript', 'Timing', 'RF whole', fs.SYS]
    c08 = [0.5, 24 / 40, g('C08_order', 'original/whole_260'), g('C08_order', 'original/temporal_260')]
    n2 = s2['n']; m = s2['models']
    c26 = [s2['transcript_bound_correct'] / n2, m['elapsed']['correct'] / n2, m['record_whole']['correct'] / n2, m['call_temporal']['correct'] / n2]
    with fs.ieee_style(**{'xtick.labelsize': 6.5, 'ytick.labelsize': 6.5, 'axes.labelsize': 6.5}):
        fig, ax = plt.subplots(figsize=(1.45, 1.68), layout='constrained')
        y = np.arange(len(cats)) * 1.1
        ax.barh(y - 0.19, c08, 0.36, color=[fs.GREY] * 3 + [fs.BLUE], edgecolor=fs.EDGE, lw=0.4, label='synthetic order (C08)')
        ax.barh(y + 0.19, c26, 0.36, color=['white'] * 3 + [fs.NAVY], edgecolor=fs.EDGE, lw=0.4, hatch='////', label='real installer (C26)')
        for yy, v in list(zip(y - 0.19, c08)) + list(zip(y + 0.19, c26)):
            ax.text(v + 0.02, yy, f'{v * 100:.0f}%', va='center', fontsize=6.5)
        ax.axvline(0.5, color='black', lw=0.5, ls=':', zorder=0)
        ax.set_yticks(y, cats)
        ax.invert_yaxis()
        ax.set_xlim(0, 1.38); ax.set_xticks([0, .5, 1], ['0', '50', '100%'])
        ax.set_xlabel('Accuracy on new runs', labelpad=1)
        fig.legend(loc='outside upper center', ncol=1, frameon=False, fontsize=6.5, handlelength=1.2, labelspacing=0.2)
        REPORT['ins_teaser_bars'] = {'C08': [round(v, 3) for v in c08], 'C26': [round(v, 3) for v in c26]}
        mf.finish(fig, 'ins_teaser_bars', {'raw_data': ['stats/paper_stats.json', 'stats/supp_stats.json (s2)'], 'transformations': ['accuracy of frozen models'],
                                           'uncertainty': 'none drawn (see Fig. results)'})
    with fs.ieee_style():
        fig, ax = plt.subplots(figsize=(0.95, 0.36))
        ax.plot(t, np.median(MC, axis=0), color=fs.VERM, lw=0.8)
        ax.axvline(0, color='black', lw=0.4, ls=':')
        ax.set_axis_off(); fig.subplots_adjust(0, 0, 1, 1)
        fs.save(fig, 'ins_thumb_trace', {'raw_data': ['C08 order, memory->CPU median'], 'note': 'thumbnail of measured data'})
        plt.close(fig)
        valid = [i for i in range(64) if i not in (0, 58, 59, 60, 61, 62, 63)]
        fig, ax = plt.subplots(figsize=(0.95, 0.42))
        ax.imshow(np.median(BMC, axis=0)[:, valid].T, aspect='auto', origin='lower', cmap='RdBu_r', vmin=-6, vmax=6, interpolation='nearest')
        ax.set_axis_off(); fig.subplots_adjust(0, 0, 1, 1)
        fs.save(fig, 'ins_thumb_bands', {'raw_data': ['C08 order, memory->CPU median band map'], 'note': 'thumbnail of measured data'})
        plt.close(fig)


BUILDERS = {'results': mf.fig_results, 'budget': mf.fig_budget, 'traces': mf.fig_traces, 'frontier': fig_frontier, 'roc': fig_roc,
            'drift': fig_drift, 'spectro': fig_spectro, 'timeline': fig_timeline, 'inserts': fig_inserts}

if __name__ == '__main__':
    todo = sys.argv[1:] or list(BUILDERS)
    for name in todo:
        BUILDERS[name]()
    fs.OUT.mkdir(parents=True, exist_ok=True)
    rep = {k: (v if not isinstance(v, dict) else {kk: vv for kk, vv in v.items() if kk != 'preview'}) for k, v in REPORT.items()}
    (fs.OUT / ('make_figures_submission_report_' + '_'.join(todo) + '.json')).write_text(json.dumps(rep, indent=1, default=str), encoding='utf-8')
    for k, v in REPORT.items():
        if isinstance(v, dict) and 'preview' in v:
            print(f'===== {k}: outputs {v["outputs"]}')
            print(json.dumps(v['check'], default=str))
        else:
            print(f'===== {k}:', json.dumps(v, default=str)[:1500])
