"""Pi functional pilot for planned S&P supplements (no RF, no model calls).

Measures, under the capture-time CPU setting (performance governor, 1.8 GHz floor):
  * N1 real verify/extract phases: sha256sum of a gzip archive and gzip -dc to tmpfs;
  * N2 throttled hidden archiving: gzip -1 on the C07 fixture prefix at several duty cycles
    (cpulimit-style SIGSTOP/SIGCONT), to choose sizes that stay inside a 4 s wait.
Holds the shared Pi controller lock for the whole run and restores CPU settings in finally.
"""
import fcntl, hashlib, json, os, pathlib, random, signal, subprocess, sys, time

LOCK = '/home/pi/telltale_g1_20261026/controller.lock'
CPU = '/sys/devices/system/cpu/cpu0/cpufreq/'
OWNER = 'sp2027_pilot_' + time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())

def sh(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)

def gzip_throttled(src, dst, duty, period=0.02):
    t0 = time.monotonic()
    with open(dst, 'wb') as fo:
        p = subprocess.Popen(['taskset', '-c', '3', 'nice', '-n', '10', 'gzip', '-n', '-1', '-c', src], stdout=fo, stderr=subprocess.PIPE)
        if duty < 1.0:
            on, off = duty * period, (1 - duty) * period
            while p.poll() is None:
                time.sleep(on)
                if p.poll() is not None:
                    break
                try:
                    os.kill(p.pid, signal.SIGSTOP); time.sleep(off); os.kill(p.pid, signal.SIGCONT)
                except ProcessLookupError:
                    break
        rc = p.wait(); fo.flush(); os.fsync(fo.fileno())
    assert rc == 0, p.stderr.read()
    return time.monotonic() - t0

def timed(cmd):
    t0 = time.monotonic(); r = subprocess.run(cmd, shell=True, capture_output=True, text=True); dt = time.monotonic() - t0
    assert r.returncode == 0, r.stderr
    return dt, r.stdout

def text_fixture(path, mib, seed):
    rng = random.Random(seed)
    vocab = ['agent', 'tool', 'call', 'verify', 'extract', 'package', 'digest', 'skill', 'gateway', 'config', 'error', 'info',
             'warn', 'debug', 'user', 'file', 'path', 'value', 'result', 'status', 'session', 'token', 'cache', 'build']
    block = []
    size = 0
    while size < 1024 * 1024:
        line = '%08d %s\n' % (rng.randrange(10 ** 8), ' '.join(rng.choice(vocab) for _ in range(rng.randrange(6, 14))))
        block.append(line); size += len(line)
    base = ''.join(block).encode()[:1024 * 1024]
    with open(path, 'wb') as f:
        for i in range(mib):
            f.write(('#block %06d\n' % i).encode() + base[13:])

def main():
    root = pathlib.Path(sys.argv[1]); root.mkdir(parents=True, exist_ok=False)
    shm = pathlib.Path('/dev/shm/' + OWNER); shm.mkdir()
    fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    old = None
    out = {'owner': OWNER, 'utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB); os.write(fd, OWNER.encode())
        old = [open(CPU + 'scaling_governor').read().strip(), open(CPU + 'scaling_min_freq').read().strip()]
        busy = '\n'.join(l for l in sh("pgrep -af '^(perf|strace|resident_tool|python3.*telltale)' || true").stdout.splitlines()
                         if l.strip() and int(l.split()[0]) != os.getpid())
        if busy:
            raise RuntimeError('Pi occupied: ' + busy)
        assert sh("sudo -n sh -c 'echo performance > %sscaling_governor; echo 1800000 > %sscaling_min_freq'" % (CPU, CPU)).returncode == 0
        out['cpu_before'] = old
        out['throttled'] = sh('vcgencmd get_throttled').stdout.strip(); out['temp'] = sh('vcgencmd measure_temp').stdout.strip()
        # ---- N2: throttled gzip on prefixes of the C07 fixture (identical seed)
        full = hashlib.shake_256(b'Telltale:C07:20261104:fixture:v1').digest(16 * 1024 * 1024)
        for mib in (16, 8, 4, 2):
            (root / ('rand_%d.bin' % mib)).write_bytes(full[:mib * 1024 * 1024])
        n2 = []
        for mib, duty in [(16, 1.0), (8, 1.0), (8, 0.5), (4, 0.25), (2, 0.125), (4, 0.5), (2, 0.25)]:
            for rep in range(2):
                dst = root / ('o_%d_%g_%d.gz' % (mib, duty, rep))
                dt = gzip_throttled(str(root / ('rand_%d.bin' % mib)), str(dst), duty)
                n2.append({'mib': mib, 'duty': duty, 'rep': rep, 'seconds': round(dt, 3), 'out_bytes': dst.stat().st_size}); dst.unlink()
                time.sleep(2)
        out['n2_throttled_gzip'] = n2
        # ---- N1: real verify / extract phases on a compressible archive
        n1 = []
        for mib in (48, 96):
            src = root / ('text_%d.bin' % mib); text_fixture(src, mib, 20261105)
            arc = root / ('text_%d.bin.gz' % mib)
            dt_c, _ = timed('gzip -n -6 -c %s > %s' % (src, arc))
            digest = hashlib.sha256(arc.read_bytes()).hexdigest(); plain = hashlib.sha256(src.read_bytes()).hexdigest()
            for rep in range(3):
                dv, o = timed('taskset -c 3 nice -n 10 sha256sum %s' % arc)
                assert o.split()[0] == digest
                dx, _ = timed('taskset -c 3 nice -n 10 gzip -dc %s > %s/x.bin' % (arc, shm))
                assert hashlib.sha256((shm / 'x.bin').read_bytes()).hexdigest() == plain
                (shm / 'x.bin').unlink(); time.sleep(2)
                n1.append({'plain_mib': mib, 'archive_bytes': arc.stat().st_size, 'compress_s': round(dt_c, 3), 'verify_s': round(dv, 3), 'extract_s': round(dx, 3), 'rep': rep})
            src.unlink(); arc.unlink()
        out['n1_verify_extract'] = n1
        out['temp_after'] = sh('vcgencmd measure_temp').stdout.strip()
    finally:
        if old:
            out['restore_rc'] = sh("sudo -n sh -c 'echo %s > %sscaling_min_freq; echo %s > %sscaling_governor'" % (old[1], CPU, old[0], CPU)).returncode
            out['cpu_after'] = [open(CPU + 'scaling_governor').read().strip(), open(CPU + 'scaling_min_freq').read().strip()]
        for p in list(root.glob('*')) + list(shm.glob('*')):
            p.unlink()
        shm.rmdir()
        os.close(fd)
        if open(LOCK).read() == OWNER:
            os.unlink(LOCK)
        print(json.dumps(out), flush=True)

if __name__ == '__main__':
    main()
