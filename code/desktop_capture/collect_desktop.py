""" HackRF 

 0–2500 MHz20 MHz/ 125  0.02 s  --dur  0.2 s
 10-26 iPhone v3 int8 IQ  --root
  psd   : Welch 4096 4.88 kHz  dBfloat32
  env   : 10 µs /float32
:
  python collect_desktop.py --run R --block b01 --cond idle --count 2 --start 1 --confirm ""
≤180 s block --budget 
"""
import os
os.environ['OPENBLAS_NUM_THREADS'] = '4'; os.environ['OMP_NUM_THREADS'] = '4'
import argparse, ctypes, hashlib, json, pathlib, queue, shutil, sys, threading, time, traceback
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import numpy as np
import rf_capture as rc
import sweeplib as sl

NFFT = 4096
ENV_BIN = 200          # 200  = 10 µs @ 20 MS/s
WIN = np.hanning(NFFT).astype(np.float32)


def js(p, o):
    p = pathlib.Path(p); tmp = p.with_suffix(p.suffix + '.tmp')
    tmp.write_text(json.dumps(o, ensure_ascii=False, indent=1), encoding='utf-8'); os.replace(tmp, p)


def feats(raw):
    x = raw.astype(np.float32).reshape(-1, 2)
    z = (x[:, 0] + 1j * x[:, 1]) / 128.0
    z = z - z.mean()
    n = z.size // NFFT
    seg = z[:n * NFFT].reshape(n, NFFT) * WIN
    psd = np.mean(np.abs(np.fft.fftshift(np.fft.fft(seg, axis=1), axes=1)) ** 2, axis=0)
    m = z.size // ENV_BIN
    env = np.mean((np.abs(z[:m * ENV_BIN]) ** 2).reshape(m, ENV_BIN), axis=1)
    return (10 * np.log10(psd + 1e-20)).astype(np.float32), env.astype(np.float32)


class Writer(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True); self.q = queue.Queue(maxsize=8); self.err = None

    def run(self):
        while True:
            item = self.q.get()
            if item is None:
                return
            path, raw, rec, fd = item
            try:
                data = raw.tobytes()
                with open(path, 'wb') as f:
                    f.write(data)
                rec.update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), **sl.fast_stats(raw))
                fd['psd'][rec['idx']], fd['env'][rec['idx']] = feats(raw)
            except Exception as e:  # noqa: BLE001
                self.err = repr(e)
            finally:
                self.q.task_done()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', required=True); ap.add_argument('--block', required=True); ap.add_argument('--cond', required=True)
    ap.add_argument('--count', type=int, default=2); ap.add_argument('--start', type=int, default=1)
    ap.add_argument('--budget', type=float, default=90.0); ap.add_argument('--dur', type=float, default=0.2)
    ap.add_argument('--root', default=r'<CAPTURE_ROOT>\data')
    ap.add_argument('--gain', default=str(HERE / 'gain_table_locked_v3_from_20261026.json'))
    ap.add_argument('--confirm', default=''); ap.add_argument('--camera', default='unknown'); ap.add_argument('--note', default='')
    a = ap.parse_args()
    base = pathlib.Path(a.root) / a.run; base.mkdir(parents=True, exist_ok=True)
    busy = pathlib.Path(a.root).parent / 'HW_BUSY.txt'
    st = dict(run=a.run, pid=os.getpid(), block=a.block, cond=a.cond, requested=a.count, done=0, failed=0, current=None,
              started=time.strftime('%Y-%m-%d %H:%M:%S'), phase='starting')
    sp = base / f'status_{a.block}_from{a.start:02d}.json'; T0 = time.time()
    save = lambda: js(sp, st)  # noqa: E731
    if busy.exists():
        raise RuntimeError('hardware busy ' + str(busy))
    if (base / 'STOP').exists():
        raise RuntimeError('STOP file exists')
    if shutil.disk_usage(base).free < a.count * 1.2e9 + 50e9:
        raise RuntimeError('insufficient disk')
    h = None; locked = False
    try:
        with open(busy, 'x', encoding='utf-8') as f:
            f.write(f'ws_desktop {a.run} {a.block} {a.cond} pid={os.getpid()}; do not move probe/camera')
        locked = True
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
        gp = pathlib.Path(a.gain); gains, _ = sl.load_gain_table(str(gp)); gsha = hashlib.sha256(gp.read_bytes()).hexdigest()
        h = rc.HackRF(); st['device'] = rc.device_meta(h); st['phase'] = 'collecting'; save()
        bands = sl.plan(0, 2500, 20)
        for k in range(a.start, a.start + a.count):
            if (base / 'STOP').exists():
                raise RuntimeError('STOP requested')
            if k > a.start and time.time() - T0 > a.budget:
                st['stopped_by_budget'] = k; print('budget reached before round', k, flush=True); break
            sid = f'{a.block}_r{k:02d}_{a.cond}'; out = base / 'raw' / sid
            if out.exists():
                raise RuntimeError('refusing overwrite ' + sid)
            out.mkdir(parents=True); st['current'] = sid; save()
            w = Writer(); w.start(); t0 = time.time(); recs = []
            fd = dict(psd=np.zeros((len(bands), NFFT), np.float32), env=np.zeros((len(bands), int(rc.SR * a.dur) // ENV_BIN), np.float32))
            for i, b in enumerate(bands):
                lna, vga = gains[b['start_mhz']]; t = time.time()
                raw, ok = h.record(b['lo_hz'], a.dur, lna, vga, settle=0.02)
                fn = f'band_{b["start_mhz"]:04d}MHz.iq8'
                rec = dict(b, idx=i, file=fn, lna=lna, vga=vga, complete=bool(ok and raw.size == int(rc.SR * a.dur) * 2), t_unix=t)
                recs.append(rec); w.q.put((str(out / fn), raw, rec, fd))
            w.q.join(); w.q.put(None); w.join()
            if w.err:
                raise RuntimeError('writer: ' + w.err)
            np.savez_compressed(out / 'features.npz', psd_db=fd['psd'], env=fd['env'], start_mhz=np.array([b['start_mhz'] for b in bands]),
                                lo_hz=np.array([b['lo_hz'] for b in bands]), nfft=NFFT, env_bin=ENV_BIN, sr=rc.SR)
            inc = sum(not x['complete'] for x in recs); clp = sum(x['clip_frac'] > 1e-4 for x in recs)
            man = dict(run=a.run, sid=sid, round=k, block=a.block, cond=a.cond, dur=a.dur, settle=0.02, sample_rate=rc.SR,
                       serial=h.serial, host=st['device']['host'], gain_table=str(gp), gain_table_sha256=gsha,
                       camera=a.camera, user_confirm=a.confirm, note=a.note,
                       state_source='manual_user_reported_not_automatically_verified', rf_amp=0, antenna_power=0,
                       t_sweep0=t0, t_sweep1=time.time(), n_incomplete=inc, n_clipped_bands=clp,
                       valid=bool(inc == 0 and clp == 0), technical_repeat=True, bands=recs)
            js(out / 'manifest.json', man)
            (out / 'SHA256SUMS').write_text(''.join(f"{x['sha256']}  {x['file']}\n" for x in recs), encoding='utf-8')
            st['done'] += 1; st['failed'] += int(not man['valid']); st['last_sweep_seconds'] = round(time.time() - t0, 1); save()
            print(sid, 'valid', man['valid'], 'sec', st['last_sweep_seconds'], 'incomplete', inc, 'clipped', clp, flush=True)
        st['phase'] = 'FINISHED'
    except Exception:
        st['phase'] = 'FAILED'; st['error'] = traceback.format_exc(); raise
    finally:
        if h:
            h.close()
        if locked:
            try:
                busy.unlink()
            except OSError:
                pass
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
        st['ended'] = time.strftime('%Y-%m-%d %H:%M:%S'); save()


if __name__ == '__main__':
    main()
