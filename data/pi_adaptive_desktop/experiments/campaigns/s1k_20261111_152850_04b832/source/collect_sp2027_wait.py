"""S1/S3 controller (derived from the C13 untraced-wait controller; no model calls).

S1: hidden gzip under adaptive throttling and a new input, plus extra silent runs.
S3: adversarial CPU frequency capping during the call.
Frozen models are NOT touched here; this script only collects, validates, and freezes the plan.
Reuses (read-only) bridge_utils.py and collect.Rig of session ws_pi; the rig is rig_capture_stagger_sp2027.py
(capture code identical to the original; only the capture_pc session precondition differs, see PROTOCOL_LEGACY.md).
"""
import argparse, bz2, gzip, hashlib, http.server, json, os, pathlib, random, shlex, sys, threading, time, traceback
B = pathlib.Path(__file__).resolve().parent
SRC = pathlib.Path(r'<WORKSPACE>/ws_pi\results\scenario_rf_20261104')
sys.path.insert(0, str(SRC / 'burst_study')); from bridge_utils import *   # noqa
sys.path.insert(1, str(SRC)); from collect import Rig                      # noqa
SEED = b'Telltale:C07:20261104:fixture:v1'; MIB = 1024 * 1024
VALUES = [13, 31, 53, 73, 97]

CONDITIONS = {
    'silent':        {'activity': False},
    'gzip16':        {'activity': True, 'input': 'rand16', 'duty': 1.0},
    'text8':         {'activity': True, 'input': 'text8', 'duty': 1.0},
    'gzip8_d50':     {'activity': True, 'input': 'rand8', 'duty': 0.5},
    'gzip4_d25':     {'activity': True, 'input': 'rand4', 'duty': 0.25},
    'gzip2_d12':     {'activity': True, 'input': 'rand2', 'duty': 0.125},
    'silent_cap':    {'activity': False, 'dvfs': 1200000},
    'gzip16_cap':    {'activity': True, 'input': 'rand16', 'duty': 1.0, 'dvfs': 1200000},
    # C27 (stage s1b): prospective test of the diverse-workload model; unseen duty cycles, input, and tool
    'gzip6_d37':     {'activity': True, 'input': 'rand6', 'duty': 0.375},
    'gzip3_d19':     {'activity': True, 'input': 'rand3', 'duty': 0.1875},
    'json8':         {'activity': True, 'input': 'json8', 'duty': 1.0},
    'bzip2_r':       {'activity': True, 'input': None, 'duty': 1.0, 'compressor': 'bzip2'},   # input set by --bzip2-mib
    # C28 (stage s1c): duty cycles below 18.75% for the frozen C27 model; same ~1.1 s throttled span as C24/C27 ...
    'gzip1_d06':     {'activity': True, 'input': 'rand1', 'duty': 0.0625},
    'gzip05_d03':    {'activity': True, 'input': 'rand05', 'duty': 0.03125},
    # ... and low-and-slow: twice the work at the same duty, spread over about twice the span
    'gzip2_d06':     {'activity': True, 'input': 'rand2', 'duty': 0.0625},
    'gzip1_d03':     {'activity': True, 'input': 'rand1', 'duty': 0.03125},
    # C29 (stage s1d): silent calibration calls at the start of the session (per-session calibration of the C29 models)
    'silent_cal':    {'activity': False},
    # C33 (stage s1h, 2026-11-10): unseen tools and sizes (in no training set) and contract-permitted background work
    'zstd32':      {'activity': True, 'input': 'rand32', 'duty': 1.0, 'compressor': 'zstd'},
    'xz2':         {'activity': True, 'input': 'rand2', 'duty': 1.0, 'compressor': 'xz'},
    'ossl16':      {'activity': True, 'input': 'rand16', 'duty': 1.0, 'compressor': 'openssl'},
    'sha32':       {'activity': True, 'input': 'rand32', 'duty': 1.0, 'compressor': 'sha256sum'},
    'gzip1_full':  {'activity': True, 'input': 'rand1', 'duty': 1.0},
    'gzip32':      {'activity': True, 'input': 'rand32', 'duty': 1.0},
    'bg_log':      {'activity': False, 'background': 'log'},
    'bg_download': {'activity': False, 'background': 'download'},
    # C33 amendment (stage s1i): outputs capped near 16 MiB so that compute + fsync to the SD card stays inside the wait
    'zstd16':      {'activity': True, 'input': 'rand16', 'duty': 1.0, 'compressor': 'zstd'},
    'gziptxt32':   {'activity': True, 'input': 'text32', 'duty': 1.0},
}
PLANS = {
    's1': (8, ['silent', 'silent', 'gzip16', 'text8', 'gzip8_d50', 'gzip4_d25', 'gzip2_d12'], 2026110601),
    's3': (6, ['silent', 'gzip16', 'silent_cap', 'gzip16_cap'], 2026110603),
    's1b': (8, ['silent', 'silent', 'gzip16', 'gzip4_d25', 'gzip6_d37', 'gzip3_d19', 'json8', 'bzip2_r'], 2026110607),
    's1c': (8, ['silent', 'silent', 'gzip3_d19', 'gzip2_d12', 'gzip1_d06', 'gzip05_d03', 'gzip2_d06', 'gzip1_d03'], 2026110608),
    's1d': (8, ['silent', 'silent', 'gzip3_d19', 'gzip2_d12', 'gzip1_d06', 'gzip05_d03', 'gzip2_d06', 'gzip1_d03'], 2026110609),
    # C30 (stage s1e, 2026-11-10): the C27 (s1b) cells unchanged (run with --bzip2-mib 4 as C27), plus calibration silents
    's1e': (8, ['silent', 'silent', 'gzip16', 'gzip4_d25', 'gzip6_d37', 'gzip3_d19', 'json8', 'bzip2_r'], 2026111001),
    # C31 (stage s1f, 2026-11-10): same cells as C27/C30 in a new session, for the frozen C31 ensemble
    's1f': (8, ['silent', 'silent', 'gzip16', 'gzip4_d25', 'gzip6_d37', 'gzip3_d19', 'json8', 'bzip2_r'], 2026111002),
    # C32 (stage s1g, 2026-11-10): false-alarm control; four silents per block (32 test silents) + the six C27 hidden cells
    's1g': (8, ['silent', 'silent', 'silent', 'silent', 'gzip16', 'gzip4_d25', 'gzip6_d37', 'gzip3_d19', 'json8', 'bzip2_r'], 2026111003),
    # C33 (stage s1h, 2026-11-10): generalisation to unseen tools/sizes and false alarms under legitimate background work
    's1h': (8, ['silent', 'silent', 'bg_log', 'bg_download', 'zstd32', 'xz2', 'ossl16', 'sha32', 'gzip1_full', 'gzip32'], 2026111004),
    # s1h stopped at run 10 (gzip32: fsync of 32 MiB to the SD card ran past the wait); amended plan:
    's1i': (8, ['silent', 'silent', 'bg_log', 'bg_download', 'zstd16', 'xz2', 'ossl16', 'sha32', 'gzip1_full', 'gziptxt32'], 2026111005),
    # C34 (stage s1j, 2026-11-11 UTC, user-approved; session ws_followup): time-separated hold-out, ~4-9 h after the last
    # training/test session, same boot and probe placement; frozen detectors only (no model trained); seen + unseen hidden
    # cells and contract-permitted log writes as a negative; 4 silents per block (32 test silents)
    's1j': (8, ['silent', 'silent', 'silent', 'silent', 'bg_log', 'gzip16', 'gzip3_d19', 'zstd16', 'xz2', 'ossl16', 'sha32'], 2026111101),
    # C35 (stage s1k, 2026-11-11 UTC, user-approved; session ws_followup): prospective test of the frozen C35 false-alarm
    # control (pre-dispatch self reference + rolling reference of the last 4 no-work calls, P > 0.7); the C34 cells, new seed
    's1k': (8, ['silent', 'silent', 'silent', 'silent', 'bg_log', 'gzip16', 'gzip3_d19', 'zstd16', 'xz2', 'ossl16', 'sha32'], 2026111102),
}
CALIBRATION_RUNS = {'s1d': 8, 's1e': 8, 's1f': 8, 's1g': 8, 's1h': 8, 's1i': 8, 's1j': 8, 's1k': 8}  # block -1: silent calibration calls before the test blocks
DIVERSE = B / 'models' / 'C27_DIVERSE_MODELS.json'
LOWDUTY = B / 'models' / 'C29_LOWDUTY_MODELS.json'
ALLSESS = B / 'models' / 'C30_ALLSESS_MODELS.json'
ENSEMBLE = B / 'models' / 'C31_ENSEMBLE_MODELS.json'
NEGW = B / 'models' / 'C32_NEGW_MODELS.json'
SELFROLL = B / 'models' / 'C35_SELFROLL_MODELS.json'
MIRROR = hashlib.shake_256(b'Telltale:C33:mirror:v1').digest(16 * MIB)   # C33 legitimate download payload
PI_VERIFY = {'zstd': 'zstd -dc -q {o} | sha256sum', 'xz': 'xz -dc {o} | sha256sum',
             'openssl': 'openssl enc -d -aes-256-cbc -pbkdf2 -pass pass:telltale-c33 -in {o} | sha256sum', 'sha256sum': 'cat {o}'}

def pi_verify(p, comp, path, inp):
    """C33: verify an unseen tool's output on the Pi after the RF capture (decompress/decrypt and hash, or read the digest)."""
    r = run(p, PI_VERIFY[comp].format(o=path), timeout=60)['stdout'].split()
    return {'fetched': False, 'verified_on_pi': True, 'tool': comp, 'remote_bytes': int(run(p, 'stat -c %s ' + path)['stdout'].strip()),
            'matches_input': bool(r) and r[0] == inp['sha256']}

class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def log_message(self, *args):
        pass
    def do_GET(self):
        token = self.headers.get('X-TT-Token', ''); values = self.server.registry.get(token)
        event = {'token': token, 'path': self.path, 'client': self.client_address, 'begin_desktop_ns': time.perf_counter_ns()}
        if self.path == '/approved/mirror' and values is not None:     # C33 legitimate download (16 MiB, no delay)
            body = MIRROR; self.send_response_only(200); self.send_header('Content-Type', 'application/octet-stream'); self.send_header('Content-Length', str(len(body)))
            self.end_headers(); self.wfile.write(body); self.wfile.flush()
            event.update(end_desktop_ns=time.perf_counter_ns(), status=200, response_sha256=hashlib.sha256(body).hexdigest()); self.server.events.append(event); return
        if self.path != '/approved/package' or values is None:
            self.send_error(403); return
        time.sleep(4)
        body = json.dumps({'values': values}, sort_keys=True, separators=(',', ':')).encode()
        self.send_response_only(200); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(body)))
        self.end_headers(); self.wfile.write(body); self.wfile.flush()
        event.update(end_desktop_ns=time.perf_counter_ns(), status=200, response_sha256=hashlib.sha256(body).hexdigest()); self.server.events.append(event)

CPUF = '/sys/devices/system/cpu/cpu0/cpufreq/'

def guard_wait(p, limit_s=1500, cool_to=None):
    """Pre-run precondition (2026-11-06 amendments after the thermal stops of the first S2 test batch and of C27).
    If only the thermal limit is exceeded: with cool_to=(governor, min_khz) the original governor is restored so that
    the idle device actually cools (under the campaign's performance governor it settles near the limit), the
    coordinator waits until CPU <= 46 C and DDR <= 41.5 C (30 s steps), re-applies performance with the 1.8 GHz floor,
    lets it settle for 20 s, and checks the normal precondition again; at most 25 min in total.  Anything else aborts."""
    t0 = time.time(); waits = 0; cycles = 0
    while True:
        try:
            g = guard(p); g.update(thermal_waits=waits, thermal_cool_cycles=cycles, thermal_wait_s=round(time.time() - t0, 1)); return g
        except RuntimeError as ex:
            if 'thermal precondition' not in str(ex) or time.time() - t0 > limit_s:
                raise
        if cool_to is None:
            waits += 1; time.sleep(30); continue
        cycles += 1
        run(p, "sudo -n sh -c 'echo " + cool_to[0] + " > " + CPUF + "scaling_governor; echo " + str(int(cool_to[1])) + " > " + CPUF + "scaling_min_freq'")
        try:
            while time.time() - t0 <= limit_s:
                waits += 1; time.sleep(30); t = thermal()
                if t['cpu_c'] <= 46 and t['ddr_c'] <= 41.5:
                    break
        finally:
            run(p, "sudo -n sh -c 'echo performance > " + CPUF + "scaling_governor; echo 1800000 > " + CPUF + "scaling_min_freq'")
        time.sleep(20)

def guard_post(p):
    """Post-run record: thermal excess is recorded (the next run's guard_wait enforces the limit); throttling still aborts."""
    try:
        return guard(p)
    except RuntimeError as ex:
        if 'thermal precondition' not in str(ex):
            raise
        return {'state': snapshot(p), 'temperature': thermal(), 'thermal_exceeded_after_run': str(ex)}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--stage', choices=sorted(PLANS), required=True)
    ap.add_argument('--bzip2-mib', type=int, default=2, choices=[1, 2, 3, 4, 6, 8]); args = ap.parse_args()
    lower_priority()
    if args.stage in ('s1b', 's1c', 's1d', 's1e', 's1f', 's1g', 's1h', 's1i', 's1j', 's1k') and not DIVERSE.exists():
        raise RuntimeError(args.stage + ' requires the frozen C27 diverse-workload model')
    if args.stage in ('s1d', 's1e', 's1f', 's1g', 's1h', 's1i', 's1j', 's1k') and not LOWDUTY.exists():
        raise RuntimeError('s1d requires the frozen C29 low-duty model')
    if args.stage in ('s1e', 's1f', 's1g', 's1h', 's1i', 's1j', 's1k') and not ALLSESS.exists():
        raise RuntimeError('s1e requires the frozen C30 all-session model')
    if args.stage in ('s1f', 's1g', 's1h', 's1i', 's1j', 's1k') and not ENSEMBLE.exists():
        raise RuntimeError('s1f requires the frozen C31 ensemble model')
    if args.stage in ('s1g', 's1h', 's1i', 's1j', 's1k') and not NEGW.exists():
        raise RuntimeError('s1g requires the frozen C32 model')
    if args.stage == 's1k' and not SELFROLL.exists():
        raise RuntimeError('s1k requires the frozen C35 model')
    CONDITIONS['bzip2_r']['input'] = 'rand%d' % args.bzip2_mib
    campaign = args.stage + '_' + time.strftime('%Y%m%d_%H%M%S', time.gmtime()) + '_' + os.urandom(3).hex()
    d = B / 'campaigns' / campaign; d.mkdir(parents=True); save(B / 'campaigns' / ('LATEST_' + args.stage + '.json'), {'directory': str(d), 'campaign': campaign})
    pr = '/home/pi/telltale_sp2027/' + campaign; wr = '<DATA>/telltale_sp2027/' + campaign
    lock = '/home/pi/telltale_g1_20261026/controller.lock'
    p = w = pf = wf = rig = li = lo = le = wi = wo = we = server = None; pid = None; old = None; changed = False; rows = []
    try:
        p = connect('192.0.2.60', 'admin', 522); w = connect('192.0.2.4', 'win'); pf = p.open_sftp(); wf = w.open_sftp()
        pre = guard_wait(p); old = pre['state'].splitlines()[:3]
        busy = run(p, "pgrep -af '^(perf|strace|resident_tool|python3.*telltale)' || true")['stdout']
        if busy.strip():
            raise RuntimeError('Pi occupied ' + busy)
        code = ('import os,fcntl,sys\np=' + repr(lock) + '\nfd=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)\ntry:\n fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)\n os.write(fd,'
                + repr(campaign.encode()) + ")\n print('LOCKED',flush=True)\n sys.stdin.read()\nfinally:\n os.close(fd)\n if open(p).read()==" + repr(campaign) + ':os.unlink(p)\n')
        li, lo, le = p.exec_command('python3 -u -c ' + shlex.quote(code), timeout=30)
        if lo.readline().strip() != 'LOCKED':
            raise RuntimeError('Pi lock ' + le.read().decode())
        # ---- rig first: refuses (and we stop) if capture_pc has a console user, other workloads, or too little space
        try:
            wf.mkdir('<DATA>/telltale_sp2027')
        except OSError:
            pass
        rs = '<DATA>/telltale_sp2027/rig_' + campaign + '.py'; wf.put(str(B / 'rig_capture_stagger_sp2027.py'), rs)
        rig = Rig(w, rs, wr, campaign)
        assert int(rig.pre['preflight']['free']) >= 100 * 10 ** 9
        # ---- fixtures on the Pi
        run(p, 'mkdir -p ' + pr); pf.put(str(B / ('pi_api_sp2027_c33.py' if args.stage in ('s1h', 's1i', 's1j', 's1k') else 'pi_api_sp2027_wait.py')), pr + '/pi_api.py')
        full = hashlib.shake_256(SEED).digest(16 * MIB); fx = {}
        gen = 'import hashlib,pathlib;d=hashlib.shake_256(' + repr(SEED) + ').digest(' + str(16 * MIB) + ')\n'
        for name, nbytes in [('rand%d' % mib, mib * MIB) for mib in (16, 8, 6, 4, 3, 2, 1)] + [('rand05', MIB // 2)]:
            gen += 'pathlib.Path(' + repr(pr + '/' + name + '.bin') + ').write_bytes(d[:' + str(nbytes) + '])\n'
            fx[name] = {'path': pr + '/' + name + '.bin', 'sha256': hashlib.sha256(full[:nbytes]).hexdigest()}
        if args.stage in ('s1h', 's1i', 's1j', 's1k'):
            gen += 'pathlib.Path(' + repr(pr + '/rand32.bin') + ').write_bytes(hashlib.shake_256(' + repr(SEED) + ').digest(' + str(32 * MIB) + '))\n'
            fx['rand32'] = {'path': pr + '/rand32.bin', 'sha256': hashlib.sha256(hashlib.shake_256(SEED).digest(32 * MIB)).hexdigest()}
        run(p, 'python3 -c ' + shlex.quote(gen), timeout=60)
        pf.put(str(B / 'textgen.py'), pr + '/textgen.py'); run(p, 'python3 ' + pr + '/textgen.py ' + pr + '/text8.bin 8', timeout=60)
        th = run(p, 'sha256sum ' + pr + '/text8.bin')['stdout'].split()[0]
        fx['text8'] = {'path': pr + '/text8.bin', 'sha256': th}
        if args.stage == 's1i':
            run(p, 'python3 ' + pr + '/textgen.py ' + pr + '/text32.bin 32', timeout=120)
            fx['text32'] = {'path': pr + '/text32.bin', 'sha256': run(p, 'sha256sum ' + pr + '/text32.bin')['stdout'].split()[0]}
        pf.put(str(B / 'jsongen.py'), pr + '/jsongen.py'); run(p, 'python3 ' + pr + '/jsongen.py ' + pr + '/json8.bin 8', timeout=60)
        fx['json8'] = {'path': pr + '/json8.bin', 'sha256': run(p, 'sha256sum ' + pr + '/json8.bin')['stdout'].split()[0]}
        for k, v in fx.items():
            assert run(p, 'sha256sum ' + v['path'])['stdout'].split()[0] == v['sha256'], k
        save(d / 'FIXTURES.json', fx)
        server = http.server.ThreadingHTTPServer(('192.0.2.39', 0), Handler); server.daemon_threads = True; server.registry = {}; server.events = []
        threading.Thread(target=server.serve_forever, daemon=True).start(); port = server.server_address[1]
        run(p, "sudo -n sh -c 'echo performance > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor; echo 1800000 > /sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq'"); changed = True

        def start_worker(ident, cond):
            nonlocal wi, wo, we, pid
            c = CONDITIONS[cond]; stem = pr + '/' + ident
            inp = fx[c.get('input', 'rand16')]
            config = {'activity_code': 'A___' if c['activity'] else 'Q___', 'input_path': inp['path'], 'input_sha256': inp['sha256'],
                      'output_path': stem + '.gz', 'port': port, 'duty': c.get('duty', 1.0), 'period_s': 0.02, 'dvfs_cap_khz': c.get('dvfs'),
                      'compressor': c.get('compressor', 'gzip'), 'background': c.get('background')}
            td = d / 'records' / ident; td.mkdir(parents=True); save(td / 'private_config.json', config); pf.put(str(td / 'private_config.json'), stem + '.json')
            cmd = 'env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 nice -n 10 python3 -u ' + pr + '/pi_api.py --private-config ' + stem + '.json'
            wi, wo, we = p.exec_command(cmd, timeout=25); ready = json.loads(wo.readline()); pid = ready['pid']
            assert ready['ready'] and ready['input_sha256'] == inp['sha256']
            status = run(p, 'cat /proc/' + str(pid) + '/status')['stdout']
            tracer = int(next(x.split()[1] for x in status.splitlines() if x.startswith('TracerPid:'))); assert tracer == 0
            ready['independently_checked_tracer_pid'] = tracer
            return stem, td, ready, inp

        def finish_worker(stem, td):
            nonlocal wi, wo, we, pid
            wi.write('{"research_flush":true}\n'); wi.flush(); wi.channel.shutdown_write()
            extra = wo.read().decode('utf-8', 'replace'); err = we.read().decode('utf-8', 'replace'); rc = wo.channel.recv_exit_status()
            wi = wo = we = None; pid = None; (td / 'stderr.log').write_text(err)
            assert not extra.strip() and not err.strip() and rc == 0, (extra, err, rc)
            pf.get(stem + '.private.json', str(td / 'worker.private.json'))
            return json.loads((td / 'worker.private.json').read_text())

        nblocks, cells, seed = PLANS[args.stage]; plan = []
        if args.stage in CALIBRATION_RUNS:
            token = os.urandom(16).hex(); request = {'id': token, 'method': 'solve', 'params': {'values': VALUES}}; server.registry[token] = VALUES
            for _ in range(CALIBRATION_RUNS[args.stage]):
                plan.append({'id': 'n' + os.urandom(6).hex(), 'block': -1, 'stage': 'sp2027_' + args.stage, 'condition': 'silent_cal',
                             'actual_active': False, 'expected_active': False, 'dvfs_cap_khz': None, 'request': request})
        for block in range(nblocks):
            cc = list(cells); random.Random(seed + block).shuffle(cc)
            token = os.urandom(16).hex(); request = {'id': token, 'method': 'solve', 'params': {'values': VALUES}}; server.registry[token] = VALUES
            for cond in cc:
                plan.append({'id': 'n' + os.urandom(6).hex(), 'block': block, 'stage': 'sp2027_' + args.stage, 'condition': cond,
                             'actual_active': CONDITIONS[cond]['activity'], 'expected_active': False, 'dvfs_cap_khz': CONDITIONS[cond].get('dvfs'),
                             'request': request})
        sources = [B / 'collect_sp2027_wait.py', B / 'pi_api_sp2027_wait.py', B / 'textgen.py', B / 'jsongen.py', B.parent / 'PROTOCOL_LEGACY.md', B / 'rig_capture_stagger_sp2027.py', SRC / 'rig_capture_stagger.py',
                   SRC / 'burst_study/bridge_utils.py', SRC / 'collect.py']
        if args.stage in ('s1b', 's1c', 's1d', 's1e', 's1f', 's1g', 's1h', 's1i', 's1j', 's1k'):
            sources.append(DIVERSE)
        if args.stage in ('s1d', 's1e', 's1f', 's1g', 's1h', 's1i', 's1j', 's1k'):
            sources.append(LOWDUTY)
        if args.stage in ('s1e', 's1f', 's1g', 's1h', 's1i', 's1j', 's1k'):
            sources.append(ALLSESS)
        if args.stage in ('s1f', 's1g', 's1h', 's1i', 's1j', 's1k'):
            sources.append(ENSEMBLE)
        if args.stage in ('s1g', 's1h', 's1i', 's1j', 's1k'):
            sources.append(NEGW)
        if args.stage == 's1k':
            sources.append(SELFROLL)
        if args.stage in ('s1h', 's1i', 's1j', 's1k'):
            sources += [B / 'pi_api_sp2027_c33.py', B.parent / 'scripts' / 'make_pi_api_c33.py']
        sd = d / 'source'; sd.mkdir()
        for path in sources:
            (sd / path.name).write_bytes(path.read_bytes())
        freeze = {'campaign': campaign, 'stage': args.stage, 'plan': plan, 'seconds': 8, 'cooldown_s': 25, 'winroot': wr, 'piroot': pr, 'bzip2_mib': args.bzip2_mib,
                  'pre_state': pre, 'rig_preflight': rig.pre, 'source_sha256': {str(x): sha(x) for x in sources}, 'utc': stamp(),
                  'syscall_tracing': False, 'all_trials_test_only': True, 'fixtures': fx}
        save(d / 'FREEZE.json', freeze); wf.put(str(d / 'FREEZE.json'), wr + '/FREEZE.json')
        for idx, cfg in enumerate(plan):
            row = dict(cfg); row['pre'] = guard_wait(p, cool_to=(old[0], old[1]))
            stem, td, ready, inp = start_worker(cfg['id'], cfg['condition']); row['ready'] = ready
            row['capture_ready'] = rig.rpc({'op': 'capture', 'id': cfg['id'], 'seconds': 8})
            time.sleep(random.Random(71106 + idx).uniform(.25, .45))
            row['before'] = rig.rpc({'op': 'mark'}); row['dispatch_desktop_ns'] = time.perf_counter_ns()
            wi.write(json.dumps(cfg['request'], sort_keys=True, separators=(',', ':')) + '\n'); wi.flush()
            response = json.loads(wo.readline()); row['return_desktop_ns'] = time.perf_counter_ns()
            row['after'] = rig.rpc({'op': 'mark'}); row['rf'] = rig.rpc({'op': 'finish'}); row['rf_finish_desktop_ns'] = time.perf_counter_ns()
            private = finish_worker(stem, td); row['private'] = private
            # independent archive check on the desktop
            arch = {'fetched': False}
            comp = CONDITIONS[cfg['condition']].get('compressor', 'gzip')
            if cfg['actual_active'] and comp in PI_VERIFY:
                arch = pi_verify(p, comp, stem + '.gz', inp)
            elif cfg['actual_active']:
                local = td / 'archive.gz'; pf.get(stem + '.gz', str(local))
                data = (bz2.decompress if CONDITIONS[cfg['condition']].get('compressor') == 'bzip2' else gzip.decompress)(local.read_bytes()); arch = {'fetched': True, 'gz_bytes': local.stat().st_size, 'gz_sha256': sha(local),
                                                                    'decompressed_bytes': len(data), 'matches_input': hashlib.sha256(data).hexdigest() == inp['sha256']}
                local.unlink()
            else:
                arch['remote_bytes'] = int(run(p, 'stat -c %s ' + stem + '.gz')['stdout'].strip())
            run(p, 'rm -f ' + stem + '.gz ' + stem + '.gz.log ' + stem + '.gz.dl')
            row['archive_check'] = arch
            trace = {'request': cfg['request'], 'response': response}; save(td / 'canonical_trace.json', trace)
            row.update(canonical_trace=trace, canonical_trace_sha256=sha(td / 'canonical_trace.json'),
                       elapsed_s=(row['return_desktop_ns'] - row['dispatch_desktop_ns']) / 1e9, post=guard_post(p))
            ok_dvfs = True; ok_bg = True
            if CONDITIONS[cfg['condition']].get('background'):
                ok_bg = bool(private.get('background_inside_wait')) and (private.get('background_kind') != 'download' or private['background'].get('sha256') == hashlib.sha256(MIRROR).hexdigest())
            if cfg['dvfs_cap_khz']:
                dv = private.get('dvfs', {}); ok_dvfs = bool(dv.get('after')) and dv['after'] == dv['before'] and int(dv.get('cur_before_restore', 10 ** 9)) <= cfg['dvfs_cap_khz']
            valid = (response == {'id': cfg['request']['id'], 'status': 'complete', 'result': sum(VALUES)}
                     and all(r['rc'] == 0 and r['bytes'] == r['expected_bytes'] == 320000000 for r in row['rf']['radios'])
                     and all(m['running'] and 0 < m['bytes'] < 320000000 for key in ('before', 'after') for m in row[key]['marks'])
                     and bool(private['archive_inside_wait']) == cfg['actual_active']
                     and (arch.get('matches_input') if cfg['actual_active'] else arch.get('remote_bytes') == 0) and ok_dvfs and ok_bg)
            row['valid'] = bool(valid); save(td / 'record.json', row); rows.append(row); save(d / 'RESULTS.json', rows); save(d / 'HTTP_EVENTS.json', server.events)
            for r in row['rf']['radios']:
                wf.get(r['log'].replace('\\', '/'), str(td / (r['radio'] + '.rf.log')))
            print(json.dumps({'completed': idx + 1, 'planned': len(plan), 'id': cfg['id'], 'condition': cfg['condition'], 'valid': valid,
                              'inside_wait': private['archive_inside_wait'], 'elapsed_s': row['elapsed_s'], 'utc': stamp()}), flush=True)
            if not valid:
                raise RuntimeError('invalid bounded acquisition')
            if idx < len(plan) - 1:
                time.sleep(25)
        for block in sorted({x['block'] for x in rows}):
            assert len({x['canonical_trace_sha256'] for x in rows if x['block'] == block}) == 1
        save(d / 'COMPLETE.json', {'utc': stamp(), 'trials': len(rows), 'valid': sum(x['valid'] for x in rows),
                                   'raw_bytes': sum(q['bytes'] for x in rows for q in x['rf']['radios']), 'same_canonical_trace_per_block': True})
    except Exception:
        (d / 'FAILURE.log').write_text(traceback.format_exc(), encoding='utf-8'); raise
    finally:
        close = {}
        if pid and p:
            cmd = run(p, 'cat /proc/' + str(pid) + '/cmdline', check=False)['stdout']
            if pr + '/pi_api.py' in cmd:
                close['own_worker_stop'] = run(p, 'kill -TERM ' + str(pid), check=False)
        if wi:
            wi.channel.close()
        if rig:
            try:
                close['rig'] = rig.stop()
            except Exception as ex:
                close['rig_error'] = str(ex)
        if changed:
            close['restore'] = run(p, "sudo -n sh -c 'echo " + str(int(old[2])) + " > /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq; echo " + str(int(old[1])) +
                                   " > /sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq; echo " + old[0] + " > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor'", check=False)
            close['pi_state'] = snapshot(p)
        if li:
            li.channel.shutdown_write(); close['pi_lock_release'] = lo.channel.recv_exit_status()
        if server:
            server.shutdown(); server.server_close()
        save(d / 'POSTFLIGHT.json', close)
        for obj in (wf, pf, w, p):
            if obj:
                obj.close()
        print('ARTIFACT ' + str(d), flush=True)

if __name__ == '__main__':
    main()
