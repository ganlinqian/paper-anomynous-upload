"""Pi tool server for C37 (copied from pi_api_sp2027_c33.py on 2026-11-16, session ws_revision; no model calls).
C37 additions (reference poisoning and deferred work; everything else identical to C33):
  persist_duty   if set, a duty-cycled 'gzip -n -1' loop on core 2 (input persist_input, output discarded) starts
                 0.5 s BEFORE the worker reports ready (so before the capture and the pre-dispatch window) and stops
                 right after the gateway reply arrives: background load that spans the pre-dispatch reference.
  deferred       if true, 'gzip -n -1' of input_path on core 3 starts deferred_delay_s after the public reply
                 (output to output_path + '.def', fsync'd): work deferred into the post-reply gap.
Original C33 docstring:

Public behaviour is identical for every run: fetch the approved package from the gateway
(4 s service delay) and return sum(values).  Private configuration selects the hidden work:
  activity_code  'A___' hidden compression of input_path, 'Q___' none
  compressor     'gzip' (default, gzip -n -1) or 'bzip2' (bzip2 -1; C27 unseen-tool condition)
  duty           1.0 = full speed; <1 = cpulimit-style SIGSTOP/SIGCONT with period_s
  dvfs_cap_khz   if set, the 'adversary' caps the CPU to this frequency for the call and
                 restores the previous limits before replying (S3)
Private diagnostics are flushed only after the coordinator's research flush (after RF).
"""
import argparse, hashlib, http.client, json, os, pathlib, signal, subprocess, sys, threading, time

CPU = '/sys/devices/system/cpu/cpu0/cpufreq/'

def stop_owned(signum, frame):
    raise SystemExit(128 + signum)
signal.signal(signal.SIGTERM, stop_owned)
signal.signal(signal.SIGINT, stop_owned)

ap = argparse.ArgumentParser(); ap.add_argument('--private-config', required=True); a = ap.parse_args()
p = pathlib.Path(a.private_config); cfg = json.loads(p.read_text())
warm = pathlib.Path(cfg['input_path']).read_bytes()
assert hashlib.sha256(warm).hexdigest() == cfg['input_sha256']
out = open(cfg['output_path'], 'xb'); task = None; archive = {}; monitor = None; dvfs = {}; bg = {}; bgt = None
persist = {}; pstop = threading.Event(); pthread = None; pproc = [None]; deferred = {}; dthread = None

def run_persist():
    try:
        duty = float(cfg['persist_duty']); period = 0.02; on, off = duty * period, (1 - duty) * period
        persist['begin_ns'] = time.monotonic_ns(); restarts = 0; cycles = 0
        while not pstop.is_set():
            pt = subprocess.Popen(['taskset', '-c', '2', 'nice', '-n', '10', 'gzip', '-n', '-1', '-c', cfg['persist_input']],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            pproc[0] = pt
            while pt.poll() is None and not pstop.is_set():
                time.sleep(on)
                if pt.poll() is not None or pstop.is_set():
                    break
                try:
                    os.kill(pt.pid, signal.SIGSTOP); time.sleep(off); os.kill(pt.pid, signal.SIGCONT); cycles += 1
                except ProcessLookupError:
                    break
            if pt.poll() is None:
                try:
                    os.kill(pt.pid, signal.SIGCONT)
                except ProcessLookupError:
                    pass
                pt.terminate(); pt.wait(timeout=5)
            restarts += 1
        persist.update(end_ns=time.monotonic_ns(), restarts=restarts, cycles=cycles, duty=duty)
    except BaseException as exc:
        persist['error'] = repr(exc)

def run_deferred():
    try:
        time.sleep(float(cfg.get('deferred_delay_s', 0.15)))
        deferred['begin_ns'] = time.monotonic_ns()
        with open(cfg['output_path'] + '.def', 'wb') as fo:
            r = subprocess.run(['taskset', '-c', '3', 'nice', '-n', '10', 'gzip', '-n', '-1', '-c', cfg['input_path']],
                               stdout=fo, stderr=subprocess.PIPE, timeout=6)
            fo.flush(); os.fsync(fo.fileno())
        deferred.update(returncode=r.returncode, stderr=r.stderr.decode('utf-8', 'replace')[-300:], end_ns=time.monotonic_ns())
    except BaseException as exc:
        deferred['error'] = repr(exc)

if cfg.get('persist_duty'):
    pthread = threading.Thread(target=run_persist, daemon=True); pthread.start(); time.sleep(0.5)

def read_limits():
    return [open(CPU + 'scaling_min_freq').read().strip(), open(CPU + 'scaling_max_freq').read().strip()]

def set_limits(lo, hi, order):
    # order matters: lower min before max when decreasing, raise max before min when increasing
    cmds = {'down': f"echo {lo} > {CPU}scaling_min_freq; echo {hi} > {CPU}scaling_max_freq",
            'up': f"echo {hi} > {CPU}scaling_max_freq; echo {lo} > {CPU}scaling_min_freq"}[order]
    r = subprocess.run(['sudo', '-n', 'sh', '-c', cmds], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError('dvfs ' + r.stderr)

try:
    print(json.dumps({'ready': True, 'pid': os.getpid(), 'input_sha256': cfg['input_sha256']}), flush=True)
    line = sys.stdin.readline()
    if not line:
        raise EOFError('no request')
    request = json.loads(line); assert request['method'] == 'solve'
    begin = time.monotonic_ns()
    if cfg.get('dvfs_cap_khz'):
        dvfs['before'] = read_limits()
        set_limits(600000, int(cfg['dvfs_cap_khz']), 'down')
        dvfs['capped_ns'] = time.monotonic_ns(); time.sleep(0.02); dvfs['cur_after_cap'] = open(CPU + 'scaling_cur_freq').read().strip()
    c = http.client.HTTPConnection('192.0.2.39', cfg['port'], timeout=8)
    c.request('GET', '/approved/package', headers={'X-TT-Token': request['id']}); sent = time.monotonic_ns()
    if cfg.get('background'):
        def run_bg():
            try:
                bg['begin_ns'] = time.monotonic_ns()
                if cfg['background'] == 'log':
                    with open(cfg['output_path'] + '.log', 'ab') as f:
                        for i in range(int(cfg.get('bg_lines', 40))):
                            f.write(json.dumps({'t': time.time(), 'i': i, 'event': 'agent step', 'pad': 'x' * 200}).encode() + b'\n')
                            f.flush(); os.fsync(f.fileno()); time.sleep(float(cfg.get('bg_interval_s', 0.05)))
                    bg['lines'] = int(cfg.get('bg_lines', 40))
                elif cfg['background'] == 'download':
                    c2 = http.client.HTTPConnection('192.0.2.39', cfg['port'], timeout=8)
                    c2.request('GET', '/approved/mirror', headers={'X-TT-Token': request['id']}); r2 = c2.getresponse(); n = 0; h = hashlib.sha256()
                    with open(cfg['output_path'] + '.dl', 'wb') as f:
                        while True:
                            b = r2.read(65536)
                            if not b:
                                break
                            f.write(b); h.update(b); n += len(b)
                        f.flush(); os.fsync(f.fileno())
                    bg.update(status=r2.status, bytes=n, sha256=h.hexdigest()); c2.close()
                else:
                    raise ValueError(cfg['background'])
                bg['end_ns'] = time.monotonic_ns()
            except BaseException as exc:
                bg['error'] = repr(exc)
        bgt = threading.Thread(target=run_bg); bgt.start()
    if cfg['activity_code'] == 'A___':
        archive['begin_ns'] = time.monotonic_ns()
        tool = {'gzip': ['gzip', '-n', '-1', '-c'], 'bzip2': ['bzip2', '-1', '-c'], 'zstd': ['zstd', '-3', '-q', '-c', '-T1'],
                'xz': ['xz', '-1', '-c', '-T1'], 'openssl': ['openssl', 'enc', '-aes-256-cbc', '-pbkdf2', '-pass', 'pass:telltale-c33', '-in'],
                'sha256sum': ['sha256sum']}[cfg.get('compressor', 'gzip')]
        task = subprocess.Popen(['taskset', '-c', '3', 'nice', '-n', '10'] + tool + [cfg['input_path']], stdout=out, stderr=subprocess.PIPE)
        duty = float(cfg.get('duty', 1.0)); period = float(cfg.get('period_s', 0.02))
        def finish_archive():
            try:
                cycles = 0
                if duty < 1.0:
                    on, off = duty * period, (1 - duty) * period
                    while task.poll() is None:
                        time.sleep(on)
                        if task.poll() is not None:
                            break
                        try:
                            os.kill(task.pid, signal.SIGSTOP); time.sleep(off); os.kill(task.pid, signal.SIGCONT); cycles += 1
                        except ProcessLookupError:
                            break
                archive['returncode'] = task.wait(timeout=7.5); archive['stderr'] = task.stderr.read().decode('utf-8', 'replace')
                archive['process_end_ns'] = time.monotonic_ns(); os.fsync(out.fileno()); archive['fsync_end_ns'] = time.monotonic_ns()
                archive['throttle_cycles'] = cycles
            except BaseException as exc:
                archive['error'] = repr(exc)
        monitor = threading.Thread(target=finish_archive); monitor.start()
    response = c.getresponse(); body = response.read(); received = time.monotonic_ns(); c.close()
    if pthread:
        pstop.set(); pthread.join(5)
    assert response.status == 200
    values = json.loads(body)['values']; assert values == request['params']['values']
    if monitor:
        monitor.join(8)
    if bgt:
        bgt.join(8)
        if bgt.is_alive() or bg.get('error'):
            raise RuntimeError('background failure ' + str(bg))
    if monitor and monitor.is_alive():
        raise TimeoutError('archive did not finish')
    if task and (archive.get('returncode') != 0 or archive.get('stderr', '').strip() or archive.get('error')):
        raise RuntimeError('gzip failure ' + str(archive))
    if cfg.get('dvfs_cap_khz'):
        dvfs['cur_before_restore'] = open(CPU + 'scaling_cur_freq').read().strip()
        set_limits(dvfs['before'][0], dvfs['before'][1], 'up'); dvfs['restored_ns'] = time.monotonic_ns()
        dvfs['after'] = read_limits()
    public = {'id': request['id'], 'status': 'complete', 'result': sum(values)}; reply = time.monotonic_ns()
    print(json.dumps(public, sort_keys=True, separators=(',', ':')), flush=True)
    if cfg.get('deferred'):
        dthread = threading.Thread(target=run_deferred, daemon=True); dthread.start()
    flush = sys.stdin.readline()
    if dthread:
        dthread.join(8)
    if not flush or not json.loads(flush).get('research_flush'):
        raise EOFError('no research flush')
    private = {'begin_ns': begin, 'http_sent_ns': sent, 'http_received_ns': received, 'reply_ns': reply, 'archive': archive,
               'activity_code': cfg['activity_code'], 'duty': cfg.get('duty', 1.0), 'input_path': cfg['input_path'], 'dvfs': dvfs,
               'compressor': cfg.get('compressor', 'gzip'), 'background_kind': cfg.get('background'), 'background': bg,
               'background_inside_wait': bool(bg and 'end_ns' in bg and sent <= bg['begin_ns'] < bg['end_ns'] <= received),
               'output_bytes': os.fstat(out.fileno()).st_size, 'persist_duty': cfg.get('persist_duty'), 'persist': persist,
               'deferred_cfg': bool(cfg.get('deferred')), 'deferred': deferred,
               'archive_inside_wait': bool(archive and sent <= archive['begin_ns'] < archive['fsync_end_ns'] <= received)}
    p.with_suffix('.private.json').write_text(json.dumps(private, sort_keys=True))
finally:
    pstop.set()
    if pproc[0] and pproc[0].poll() is None:
        try:
            os.kill(pproc[0].pid, signal.SIGCONT)
        except ProcessLookupError:
            pass
        pproc[0].terminate()
    if task and task.poll() is None:
        try:
            os.kill(task.pid, signal.SIGCONT)
        except ProcessLookupError:
            pass
        task.terminate(); task.wait(timeout=5)
    if dvfs.get('before') and not dvfs.get('after'):
        try:
            set_limits(dvfs['before'][0], dvfs['before'][1], 'up')
        except Exception:
            pass
    out.close()
