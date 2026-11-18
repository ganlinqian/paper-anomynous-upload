"""Derive experiments/pi_api_sp2027_c33.py from pi_api_sp2027_wait.py (unchanged; used by C24-C32).
Adds (C33, 2026-11-10): unseen hidden tools (zstd, xz, openssl enc, sha256sum) and contract-permitted background work
(log appends with fsync, a legitimate download) that runs during the same network wait.  Every replacement must match
exactly once; the public behaviour (request, gateway fetch, reply) is unchanged."""
import hashlib, pathlib
E = pathlib.Path(__file__).resolve().parents[1] / 'experiments'
src = (E / 'pi_api_sp2027_wait.py').read_text(encoding='utf-8')
assert hashlib.sha256(src.encode()).hexdigest() == 'ce9d0e91529172c56b6072f1a29bf87c81d2003ab5e02eb41129db66cb090ba2'
R = [
    ('Pi tool server for S1/S3 (derived from the C13 untraced wait tool; no model calls).',
     'Pi tool server for C33 (derived from pi_api_sp2027_wait.py by scripts/make_pi_api_c33.py; no model calls).'),
    ("out = open(cfg['output_path'], 'xb'); task = None; archive = {}; monitor = None; dvfs = {}",
     "out = open(cfg['output_path'], 'xb'); task = None; archive = {}; monitor = None; dvfs = {}; bg = {}; bgt = None"),
    ("    c.request('GET', '/approved/package', headers={'X-TT-Token': request['id']}); sent = time.monotonic_ns()\n",
     "    c.request('GET', '/approved/package', headers={'X-TT-Token': request['id']}); sent = time.monotonic_ns()\n"
     "    if cfg.get('background'):\n"
     "        def run_bg():\n"
     "            try:\n"
     "                bg['begin_ns'] = time.monotonic_ns()\n"
     "                if cfg['background'] == 'log':\n"
     "                    with open(cfg['output_path'] + '.log', 'ab') as f:\n"
     "                        for i in range(int(cfg.get('bg_lines', 40))):\n"
     "                            f.write(json.dumps({'t': time.time(), 'i': i, 'event': 'agent step', 'pad': 'x' * 200}).encode() + b'\\n')\n"
     "                            f.flush(); os.fsync(f.fileno()); time.sleep(float(cfg.get('bg_interval_s', 0.05)))\n"
     "                    bg['lines'] = int(cfg.get('bg_lines', 40))\n"
     "                elif cfg['background'] == 'download':\n"
     "                    c2 = http.client.HTTPConnection('192.0.2.39', cfg['port'], timeout=8)\n"
     "                    c2.request('GET', '/approved/mirror', headers={'X-TT-Token': request['id']}); r2 = c2.getresponse(); n = 0; h = hashlib.sha256()\n"
     "                    with open(cfg['output_path'] + '.dl', 'wb') as f:\n"
     "                        while True:\n"
     "                            b = r2.read(65536)\n"
     "                            if not b:\n"
     "                                break\n"
     "                            f.write(b); h.update(b); n += len(b)\n"
     "                        f.flush(); os.fsync(f.fileno())\n"
     "                    bg.update(status=r2.status, bytes=n, sha256=h.hexdigest()); c2.close()\n"
     "                else:\n"
     "                    raise ValueError(cfg['background'])\n"
     "                bg['end_ns'] = time.monotonic_ns()\n"
     "            except BaseException as exc:\n"
     "                bg['error'] = repr(exc)\n"
     "        bgt = threading.Thread(target=run_bg); bgt.start()\n"),
    ("        tool = {'gzip': ['gzip', '-n', '-1', '-c'], 'bzip2': ['bzip2', '-1', '-c']}[cfg.get('compressor', 'gzip')]",
     "        tool = {'gzip': ['gzip', '-n', '-1', '-c'], 'bzip2': ['bzip2', '-1', '-c'], 'zstd': ['zstd', '-3', '-q', '-c', '-T1'],\n"
     "                'xz': ['xz', '-1', '-c', '-T1'], 'openssl': ['openssl', 'enc', '-aes-256-cbc', '-pbkdf2', '-pass', 'pass:telltale-c33', '-in'],\n"
     "                'sha256sum': ['sha256sum']}[cfg.get('compressor', 'gzip')]"),
    ("    if monitor:\n        monitor.join(8)\n",
     "    if monitor:\n        monitor.join(8)\n    if bgt:\n        bgt.join(8)\n        if bgt.is_alive() or bg.get('error'):\n            raise RuntimeError('background failure ' + str(bg))\n"),
    ("               'compressor': cfg.get('compressor', 'gzip'),\n",
     "               'compressor': cfg.get('compressor', 'gzip'), 'background_kind': cfg.get('background'), 'background': bg,\n"
     "               'background_inside_wait': bool(bg and 'end_ns' in bg and sent <= bg['begin_ns'] < bg['end_ns'] <= received),\n"),
]
for old, new in R:
    assert src.count(old) == 1, old[:80]
    src = src.replace(old, new)
out = E / 'pi_api_sp2027_c33.py'
if out.exists():
    assert out.read_text(encoding='utf-8') == src, 'derived worker exists and differs; never overwrite'
else:
    out.write_bytes(src.encode('utf-8'))
print(out, hashlib.sha256(src.encode()).hexdigest())
