"""Deterministic JSON-lines log fixture for C27 condition 'json8' (unseen input: non-repeating records,
different compressibility from text8). Usage: jsongen.py OUT MIB"""
import json, random, sys
rng = random.Random(20261106)
levels = ['DEBUG', 'INFO', 'INFO', 'INFO', 'WARN', 'ERROR']
comps = ['gateway', 'skill-runner', 'fs-watch', 'http-proxy', 'scheduler', 'auth', 'cache']
msgs = ['tool call dispatched', 'package fetched', 'digest verified', 'archive extracted', 'session refreshed', 'retrying request',
        'cache miss', 'file written', 'permission denied', 'timeout waiting for reply', 'rate limit applied']
target = int(sys.argv[2]) * 1024 * 1024; size = 0; t = 1793664000.0
with open(sys.argv[1], 'wb') as f:
    while size < target:
        t += rng.expovariate(40.0)
        rec = {'ts': round(t, 6), 'level': rng.choice(levels), 'component': rng.choice(comps), 'msg': rng.choice(msgs),
               'request_id': '%032x' % rng.getrandbits(128), 'latency_ms': round(rng.lognormvariate(3.0, 1.0), 3),
               'bytes': rng.randrange(0, 1 << 20), 'path': '/home/agent/work/%s/%06d.dat' % (rng.choice(comps), rng.randrange(10 ** 6))}
        line = (json.dumps(rec, separators=(',', ':')) + '\n').encode()
        line = line[:target - size] if size + len(line) > target else line
        f.write(line); size += len(line)
