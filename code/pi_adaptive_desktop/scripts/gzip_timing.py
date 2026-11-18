import json, pathlib, statistics
R = pathlib.Path(r'<WORKSPACE>/ws_pi\results\scenario_rf_20261104')
for name, p in [('C13', R/'untraced_wait_study/untracedwait_20261105_061041_b80fac/RESULTS.json'),
                ('C10', R/'wait_confirmation_study/waitconfirm_20261105_051433_3df228/RESULTS.json')]:
    rows = json.loads(p.read_text(encoding='utf-8-sig'))
    d, start, cov = [], [], []
    for r in rows:
        pr = r.get('private', {})
        a = pr.get('archive') or {}
        if a.get('fsync_end_ns'):
            d.append((a['fsync_end_ns'] - a['begin_ns']) / 1e9)
            start.append((a['begin_ns'] - pr['begin_ns']) / 1e9)
        c = pr.get('cover') or {}
        if c.get('end_ns'):
            cov.append((c['end_ns'] - c['begin_ns']) / 1e9)
    print(name, 'n_rows', len(rows), 'gzip n', len(d), 'dur s min/med/max', round(min(d), 3), round(statistics.median(d), 3), round(max(d), 3),
          'start offset med', round(statistics.median(start), 4), 'cover n', len(cov), 'cover dur med', round(statistics.median(cov), 3) if cov else None)
    print(' keys', sorted(rows[0].keys())[:40])
