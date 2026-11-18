"""0–2.5 GHz <HOST> rf_capture.py  ctypes HackRF IQ=int8

2026-10-09 stop/start  2 ms / settle  0.02 s 0.07 s
"""
import hashlib
import json
import os
import queue
import threading
import time

import numpy as np

import rf_capture as rc

SR = rc.SR
SETTLE = 0.02


def plan(f0=0, f1=2500, step=20):
    return [dict(start_mhz=s, lo_hz=int((s + step / 2) * 1e6)) for s in range(f0, f1, step)]


def fast_stats(raw):
    i, q = raw[0::2], raw[1::2]
    fi, fq = i.astype(np.float32), q.astype(np.float32)
    return dict(clip_frac=float(np.mean((np.abs(i) >= 127) | (np.abs(q) >= 127))),
                rms_fs=float(np.sqrt(np.mean(fi * fi + fq * fq) / 2.0) / 128.0),
                peak_fs=float(max(np.abs(fi).max(), np.abs(fq).max()) / 128.0),
                dc_i=float(fi.mean() / 128.0), dc_q=float(fq.mean() / 128.0),
                std_i_lsb=float(fi.std()), std_q_lsb=float(fq.std()))


class Writer(threading.Thread):
    """ + SHA-256 + """

    def __init__(self):
        super().__init__(daemon=True)
        self.q = queue.Queue(maxsize=16)
        self.err = None

    def run(self):
        while True:
            item = self.q.get()
            if item is None:
                return
            path, raw, rec = item
            try:
                data = raw.tobytes()
                with open(path, 'wb') as f:
                    f.write(data)
                rec.update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), **fast_stats(raw))
            except Exception as e:      # noqa: BLE001
                self.err = repr(e)
            finally:
                self.q.task_done()


def sweep(h, bands, gains, dur, out_dir, writer, settle=SETTLE, stop_check=None, prefix=''):
    """ writer  writer.q.join()"""
    os.makedirs(out_dir, exist_ok=True)
    recs = []
    for b in bands:
        if stop_check and stop_check():
            break
        lna, vga = gains[b['start_mhz']]
        t = time.time()
        raw, ok = h.record(b['lo_hz'], dur, lna, vga, settle=settle)
        fn = (f'band_{b["start_mhz"]:04d}MHz.iq8' if not prefix
              else f'{prefix}{b["lo_hz"] / 1e3:.0f}kHz_{lna}_{vga}.iq8')
        rec = dict(b, file=fn, lna=lna, vga=vga, complete=ok, t_unix=t)
        recs.append(rec)
        writer.q.put((os.path.join(out_dir, fn), raw, rec))
    return recs


def load_gain_table(path):
    with open(path, encoding='utf-8') as f:
        gt = json.load(f)
    return {int(k): tuple(v) for k, v in gt['table'].items()}, gt
