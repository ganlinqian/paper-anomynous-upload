"""C28 sizing pilot WITHOUT radio capture (no model calls).

Runs the unchanged Pi tool server (pi_api_sp2027_wait.py) on every C28 throttled condition twice under the campaign CPU
settings (performance, 1.8 GHz floor) and records the hidden span, throttle cycles, margin to the gateway reply, and the
archive check.  Acceptance rule (fixed before running): every run valid, inside the wait, archive matches its input, and
margin to the reply >= 1.0 s.  Holds the shared Pi controller lock and restores the CPU settings.
"""
import gzip, hashlib, http.server, json, os, pathlib, shlex, sys, threading, time
B = pathlib.Path(__file__).resolve().parent
SRC = pathlib.Path(r'<WORKSPACE>/ws_pi\results\scenario_rf_20261104')
sys.path.insert(0, str(SRC / 'burst_study')); from bridge_utils import *   # noqa
import collect_sp2027_wait as CW                                           # noqa
OUT = B / 'pi_pilots'; OUT.mkdir(exist_ok=True); TMP = OUT / 'c28_tmp'; TMP.mkdir(exist_ok=True)
CONDS = ['gzip3_d19', 'gzip2_d12', 'gzip1_d06', 'gzip05_d03', 'gzip2_d06', 'gzip1_d03']
owner = 'sp2027_c28pilot_' + time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()); pr = '/home/pi/telltale_sp2027/' + owner
lock = '/home/pi/telltale_g1_20261026/controller.lock'; MIB = 1024 * 1024
p = connect('192.0.2.60', 'admin', 522); pf = p.open_sftp(); res = {'owner': owner, 'utc_start': stamp(), 'runs': []}; changed = False; old = None; li = None
try:
    pre = guard(p); old = pre['state'].splitlines()[:3]; res['pre'] = pre
    busy = run(p, "pgrep -af '^(perf|strace|resident_tool|python3.*(telltale|pi_api))' | grep -v pgrep || true")['stdout']
    if busy.strip():
        raise RuntimeError('Pi occupied ' + busy)
    code = ('import os,fcntl,sys\np=' + repr(lock) + '\nfd=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)\ntry:\n fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)\n os.write(fd,'
            + repr(owner.encode()) + ")\n print('LOCKED',flush=True)\n sys.stdin.read()\nfinally:\n os.close(fd)\n if open(p).read()==" + repr(owner) + ':os.unlink(p)\n')
    li, lo, le = p.exec_command('python3 -u -c ' + shlex.quote(code), timeout=30); assert lo.readline().strip() == 'LOCKED'
    run(p, 'mkdir -p ' + pr); pf.put(str(B / 'pi_api_sp2027_wait.py'), pr + '/pi_wait.py')
    full = hashlib.shake_256(CW.SEED).digest(16 * MIB); fx = {}
    gen = 'import hashlib,pathlib;d=hashlib.shake_256(' + repr(CW.SEED) + ').digest(' + str(16 * MIB) + ')\n'
    for name, nbytes in [('rand3', 3 * MIB), ('rand2', 2 * MIB), ('rand1', MIB), ('rand05', MIB // 2)]:
        gen += 'pathlib.Path(' + repr(pr + '/' + name + '.bin') + ').write_bytes(d[:' + str(nbytes) + '])\n'
        fx[name] = {'path': pr + '/' + name + '.bin', 'sha256': hashlib.sha256(full[:nbytes]).hexdigest()}
    run(p, 'python3 -c ' + shlex.quote(gen), timeout=60)
    for k, v in fx.items():
        assert run(p, 'sha256sum ' + v['path'])['stdout'].split()[0] == v['sha256'], k
    server = http.server.ThreadingHTTPServer(('192.0.2.39', 0), CW.Handler); server.daemon_threads = True; server.registry = {}; server.events = []
    threading.Thread(target=server.serve_forever, daemon=True).start(); port = server.server_address[1]
    run(p, "sudo -n sh -c 'echo performance > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor; echo 1800000 > /sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq'"); changed = True
    token = os.urandom(16).hex(); req = {'id': token, 'method': 'solve', 'params': {'values': CW.VALUES}}; server.registry[token] = CW.VALUES
    for rep in range(2):
        for cond in CONDS:
            c = CW.CONDITIONS[cond]; inp = fx[c['input']]; ident = 'q' + os.urandom(4).hex(); stem = pr + '/' + ident
            cfg = {'activity_code': 'A___', 'input_path': inp['path'], 'input_sha256': inp['sha256'], 'output_path': stem + '.gz',
                   'port': port, 'duty': c['duty'], 'period_s': 0.02, 'dvfs_cap_khz': None, 'compressor': 'gzip'}
            (TMP / (ident + '.json')).write_text(json.dumps(cfg)); pf.put(str(TMP / (ident + '.json')), stem + '.json')
            wi, wo, we = p.exec_command('env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 nice -n 10 python3 -u ' + pr + '/pi_wait.py --private-config ' + stem + '.json', timeout=25)
            ready = json.loads(wo.readline()); t0 = time.perf_counter(); wi.write(json.dumps(req) + '\n'); wi.flush(); resp = json.loads(wo.readline()); el = time.perf_counter() - t0
            wi.write('{"research_flush":true}\n'); wi.flush(); wi.channel.shutdown_write(); err = we.read().decode(); rc = wo.channel.recv_exit_status()
            pf.get(stem + '.private.json', str(TMP / (ident + '.private.json'))); priv = json.loads((TMP / (ident + '.private.json')).read_text())
            pf.get(stem + '.gz', str(TMP / (ident + '.gz'))); ok = hashlib.sha256(gzip.decompress((TMP / (ident + '.gz')).read_bytes())).hexdigest() == inp['sha256']
            (TMP / (ident + '.gz')).unlink(); run(p, 'rm -f ' + stem + '.gz')
            a = priv['archive']
            res['runs'].append({'cond': cond, 'rep': rep, 'rc': rc, 'stderr': err[-300:], 'response_ok': resp == {'id': token, 'status': 'complete', 'result': sum(CW.VALUES)},
                                'elapsed_s': round(el, 3), 'inside_wait': priv['archive_inside_wait'], 'archive_ok': ok,
                                'process_s': round((a['process_end_ns'] - a['begin_ns']) / 1e9, 3), 'hidden_s': round((a['fsync_end_ns'] - a['begin_ns']) / 1e9, 3),
                                'margin_s': round((priv['http_received_ns'] - a['fsync_end_ns']) / 1e9, 3), 'cycles': a.get('throttle_cycles'), 'temp': thermal()})
            print(json.dumps(res['runs'][-1]), flush=True)
            time.sleep(3)
    server.shutdown(); server.server_close()
    res['accepted'] = all(r['rc'] == 0 and r['response_ok'] and r['inside_wait'] and r['archive_ok'] and r['margin_s'] >= 1.0 for r in res['runs'])
finally:
    if changed:
        res['restore'] = run(p, "sudo -n sh -c 'echo " + str(int(old[2])) + " > /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq; echo " + str(int(old[1])) + " > /sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq; echo " + old[0] + " > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor'", check=False)['rc']
        res['state_after'] = snapshot(p).splitlines()[:5]
    run(p, 'rm -rf ' + pr, check=False)
    if li:
        li.channel.shutdown_write(); res['lock_release'] = lo.channel.recv_exit_status()
    pf.close(); p.close(); res['utc_end'] = stamp()
    for q in TMP.glob('*'):
        q.unlink()
    TMP.rmdir()
    (OUT / 'C28_DUTY_PILOT.json').write_text(json.dumps(res, indent=1)); print('ACCEPTED', res.get('accepted'), flush=True)
