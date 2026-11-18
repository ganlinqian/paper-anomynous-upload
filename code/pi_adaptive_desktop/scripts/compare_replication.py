import json, pathlib, sys
import numpy as np
new = pathlib.Path(sys.argv[1]); old = pathlib.Path(sys.argv[2])
rep = {}
for f in sorted(new.glob('*_930c.npz')):
    a = np.load(f); b = np.load(old / f.name)
    ja = json.loads(f.with_suffix('.json').read_text(encoding='utf-8-sig')); jb = json.loads((old / f.with_suffix('.json').name).read_text(encoding='utf-8-sig'))
    rep[f.name] = {'raw_sha256_equal': ja['raw_sha256'] == jb['raw_sha256'],
                   **{k: float(np.max(np.abs(a[k].astype(float) - b[k].astype(float)))) for k in ('features', 'power_db', 'band_db', 'clip_fraction', 'sample_counts')}}
print(json.dumps(rep, indent=1))
