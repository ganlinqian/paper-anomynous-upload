"""C37 power time-axis QA (written AFTER analyze_c37.py ran; QA only, no detector/threshold is changed).
Trigger: the six-edge linear fit gave rate deviation 2.36 % (> 1 % gate in C37_PREREG), i.e. the ATK-C file dropped
samples during the batch.  For every run with Pi-timed CPU work (archive gzip in the wait, or deferred gzip after the
reply) we cross-correlate the Pi-recorded work interval (boxcar, mapped with the frozen time map) against the power
trace and report the lag that maximises the correlation (search +-LAG s).  If the linear map were right, lags would be
~0 for all runs.  Output: power_align_qa.json / .md."""
import json, pathlib, sys
import numpy as np
sys.stdout.reconfigure(encoding='utf-8')
H = pathlib.Path(__file__).parent
sys.path.insert(0, str(H))
import analyze_c37 as A  # noqa: E402  (frozen file, imported read-only)

LAG = 8000.0      # ms
STEP = 5.0


def work_interval(x):
    p = x['private']
    if p.get('archive_inside_wait') and isinstance(p.get('archive'), dict) and p['archive'].get('begin_ns'):
        a = p['archive']; return 'archive', a['begin_ns'], a['process_end_ns']
    dfr = p.get('deferred')
    if isinstance(dfr, dict) and dfr.get('begin_ns'):
        return 'deferred', dfr['begin_ns'], dfr['end_ns']
    return None


def main():
    P = A.power_setup(); t, pw, f = P['t'], P['pw'], P['to_csv']
    out = []
    for stage in ('s1m', 's1n'):
        d = A.latest(stage); rows = json.loads((d / 'RESULTS.json').read_text(encoding='utf-8'))
        for x in rows:
            w = work_interval(x)
            if not w: continue
            kind, b, e = w; cb, ce = f(b), f(e)
            i0 = np.searchsorted(t, cb - LAG - 3000); i1 = np.searchsorted(t, ce + LAG + 3000)
            seg = pw[i0:i1]; tt = t[i0:i1]
            if len(seg) < 100: out.append({'stage': stage, 'id': x['id'], 'cond': x['condition'], 'err': 'no power rows'}); continue
            n = max(int(round((ce - cb) / STEP)), 1); tmpl = np.ones(n) - 0.0
            s = seg - np.median(seg)
            c = np.correlate(s, tmpl, 'valid')                     # c[k] = sum s[k:k+n]
            lags = tt[:len(c)] - cb
            ok = np.abs(lags) <= LAG
            k = int(np.argmax(np.where(ok, c, -np.inf)))
            k0 = int(np.argmin(np.abs(lags)))
            rise = float(np.mean(seg[k:k + n]) - np.median(seg))
            out.append({'stage': stage, 'id': x['id'], 'cond': x['condition'], 'kind': kind, 'dur_ms': round(ce - cb),
                        'csv_ms': round(cb), 'lag_ms': round(float(lags[k])), 'rise_W': round(rise, 3),
                        'corr_at_0_over_best': round(float(c[k0] / c[k]), 3) if c[k] > 0 else None})
    lag = np.array([o['lag_ms'] for o in out if 'lag_ms' in o])
    summ = {'n': len(lag), 'median_lag_ms': float(np.median(lag)), 'abs_lag_le_200ms': int((np.abs(lag) <= 200).sum()),
            'abs_lag_le_500ms': int((np.abs(lag) <= 500).sum()), 'min': float(lag.min()), 'max': float(lag.max())}
    (H / 'power_align_qa.json').write_text(json.dumps({'summary': summ, 'runs': out}, indent=1), encoding='utf-8')
    lines = ['| stage | cond | kind | csv_ms | lag_ms | rise_W | c0/cbest |', '|---|---|---|---|---|---|---|']
    lines += ['| %s | %s | %s | %s | %s | %s | %s |' % (o['stage'], o['cond'], o.get('kind'), o.get('csv_ms'), o.get('lag_ms'), o.get('rise_W'), o.get('corr_at_0_over_best')) for o in out]
    (H / 'power_align_qa.md').write_text('# C37 power alignment QA\n\n' + json.dumps(summ) + '\n\n' + '\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps(summ)); print('\n'.join(lines))


if __name__ == '__main__':
    main()
