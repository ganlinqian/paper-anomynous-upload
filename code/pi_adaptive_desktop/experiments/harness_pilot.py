"""Functional pilot of the new Pi tool servers WITHOUT radio capture (no model calls).

Runs a few conditions end to end (gateway wait, hidden throttled gzip, text input, adversarial DVFS cap
and restore, verify/extract orders) and checks every validity condition the collectors will check.
Holds the shared Pi controller lock and restores CPU settings.
"""
import gzip, hashlib, http.server, json, os, pathlib, shlex, sys, threading, time
B = pathlib.Path(__file__).resolve().parent
SRC = pathlib.Path(r'<WORKSPACE>/ws_pi\results\scenario_rf_20261104')
sys.path.insert(0, str(SRC / 'burst_study')); from bridge_utils import *   # noqa
import collect_sp2027_wait as CW                                           # noqa
OUT = B / 'harness_pilot'; OUT.mkdir(exist_ok=True)
owner = 'sp2027_harness_' + time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()); pr = '/home/pi/telltale_sp2027/' + owner
lock = '/home/pi/telltale_g1_20261026/controller.lock'; MIB = 1024 * 1024
p = connect('192.0.2.60', 'admin', 522); pf = p.open_sftp(); res = {'owner': owner, 'runs': []}; changed = False; old = None; li = None
try:
    pre = guard(p); old = pre['state'].splitlines()[:3]
    code = ('import os,fcntl,sys\np=' + repr(lock) + '\nfd=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)\ntry:\n fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)\n os.write(fd,'
            + repr(owner.encode()) + ")\n print('LOCKED',flush=True)\n sys.stdin.read()\nfinally:\n os.close(fd)\n if open(p).read()==" + repr(owner) + ':os.unlink(p)\n')
    li, lo, le = p.exec_command('python3 -u -c ' + shlex.quote(code), timeout=30); assert lo.readline().strip() == 'LOCKED'
    run(p, 'mkdir -p ' + pr); pf.put(str(B / 'pi_api_sp2027_wait.py'), pr + '/pi_wait.py'); pf.put(str(B / 'pi_api_sp2027_order.py'), pr + '/pi_order.py'); pf.put(str(B / 'textgen.py'), pr + '/textgen.py')
    full = hashlib.shake_256(CW.SEED).digest(16 * MIB); fx = {}
    gen = 'import hashlib,pathlib;d=hashlib.shake_256(' + repr(CW.SEED) + ').digest(' + str(16 * MIB) + ')\n'
    for mib in (16, 8):
        gen += 'pathlib.Path(' + repr(pr + '/rand%d.bin' % mib) + ').write_bytes(d[:' + str(mib * MIB) + '])\n'; fx['rand%d' % mib] = {'path': pr + '/rand%d.bin' % mib, 'sha256': hashlib.sha256(full[:mib * MIB]).hexdigest()}
    run(p, 'python3 -c ' + shlex.quote(gen), timeout=60); run(p, 'python3 ' + pr + '/textgen.py ' + pr + '/text8.bin 8', timeout=60)
    fx['text8'] = {'path': pr + '/text8.bin', 'sha256': run(p, 'sha256sum ' + pr + '/text8.bin')['stdout'].split()[0]}
    server = http.server.ThreadingHTTPServer(('192.0.2.39', 0), CW.Handler); server.daemon_threads = True; server.registry = {}; server.events = []
    threading.Thread(target=server.serve_forever, daemon=True).start(); port = server.server_address[1]
    run(p, "sudo -n sh -c 'echo performance > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor; echo 1800000 > /sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq'"); changed = True
    token = os.urandom(16).hex(); req = {'id': token, 'method': 'solve', 'params': {'values': CW.VALUES}}; server.registry[token] = CW.VALUES
    for cond in ['silent', 'gzip8_d50', 'text8', 'gzip16_cap']:
        c = CW.CONDITIONS[cond]; inp = fx[c.get('input', 'rand16')]; ident = 'h' + os.urandom(4).hex(); stem = pr + '/' + ident
        cfg = {'activity_code': 'A___' if c['activity'] else 'Q___', 'input_path': inp['path'], 'input_sha256': inp['sha256'], 'output_path': stem + '.gz',
               'port': port, 'duty': c.get('duty', 1.0), 'period_s': 0.02, 'dvfs_cap_khz': c.get('dvfs')}
        (OUT / (ident + '.json')).write_text(json.dumps(cfg)); pf.put(str(OUT / (ident + '.json')), stem + '.json')
        wi, wo, we = p.exec_command('nice -n 10 python3 -u ' + pr + '/pi_wait.py --private-config ' + stem + '.json', timeout=25)
        ready = json.loads(wo.readline()); t0 = time.perf_counter(); wi.write(json.dumps(req) + '\n'); wi.flush(); resp = json.loads(wo.readline()); el = time.perf_counter() - t0
        wi.write('{"research_flush":true}\n'); wi.flush(); wi.channel.shutdown_write(); err = we.read().decode(); rc = wo.channel.recv_exit_status()
        pf.get(stem + '.private.json', str(OUT / (ident + '.private.json'))); priv = json.loads((OUT / (ident + '.private.json')).read_text())
        arch = None
        if c['activity']:
            pf.get(stem + '.gz', str(OUT / (ident + '.gz'))); data = gzip.decompress((OUT / (ident + '.gz')).read_bytes()); arch = hashlib.sha256(data).hexdigest() == inp['sha256']; (OUT / (ident + '.gz')).unlink()
        run(p, 'rm -f ' + stem + '.gz')
        a = priv.get('archive', {})
        res['runs'].append({'cond': cond, 'rc': rc, 'stderr': err[-300:], 'response_ok': resp == {'id': token, 'status': 'complete', 'result': 267}, 'elapsed_s': round(el, 3),
                            'inside_wait': priv['archive_inside_wait'], 'archive_ok': arch,
                            'hidden_s': round((a['fsync_end_ns'] - a['begin_ns']) / 1e9, 3) if a.get('fsync_end_ns') else None,
                            'cycles': a.get('throttle_cycles'), 'dvfs': priv.get('dvfs')})
        time.sleep(3)
    # S2 order worker
    gen2 = 'import hashlib,pathlib;pathlib.Path(' + repr(pr + '/payload.bin') + ').write_bytes(hashlib.shake_256(b"Telltale:S2:payload:v1").digest(' + str(96 * MIB) + '))'
    run(p, 'python3 -c ' + shlex.quote(gen2), timeout=120); plain = run(p, 'sha256sum ' + pr + '/payload.bin', timeout=60)['stdout'].split()[0]
    run(p, 'gzip -n -1 -c ' + pr + '/payload.bin > ' + pr + '/package.gz && rm ' + pr + '/payload.bin', timeout=120); arc = run(p, 'sha256sum ' + pr + '/package.gz', timeout=60)['stdout'].split()[0]
    for order in ['VX', 'XV']:
        ident = 'o' + os.urandom(4).hex(); stem = pr + '/' + ident
        cfg = {'archive_path': pr + '/package.gz', 'archive_sha256': arc, 'plain_sha256': plain, 'order': order, 'output_path': '/dev/shm/' + owner + '/' + ident + '.out', 'envelope_s': 2.5}
        (OUT / (ident + '.json')).write_text(json.dumps(cfg)); pf.put(str(OUT / (ident + '.json')), stem + '.json')
        wi, wo, we = p.exec_command('nice -n 10 python3 -u ' + pr + '/pi_order.py --private-config ' + stem + '.json', timeout=30)
        ready = json.loads(wo.readline()); t0 = time.perf_counter(); wi.write(json.dumps(req) + '\n'); wi.flush(); resp = json.loads(wo.readline()); el = time.perf_counter() - t0
        wi.write('{"research_flush":true}\n'); wi.flush(); wi.channel.shutdown_write(); err = we.read().decode(); rc = wo.channel.recv_exit_status()
        pf.get(stem + '.private.json', str(OUT / (ident + '.private.json'))); priv = json.loads((OUT / (ident + '.private.json')).read_text())
        res['runs'].append({'cond': 'order_' + order, 'rc': rc, 'stderr': err[-300:], 'response_ok': resp == {'id': token, 'status': 'complete', 'result': 267}, 'elapsed_s': round(el, 3),
                            'phases': [(x['kind'], round((x['end_ns'] - x['begin_ns']) / 1e9, 3)) for x in priv['phases']], 'output_ok': priv['output_ok'],
                            'inside_envelope': priv['work_inside_envelope'], 'envelope_s': round(priv['envelope_s'], 3)})
        time.sleep(3)
    server.shutdown(); server.server_close()
finally:
    if changed:
        res['restore'] = run(p, "sudo -n sh -c 'echo " + str(int(old[2])) + " > /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq; echo " + str(int(old[1])) + " > /sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq; echo " + old[0] + " > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor'", check=False)['rc']
        res['state_after'] = snapshot(p).splitlines()[:3]
    run(p, 'rm -rf ' + pr + ' /dev/shm/' + owner, check=False)
    if li:
        li.channel.shutdown_write(); res['lock_release'] = lo.channel.recv_exit_status()
    pf.close(); p.close()
    (OUT / 'HARNESS_RESULT.json').write_text(json.dumps(res, indent=1)); print(json.dumps(res, indent=1))
