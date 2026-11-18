"""Feature cache for the C35 exploratory false-alarm search (2026-11-11, session ws_followup).
For every run of the nine Pi sessions C24 C27 C28 C29 C30 C31 C32 C33 C34 stores:
  W, T   call-bracket features exactly as deployed (execution_window_features.feature, whole / phase-resolved)
  base   64-band mean (dB) and total-power mean (dB) over all complete frames that END before the dispatch mark
         (within-run pre-dispatch reference; empty bands zeroed)
plus condition, block, label, dispatch time.  Output: stats/c35_cache.npz (+ .json with meta).
"""
import json, pathlib, sys
import numpy as np
sys.stdout.reconfigure(encoding='utf-8')
E = pathlib.Path(r'<WORKSPACE>/ws_main\results\sp2027\experiments')
sys.path.insert(0, str(E))
import process_sp2027 as ps  # noqa: E402
from execution_window_features import EMPTY, FS  # noqa: E402
STAGES = [('C24', 's1'), ('C27', 's1b'), ('C28', 's1c'), ('C29', 's1d'), ('C30', 's1e'), ('C31', 's1f'), ('C32', 's1g'), ('C33', 's1i'), ('C34', 's1j')]


def pre_base(d, row):
    with np.load(d / 'features' / (row['id'] + '_930c.npz')) as f:
        w = f['sample_counts'].copy(); bands = f['band_db'].copy(); power = f['power_db'].copy()
    end = np.cumsum(w)
    before = next(m['bytes'] for m in row['before']['marks'] if m['radio'] == '930c')
    m = (end * 2 <= before) & (w > 0)
    assert m.sum() >= 4, (row['id'], int(m.sum()))
    b = 10 * np.log10(np.maximum(np.average(10 ** (bands[m] / 10), axis=0, weights=w[m]), 1e-20))
    p = 10 * np.log10(np.maximum(np.average(10 ** (power[m] / 10), weights=w[m]), 1e-20))
    b[EMPTY] = 0
    return np.r_[b, p], int(m.sum()), float(end[m][-1] / FS)


def main():
    out = {}; meta = {}
    for name, st in STAGES:
        d = pathlib.Path(json.loads((E / 'campaigns' / ('LATEST_' + st + '.json')).read_text(encoding='utf-8-sig'))['directory'])
        rows = ps.rows_of(d); assert all(x['valid'] for x in rows)
        t = np.array([x['dispatch_desktop_ns'] for x in rows], float)
        W = np.array([ps.windowed(d, x, 'call_bracket', False)[0] for x in rows])
        T = np.array([ps.windowed(d, x, 'call_bracket', True)[0] for x in rows])
        pb = [pre_base(d, x) for x in rows]
        out[name + '/W'] = W; out[name + '/T'] = T; out[name + '/base'] = np.array([p[0] for p in pb])
        out[name + '/cond'] = np.array([x['condition'] for x in rows]); out[name + '/block'] = np.array([int(x['block']) for x in rows])
        out[name + '/y'] = np.array([bool(x['actual_active']) for x in rows]); out[name + '/t'] = t
        meta[name] = {'stage': st, 'dir': str(d), 'n': len(rows), 'chronological': bool(np.all(np.diff(t) > 0)),
                      'pre_frames_min': min(p[1] for p in pb), 'pre_seconds_min': min(p[2] for p in pb), 'pre_seconds_max': max(p[2] for p in pb)}
        print(name, meta[name], flush=True)
    o = E.parent / 'stats' / 'c35_cache.npz'
    np.savez_compressed(o, **out)
    (E.parent / 'stats' / 'c35_cache.json').write_text(json.dumps(meta, indent=1), encoding='utf-8')
    print('wrote', o)


if __name__ == '__main__':
    main()
