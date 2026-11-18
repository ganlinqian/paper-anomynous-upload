"""Pi functional pilot 2 (no RF): size S2 verify/extract phases with an incompressible payload."""
import fcntl, hashlib, json, os, pathlib, subprocess, sys, time
LOCK = '/home/pi/telltale_g1_20261026/controller.lock'
CPU = '/sys/devices/system/cpu/cpu0/cpufreq/'
OWNER = 'sp2027_pilot2_' + time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
def sh(c): return subprocess.run(c, shell=True, capture_output=True, text=True)
def timed(c):
    t = time.monotonic(); r = subprocess.run(c, shell=True, capture_output=True, text=True); assert r.returncode == 0, r.stderr; return time.monotonic() - t, r.stdout
root = pathlib.Path(sys.argv[1]); root.mkdir(parents=True, exist_ok=False); shm = pathlib.Path('/dev/shm/' + OWNER); shm.mkdir()
fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600); old = None; out = {'owner': OWNER}
try:
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB); os.write(fd, OWNER.encode())
    old = [open(CPU + 'scaling_governor').read().strip(), open(CPU + 'scaling_min_freq').read().strip()]
    assert sh("sudo -n sh -c 'echo performance > %sscaling_governor; echo 1800000 > %sscaling_min_freq'" % (CPU, CPU)).returncode == 0
    res = []
    for mib, level in [(64, 1), (96, 1), (64, 6)]:
        payload = root / ('pay_%d.bin' % mib); payload.write_bytes(hashlib.shake_256(b'Telltale:S2:payload:v1').digest(mib * 1024 * 1024))
        arc = root / ('pay_%d_l%d.gz' % (mib, level)); dc, _ = timed('gzip -n -%d -c %s > %s' % (level, payload, arc))
        digest = hashlib.sha256(arc.read_bytes()).hexdigest(); plain = hashlib.sha256(payload.read_bytes()).hexdigest()
        for rep in range(3):
            dv, o = timed('taskset -c 3 nice -n 10 sha256sum %s' % arc); assert o.split()[0] == digest
            dx, _ = timed('taskset -c 3 nice -n 10 gzip -dc %s > %s/x.bin' % (arc, shm))
            assert hashlib.sha256((shm / 'x.bin').read_bytes()).hexdigest() == plain
            (shm / 'x.bin').unlink(); time.sleep(2)
            res.append({'payload_mib': mib, 'level': level, 'archive_bytes': arc.stat().st_size, 'verify_s': round(dv, 3), 'extract_s': round(dx, 3)})
        payload.unlink(); arc.unlink()
    out['s2'] = res; out['temp'] = sh('vcgencmd measure_temp').stdout.strip()
finally:
    if old:
        out['restore_rc'] = sh("sudo -n sh -c 'echo %s > %sscaling_min_freq; echo %s > %sscaling_governor'" % (old[1], CPU, old[0], CPU)).returncode
    for q in list(root.glob('*')) + list(shm.glob('*')): q.unlink()
    shm.rmdir(); root.rmdir(); os.close(fd)
    if open(LOCK).read() == OWNER: os.unlink(LOCK)
    print(json.dumps(out), flush=True)
