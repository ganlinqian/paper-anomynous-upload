"""Desktop (x86) EM feasibility sweep for the Telltale paper.

Target: this data desktop (Intel i7-11700, desktop). Receiver: the HackRF One
attached to it (serial <hackrf-serial>), driven through the shared capture library's
rf_capture.HackRF wrapper (read-only reuse; the shared script is not modified).

Alternates idle / memory-bound / compute-bound single-thread workloads and sweeps
10-2510 MHz in 20 MHz bands during each condition. Only per-band Welch PSDs are kept
(no raw IQ). Holds the shared hardware lock <CAPTURE_ROOT>\\HW_BUSY.txt.

usage: python -I probe_sweep.py --out <dir> [--dur 0.1] [--order i,m,i,c,i,m,i,c,i]
"""
import argparse, json, multiprocessing as mp, os, sys, time, socket, datetime
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1'); os.environ.setdefault('OMP_NUM_THREADS', '1')
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')
RF_DIR = r'<WORKSPACE>/ws_desktop\scripts'
LOCK = r'<CAPTURE_ROOT>\HW_BUSY.txt'
SERIAL = '<hackrf-serial>'
NFFT = 1024


def mem_worker(stop):
    buf = np.arange(64 * 1024 * 1024 // 4, dtype=np.uint32)   # 64 MiB, streamed
    k = np.uint32(2654435761)
    while not stop.is_set():
        np.multiply(buf, k, out=buf)


def cpu_worker(stop):
    import bz2
    data = os.urandom(256 * 1024)                                # L2-resident BWT
    while not stop.is_set():
        bz2.compress(data, 9)


def psd_db(raw):
    x = raw.astype(np.float32).reshape(-1, 2)
    z = (x[:, 0] + 1j * x[:, 1]) / 128.0
    z = z - z.mean()
    n = z.size // NFFT
    seg = z[:n * NFFT].reshape(n, NFFT) * np.hanning(NFFT).astype(np.float32)
    p = np.mean(np.abs(np.fft.fftshift(np.fft.fft(seg, axis=1), axes=1)) ** 2, axis=0)
    return (10 * np.log10(p + 1e-20)).astype(np.float32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--dur', type=float, default=0.1)
    ap.add_argument('--lna', type=int, default=24)
    ap.add_argument('--vga', type=int, default=20)
    ap.add_argument('--order', default='i,m,i,c,i,m,i,c,i')
    ap.add_argument('--starts', default='10:2510:20')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    if os.path.exists(LOCK):
        print('LOCK present, abort:', open(LOCK, encoding='utf-8', errors='replace').read()); return 2
    with open(LOCK, 'w', encoding='utf-8') as f:
        f.write(f'telltale desktop_em probe, session ws_main, pid {os.getpid()}, {datetime.datetime.now().astimezone().isoformat()}\n')
    sys.path.insert(0, RF_DIR)
    import rf_capture as rc
    s0, s1, st = (int(v) for v in a.starts.split(':'))
    los = [int((s + 10) * 1e6) for s in range(s0, s1, st)]
    meta = dict(host=socket.gethostname(), started=datetime.datetime.now().astimezone().isoformat(),
                los_hz=los, dur=a.dur, lna=a.lna, vga=a.vga, nfft=NFFT, order=a.order, sweeps=[])
    h = None
    procs = []
    try:
        h = rc.HackRF()
        meta['serial'] = h.serial; meta['firmware'] = h.firmware
        if h.serial != SERIAL:
            print('unexpected serial', h.serial); return 3
        ctx = mp.get_context('spawn')
        for k, cond in enumerate(a.order.split(',')):
            stop = ctx.Event(); procs = []
            if cond in ('m', 'c'):
                p = ctx.Process(target=mem_worker if cond == 'm' else cpu_worker, args=(stop,), daemon=True)
                p.start(); procs.append(p); time.sleep(2.0)
            t0 = time.time(); P = np.full((len(los), NFFT), np.nan, np.float32); ok = []
            for j, lo in enumerate(los):
                raw, good = h.record(lo, a.dur, a.lna, a.vga)
                ok.append(bool(good))
                if raw.size >= 2 * NFFT * 4:
                    P[j] = psd_db(raw)
            t1 = time.time()
            stop.set()
            for p in procs:
                p.join(5)
            np.save(os.path.join(a.out, f'sweep_{k:02d}_{cond}.npy'), P)
            meta['sweeps'].append(dict(k=k, cond=cond, t0=t0, t1=t1, n_ok=int(sum(ok)), n=len(ok)))
            print(f'sweep {k} cond={cond} ok={sum(ok)}/{len(ok)} {t1 - t0:.1f}s', flush=True)
            time.sleep(3.0)
    finally:
        for p in procs:
            try:
                p.terminate()
            except Exception:
                pass
        if h is not None:
            h.close()
        meta['ended'] = datetime.datetime.now().astimezone().isoformat()
        with open(os.path.join(a.out, 'meta.json'), 'w', encoding='utf-8') as f:
            json.dump(meta, f, indent=1)
        try:
            os.remove(LOCK)
        except OSError:
            pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
