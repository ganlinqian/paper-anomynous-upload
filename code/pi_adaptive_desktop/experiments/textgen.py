"""Deterministic text-like (compressible) fixture for S1 condition 'text8'. Usage: textgen.py OUT MIB"""
import random, sys
rng = random.Random(20261105)
vocab = ['agent', 'tool', 'call', 'verify', 'extract', 'package', 'digest', 'skill', 'gateway', 'config', 'error', 'info',
         'warn', 'debug', 'user', 'file', 'path', 'value', 'result', 'status', 'session', 'token', 'cache', 'build']
block = []; size = 0
while size < 1024 * 1024:
    line = '%08d %s\n' % (rng.randrange(10 ** 8), ' '.join(rng.choice(vocab) for _ in range(rng.randrange(6, 14))))
    block.append(line); size += len(line)
base = ''.join(block).encode()[:1024 * 1024]
with open(sys.argv[1], 'wb') as f:
    for i in range(int(sys.argv[2])):
        f.write(('#block %06d\n' % i).encode() + base[13:])
