"""2.4 GHz  2420/2440/2460  IQ> +THR dB
 PSD  -10 dB : python burst_24g.py <run_dir> <out_json>
"""
import os
os.environ['OPENBLAS_NUM_THREADS'] = '4'; os.environ['OMP_NUM_THREADS'] = '4'
import glob, json, sys
import numpy as np

SR, BIN, THR, NFFT = 20e6, 200, 15.0, 256
BANDS = (2420, 2440, 2460)


def one(path, lo):
    raw = np.fromfile(path, np.int8).astype(np.float32).reshape(-1, 2)
    z = (raw[:, 0] + 1j * raw[:, 1]) / 128.0; z -= z.mean()
    m = z.size // BIN; env = np.mean((np.abs(z[:m * BIN]) ** 2).reshape(m, BIN), 1)
    fl = np.median(env); hot = env > fl * 10 ** (THR / 10)
    d = np.diff(np.r_[0, hot.astype(int), 0]); s, e = np.flatnonzero(d == 1), np.flatnonzero(d == -1)
    dur_us = (e - s) * BIN / SR * 1e6
    r = dict(n_bursts=int(s.size), dur_us_median=(float(np.median(dur_us)) if s.size else None), dur_us_max=(float(dur_us.max()) if s.size else None),
             hot_frac=float(hot.mean()), peak_db_over_floor=float(10 * np.log10(env.max() / fl)), floor_db=float(10 * np.log10(fl)))
    if hot.sum() >= 4:
        idx = np.flatnonzero(hot); segs = []
        for k in idx:
            a = k * BIN
            seg = z[a:a + NFFT]
            if seg.size == NFFT:
                segs.append(seg)
        S = np.mean(np.abs(np.fft.fftshift(np.fft.fft(np.array(segs) * np.hanning(NFFT), axis=1), axes=1)) ** 2, 0)
        f = (lo + (np.arange(NFFT) - NFFT // 2) * SR / NFFT) / 1e6
        Sd = 10 * np.log10(S + 1e-20); occ = np.flatnonzero(Sd >= Sd.max() - 10)
        r.update(burst_center_mhz=round(float(np.sum(f * S) / S.sum()), 2), burst_occ10_mhz=[round(float(f[occ[0]]), 2), round(float(f[occ[-1]]), 2)],
                 burst_occ10_width_mhz=round(float(f[occ[-1]] - f[occ[0]] + SR / NFFT / 1e6), 2))
    return r


def main():
    run, outp = sys.argv[1], sys.argv[2]; res = {}
    for d in sorted(glob.glob(os.path.join(run, 'raw', 'b0*'))):
        sid = os.path.basename(d); res[sid] = {}
        for b in BANDS:
            res[sid][b] = one(os.path.join(d, f'band_{b:04d}MHz.iq8'), (b + 10) * 1e6)
    json.dump(res, open(outp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for sid, v in res.items():
        print(sid, ' | '.join(f"{b}: n={x['n_bursts']} hot={x['hot_frac']:.3f} pk={x['peak_db_over_floor']:.1f} dur={x['dur_us_median']} "
                                f"c={x.get('burst_center_mhz')} w={x.get('burst_occ10_width_mhz')}" for b, x in v.items()))


if __name__ == '__main__':
    main()
