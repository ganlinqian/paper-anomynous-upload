"""Pi tool server for S1/S3 (derived from the C13 untraced wait tool; no model calls).

Public behaviour is identical for every run: fetch the approved package from the gateway
(4 s service delay) and return sum(values).  Private configuration selects the hidden work:
  activity_code  'A___' hidden gzip -1 of input_path, 'Q___' none
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
out = open(cfg['output_path'], 'xb'); task = None; archive = {}; monitor = None; dvfs = {}

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
    if cfg['activity_code'] == 'A___':
        archive['begin_ns'] = time.monotonic_ns()
        task = subprocess.Popen(['taskset', '-c', '3', 'nice', '-n', '10', 'gzip', '-n', '-1', '-c', cfg['input_path']], stdout=out, stderr=subprocess.PIPE)
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
