"""Paper figure: dispatch-aligned received-power traces for transcript-equivalent executions.

Uses only stored per-frame features (power_db, band_db) of the main 1.8 GHz channel and the
controller's receiver byte marks.  Nothing is refit; this is a visualization of test batches.
"""
import json, pathlib, sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

R = pathlib.Path(r'<WORKSPACE>/ws_pi\results\scenario_rf_20261104')
OUT = pathlib.Path(r'<WORKSPACE>/ws_main\results\sp2027\figures')
OUT.mkdir(parents=True, exist_ok=True)
FRAME_S = 204800 / 20e6          # 10.24 ms per frame
BYTES_PER_FRAME = 2 * 204800     # int8 I/Q

def load_rows(results_json):
    rows = json.loads(pathlib.Path(results_json).read_text(encoding='utf-8-sig'))
    return rows if isinstance(rows, list) else rows.get('records', rows)

def mark_frame(row, key):
    m = next(x for x in row[key]['marks'] if x['radio'] == '930c')
    return m['bytes'] / BYTES_PER_FRAME

def trace(feat_dir, rid):
    z = np.load(pathlib.Path(feat_dir) / f'{rid}_930c.npz')
    return z['power_db'], z['band_db']

SKIPPED = {}

def aligned(rows, feat_dir, sel, pre_s=0.5, post_s=None, tag=''):
    out, bands, info = [], [], []
    for r in rows:
        if not sel(r):
            continue
        f = pathlib.Path(feat_dir) / f"{r['id']}_930c.npz"
        if not f.exists():
            continue
        p, bd = trace(feat_dir, r['id'])
        d0 = mark_frame(r, 'before'); d1 = mark_frame(r, 'after')
        i0 = int(round(d0)); pre = int(round(pre_s / FRAME_S))
        span = int(round((post_s if post_s else (d1 - d0) * FRAME_S + 0.6) / FRAME_S))
        lo, hi = i0 - pre, i0 + span
        if lo < 0 or hi > len(p):
            SKIPPED[tag] = SKIPPED.get(tag, 0) + 1
            continue
        ref = np.median(p[lo:i0])                    # pre-dispatch silence reference
        out.append(p[lo:hi] - ref)
        bref = np.median(bd[lo:i0], axis=0)
        bands.append(bd[lo:hi] - bref)
        info.append({'id': r['id'], 'dispatch_frame': d0, 'reply_frame': d1})
    t = (np.arange(-pre, span)) * FRAME_S
    return t, np.array(out), np.array(bands), info

def band_plot(ax, t, arr, color, label):
    m = np.median(arr, axis=0); q1, q3 = np.percentile(arr, [25, 75], axis=0)
    ax.plot(t, m, color=color, lw=1.0, label=f'{label} (n={len(arr)})')
    ax.fill_between(t, q1, q3, color=color, alpha=0.22, lw=0)

plt.rcParams.update({'font.size': 7.5, 'font.family': 'serif', 'axes.linewidth': 0.6,
                     'xtick.major.width': 0.5, 'ytick.major.width': 0.5, 'legend.fontsize': 6.5,
                     'pdf.fonttype': 42, 'ps.fonttype': 42})

summary = {}
# ---- C08 order & activity (4 s captures, same public request/response within a block)
c08 = R / 'confirmation_study/confirm_20261105_035739_c92be0/RESULTS.json'
c08_feat = R / 'confirmation_processing_20261105/analysis/features'
rows08 = load_rows(c08)
fams = sorted({r.get('family') for r in rows08})
summary['c08_families'] = fams
dsp = [mark_frame(r, 'before') * FRAME_S for r in rows08]
summary['c08_dispatch_s_range'] = [round(min(dsp), 3), round(max(dsp), 3)]
POST08 = min(2.75, 4.0 - max(dsp) - 0.02)
summary['c08_post_s'] = round(POST08, 3)
tO_a, O_a, OB_a, _ = aligned(rows08, c08_feat, lambda r: r.get('family') == 'order' and r['actual_condition'], post_s=POST08, tag='order_MC')
tO_b, O_b, OB_b, _ = aligned(rows08, c08_feat, lambda r: r.get('family') == 'order' and not r['actual_condition'], post_s=POST08, tag='order_CM')
tP_a, P_a, _, _ = aligned(rows08, c08_feat, lambda r: r.get('family') == 'trace' and r['actual_condition'], post_s=POST08, tag='pres_a')
tP_b, P_b, _, _ = aligned(rows08, c08_feat, lambda r: r.get('family') == 'trace' and not r['actual_condition'], post_s=POST08, tag='pres_s')
# ---- C13 untraced gzip (8 s captures)
c13 = R / 'untraced_wait_study/untracedwait_20261105_061041_b80fac/RESULTS.json'
c13_feat = R / 'untraced_processing_20261105/analysis/features'
rows13 = load_rows(c13)
tG_a, G_a, GB_a, _ = aligned(rows13, c13_feat, lambda r: r['actual_active'], post_s=4.8, tag='gzip_a')
tG_b, G_b, GB_b, _ = aligned(rows13, c13_feat, lambda r: not r['actual_active'], post_s=4.8, tag='gzip_s')
summary.update({'order_MC': len(O_a), 'order_CM': len(O_b), 'pres_active': len(P_a), 'pres_silent': len(P_b),
                'gzip_active': len(G_a), 'gzip_silent': len(G_b), 'skipped': SKIPPED})
def probe(t, arr, pts):
    m = np.median(arr, axis=0)
    return {f'{x:.2f}s': round(float(m[np.searchsorted(t, x)]), 3) for x in pts}
summary['median_probe'] = {
    'order_MC': probe(tO_a, O_a, [-0.2, 0.3, 0.8, 1.3, 1.8, 2.3]),
    'order_CM': probe(tO_b, O_b, [-0.2, 0.3, 0.8, 1.3, 1.8, 2.3]),
    'pres_active': probe(tP_a, P_a, [-0.2, 0.3, 0.8, 1.3, 1.8]),
    'pres_silent': probe(tP_b, P_b, [-0.2, 0.3, 0.8, 1.3, 1.8]),
    'gzip_active': probe(tG_a, G_a, [-0.2, 0.2, 0.5, 1.0, 2.0, 3.0, 4.2]),
    'gzip_silent': probe(tG_b, G_b, [-0.2, 0.2, 0.5, 1.0, 2.0, 3.0, 4.2])}

fig, axs = plt.subplots(1, 3, figsize=(7.16, 1.85), constrained_layout=True)
band_plot(axs[0], tO_a, O_a, '#c0392b', 'memory$\\rightarrow$CPU')
band_plot(axs[0], tO_b, O_b, '#2471a3', 'CPU$\\rightarrow$memory')
axs[0].set_title('(a) Order bit (C08, 40 new runs)', fontsize=7.5)
band_plot(axs[1], tP_a, P_a, '#c0392b', 'hidden 1 s burst')
band_plot(axs[1], tP_b, P_b, '#2471a3', 'no burst')
axs[1].set_title('(b) Presence bit (C08, 40 new runs)', fontsize=7.5)
# (c) gzip leaves total power almost unchanged; show its band-resolved signature instead
freqs = (np.arange(64) + 0.5) * (10.0 / 64)
valid = [i for i in range(64) if i not in (0, 58, 59, 60, 61, 62, 63)]
ia = np.searchsorted(tG_a, 0.05); ib = np.searchsorted(tG_a, 2.25)
sig_a = np.median(GB_a[:, ia:ib, :], axis=1)[:, valid]      # per-run band change in hidden window
sig_b = np.median(GB_b[:, ia:ib, :], axis=1)[:, valid]
for arr, c, lab in [(sig_a, '#c0392b', 'hidden gzip of 16 MiB'), (sig_b, '#2471a3', 'no archiving')]:
    m = np.median(arr, axis=0); q1, q3 = np.percentile(arr, [25, 75], axis=0)
    axs[2].plot(freqs[valid], m, color=c, lw=0.9, label=f'{lab} (n={len(arr)})')
    axs[2].fill_between(freqs[valid], q1, q3, color=c, alpha=0.22, lw=0)
axs[2].set_title('(c) Real gzip, no host tracing (C13)', fontsize=7.5)
axs[2].set_xlabel('|offset from 1.8 GHz| (MHz)')
summary['gzip_band_sig_median_db'] = {'active': [round(float(x), 3) for x in np.median(sig_a, axis=0)],
                                      'silent': [round(float(x), 3) for x in np.median(sig_b, axis=0)]}
sep = np.median(sig_a, axis=0) - np.median(sig_b, axis=0)
summary['gzip_band_sig_top'] = sorted([(round(float(freqs[valid][i]), 3), round(float(sep[i]), 3)) for i in range(len(valid))], key=lambda x: -abs(x[1]))[:8]
for ax in axs[:2]:
    ax.axvline(0, color='k', lw=0.5, ls=':')
    ax.set_xlabel('time since dispatch (s)')
for ax in axs:
    ax.legend(loc='upper right', frameon=False, handlelength=1.2)
    ax.grid(alpha=0.25, lw=0.4)
axs[2].set_ylabel('band power change (dB)')
axs[0].set_ylabel('rel. received power (dB)')
fig.savefig(OUT / 'fig_traces.pdf'); fig.savefig(OUT / 'fig_traces.png', dpi=220)

# ---- band-resolved difference for the order bit: segment means, memory->CPU minus CPU->memory
seg = [(0.0, 1.0), (1.0, 2.0)]
diff = {}
for a, bnd in seg:
    ia = np.searchsorted(tO_a, a); ib = np.searchsorted(tO_a, bnd)
    diff[f'{a:.0f}-{bnd:.0f}s'] = (np.median(OB_a[:, ia:ib, :], axis=(0, 1)) - np.median(OB_b[:, ia:ib, :], axis=(0, 1))).tolist()
summary['order_band_diff_db_first_second_s'] = {k: [round(x, 3) for x in v] for k, v in diff.items()}

fig2, ax = plt.subplots(figsize=(3.4, 1.6), constrained_layout=True)
for (k, v), c in zip(diff.items(), ['#c0392b', '#2471a3']):
    ax.plot(freqs[valid], np.array(v)[valid], color=c, lw=0.9, label=f'phase window {k}')
ax.axhline(0, color='k', lw=0.4)
ax.set_xlabel('|offset from 1.8 GHz| (MHz)'); ax.set_ylabel('$\\Delta$ band power (dB)')
ax.legend(frameon=False); ax.grid(alpha=0.25, lw=0.4)
fig2.savefig(OUT / 'fig_order_bands.pdf'); fig2.savefig(OUT / 'fig_order_bands.png', dpi=220)

(OUT / 'fig_traces_summary.json').write_text(json.dumps(summary, indent=1), encoding='utf-8')
print(json.dumps({k: v for k, v in summary.items() if k not in ('order_band_diff_db_first_second_s', 'gzip_band_sig_median_db', 'median_probe')}, indent=1))
