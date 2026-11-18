"""No-RF Pi pilot for C27: times bzip2 -1 on 1-4 MiB of the C07 random fixture and gzip -1 on the json8 fixture under
campaign conditions (performance governor, 1.8 GHz floor, core 3, nice 10).  Takes the controller lock, restores the
governor, removes its directory.  Rule fixed in the protocol: bzip2 MiB = largest of {1,2,3,4} with median <= 1.5 s."""
import hashlib, json, pathlib, shlex, statistics, sys, time
SRC = pathlib.Path(r'<WORKSPACE>/ws_pi\results\scenario_rf_20261104')
E = pathlib.Path(r'<WORKSPACE>/ws_main\results\sp2027\experiments')
sys.path.insert(0, str(SRC / 'burst_study'))
from bridge_utils import connect, run, snapshot, guard  # noqa: E402
SEED = b'Telltale:C07:20261104:fixture:v1'; MIB = 1024 * 1024
lock = '/home/pi/telltale_g1_20261026/controller.lock'; pr = '/home/pi/telltale_sp2027/pilot_bzip2_' + time.strftime('%Y%m%d_%H%M%S', time.gmtime())
p = connect('192.0.2.60', 'admin', 522); pf = p.open_sftp(); out = {'dir': pr}
pre = guard(p); old = pre['state'].splitlines()[:3]; out['pre'] = pre
assert not run(p, "pgrep -af '^(perf|strace|resident_tool|python3.*telltale)' || true")['stdout'].strip(), 'Pi busy'
code = ('import os,fcntl,sys\np=' + repr(lock) + '\nfd=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)\ntry:\n fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)\n os.write(fd,b"pilot")\n'
        " print('LOCKED',flush=True)\n sys.stdin.read()\nfinally:\n os.close(fd)\n if open(p).read()=='pilot':os.unlink(p)\n")
li, lo, le = p.exec_command('python3 -u -c ' + shlex.quote(code), timeout=30); assert lo.readline().strip() == 'LOCKED'
try:
    out['which'] = run(p, 'command -v bzip2 gzip; bzip2 --version 2>&1 | head -1')['stdout']
    run(p, 'mkdir -p ' + pr)
    gen = 'import hashlib,pathlib;d=hashlib.shake_256(' + repr(SEED) + ').digest(' + str(4 * MIB) + ')\n'
    for n in (1, 2, 3, 4):
        gen += 'pathlib.Path(' + repr(pr + '/rand%d.bin' % n) + ').write_bytes(d[:' + str(n * MIB) + '])\n'
    run(p, 'python3 -c ' + shlex.quote(gen), timeout=60)
    full = hashlib.shake_256(SEED).digest(4 * MIB)
    for n in (1, 2, 3, 4):
        assert run(p, 'sha256sum ' + pr + '/rand%d.bin' % n)['stdout'].split()[0] == hashlib.sha256(full[:n * MIB]).hexdigest()
    pf.put(str(E / 'jsongen.py'), pr + '/jsongen.py'); run(p, 'python3 ' + pr + '/jsongen.py ' + pr + '/json8.bin 8', timeout=60)
    out['json8_sha256'] = run(p, 'sha256sum ' + pr + '/json8.bin')['stdout'].split()[0]
    run(p, "sudo -n sh -c 'echo performance > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor; echo 1800000 > /sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq'")
    def t(cmd, k=3):
        r = run(p, 'for i in $(seq ' + str(k) + '); do s=$(date +%s%N); taskset -c 3 nice -n 10 ' + cmd + ' > /dev/null; e=$(date +%s%N); echo $(( (e-s)/1000000 )); sleep 1; done', timeout=120)
        return [int(x) / 1000 for x in r['stdout'].split()]
    out['bzip2_s'] = {n: t('bzip2 -1 -c ' + pr + '/rand%d.bin' % n) for n in (1, 2, 3, 4)}
    out['gzip_json8_s'] = t('gzip -n -1 -c ' + pr + '/json8.bin')
    out['gzip_json8_ratio'] = run(p, 'gzip -n -1 -c ' + pr + '/json8.bin | wc -c')['stdout'].strip()
    ok = [n for n in (1, 2, 3, 4) if statistics.median(out['bzip2_s'][n]) <= 1.5]
    out['chosen_bzip2_mib'] = max(ok) if ok else 1
finally:
    run(p, "sudo -n sh -c 'echo " + str(int(old[2])) + " > /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq; echo " + str(int(old[1])) +
        " > /sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq; echo " + old[0] + " > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor'", check=False)
    run(p, 'rm -rf ' + pr, check=False); out['post'] = snapshot(p)
    li.channel.shutdown_write(); out['lock_release'] = lo.channel.recv_exit_status(); pf.close(); p.close()
(E / 'pi_pilots' / 'C27_BZIP2_PILOT.json').write_text(json.dumps(out, indent=1, default=str), encoding='utf-8')
print(json.dumps({k: out[k] for k in ('which', 'bzip2_s', 'gzip_json8_s', 'gzip_json8_ratio', 'chosen_bzip2_mib')}, indent=1, default=str))
