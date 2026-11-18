import json, pathlib, sys
import numpy as np
d = pathlib.Path(sys.argv[1])
files = sorted(d.glob('*_930c.npz'))
print('n_930c_npz', len(files))
z = np.load(files[0], allow_pickle=False)
for k in z.files:
    a = z[k]
    print(k, a.dtype, a.shape, (float(a.min()), float(a.max())) if a.size and a.dtype.kind in 'fiu' else '')
j = json.loads(files[0].with_suffix('.json').read_text(encoding='utf-8-sig'))
print(json.dumps(j, indent=1)[:1500])
