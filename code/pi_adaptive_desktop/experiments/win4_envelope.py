"""capture_pc-local envelope-modulation features (session ws_revision, C38 exploration; no models).
For each IQ file: 1024-point Hann FFT frames (51.2 us, no overlap, same 64 band groups as win4_extract.py), band power
per frame, averaged over 4 frames (204.8 us steps, 4.883 kHz envelope rate).  For two windows -- 'pre' = the last
1.0 s before the dispatch mark and 'call' = dispatch mark to reply mark -- each band's log-power envelope is
mean-removed and its Welch PSD (segments of 1024 steps = 0.21 s, Hann, 50 % overlap) is summed into 9 log-spaced
modulation bins between 4.77 and 2441 Hz.  The wideband (sum of valid bands) envelope gets the same treatment.
Output per file: <stem>_env.npz with mod_pre/mod_call (65 x 9, log10), lvl_pre/lvl_call (65, mean log10 power).
Usage: python win4_envelope.py --list env_list.json --out OUTDIR [--workers 2]
env_list.json: [{"path": ".../x_930c.iq", "id": "...", "before": bytes, "after": bytes}, ...]
"""
import argparse, concurrent.futures, ctypes, json, os, pathlib, time, traceback
os.environ["OPENBLAS_NUM_THREADS"] = "1"; os.environ["OMP_NUM_THREADS"] = "1"; os.environ["MKL_NUM_THREADS"] = "1"
import numpy as np
NFFT = 1024; SR = 20000000; AVG = 4; STEP = NFFT * AVG          # samples per envelope step
RATE = SR / STEP; SEGN = 1024
EDGES = np.array([4.77, 9.5, 19, 38, 76, 152, 305, 610, 1220, 2442])


def below_normal():
    try:
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
    except Exception:
        pass


def bands_env(raw, s0, s1):
    """band power envelope (n_steps, 65) for complex samples [s0, s1)."""
    band = np.minimum((np.abs(np.fft.fftfreq(NFFT, 1 / SR)) / 1e7 * 64).astype(int), 63)
    fa = np.abs(np.fft.fftfreq(NFFT, 1 / SR)); valid = (fa > .15e6) & (fa < 9e6)
    M = np.zeros((NFFT, 65), np.float32)
    for j in range(64):
        g = valid & (band == j)
        if g.any():
            M[g, j] = 1.0 / g.sum()
    M[valid, 64] = 1.0 / valid.sum()
    s0 = (s0 // STEP) * STEP; n = (s1 - s0) // STEP
    win = np.hanning(NFFT).astype(np.float32); out = []
    with open(raw, 'rb') as f:
        f.seek(2 * s0)
        CH = 64                                           # steps per read
        for k in range(0, n, CH):
            m = min(CH, n - k); a = np.frombuffer(f.read(2 * STEP * m), dtype=np.int8)
            z = (a[0::2].astype(np.float32) + 1j * a[1::2].astype(np.float32)).reshape(-1, NFFT)
            z = z - z.mean(axis=1, keepdims=True)
            sp = np.abs(np.fft.fft(z * win, axis=1)) ** 2
            out.append((sp @ M).reshape(m, AVG, 65).mean(1))
    return np.log10(np.maximum(np.vstack(out), 1e-12))


def modspec(env):
    x = env - env.mean(0); n = len(x)
    seg = min(SEGN, n - n % 2); hop = seg // 2; w = np.hanning(seg)[:, None]
    P = 0; cnt = 0
    for s in range(0, n - seg + 1, hop):
        P = P + np.abs(np.fft.rfft(x[s:s + seg] * w, axis=0)) ** 2; cnt += 1
    P = P / max(cnt, 1); fr = np.fft.rfftfreq(seg, 1 / RATE)
    return np.log10(np.maximum(np.array([P[(fr >= lo) & (fr < hi)].sum(0) for lo, hi in zip(EDGES[:-1], EDGES[1:])]).T, 1e-12))


def one(t):
    below_normal()
    out = pathlib.Path(t['out']) / (pathlib.Path(t['path']).stem + '_env.npz')
    b, a = t['before'] // 2, t['after'] // 2
    pre = bands_env(t['path'], max(0, b - SR), b); call = bands_env(t['path'], b, a)
    tmp = out.parent / (out.stem + '.part.npz')          # atomic: a killed run never leaves a partial *_env.npz
    np.savez_compressed(tmp, mod_pre=modspec(pre), mod_call=modspec(call), lvl_pre=pre.mean(0), lvl_call=call.mean(0),
                        n_pre=len(pre), n_call=len(call))
    os.replace(tmp, out)
    return {'id': t['id'], 'n_pre': len(pre), 'n_call': len(call)}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--list', required=True); ap.add_argument('--out', required=True); ap.add_argument('--workers', type=int, default=2)
    a = ap.parse_args(); below_normal(); out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    tasks = [dict(t, out=str(out)) for t in json.loads(pathlib.Path(a.list).read_text(encoding='utf-8-sig'))
             if not (out / (pathlib.Path(t['path']).stem + '_env.npz')).exists()]
    st = time.time(); n = 0
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers) as ex:
        for r in ex.map(one, tasks):
            n += 1; print(json.dumps({'done': n, 'of': len(tasks), 's': round(time.time() - st, 1), **r}), flush=True)
    (out / 'ENV_COMPLETE.json').write_text(json.dumps({'files': len(tasks), 'elapsed_s': time.time() - st}))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        pathlib.Path(__file__).with_name('WIN4_ENV_FAILURE.log').write_text(traceback.format_exc()); raise
