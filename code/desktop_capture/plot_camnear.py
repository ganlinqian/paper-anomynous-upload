"""camnear : python plot_camnear.py <run_dir> <analysis_dir>"""
import os
os.environ['OPENBLAS_NUM_THREADS'] = '4'
import json, sys
import numpy as np
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']; plt.rcParams['axes.unicode_minus'] = False

run, ad = sys.argv[1], sys.argv[2]
m = np.load(os.path.join(ad, 'median_psd.npz')); keep = m['keep']; f = m['freq_mhz'][:, keep].ravel()
on = np.median(np.stack([m['psd_b02'], m['psd_b04']]), 0)[:, keep].ravel()
off = np.median(np.stack([m['psd_b01'], m['psd_b03'], m['psd_b05']]), 0)[:, keep].ravel()
mar = m['margin'][:, keep].ravel()
o = np.argsort(f); f, on, off, mar = f[o], on[o], off[o], mar[o]
fig, ax = plt.subplots(3, 1, figsize=(13, 9), sharex=True)
ax[0].plot(f, off, lw=0.4, c='0.4', label='OFF b01/b03/b05'); ax[0].plot(f, on, lw=0.4, c='C3', alpha=0.7, label='ON b02/b04')
ax[0].set_ylabel('PSD (dB)'); ax[0].legend(loc='upper left'); ax[0].set_title('camnear_202610280–2.5 GHz ')
ax[1].plot(f, on - off, lw=0.4, c='C0'); ax[1].axhline(6, c='r', ls='--', lw=0.8); ax[1].set_ylabel('ON−OFF  (dB)'); ax[1].set_ylim(-10, 10)
ax[2].plot(f, mar, lw=0.4, c='C2'); ax[2].axhline(0, c='k', lw=0.6); ax[2].axhline(3, c='r', ls='--', lw=0.8)
ax[2].set_ylabel('min(ON)−max(OFF) (dB)'); ax[2].set_xlabel(' (MHz)'); ax[2].set_ylim(-30, 5)
fig.tight_layout(); fig.savefig(os.path.join(ad, 'fig1_spectrum_on_off.png'), dpi=130); plt.close(fig)

b = json.load(open(os.path.join(ad, 'burst_24g.json'), encoding='utf-8')); sids = list(b)
col = ['C3' if s[:3] in ('b02', 'b04') else '0.5' for s in sids]
fig, ax = plt.subplots(1, 2, figsize=(13, 4.5))
for k, band in enumerate(('2440', '2460')):
    pk = [b[s][band]['peak_db_over_floor'] for s in sids]
    ax[k].bar(range(len(sids)), pk, color=col); ax[k].set_xticks(range(len(sids))); ax[k].set_xticklabels([s[:7] for s in sids], rotation=90, fontsize=7)
    ax[k].set_ylabel(' −  (dB)'); ax[k].set_title(f'{band}–{int(band) + 20} MHz _=_')
fig.tight_layout(); fig.savefig(os.path.join(ad, 'fig2_24g_burst_peak.png'), dpi=130); plt.close(fig)

fig, ax = plt.subplots(3, 1, figsize=(13, 7), sharex=True)
for a, sid in zip(ax, ('b02_r01_cam_on', 'b04_r03_cam_on', 'b05_r04_idle')):
    z = np.load(os.path.join(run, 'raw', sid, 'features.npz')); i = int(np.flatnonzero(z['start_mhz'] == 2440)[0])
    x = z['env'][i]; t = np.arange(x.size) * 10e-3
    a.plot(t, 10 * np.log10(x / np.median(x)), lw=0.4); a.set_ylabel('dB '); a.set_title(f'{sid}_2440–2460 MHz _ 10 µs _'); a.set_ylim(-5, 45)
ax[-1].set_xlabel(' (ms)'); fig.tight_layout(); fig.savefig(os.path.join(ad, 'fig3_24g_envelope_examples.png'), dpi=130); plt.close(fig)
print('ok')
