"""Smoke test of the clock-check statistics on the old C13 replay (validation_c13); no S3 data involved."""
import collections, json, pathlib, sys
import numpy as np
E = pathlib.Path(r'<WORKSPACE>/ws_main\results\sp2027\experiments')
sys.path.insert(0, str(E))
import process_sp2027 as ps  # noqa: E402
d = E / 'validation_c13'
rows = ps.rows_of(d)
g = collections.defaultdict(list)
for x in rows:
    g[(x.get('condition'), bool(x['actual_active']))].append(ps.clock_stats(d, x))
for k, v in sorted(g.items(), key=str):
    a = np.array(v)
    print(k, 'n=%d' % len(a), 'dP mean %.4f sd %.4f [%.4f, %.4f]' % (a[:, 0].mean(), a[:, 0].std(ddof=1), a[:, 0].min(), a[:, 0].max()),
          'S mean %.4f sd %.4f max %.4f' % (a[:, 1].mean(), a[:, 1].std(ddof=1), a[:, 1].max()))
