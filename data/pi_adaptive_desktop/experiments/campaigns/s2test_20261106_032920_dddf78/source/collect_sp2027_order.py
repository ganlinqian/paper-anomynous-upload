"""S2 controller: real verify-then-extract order (train or test stage; no model calls).

Contract (trusted, coordinator-side): verify the archive digest before extracting.
Physical bit A: actual order (VX compliant, XV violating).  Each block holds 2 VX + 2 XV runs with one
shared request/response.  Reuses (read-only) bridge_utils.py and collect.Rig; the rig is rig_capture_stagger_sp2027.py
(capture code identical to the original; only the capture-pc session precondition differs, see the supplement protocol).
"""
import argparse, hashlib, json, os, pathlib, random, shlex, sys, time, traceback
B = pathlib.Path(__file__).resolve().parent
SRC = pathlib.Path(r'<WORKSPACE>/ws_pi\results\scenario_rf_20261104')
sys.path.insert(0, str(SRC / 'burst_study')); from bridge_utils import *   # noqa
sys.path.insert(1, str(SRC)); from collect import Rig                      # noqa
PAYLOAD_SEED = b'Telltale:S2:payload:v1'; MIB = 1024 * 1024; PAYLOAD_MIB = 96
VALUES = [13, 31, 53, 73, 97]; ENVELOPE = 2.5
STAGES = {'train': (4, 2026110611), 'test': (10, 2026110621)}

def guard_wait(p, limit_s=900):
    """Pre-run precondition (2026-11-06 amendment after the thermal stop of the first S2 test batch): if only the thermal
    limit is exceeded, wait in 30 s steps (at most 15 min) until it is met instead of aborting; anything else aborts."""
    t0 = time.time(); waits = 0
    while True:
        try:
            g = guard(p); g['thermal_waits'] = waits; g['thermal_wait_s'] = round(time.time() - t0, 1); return g
        except RuntimeError as ex:
            if 'thermal precondition' not in str(ex) or time.time() - t0 > limit_s:
                raise
            waits += 1; time.sleep(30)

def guard_post(p):
    """Post-run record: thermal excess is recorded (the next run's guard_wait enforces the limit); throttling still aborts."""
    try:
        return guard(p)
    except RuntimeError as ex:
        if 'thermal precondition' not in str(ex):
            raise
        return {'state': snapshot(p), 'temperature': thermal(), 'thermal_exceeded_after_run': str(ex)}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--stage', choices=sorted(STAGES), required=True); args = ap.parse_args()
    lower_priority()
    if args.stage == 'test':
        frozen = B / 'models' / 'S2_ORDER_MODELS.json'
        if not frozen.exists():
            raise RuntimeError('test stage requires the frozen S2 model from the train stage')
    campaign = 's2' + args.stage + '_' + time.strftime('%Y%m%d_%H%M%S', time.gmtime()) + '_' + os.urandom(3).hex()
    d = B / 'campaigns' / campaign; d.mkdir(parents=True); save(B / 'campaigns' / ('LATEST_s2' + args.stage + '.json'), {'directory': str(d), 'campaign': campaign})
    pr = '/home/pi/telltale_sp2027/' + campaign; wr = '<DATA>/telltale_sp2027/' + campaign; shm = '/dev/shm/' + campaign
    lock = '/home/pi/telltale_g1_20261026/controller.lock'
    p = w = pf = wf = rig = li = lo = le = wi = wo = we = None; pid = None; old = None; changed = False; rows = []
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
        try:
            wf.mkdir('<DATA>/telltale_sp2027')
        except OSError:
            pass
        rs = '<DATA>/telltale_sp2027/rig_' + campaign + '.py'; wf.put(str(B / 'rig_capture_stagger_sp2027.py'), rs)
        rig = Rig(w, rs, wr, campaign); assert int(rig.pre['preflight']['free']) >= 100 * 10 ** 9
        # ---- fixtures: deterministic incompressible payload; archive built on the Pi with gzip -1 -n
        run(p, 'mkdir -p ' + pr + ' ' + shm); pf.put(str(B / 'pi_api_sp2027_order.py'), pr + '/pi_api.py')
        payload = hashlib.shake_256(PAYLOAD_SEED).digest(PAYLOAD_MIB * MIB); plain_sha = hashlib.sha256(payload).hexdigest(); del payload
        gen = 'import hashlib,pathlib;pathlib.Path(' + repr(pr + '/payload.bin') + ').write_bytes(hashlib.shake_256(' + repr(PAYLOAD_SEED) + ').digest(' + str(PAYLOAD_MIB * MIB) + '))'
        run(p, 'python3 -c ' + shlex.quote(gen), timeout=120)
        assert run(p, 'sha256sum ' + pr + '/payload.bin', timeout=60)['stdout'].split()[0] == plain_sha
        run(p, 'gzip -n -1 -c ' + pr + '/payload.bin > ' + pr + '/package.gz && rm ' + pr + '/payload.bin', timeout=120)
        arc_sha = run(p, 'sha256sum ' + pr + '/package.gz', timeout=60)['stdout'].split()[0]
        # independent check on the desktop: archive decompresses to the expected payload
        local = d / 'package.gz'; pf.get(pr + '/package.gz', str(local)); assert sha(local) == arc_sha
        import gzip as _gz
        with _gz.open(local, 'rb') as g:
            hh = hashlib.sha256()
            for blk in iter(lambda: g.read(4 * MIB), b''):
                hh.update(blk)
        assert hh.hexdigest() == plain_sha; local.unlink()
        fx = {'archive_sha256': arc_sha, 'plain_sha256': plain_sha, 'payload_mib': PAYLOAD_MIB}; save(d / 'FIXTURES.json', fx)
        run(p, "sudo -n sh -c 'echo performance > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor; echo 1800000 > /sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq'"); changed = True

        def start_worker(ident, order):
            nonlocal wi, wo, we, pid
            stem = pr + '/' + ident
            config = {'archive_path': pr + '/package.gz', 'archive_sha256': arc_sha, 'plain_sha256': plain_sha, 'order': order,
                      'output_path': shm + '/' + ident + '.out', 'envelope_s': ENVELOPE}
            td = d / 'records' / ident; td.mkdir(parents=True); save(td / 'private_config.json', config); pf.put(str(td / 'private_config.json'), stem + '.json')
            cmd = 'env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 nice -n 10 python3 -u ' + pr + '/pi_api.py --private-config ' + stem + '.json'
            wi, wo, we = p.exec_command(cmd, timeout=30); ready = json.loads(wo.readline()); pid = ready['pid']
            assert ready['ready'] and ready['archive_sha256'] == arc_sha
            status = run(p, 'cat /proc/' + str(pid) + '/status')['stdout']
            tracer = int(next(x.split()[1] for x in status.splitlines() if x.startswith('TracerPid:'))); assert tracer == 0
            ready['independently_checked_tracer_pid'] = tracer
            return stem, td, ready

        def finish_worker(stem, td):
            nonlocal wi, wo, we, pid
            wi.write('{"research_flush":true}\n'); wi.flush(); wi.channel.shutdown_write()
            extra = wo.read().decode('utf-8', 'replace'); err = we.read().decode('utf-8', 'replace'); rc = wo.channel.recv_exit_status()
            wi = wo = we = None; pid = None; (td / 'stderr.log').write_text(err)
            assert not extra.strip() and not err.strip() and rc == 0, (extra, err, rc)
            pf.get(stem + '.private.json', str(td / 'worker.private.json'))
            return json.loads((td / 'worker.private.json').read_text())

        nblocks, seed = STAGES[args.stage]; plan = []
        for block in range(nblocks):
            cc = ['VX', 'VX', 'XV', 'XV']; random.Random(seed + block).shuffle(cc)
            token = os.urandom(16).hex(); request = {'id': token, 'method': 'solve', 'params': {'values': VALUES}}
            for order in cc:
                plan.append({'id': 'v' + os.urandom(6).hex(), 'block': block, 'stage': 'sp2027_s2' + args.stage, 'order': order,
                             'actual_verify_first': order == 'VX', 'expected_verify_first': True, 'request': request})
        sources = [B / 'collect_sp2027_order.py', B / 'pi_api_sp2027_order.py', B.parent / '03_supplementary_experimental_plan.md', B / 'rig_capture_stagger_sp2027.py', SRC / 'rig_capture_stagger.py',
                   SRC / 'burst_study/bridge_utils.py', SRC / 'collect.py']
        if args.stage == 'test':
            sources.append(B / 'models' / 'S2_ORDER_MODELS.json')
        sd = d / 'source'; sd.mkdir()
        for path in sources:
            (sd / path.name).write_bytes(path.read_bytes())
        freeze = {'campaign': campaign, 'stage': args.stage, 'plan': plan, 'seconds': 8, 'cooldown_s': 25, 'winroot': wr, 'piroot': pr, 'pre_state': pre,
                  'rig_preflight': rig.pre, 'source_sha256': {str(x): sha(x) for x in sources}, 'utc': stamp(), 'syscall_tracing': False,
                  'fixtures': fx, 'envelope_s': ENVELOPE}
        save(d / 'FREEZE.json', freeze); wf.put(str(d / 'FREEZE.json'), wr + '/FREEZE.json')
        for idx, cfg in enumerate(plan):
            row = dict(cfg); row['pre'] = guard_wait(p)
            stem, td, ready = start_worker(cfg['id'], cfg['order']); row['ready'] = ready
            row['capture_ready'] = rig.rpc({'op': 'capture', 'id': cfg['id'], 'seconds': 8})
            time.sleep(random.Random(71206 + idx).uniform(.25, .45))
            row['before'] = rig.rpc({'op': 'mark'}); row['dispatch_desktop_ns'] = time.perf_counter_ns()
            wi.write(json.dumps(cfg['request'], sort_keys=True, separators=(',', ':')) + '\n'); wi.flush()
            response = json.loads(wo.readline()); row['return_desktop_ns'] = time.perf_counter_ns()
            row['after'] = rig.rpc({'op': 'mark'}); row['rf'] = rig.rpc({'op': 'finish'}); row['rf_finish_desktop_ns'] = time.perf_counter_ns()
            private = finish_worker(stem, td); row['private'] = private
            trace = {'request': cfg['request'], 'response': response}; save(td / 'canonical_trace.json', trace)
            row.update(canonical_trace=trace, canonical_trace_sha256=sha(td / 'canonical_trace.json'),
                       elapsed_s=(row['return_desktop_ns'] - row['dispatch_desktop_ns']) / 1e9, post=guard_post(p))
            kinds = [x['kind'] for x in private['phases']]
            valid = (response == {'id': cfg['request']['id'], 'status': 'complete', 'result': sum(VALUES)}
                     and all(r['rc'] == 0 and r['bytes'] == r['expected_bytes'] == 320000000 for r in row['rf']['radios'])
                     and all(m['running'] and 0 < m['bytes'] < 320000000 for key in ('before', 'after') for m in row[key]['marks'])
                     and kinds == (['verify', 'extract'] if cfg['order'] == 'VX' else ['extract', 'verify'])
                     and private['output_ok'] and private['work_inside_envelope'])
            row['valid'] = bool(valid); save(td / 'record.json', row); rows.append(row); save(d / 'RESULTS.json', rows)
            for r in row['rf']['radios']:
                wf.get(r['log'].replace('\\', '/'), str(td / (r['radio'] + '.rf.log')))
            print(json.dumps({'completed': idx + 1, 'planned': len(plan), 'id': cfg['id'], 'order': cfg['order'], 'valid': valid,
                              'envelope_s': private['envelope_s'], 'utc': stamp()}), flush=True)
            if not valid:
                raise RuntimeError('invalid bounded acquisition')
            if idx < len(plan) - 1:
                time.sleep(25)
        for block in range(nblocks):
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
        if p:
            close['cleanup'] = run(p, 'rm -rf ' + shm + ' ' + pr + '/package.gz ' + pr + '/payload.bin', check=False)
        if changed:
            close['restore'] = run(p, "sudo -n sh -c 'echo " + str(int(old[2])) + " > /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq; echo " + str(int(old[1])) +
                                   " > /sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq; echo " + old[0] + " > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor'", check=False)
            close['pi_state'] = snapshot(p)
        if li:
            li.channel.shutdown_write(); close['pi_lock_release'] = lo.channel.recv_exit_status()
        save(d / 'POSTFLIGHT.json', close)
        for obj in (wf, pf, w, p):
            if obj:
                obj.close()
        print('ARTIFACT ' + str(d), flush=True)

if __name__ == '__main__':
    main()
