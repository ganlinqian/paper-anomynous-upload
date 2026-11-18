"""Pi tool server for C33 (derived from pi_api_sp2027_wait.py by scripts/make_pi_api_c33.py; no model calls).

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
    flush = sys.stdin.readline()
    if not flush or not json.loads(flush).get('research_flush'):
        raise EOFError('no research flush')
    private = {'begin_ns': begin, 'http_sent_ns': sent, 'http_received_ns': received, 'reply_ns': reply, 'archive': archive,
               'activity_code': cfg['activity_code'], 'duty': cfg.get('duty', 1.0), 'input_path': cfg['input_path'], 'dvfs': dvfs,
               'compressor': cfg.get('compressor', 'gzip'), 'background_kind': cfg.get('background'), 'background': bg,
               'background_inside_wait': bool(bg and 'end_ns' in bg and sent <= bg['begin_ns'] < bg['end_ns'] <= received),
               'output_bytes': os.fstat(out.fileno()).st_size,
               'archive_inside_wait': bool(archive and sent <= archive['begin_ns'] < archive['fsync_end_ns'] <= received)}
    p.with_suffix('.private.json').write_text(json.dumps(private, sort_keys=True))
finally:
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
