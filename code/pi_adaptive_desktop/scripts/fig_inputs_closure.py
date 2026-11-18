"""Summarise the traced figure inputs into a data closure, and compare the traced outputs with the paper figures.

Usage: python -I closure.py TRACE_DIR OUT_JSON
"""
import collections
import hashlib
import json
import os
import pathlib
import sys

trace_dir, out_json = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
S = pathlib.Path(r'<WORKSPACE>/ws_main\results\sp2027')
ROOTS = {
    'sp2027': S,
    'scenario_rf_20261104': pathlib.Path(r'<WORKSPACE>/ws_pi\results\scenario_rf_20261104'),
    'scivis_skill': pathlib.Path(r'<TOOLS>'),
}
EXCLUDE_UNDER = [S / 'scripts', S / 'scratch']
IGNORE_PREFIXES = [p.lower() for p in (
    r'<PYTHON>', r'C:\Windows\Fonts', r'<HOME>\.matplotlib',
    r'<PYTHON>', r'C:\Program Files', r'<PYTHON>')]


def under(p, root):
    try:
        p.relative_to(root)
        return True
    except ValueError:
        return False


def key_of(p):
    for k, r in ROOTS.items():
        if under(p, r):
            return k, p.relative_to(r).as_posix()
    return None, None


files, dirs, other, writes = {}, set(), collections.Counter(), collections.Counter()
for tf in sorted(trace_dir.glob('trace_*.json')):
    t = json.loads(tf.read_text(encoding='utf-8'))
    print(tf.name, t['status'], len(t['events']), 'events')
    for ev, path, mode in t['events']:
        p = pathlib.Path(os.path.abspath(path))
        if any(c in mode for c in 'wax+'):
            writes[str(p.parent)] += 1
            continue
        if any(under(p, e) for e in EXCLUDE_UNDER):
            continue
        k, rel = key_of(p)
        if k is None:
            if not any(str(p).lower().startswith(x) for x in IGNORE_PREFIXES) and p.name != 'trace_fig_inputs.py':
                other[str(p)] += 1
            continue
        if ev in ('os.listdir', 'os.scandir'):
            dirs.add((k, rel))
        elif p.is_file():
            files.setdefault((k, rel), set()).add(ev)
        elif p.is_dir():
            dirs.add((k, rel))

rows = []
for (k, rel), evs in sorted(files.items()):
    p = ROOTS[k] / rel
    st = p.stat()
    rows.append({'root': k, 'path': rel, 'bytes': st.st_size, 'mtime_ns': st.st_mtime_ns,
                 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'access': sorted(evs)})
out_json.write_text(json.dumps({'roots': {k: str(v) for k, v in ROOTS.items()}, 'files': rows,
                                'dirs_listed': sorted(f'{k}:{r}' for k, r in dirs)}, indent=1), encoding='utf-8')

agg = collections.defaultdict(lambda: [0, 0])
for r in rows:
    parts = r['path'].split('/')
    g = r['root'] + ':' + '/'.join(parts[:2] if len(parts) > 2 else parts[:1])
    agg[g][0] += 1
    agg[g][1] += r['bytes']
print('\n== closure by group (files, MB)')
for g, (n, b) in sorted(agg.items()):
    print(f'{g:<80} {n:5d} {b / 1e6:8.2f}')
print('TOTAL', len(rows), 'files', round(sum(r['bytes'] for r in rows) / 1e6, 2), 'MB')
print('stat-only files:', [f"{r['root']}:{r['path']}" for r in rows if r['access'] == ['stat']][:40])
print('\n== directories listed:', sorted(f'{k}:{r}' for k, r in dirs)[:30])
print('\n== writes by directory:', dict(writes))
print('\n== other paths (not under known roots):', dict(list(other.items())[:40]))

# traced outputs vs. the figures used by the paper build
paper = S / 'paper_v9' / 'figures'
print('\n== traced outputs vs paper_v9/figures')
for f in sorted((trace_dir / 'trace_out').rglob('*')):
    if f.suffix.lower() not in ('.pdf', '.jpg'):
        continue
    ref = paper / f.name
    if not ref.exists():
        print(f'{f.parent.name}/{f.name}: not used by paper_v9')
        continue
    same = f.read_bytes() == ref.read_bytes()
    print(f'{f.parent.name}/{f.name}: {"IDENTICAL" if same else "DIFFERS"} ({f.stat().st_size} vs {ref.stat().st_size})')
