"""Find sync-pulse triplets in the local 200 SPS C2 CSV and fit CSV time -> Pi realtime (UTC) from the pre and post
sync runs of batch 4. For each sync run: coarse search by 3-pulse template cross-correlation over +-120 s around the
nominal position, then per-edge refinement. Writes c36d_timemap.json."""
import datetime, json, pathlib, sys
import numpy as np
sys.stdout.reconfigure(encoding='utf-8')
H = pathlib.Path(__file__).parent
CSV = H / 'c2_2026-11-16_06-26-02.csv'
START = datetime.datetime(2026, 11, 15, 22, 26, 2, 558317)          # file CreationTimeUtc (CSV t = 0 nominal)
SYNC = {'pre': 'sync_pulses_c36d_pre_20261115T224436Z.json', 'post': 'sync_pulses_c36d_post_20261116T002909Z.json'}
STEP = 5.0                                                           # ms per CSV row (200 SPS)


def load():
    a = np.loadtxt(CSV, delimiter=',', skiprows=1, usecols=(2, 10), encoding='gbk')
    return a[:, 1], a[:, 0]


def utc(s): return datetime.datetime.fromisoformat(s[:26])


def main():
    t, pw = load()
    assert np.all(np.diff(t) == STEP), 'time column not uniform'
    res = {'csv': CSV.name, 'rows': len(t), 'csv_last_ms': float(t[-1])}
    anchors = []
    for tag, fn in SYNC.items():
        ev = json.loads((H / fn).read_text(encoding='utf-8'))['events']
        rel = {k: (utc(v) - START).total_seconds() * 1000 for k, v in ev.items() if not k.startswith('clock')}
        L0, L1 = rel['idle_start'], rel['gzip_start']
        n = int((L1 - L0) / STEP); tm = np.zeros(n)
        for i in (1, 2, 3):
            tm[int((rel['pulse%d_on' % i] - L0) / STEP):int((rel['pulse%d_off' % i] - L0) / STEP)] = 1
        tm -= tm.mean()
        i0 = int(L0 / STEP); best = None
        for off in range(-24000, 24001):                             # +-120 s in rows
            s = i0 + off
            if s < 0 or s + n > len(pw): continue
            seg = pw[s:s + n]; c = float(np.dot(seg - seg.mean(), tm))
            if best is None or c > best[1]: best = (off, c)
        off = best[0]
        # refine: rising edges of each pulse (threshold half-way idle/pulse on 2-row smoothing)
        edges = []
        for i in (1, 2, 3):
            k0 = int(rel['pulse%d_on' % i] / STEP) + off
            seg = pw[k0 - 100:k0 + 100]; idle = np.median(pw[k0 - 300:k0 - 120]); hi = np.median(pw[k0 + 40:k0 + 160])
            sm = np.convolve(seg, np.ones(2) / 2, 'same'); k = int(np.argmax(sm > (idle + hi) / 2))
            edges.append({'pulse': i, 'pi_utc_ms': rel['pulse%d_on' % i], 'csv_ms': float(t[k0 - 100 + k]),
                          'idle_W': float(idle), 'pulse_W': float(hi)})
        res[tag] = {'coarse_offset_rows': off, 'xcorr': best[1], 'edges': edges,
                    'gzip_W': float(pw[int(rel['gzip_start'] / STEP) + off + 20:int(rel['gzip_end'] / STEP) + off - 20].mean())}
        anchors += [(e['csv_ms'], e['pi_utc_ms']) for e in edges]
    x = np.array([a[0] for a in anchors]); y = np.array([a[1] for a in anchors])
    A = np.vstack([x, np.ones_like(x)]).T; (slope, icpt), *_ = np.linalg.lstsq(A, y, rcond=None)
    resid = y - (slope * x + icpt)
    res['fit'] = {'pi_utc_ms_since_start = a*csv_ms + b': [float(slope), float(icpt)],
                  'rate_dev_percent': float((slope - 1) * 100), 'resid_ms': resid.round(1).tolist(), 'start_utc': START.isoformat()}
    (H / 'c36d_timemap.json').write_text(json.dumps(res, indent=1), encoding='utf-8')
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
