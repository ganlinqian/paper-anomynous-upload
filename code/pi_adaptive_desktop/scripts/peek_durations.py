"""Hidden-work durations per condition in the S1/C27 campaigns (read-only peek used to size C28 inputs)."""
import json, pathlib, statistics, sys
B = pathlib.Path(__file__).resolve().parents[1] / 'experiments' / 'campaigns'
for name in sys.argv[1:]:
    rows = json.loads((B / name / 'RESULTS.json').read_text(encoding='utf-8'))
    by = {}
    for r in rows:
        a = r['private'].get('archive') or {}
        if 'begin_ns' in a:
            by.setdefault(r['condition'], []).append(((a['fsync_end_ns'] - a['begin_ns']) / 1e9, a.get('throttle_cycles', 0),
                                                        (r['private']['http_received_ns'] - a['fsync_end_ns']) / 1e9))
    print(name, 'runs', len(rows), 'valid', sum(r['valid'] for r in rows))
    for c, v in sorted(by.items()):
        d = [x[0] for x in v]; m = [x[2] for x in v]
        print('  %-11s n=%d dur mean %.3f min %.3f max %.3f | cycles %d-%d | margin-to-reply min %.3f'
              % (c, len(v), statistics.mean(d), min(d), max(d), min(x[1] for x in v), max(x[1] for x in v), min(m)))
    t = [r['pre']['temperature'] for r in rows if 'temperature' in r.get('pre', {})]
    if t:
        print('  pre temp cpu %.1f-%.1f ddr %.2f-%.2f' % (min(x['cpu_c'] for x in t), max(x['cpu_c'] for x in t),
                                                     min(x['ddr_c'] for x in t), max(x['ddr_c'] for x in t)))
    w = [r['pre'].get('thermal_wait_s', 0) for r in rows]
    print('  thermal wait total %.0f s, runs waiting %d' % (sum(w), sum(1 for x in w if x)))
