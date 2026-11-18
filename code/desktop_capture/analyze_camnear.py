"""camnear  features.npz IQ

ON = b02+b04OFF = b01+b03+b05 / 
1) Welch 4096  PSD4.88 kHz 5%  DC ±3 bin
    bin  min(ON) - max(OFF) >= MARGIN  median(ON) - median(OFF) >= MED_DB bin 
2)  PSD /ON  OFF 
3) 10 µs 5 Hz 0–50 kHz ON/OFF 
: python analyze_camnear.py <run_dir> <out_dir>
"""
import os
os.environ['OPENBLAS_NUM_THREADS'] = '4'; os.environ['OMP_NUM_THREADS'] = '4'
import glob, json, pathlib, sys
import numpy as np

ON, OFF = ('b02', 'b04'), ('b01', 'b03', 'b05')
MARGIN, MED_DB = 3.0, 6.0
MOD_MARGIN, MOD_MED = 3.0, 6.0


def load(run):
    g = {}
    for p in sorted(glob.glob(os.path.join(run, 'raw', 'b0*', 'features.npz'))):
        sid = os.path.basename(os.path.dirname(p)); f = np.load(p)
        g[sid] = dict(block=sid[:3], psd=f['psd_db'], env=f['env'], lo=f['lo_hz'], start=f['start_mhz'], sr=float(f['sr']), nfft=int(f['nfft']))
    return g


def clusters(mask, gap=2):
    idx = np.flatnonzero(mask); out = []
    for i in idx:
        if out and i - out[-1][-1] <= gap:
            out[-1].append(i)
        else:
            out.append([i])
    return out


def main():
    run, out = sys.argv[1], pathlib.Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
    g = load(run); sids = sorted(g); blocks = [g[s]['block'] for s in sids]
    on = np.array([b in ON for b in blocks]); off = np.array([b in OFF for b in blocks])
    first = g[sids[0]]; nfft, sr = first['nfft'], first['sr']; lo = first['lo']; nb = len(lo)
    P = np.stack([g[s]['psd'] for s in sids])                       # (G,125,4096) dB
    freq = (lo[:, None] + (np.arange(nfft)[None, :] - nfft // 2) * sr / nfft) / 1e6
    keep = np.zeros(nfft, bool); e = int(0.05 * nfft); keep[e:nfft - e] = True; keep[nfft // 2 - 3:nfft // 2 + 4] = False
    res = dict(groups=sids, on_blocks=ON, off_blocks=OFF, criteria=dict(margin_db=MARGIN, median_db=MED_DB), spectral=[], spectral_b03=[], band=[], envelope=[])

    # 1)
    mon, moff = np.median(P[on], 0), np.median(P[off], 0)
    margin = P[on].min(0) - P[off].max(0)
    blk = {b: np.median(P[np.array(blocks) == b], 0) for b in sorted(set(blocks))}
    for i in range(nb):
        m = keep & (margin[i] >= MARGIN) & (mon[i] - moff[i] >= MED_DB)
        for c in clusters(m):
            j = c[int(np.argmax(mon[i, c] - moff[i, c]))]
            res['spectral'].append(dict(freq_mhz=round(float(freq[i, j]), 4), band_start_mhz=int(first['start'][i]), n_bins=len(c),
                                        width_khz=round(len(c) * sr / nfft / 1e3, 1), on_med_db=round(float(mon[i, j]), 2), off_med_db=round(float(moff[i, j]), 2),
                                        delta_db=round(float(mon[i, j] - moff[i, j]), 2), min_on_minus_max_off_db=round(float(margin[i, j]), 2),
                                        per_block_db={b: round(float(blk[b][i, j]), 2) for b in blk}))
    res['spectral'].sort(key=lambda x: -x['delta_db'])
    # b03
    idle = np.isin(blocks, ['b01', 'b05']); b03 = np.array(blocks) == 'b03'
    m3 = P[b03].min(0) - P[idle].max(0); d3 = np.median(P[b03], 0) - np.median(P[idle], 0)
    for i in range(nb):
        for c in clusters(keep & (m3[i] >= MARGIN) & (d3[i] >= MED_DB)):
            j = c[int(np.argmax(d3[i, c]))]
            res['spectral_b03'].append(dict(freq_mhz=round(float(freq[i, j]), 4), n_bins=len(c), delta_db=round(float(d3[i, j]), 2)))
    res['spectral_b03'].sort(key=lambda x: -x['delta_db'])

    # 2)
    floor = np.median(P[:, :, keep], axis=2)                         # (G,125)
    for i in range(nb):
        res['band'].append(dict(start_mhz=int(first['start'][i]), on_med=round(float(np.median(floor[on, i])), 2), off_med=round(float(np.median(floor[off, i])), 2),
                                delta_db=round(float(np.median(floor[on, i]) - np.median(floor[off, i])), 2),
                                sep_db=round(float(floor[on, i].min() - floor[off, i].max()), 2)))

    # 3)
    E = np.stack([g[s]['env'] for s in sids]).astype(np.float64)    # (G,125,N)
    N = E.shape[2]; fs_env = sr / 200.0
    mu = E.mean(2, keepdims=True)
    M = np.abs(np.fft.rfft((E - mu) * np.hanning(N), axis=2)) ** 2 / (mu ** 2 * N)
    M = 10 * np.log10(M + 1e-30); fm = np.fft.rfftfreq(N, 1 / fs_env)
    kf = fm >= 10
    mmon, mmoff = np.median(M[on], 0), np.median(M[off], 0); mmar = M[on].min(0) - M[off].max(0)
    for i in range(nb):
        m = kf & (mmar[i] >= MOD_MARGIN) & (mmon[i] - mmoff[i] >= MOD_MED)
        for c in clusters(m, gap=1):
            j = c[int(np.argmax(mmon[i, c] - mmoff[i, c]))]
            res['envelope'].append(dict(band_start_mhz=int(first['start'][i]), mod_hz=float(fm[j]), n_bins=len(c),
                                        delta_db=round(float(mmon[i, j] - mmoff[i, j]), 2), margin_db=round(float(mmar[i, j]), 2)))
    res['envelope'].sort(key=lambda x: -x['delta_db'])
    # 25/30 Hz  2–4
    fr = {}
    for f0 in (25, 30):
        for h in (1, 2, 3, 4):
            j = int(np.argmin(abs(fm - f0 * h)))
            d = mmon[:, j] - mmoff[:, j]; best = int(np.argmax(d))
            fr[f'{f0 * h}Hz'] = dict(best_band=int(first['start'][best]), delta_db=round(float(d[best]), 2), margin_db=round(float(mmar[best, j]), 2),
                                     n_bands_margin_pos=int((mmar[:, j] > 0).sum()))
    res['frame_rate_check'] = fr

    s = res['spectral']; bd = res['band']
    res['summary'] = dict(n_groups=len(sids), n_on=int(on.sum()), n_off=int(off.sum()), n_spectral_candidates=len(s),
                          n_spectral_b03_vs_idle=len(res['spectral_b03']), n_envelope_candidates=len(res['envelope']),
                          n_bands_floor_sep_pos=sum(b['sep_db'] > 0 for b in bd),
                          top_band_floor=sorted(bd, key=lambda b: -b['delta_db'])[:8])
    (out / 'analysis.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    np.savez_compressed(out / 'median_psd.npz', freq_mhz=freq.astype(np.float32), keep=keep,
                        **{f'psd_{b}': blk[b].astype(np.float32) for b in blk}, margin=margin.astype(np.float32))
    np.savez_compressed(out / 'median_modspec.npz', fm=fm, **{f'mod_{b}': np.median(M[np.array(blocks) == b], 0).astype(np.float32) for b in sorted(set(blocks))})
    print(json.dumps(res['summary'], ensure_ascii=False, indent=1))
    print('top spectral:'); [print(' ', json.dumps(x, ensure_ascii=False)) for x in s[:25]]
    print('b03 vs idle:', res['spectral_b03'][:10])
    print('envelope top:', res['envelope'][:15])
    print('frame rate:', json.dumps(fr, ensure_ascii=False))


if __name__ == '__main__':
    main()
