"""Desktop (x86) transcript-equivalence study for the Telltale paper (E-D2).

Target: this data desktop (Intel Core i7-11700, DDR4, Windows), measured by the HackRF
attached to it (serial <hackrf-serial>) at the memory-load-responsive band found by
probe_sweep.py (~1.696 GHz). The tool host is a persistent worker process; the coordinator
(this process) dispatches each call, reads the receiver byte counter before dispatch and
after the reply (byte marks), and never uses host timestamps for binding.

Two fixtures, both with byte-identical responses and a fixed time envelope:
  order : a memory phase (64 MiB streaming multiply) and a compute phase (bz2 on 256 KiB),
          0.8 s each, in either order (M->C or C->M); response 'ok'.
  wait  : a 3.0 s wait for a 'network reply'; the violating variant runs zlib level 6 on
          16 MiB during the wait (hidden work), the compliant one stays idle; response 'ok'.
Each block holds the four variants in a seeded random order. Only frame features are kept
(64 band powers + total power per 10.24 ms frame); the raw IQ is hashed, not stored.

usage: python -I desktop_witness.py --batch train --blocks 12 --seed 1
"""
import argparse, bz2, ctypes, datetime, hashlib, json, multiprocessing as mp, os, random, shutil, socket, subprocess, sys, tempfile, threading, time, zlib
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1'); os.environ.setdefault('OMP_NUM_THREADS', '1')
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')
RF_DIR = r'<WORKSPACE>/ws_desktop\scripts'
LOCK = r'<CAPTURE_ROOT>\HW_BUSY.txt'
SERIAL = '<hackrf-serial>'
SR = 20e6
FRAME = 204_800            # 10.24 ms
NFFT = 1024
PHASE_S, ORDER_ENV, WAIT_S = 0.8, 2.0, 3.0
PRE_S, POST_S = 0.6, 0.4


# ---------------------------------------------------------------- tool host (untrusted side)
def _stage_dir(total_mib, files=8):
    d = os.path.join(tempfile.gettempdir(), f'cg_stage_{total_mib}')
    os.makedirs(os.path.join(d, 'workspace'), exist_ok=True)
    rng = np.random.default_rng(11)
    for i in range(files):
        p = os.path.join(d, 'workspace', f'f{i}.bin')
        if not os.path.exists(p) or os.path.getsize(p) != total_mib * 1024 * 1024 // files:
            with open(p, 'wb') as f:
                f.write(rng.integers(0, 256, total_mib * 1024 * 1024 // files, dtype=np.uint8).tobytes())
    return d


def tool_host(conn, hidden='zlib16'):
    buf = np.arange(64 * 1024 * 1024 // 4, dtype=np.uint32)
    k = np.uint32(2654435761)
    cpu_data = os.urandom(256 * 1024)
    rng = np.random.default_rng(7)
    payload = (rng.integers(0, 64, 16 * 1024 * 1024, dtype=np.uint8)).tobytes()   # compressible, 16 MiB
    rnd64 = os.urandom(64 * 1024 * 1024)
    tar = shutil.which('tar')
    sizes = {32, 256}
    if hidden.startswith('tar') and hidden[3:].isdigit():
        sizes.add(int(hidden[3:]))
    stage = {m: _stage_dir(m) for m in sizes}

    def hidden_work():
        if hidden == 'zlib16':
            zlib.compress(payload, 6)
        elif hidden == 'zlib64':
            zlib.compress(rnd64, 1)
        elif hidden == 'tgz32' or (hidden.startswith('tar') and hidden[3:].isdigit()):
            m = 32 if hidden == 'tgz32' else int(hidden[3:])
            out = os.path.join(stage[m], 'stage.tgz' if hidden == 'tgz32' else 'stage.tar')
            flags = '-czf' if hidden == 'tgz32' else '-cf'
            subprocess.run([tar, flags, out, '-C', stage[m], 'workspace'], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            os.remove(out)
        else:
            raise ValueError(hidden)

    def mem_phase(t):
        end = time.perf_counter() + t
        while time.perf_counter() < end:
            np.multiply(buf, k, out=buf)

    def cpu_phase(t):
        end = time.perf_counter() + t
        while time.perf_counter() < end:
            bz2.compress(cpu_data, 9)

    while True:
        msg = conn.recv()
        if msg is None:
            return
        kind, variant = msg
        t0 = time.perf_counter()
        if kind == 'order':
            first, second = (mem_phase, cpu_phase) if variant == 'MC' else (cpu_phase, mem_phase)
            first(PHASE_S); second(PHASE_S)
            env = ORDER_ENV
        else:
            if variant == 'hidden':
                hidden_work()
            env = WAIT_S
        rest = env - (time.perf_counter() - t0)
        if rest > 0:
            time.sleep(rest)
        conn.send('ok')


# ---------------------------------------------------------------- receiver with byte counter
class Recorder:
    def __init__(self, rc, seconds_max=8.0):
        self.rc = rc
        self.lib = rc._load_dll()
        if self.lib.hackrf_init() != 0:
            raise RuntimeError('hackrf_init failed')
        self.dev = ctypes.c_void_p(0)
        if self.lib.hackrf_open(ctypes.byref(self.dev)) != 0:
            raise RuntimeError('hackrf_open failed')
        ps = rc._PartSerial()
        self.lib.hackrf_board_partid_serialno_read(self.dev, ctypes.byref(ps))
        self.serial = ''.join(f'{x:08x}' for x in ps.serial_no)
        ver = ctypes.create_string_buffer(255)
        self.lib.hackrf_version_string_read(self.dev, ver, 255)
        self.firmware = ver.value.decode(errors='replace')
        self.lib.hackrf_set_amp_enable(self.dev, 0)
        self.lib.hackrf_set_antenna_enable(self.dev, 0)
        self.cap = int(SR * seconds_max) * 2
        self.buf = bytearray(self.cap)
        self.cbuf = (ctypes.c_char * self.cap).from_buffer(self.buf)
        self.addr = ctypes.addressof(self.cbuf)
        self.lock = threading.Lock()
        self.got = 0
        self.cb = rc._CB(self._cb)

    def _cb(self, tp):
        t = tp.contents
        n = t.valid_length
        if n <= 0:
            return 0
        with self.lock:
            room = self.cap - self.got
            take = n if n < room else room
            if take > 0:
                ctypes.memmove(self.addr + self.got, t.buffer, take)
                self.got += take
            return 0 if self.got < self.cap else -1

    def tune(self, lo_hz, lna, vga):
        L = self.lib
        L.hackrf_set_sample_rate(self.dev, ctypes.c_double(SR))
        L.hackrf_set_baseband_filter_bandwidth(self.dev, ctypes.c_uint32(self.rc.BBF))
        L.hackrf_set_lna_gain(self.dev, ctypes.c_uint32(lna))
        L.hackrf_set_vga_gain(self.dev, ctypes.c_uint32(vga))
        L.hackrf_set_freq(self.dev, ctypes.c_uint64(int(lo_hz)))

    def start(self):
        with self.lock:
            self.got = 0
        return self.lib.hackrf_start_rx(self.dev, self.cb, None)

    def count(self):
        with self.lock:
            return self.got

    def stop(self):
        self.lib.hackrf_stop_rx(self.dev)
        time.sleep(0.02)
        with self.lock:
            n = self.got
        return np.frombuffer(bytes(self.buf[:n]), dtype=np.int8)

    def close(self):
        for fn, a in ((self.lib.hackrf_stop_rx, (self.dev,)), (self.lib.hackrf_close, (self.dev,)), (self.lib.hackrf_exit, ())):
            try:
                fn(*a)
            except Exception:
                pass


# ---------------------------------------------------------------- frame features (as on the Pi)
_f = np.fft.fftfreq(NFFT, 1 / SR)
_band_edges = np.linspace(0, 10e6, 65)
_absf = np.abs(_f)
_valid = (_absf >= 0.15e6) & (_absf <= 9e6)
_band_of = np.clip(np.searchsorted(_band_edges, _absf, side='right') - 1, 0, 63)
_WIN = np.hanning(NFFT).astype(np.float32)


def frame_features(raw):
    x = raw.astype(np.float32).reshape(-1, 2)
    z = (x[:, 0] + 1j * x[:, 1]).astype(np.complex64) / 128.0
    nfr = z.size // FRAME
    out = np.full((nfr, 65), np.nan, np.float32)
    counts = np.bincount(_band_of[_valid], minlength=64).astype(np.float32)
    for i in range(nfr):
        fr = z[i * FRAME:(i + 1) * FRAME]
        out[i, 64] = 10 * np.log10(np.mean(np.abs(fr) ** 2) + 1e-20)
        seg = fr.reshape(-1, NFFT)
        seg = seg - seg.mean(axis=1, keepdims=True)
        p = np.mean(np.abs(np.fft.fft(seg * _WIN, axis=1)) ** 2, axis=0)
        bp = np.bincount(_band_of[_valid], weights=p[_valid], minlength=64)
        with np.errstate(divide='ignore', invalid='ignore'):
            out[i, :64] = 10 * np.log10(bp / np.maximum(counts, 1) + 1e-20)
    out[:, :64][:, counts == 0] = np.nan
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--batch', required=True)
    ap.add_argument('--blocks', type=int, default=12)
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--lo', type=float, default=1.6955e9)
    ap.add_argument('--lna', type=int, default=24)
    ap.add_argument('--vga', type=int, default=20)
    ap.add_argument('--out', default='runs')
    ap.add_argument('--hidden', default='zlib16', help='hidden work: zlib16 | zlib64 | tgz32 | tar256')
    ap.add_argument('--kinds', default='order,wait')
    a = ap.parse_args()
    outdir = os.path.join(a.out, a.batch)
    os.makedirs(outdir, exist_ok=True)
    if os.path.exists(LOCK):
        print('LOCK present, abort:', open(LOCK, encoding='utf-8', errors='replace').read()); return 2
    with open(LOCK, 'w', encoding='utf-8') as f:
        f.write(f'telltale desktop_witness {a.batch}, session ws_main, pid {os.getpid()}, {datetime.datetime.now().astimezone().isoformat()}\n')
    sys.path.insert(0, RF_DIR)
    import rf_capture as rc
    rnd = random.Random(a.seed)
    kinds = a.kinds.split(',')
    variants = [v for v in [('order', 'MC'), ('order', 'CM'), ('wait', 'hidden'), ('wait', 'silent')] if v[0] in kinds]
    schedule = []
    for b in range(a.blocks):
        blk = variants[:]; rnd.shuffle(blk)
        schedule += [(b, *v) for v in blk]
    ctx = mp.get_context('spawn')
    parent, child = ctx.Pipe()
    host = ctx.Process(target=tool_host, args=(child, a.hidden), daemon=True)
    host.start()
    rec = None
    manifest = dict(batch=a.batch, seed=a.seed, blocks=a.blocks, lo_hz=a.lo, lna=a.lna, vga=a.vga, sr=SR, frame=FRAME, hidden=a.hidden,
                    host=socket.gethostname(), started=datetime.datetime.now().astimezone().isoformat(), runs=[])
    try:
        rec = Recorder(rc)
        manifest.update(serial=rec.serial, firmware=rec.firmware)
        if rec.serial != SERIAL:
            print('unexpected serial', rec.serial); return 3
        rec.tune(a.lo, a.lna, a.vga)
        # warm-up: one throwaway capture so the tuner and the worker are settled
        rec.start(); time.sleep(0.5); rec.stop()
        parent.send(('wait', 'silent')); parent.recv()
        for i, (blk, kind, variant) in enumerate(schedule):
            rid = f'{a.batch}_{i:03d}'
            rc0 = rec.start()
            time.sleep(PRE_S)
            m1 = rec.count(); t1 = time.perf_counter()
            parent.send((kind, variant))
            resp = parent.recv()
            t2 = time.perf_counter(); m2 = rec.count()
            time.sleep(POST_S)
            raw = rec.stop()
            sha = hashlib.sha256(raw.tobytes()).hexdigest()
            feats = frame_features(raw)
            np.save(os.path.join(outdir, rid + '.npy'), feats)
            row = dict(run=rid, block=blk, kind=kind, variant=variant, A=int(variant in ('MC', 'hidden')),
                       response=resp, start_rc=int(rc0), n_bytes=int(raw.size), sha256=sha,
                       mark1_sample=int(m1 // 2), mark2_sample=int(m2 // 2), coord_dt=t2 - t1, n_frames=int(feats.shape[0]))
            manifest['runs'].append(row)
            print(f"{rid} blk={blk} {kind}/{variant} dt={t2 - t1:.3f}s bytes={raw.size} frames={feats.shape[0]}", flush=True)
            time.sleep(1.5)
    finally:
        try:
            parent.send(None)
        except Exception:
            pass
        host.join(5)
        if rec is not None:
            rec.close()
        manifest['ended'] = datetime.datetime.now().astimezone().isoformat()
        with open(os.path.join(outdir, 'manifest.json'), 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=1)
        try:
            os.remove(LOCK)
        except OSError:
            pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
