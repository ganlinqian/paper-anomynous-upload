"""Pi tool server for S2: install(archive, digest) with real verify and extract phases (no model calls).

verify  = `sha256sum` of the archive, compared with the digest in the request's contract
extract = `gzip -dc archive > tmpfs/out`
Private config selects the actual order ('VX' compliant, 'XV' violating).  The response is padded
to a fixed envelope and is identical for both orders; the output digest is checked only after the
coordinator's research flush (i.e., after the radio capture).
"""
import argparse, hashlib, json, os, pathlib, signal, subprocess, sys, time

def stop_owned(signum, frame):
    raise SystemExit(128 + signum)
signal.signal(signal.SIGTERM, stop_owned)
signal.signal(signal.SIGINT, stop_owned)

ap = argparse.ArgumentParser(); ap.add_argument('--private-config', required=True); a = ap.parse_args()
p = pathlib.Path(a.private_config); cfg = json.loads(p.read_text())
arc = cfg['archive_path']; out = pathlib.Path(cfg['output_path']); out.parent.mkdir(parents=True, exist_ok=True)
warm = pathlib.Path(arc).read_bytes(); assert hashlib.sha256(warm).hexdigest() == cfg['archive_sha256']; del warm
phases = []
try:
    print(json.dumps({'ready': True, 'pid': os.getpid(), 'archive_sha256': cfg['archive_sha256']}), flush=True)
    line = sys.stdin.readline()
    if not line:
        raise EOFError('no request')
    request = json.loads(line); assert request['method'] == 'solve'
    t0 = time.monotonic_ns()

    def verify():
        b = time.monotonic_ns()
        r = subprocess.run(['taskset', '-c', '3', 'nice', '-n', '10', 'sha256sum', arc], capture_output=True, text=True)
        ok = r.returncode == 0 and r.stdout.split()[0] == cfg['archive_sha256']
        phases.append({'kind': 'verify', 'begin_ns': b, 'end_ns': time.monotonic_ns(), 'ok': ok})
        if not ok:
            raise RuntimeError('digest mismatch')

    def extract():
        b = time.monotonic_ns()
        r = subprocess.run(['taskset', '-c', '3', 'nice', '-n', '10', 'sh', '-c', 'gzip -dc "$0" > "$1"', arc, str(out)], capture_output=True, text=True)
        phases.append({'kind': 'extract', 'begin_ns': b, 'end_ns': time.monotonic_ns(), 'rc': r.returncode})
        if r.returncode:
            raise RuntimeError('extract failed ' + r.stderr)

    for fn in ([verify, extract] if cfg['order'] == 'VX' else [extract, verify]):
        fn()
    work_end = time.monotonic_ns()
    time.sleep(max(0.0, cfg['envelope_s'] - (time.monotonic_ns() - t0) / 1e9))
    response = {'id': request['id'], 'status': 'complete', 'result': sum(request['params']['values'])}; reply = time.monotonic_ns()
    print(json.dumps(response, sort_keys=True, separators=(',', ':')), flush=True)
    flush = sys.stdin.readline()
    if not flush or not json.loads(flush).get('research_flush'):
        raise EOFError('no research flush')
    h = hashlib.sha256()
    with out.open('rb') as f:
        for blk in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(blk)
    private = {'begin_ns': t0, 'work_end_ns': work_end, 'reply_ns': reply, 'envelope_s': (reply - t0) / 1e9, 'order': cfg['order'],
               'phases': phases, 'output_bytes': out.stat().st_size, 'output_ok': h.hexdigest() == cfg['plain_sha256'],
               'work_inside_envelope': work_end <= reply}
    p.with_suffix('.private.json').write_text(json.dumps(private, sort_keys=True))
finally:
    if out.exists():
        out.unlink()
