""" HackRF/ RF amp / bias-tee

1)  2026-10-26 <HOST> raw_health  5  LO/ × 3
2)  iPhone 10-26  v3  0–2.5 GHz 0.05 s RMS  b01 
: python hw_check.py <out_dir>
"""
import os
os.environ['OPENBLAS_NUM_THREADS'] = '4'; os.environ['OMP_NUM_THREADS'] = '4'
import glob, json, pathlib, sys, time
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import numpy as np
import rf_capture as rc
import sweeplib as sl

B01 = r'<CALIBRATION_ROOT>\raw\b01_r0*_idle\manifest.json'
HIST = {110: 6.335345268249512, 310: 1.5723600387573242, 710: 14.68615436553955, 1110: 8.75477409362793}  # 10-15  std_i
NOAMP_1026 = {110: 0.6657, 310: 0.3067, 710: 1.8563, 1110: 3.7494, 2310: 0.5821}                          # 10-26


def welch_db(raw, nfft=4096):
    x = raw.astype(np.float32).reshape(-1, 2)
    z = (x[:, 0] + 1j * x[:, 1]) / 128.0
    n = z.size // nfft
    seg = z[:n * nfft].reshape(n, nfft) * np.hanning(nfft).astype(np.float32)
    p = np.mean(np.abs(np.fft.fftshift(np.fft.fft(seg, axis=1), axes=1)) ** 2, axis=0)
    return 10 * np.log10(p + 1e-20)


def main():
    out = pathlib.Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    r = {'started': time.strftime('%Y-%m-%d %H:%M:%S'), 'samples': [], 'sweep': []}
    h = rc.HackRF()
    try:
        r['device'] = rc.device_meta(h)
        print('device', json.dumps(r['device'], ensure_ascii=False), flush=True)
        for lo, lna, vga in [(110e6, 24, 24), (310e6, 16, 16), (710e6, 32, 32), (1110e6, 40, 32), (2310e6, 24, 24)]:
            for k in range(3):
                raw, ok = h.record(lo, 0.15, lna, vga, settle=0.05)
                st = rc.iq_stats(raw); st.update(lo_mhz=lo / 1e6, lna=lna, vga=vga, repeat=k, complete=ok)
                psd = welch_db(raw); core = psd[410:-410]
                st.update(median_psd_db=float(np.median(core)), max_psd_db=float(core.max()))
                st['peak_above_median_db'] = st['max_psd_db'] - st['median_psd_db']
                r['samples'].append(st)
                if k == 0:
                    np.savez_compressed(out / ('spectrum_%d.npz' % int(lo / 1e6)), psd=psd, lo_hz=lo, lna=lna, vga=vga)
        gains, _ = sl.load_gain_table(str(HERE / 'gain_table_locked_v3_from_20261026.json'))
        for b in sl.plan(0, 2500, 20):
            lna, vga = gains[b['start_mhz']]
            raw, ok = h.record(b['lo_hz'], 0.05, lna, vga, settle=0.02)
            st = sl.fast_stats(raw); st.update(start_mhz=b['start_mhz'], lna=lna, vga=vga, complete=ok)
            r['sweep'].append(st)
    finally:
        h.close(); r['finished'] = time.strftime('%Y-%m-%d %H:%M:%S')
    #
    comp = []
    for lo in [110, 310, 710, 1110, 2310]:
        s = [x['std_i_lsb'] for x in r['samples'] if int(x['lo_mhz']) == lo]
        med = float(np.median(s))
        comp.append(dict(lo_mhz=lo, std_i_median=med, noamp_1026=NOAMP_1026.get(lo), amp_1015=HIST.get(lo),
                         db_vs_noamp_1026=20 * np.log10(med / NOAMP_1026[lo]),
                         db_vs_amp_1015=(20 * np.log10(med / HIST[lo]) if lo in HIST else None),
                         peak_above_median_db=float(np.median([x['peak_above_median_db'] for x in r['samples'] if int(x['lo_mhz']) == lo]))))
    ref = {}
    for p in sorted(glob.glob(B01)):
        for b in json.load(open(p, encoding='utf-8'))['bands']:
            ref.setdefault(b['start_mhz'], []).append(b['rms_fs'])
    d = []
    for x in r['sweep']:
        if x['start_mhz'] in ref:
            x['b01_rms_fs_median'] = float(np.median(ref[x['start_mhz']]))
            x['db_vs_b01'] = 20 * np.log10(x['rms_fs'] / x['b01_rms_fs_median'])
            d.append(x['db_vs_b01'])
    r['summary'] = dict(all_complete=all(x['complete'] for x in r['samples'] + r['sweep']),
                        max_clip=max(x['clip_frac'] for x in r['samples'] + r['sweep']),
                        n_clipped_sweep_bands=sum(x['clip_frac'] > 1e-4 for x in r['sweep']),
                        comparison_5lo=comp, b01_manifests=len(glob.glob(B01)),
                        sweep_db_vs_b01_median=(float(np.median(d)) if d else None),
                        sweep_db_vs_b01_p10_p90=([float(np.percentile(d, 10)), float(np.percentile(d, 90))] if d else None))
    (out / 'hw_check.json').write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(r['summary'], ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
