#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HackRF One  <HOST> embeddable Python 3.11 + numpy

ctypes  <CAPTURE_LIBRARY>/hackrf_iface.py HackRFSN <hackrf-serial>
IQ  signed int8 settle HackRF  RF amp(14 dB)  bias-tee 

  python rf_capture.py info
  python rf_capture.py calib   --run R --gains 16/16 24/24 32/24 --dur 0.1
  python rf_capture.py capture --run R --gain-table gain_table.json --dur 0.5   # 
  python rf_capture.py capture --run R --lna 24 --vga 24 --dur 0.5              # 
<CAPTURE_ROOT>/data/<run>/band_XXXXMHz.iq8int8  IQ+ manifest.json
"""
import argparse
import ctypes
import hashlib
import json
import os
import shutil
import socket
import sys
import threading
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
# 2026-10-27HackRF  SDR++  hackrf.dll<CAPTURE_LIBRARY>
DLL_DIR = os.environ.get('HACKRF_DLL_DIR', r'<DRIVE>/sdrpp\sdrpp_windows_x64')
DATA_ROOT = os.path.join(HERE, 'data')
os.add_dll_directory(DLL_DIR)

SR = 20e6
BBF = 20_000_000                         #  20 MHz 20 MHz
BAND_MHZ = 20
STARTS_MHZ = list(range(0, 3001, 100))   # 0-20, 100-120, ..., 3000-3020 MHz 31
BUDGET_BYTES = 1_000_000_000             #  <= 1 GB
SETTLE_SEC = 0.30
HACKRF_SUCCESS = 0


class _Transfer(ctypes.Structure):
    _fields_ = [('device', ctypes.c_void_p),
                ('buffer', ctypes.POINTER(ctypes.c_uint8)),
                ('buffer_length', ctypes.c_int),
                ('valid_length', ctypes.c_int),
                ('rx_ctx', ctypes.c_void_p),
                ('tx_ctx', ctypes.c_void_p)]


class _PartSerial(ctypes.Structure):
    _fields_ = [('part_id', ctypes.c_uint32 * 2), ('serial_no', ctypes.c_uint32 * 4)]


_CB = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.POINTER(_Transfer))


def _load_dll():
    lib = ctypes.CDLL(os.path.join(DLL_DIR, 'hackrf.dll'))
    sig = [('hackrf_init', ctypes.c_int, []),
           ('hackrf_exit', ctypes.c_int, []),
           ('hackrf_open', ctypes.c_int, [ctypes.POINTER(ctypes.c_void_p)]),
           ('hackrf_close', ctypes.c_int, [ctypes.c_void_p]),
           ('hackrf_set_freq', ctypes.c_int, [ctypes.c_void_p, ctypes.c_uint64]),
           ('hackrf_set_sample_rate', ctypes.c_int, [ctypes.c_void_p, ctypes.c_double]),
           ('hackrf_set_lna_gain', ctypes.c_int, [ctypes.c_void_p, ctypes.c_uint32]),
           ('hackrf_set_vga_gain', ctypes.c_int, [ctypes.c_void_p, ctypes.c_uint32]),
           ('hackrf_set_amp_enable', ctypes.c_int, [ctypes.c_void_p, ctypes.c_uint8]),
           ('hackrf_set_antenna_enable', ctypes.c_int, [ctypes.c_void_p, ctypes.c_uint8]),
           ('hackrf_set_baseband_filter_bandwidth', ctypes.c_int, [ctypes.c_void_p, ctypes.c_uint32]),
           ('hackrf_start_rx', ctypes.c_int, [ctypes.c_void_p, _CB, ctypes.c_void_p]),
           ('hackrf_stop_rx', ctypes.c_int, [ctypes.c_void_p]),
           ('hackrf_board_id_read', ctypes.c_int, [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint8)]),
           ('hackrf_version_string_read', ctypes.c_int, [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint8]),
           ('hackrf_board_partid_serialno_read', ctypes.c_int,
            [ctypes.c_void_p, ctypes.POINTER(_PartSerial)])]
    for name, res, args in sig:
        fn = getattr(lib, name)
        fn.restype, fn.argtypes = res, args
    return lib


class HackRF:
    def __init__(self):
        self._lib = _load_dll()
        if self._lib.hackrf_init() != HACKRF_SUCCESS:
            raise RuntimeError('hackrf_init ')
        self._dev = ctypes.c_void_p(0)
        r = self._lib.hackrf_open(ctypes.byref(self._dev))
        if r != HACKRF_SUCCESS or not self._dev.value:
            raise RuntimeError(f'hackrf_open _ (code {r})_ USB _ / _')
        bid = ctypes.c_uint8(0)
        self._lib.hackrf_board_id_read(self._dev, ctypes.byref(bid))
        ver = ctypes.create_string_buffer(255)
        self._lib.hackrf_version_string_read(self._dev, ver, 255)
        ps = _PartSerial()
        self._lib.hackrf_board_partid_serialno_read(self._dev, ctypes.byref(ps))
        self.board_id = bid.value
        self.firmware = ver.value.decode(errors='replace')
        self.serial = ''.join(f'{x:08x}' for x in ps.serial_no)
        self._lib.hackrf_set_amp_enable(self._dev, 0)
        self._lib.hackrf_set_antenna_enable(self._dev, 0)
        self._lock = threading.Lock()
        self._done = threading.Event()
        self._addr, self._need, self._got = 0, 0, 0
        self._cb_ref = _CB(self._rx_cb)
        self._cur = {}

    def _rx_cb(self, tp):
        t = tp.contents
        n = t.valid_length
        if n <= 0:
            return 0
        with self._lock:
            room = self._need - self._got
            if room <= 0:
                self._done.set()
                return -1
            take = n if n < room else room
            ctypes.memmove(self._addr + self._got, t.buffer, take)
            self._got += take
            if self._got >= self._need:
                self._done.set()
                return -1
        return 0

    def _set(self, key, val, fn, cval):
        if self._cur.get(key) != val:
            fn(self._dev, cval)
            self._cur[key] = val

    def record(self, lo_hz, seconds, lna, vga, settle=SETTLE_SEC):
        """ lo_hz settle  seconds  (int8  IQ, )"""
        lib = self._lib
        self._set('sr', SR, lib.hackrf_set_sample_rate, ctypes.c_double(SR))
        self._set('bbf', BBF, lib.hackrf_set_baseband_filter_bandwidth, ctypes.c_uint32(BBF))
        self._set('lna', lna, lib.hackrf_set_lna_gain, ctypes.c_uint32(lna))
        self._set('vga', vga, lib.hackrf_set_vga_gain, ctypes.c_uint32(vga))
        lib.hackrf_set_freq(self._dev, ctypes.c_uint64(int(lo_hz)))
        n_settle = int(SR * settle) * 2
        need = n_settle + int(SR * seconds) * 2
        buf = bytearray(need)
        cbuf = (ctypes.c_char * need).from_buffer(buf)
        with self._lock:
            self._addr, self._need, self._got = ctypes.addressof(cbuf), need, 0
            self._done.clear()
        lib.hackrf_start_rx(self._dev, self._cb_ref, None)
        ok = self._done.wait(timeout=seconds + settle + 5.0)
        lib.hackrf_stop_rx(self._dev)
        time.sleep(0.02)
        with self._lock:
            got = self._got
        del cbuf
        arr = np.frombuffer(bytes(buf[:got]), dtype=np.int8)
        return arr[n_settle:], bool(ok and got >= need)

    def close(self):
        for fn, a in ((self._lib.hackrf_stop_rx, (self._dev,)),
                      (self._lib.hackrf_close, (self._dev,)),
                      (self._lib.hackrf_exit, ())):
            try:
                fn(*a)
            except Exception:
                pass


def iq_stats(raw):
    i, q = raw[0::2], raw[1::2]
    fi, fq = i.astype(np.float32), q.astype(np.float32)
    d = np.flatnonzero(np.diff(i) != 0)
    runs = np.diff(np.concatenate(([-1], d, [i.size - 1]))) if i.size else np.array([0])
    return dict(n_complex=int(i.size),
                clip_frac=float(np.mean((np.abs(fi) >= 127) | (np.abs(fq) >= 127))),
                rms_fs=float(np.sqrt(np.mean(fi * fi + fq * fq) / 2.0) / 128.0),
                peak_fs=float(max(np.abs(fi).max(), np.abs(fq).max()) / 128.0),
                dc_i=float(fi.mean() / 128.0), dc_q=float(fq.mean() / 128.0),
                std_i_lsb=float(fi.std()), std_q_lsb=float(fq.std()),
                zero_pair_frac=float(np.mean((i == 0) & (q == 0))),
                max_const_run=int(runs.max()))


def plan(starts):
    return [dict(start_mhz=s, lo_hz=int((s + BAND_MHZ / 2) * 1e6)) for s in starts]


def device_meta(h):
    return dict(host=socket.gethostname(), serial=h.serial, board_id=h.board_id,
                firmware=h.firmware, sample_rate=SR, baseband_filter_hz=BBF,
                rf_amp=0, antenna_power=0, iq_format='int8 interleaved I,Q', settle_sec=SETTLE_SEC)


def cmd_info(a):
    h = HackRF()
    try:
        print(json.dumps(device_meta(h), ensure_ascii=False, indent=1))
        raw, ok = h.record(100e6 + 10e6, 0.05, 16, 16)
        print('smoke 100-120MHz LNA16/VGA16 0.05s complete=%s' % ok, json.dumps(iq_stats(raw)))
    finally:
        h.close()


def cmd_calib(a):
    out = os.path.join(DATA_ROOT, a.run)
    os.makedirs(out, exist_ok=True)
    gains = [tuple(int(x) for x in g.split('/')) for g in a.gains]
    h = HackRF()
    res = dict(device_meta(h), dur=a.dur, gains=[list(g) for g in gains], bands=[])
    t0 = time.time()
    try:
        for lna, vga in gains:
            for b in plan(a.starts):
                raw, ok = h.record(b['lo_hz'], a.dur, lna, vga)
                st = iq_stats(raw)
                res['bands'].append(dict(b, lna=lna, vga=vga, complete=ok, **st))
            rows = [r for r in res['bands'] if r['lna'] == lna and r['vga'] == vga]
            worst = max(rows, key=lambda r: r['peak_fs'])
            print(f'LNA{lna:2d}/VGA{vga:2d}: max clip={max(r["clip_frac"] for r in rows):.2e} '
                  f'max peak={worst["peak_fs"]:.3f}@{worst["start_mhz"]}MHz '
                  f'median rms={np.median([r["rms_fs"] for r in rows]):.4f} '
                  f'median std_i={np.median([r["std_i_lsb"] for r in rows]):.2f}LSB '
                  f'incomplete={sum(not r["complete"] for r in rows)}', flush=True)
    finally:
        h.close()
    res['wall_sec'] = time.time() - t0
    with open(os.path.join(out, 'calib.json'), 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print('calib saved', os.path.join(out, 'calib.json'), f'{res["wall_sec"]:.1f}s')


def cmd_capture(a):
    bands = plan(a.starts)
    per_band = int(SR * a.dur) * 2
    total = per_band * len(bands)
    print(f'plan: {len(bands)} bands x {a.dur}s x {SR / 1e6:.0f}MS/s x 2B = {total / 1e9:.3f} GB')
    if total > BUDGET_BYTES:
        sys.exit(f'_ 1 GB _{total / 1e9:.2f} GB_')
    out = os.path.join(DATA_ROOT, a.run)
    if os.path.exists(os.path.join(out, 'manifest.json')):
        sys.exit(f'{out} _ manifest.json_')
    os.makedirs(out, exist_ok=True)
    free = shutil.disk_usage(out).free
    if free < total + 5e9:
        sys.exit(f'_ {free / 1e9:.1f} GB _ {total / 1e9 + 5:.1f} GB_')
    if a.gain_table:
        with open(a.gain_table, encoding='utf-8') as f:
            gt = json.load(f)
        gains = {int(k): tuple(v) for k, v in gt['table'].items()}
        missing = [b['start_mhz'] for b in bands if b['start_mhz'] not in gains]
        if missing:
            sys.exit(f'_ {missing}')
    elif a.lna is None or a.vga is None:
        sys.exit(' --gain-table  --lna/--vga')
    else:
        gains = {b['start_mhz']: (a.lna, a.vga) for b in bands}
    h = HackRF()
    man = dict(device_meta(h), run=a.run, dur=a.dur, band_mhz=BAND_MHZ, note=a.note,
               gain_table=gt if a.gain_table else None,
               t_start=time.strftime('%Y-%m-%d %H:%M:%S'), bands=[])
    t0 = time.time()
    try:
        for b in bands:
            tb = time.time()
            lna, vga = gains[b['start_mhz']]
            raw, ok = h.record(b['lo_hz'], a.dur, lna, vga)
            st = iq_stats(raw)
            fn = f'band_{b["start_mhz"]:04d}MHz.iq8'
            data = raw.tobytes()
            with open(os.path.join(out, fn), 'wb') as f:
                f.write(data)
            man['bands'].append(dict(b, file=fn, bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                                     lna=lna, vga=vga, complete=ok, t_unix=tb, **st))
            print(f'{b["start_mhz"]:4d}-{b["start_mhz"] + BAND_MHZ}MHz G{lna}/{vga} ok={ok} {len(data) / 1e6:.1f}MB '
                  f'rms={st["rms_fs"]:.4f} peak={st["peak_fs"]:.3f} clip={st["clip_frac"]:.1e} '
                  f'{time.time() - tb:.2f}s', flush=True)
            with open(os.path.join(out, 'manifest.json'), 'w', encoding='utf-8') as f:
                json.dump(man, f, ensure_ascii=False, indent=1)
    finally:
        h.close()
    man['t_end'] = time.strftime('%Y-%m-%d %H:%M:%S')
    man['wall_sec'] = time.time() - t0
    man['total_bytes'] = sum(b['bytes'] for b in man['bands'])
    with open(os.path.join(out, 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(man, f, ensure_ascii=False, indent=1)
    print(f'done {len(man["bands"])} bands {man["total_bytes"] / 1e9:.3f} GB in {man["wall_sec"]:.1f}s -> {out}')


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='op', required=True)
    sub.add_parser('info')
    c = sub.add_parser('calib')
    c.add_argument('--run', required=True)
    c.add_argument('--gains', nargs='+', default=['16/16', '24/24', '32/24'])
    c.add_argument('--dur', type=float, default=0.1)
    c.add_argument('--starts', type=int, nargs='+', default=STARTS_MHZ)
    p = sub.add_parser('capture')
    p.add_argument('--run', required=True)
    p.add_argument('--gain-table')
    p.add_argument('--lna', type=int)
    p.add_argument('--vga', type=int)
    p.add_argument('--dur', type=float, default=0.5)
    p.add_argument('--starts', type=int, nargs='+', default=STARTS_MHZ)
    p.add_argument('--note', default='')
    a = ap.parse_args()
    {'info': cmd_info, 'calib': cmd_calib, 'capture': cmd_capture}[a.op](a)


if __name__ == '__main__':
    main()
