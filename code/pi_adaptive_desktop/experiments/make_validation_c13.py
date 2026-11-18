"""Build a validation campaign from the existing C13 batch to check process_sp2027.py reproduces known results."""
import json, pathlib, shutil
SRC = pathlib.Path(r'<WORKSPACE>/ws_pi\results\scenario_rf_20261104')
d = pathlib.Path(__file__).resolve().parent / 'validation_c13'
(d / 'features').mkdir(parents=True, exist_ok=True)
rows = json.loads((SRC / 'untraced_wait_study/untracedwait_20261105_061041_b80fac/RESULTS.json').read_text(encoding='utf-8-sig'))
for r in rows:
    r['condition'] = 'gzip16' if r['actual_active'] else 'silent'
    for ext in ('npz', 'json'):
        shutil.copy2(SRC / 'untraced_processing_20261105/analysis/features' / (r['id'] + '_930c.' + ext), d / 'features')
(d / 'RESULTS.json').write_text(json.dumps(rows), encoding='utf-8')
(d / 'FREEZE.json').write_text(json.dumps({'campaign': 'validation_c13', 'source_sha256': {}}), encoding='utf-8')
print(len(rows), 'rows')
