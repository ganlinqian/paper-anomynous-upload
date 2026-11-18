"""camnear  + //
: python analyze_camnear_sens.py <run_dir> <out_dir>
"""
import os
os.environ['OPENBLAS_NUM_THREADS'] = '4'; os.environ['OMP_NUM_THREADS'] = '4'
import glob, json, pathlib, sys
import numpy as np
from math import comb

ON, OFF = ('b02', 'b04'), ('b01', 'b03', 'b05')


def main():
    run, out = sys.argv[1], pathlib.Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
    ps = sorted(glob.glob(os.path.join(run, 'raw', 'b0*', 'features.npz')))
    sids = [os.path.basename(os.path.dirname(p)) for p in ps]; blocks = np.array([s[:3] for s in sids])
    on, off = np.isin(blocks, ON), np.isin(blocks, OFF)
    F = [np.load(p) for p in ps]; P = np.stack([f['psd_db'] for f in F]); lo = F[0]['lo_hz']; st = F[0]['start_mhz']
    nfft, sr = int(F[0]['nfft']), float(F[0]['sr'])
    keep = np.zeros(nfft, bool); e = int(0.05 * nfft); keep[e:nfft - e] = True; keep[nfft // 2 - 3:nfft // 2 + 4] = False
    freq = (lo[:, None] + (np.arange(nfft)[None, :] - nfft // 2) * sr / nfft) / 1e6
    margin = P[on].min(0) - P[off].max(0); delta = np.median(P[on], 0) - np.median(P[off], 0)
    r = dict(n_bins_tested=int(keep.sum() * len(lo)), p_all_on_above_all_off=1 / comb(20, 8))
    r['expected_by_chance_margin_pos'] = r['n_bins_tested'] * r['p_all_on_above_all_off']
    r['n_margin_pos'] = int((keep & (margin > 0)).sum())
    r['n_margin_pos_delta1'] = int((keep & (margin > 0) & (delta >= 1)).sum())
    r['n_margin_pos_delta2'] = int((keep & (margin > 0) & (delta >= 2)).sum())
    r['n_delta6_any'] = int((keep & (delta >= 6)).sum())
    ii, jj = np.nonzero(keep & (margin > 0))
    order = np.argsort(-delta[ii, jj])[:20]
    r['top_margin_pos'] = [dict(freq_mhz=round(float(freq[i, j]), 4), delta_db=round(float(delta[i, j]), 2), margin_db=round(float(margin[i, j]), 2),
                                per_block={b: round(float(np.median(P[blocks == b, i, j])), 2) for b in sorted(set(blocks))}) for i, j in zip(ii[order], jj[order])]
    ii, jj = np.nonzero(keep & (delta >= 6))
    order = np.argsort(-delta[ii, jj])[:15]
    r['top_delta_nonsep'] = [dict(freq_mhz=round(float(freq[i, j]), 4), delta_db=round(float(delta[i, j]), 2), margin_db=round(float(margin[i, j]), 2),
                                  per_group=[round(float(x), 1) for x in P[:, i, j]]) for i, j in zip(ii[order], jj[order])]
    #
    E = np.stack([f['env'] for f in F]).astype(np.float64)            # (G,125,N)
    fl = np.median(E, 2, keepdims=True)
    feats = dict(p999_db=10 * np.log10(np.percentile(E, 99.9, axis=2)), max_db=10 * np.log10(E.max(2)),
                 duty_10db=np.mean(E > fl * 10, axis=2), mean_db=10 * np.log10(E.mean(2)))
    r['burst'] = {}
    for k, v in feats.items():
        d = np.median(v[on], 0) - np.median(v[off], 0); sep = v[on].min(0) - v[off].max(0)
        o = np.argsort(-d)[:8]
        r['burst'][k] = dict(n_bands_sep_pos=int((sep > 0).sum()), sep_pos_bands=[int(st[i]) for i in np.flatnonzero(sep > 0)],
                             top=[dict(start_mhz=int(st[i]), delta=round(float(d[i]), 3), sep=round(float(sep[i]), 3)) for i in o])
    wifi = [i for i in range(len(st)) if 2400 <= st[i] < 2500]
    r['wifi_24g_per_group'] = {sids[g]: dict(p999_db=[round(float(feats['p999_db'][g, i]), 1) for i in wifi],
                                             duty_10db=[round(float(feats['duty_10db'][g, i]), 4) for i in wifi]) for g in range(len(sids))}
    r['wifi_bands'] = [int(st[i]) for i in wifi]
    (out / 'sensitivity.json').write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps({k: r[k] for k in r if k not in ('wifi_24g_per_group', 'top_delta_nonsep')}, ensure_ascii=False))
    print('top_delta_nonsep:', json.dumps(r['top_delta_nonsep'][:6], ensure_ascii=False))
    print('wifi bands', r['wifi_bands'])
    for s, v in r['wifi_24g_per_group'].items():
        print(s, v['p999_db'], v['duty_10db'])


if __name__ == '__main__':
    main()
