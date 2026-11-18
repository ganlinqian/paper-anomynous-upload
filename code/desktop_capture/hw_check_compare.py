"""hw_check.json  vs iPhone 10-26 b01  std : python hw_check_compare.py <hw_check.json>"""
import glob, json, sys
import numpy as np

B01 = r'<CALIBRATION_ROOT>\raw\b01_r0*_idle\manifest.json'
r = json.load(open(sys.argv[1], encoding='utf-8'))
ref = {}
for p in glob.glob(B01):
    for b in json.load(open(p, encoding='utf-8'))['bands']:
        ref.setdefault(b['start_mhz'], []).append(np.hypot(b['std_i_lsb'], b['std_q_lsb']))
rows = []
for x in r['sweep']:
    s = float(np.hypot(x['std_i_lsb'], x['std_q_lsb'])); m = float(np.median(ref[x['start_mhz']]))
    rows.append(dict(start_mhz=x['start_mhz'], std_now=s, std_b01=m, db=20 * np.log10(s / m),
                     b01_spread_db=float(np.ptp(20 * np.log10(np.array(ref[x['start_mhz']]) / m)))))
d = np.array([x['db'] for x in rows])
summ = dict(n=len(d), median_db=float(np.median(d)), p10_p90=[float(v) for v in np.percentile(d, [10, 90])],
            min_db=float(d.min()), max_db=float(d.max()), within_3db=int((abs(d) < 3).sum()), below_minus6=int((d < -6).sum()),
            low_bands=[x['start_mhz'] for x in rows if x['db'] < -6], high_bands=[x['start_mhz'] for x in rows if x['db'] > 6])
r['summary']['sweep_std_vs_b01'] = summ; r['sweep_std_vs_b01_rows'] = rows
json.dump(r, open(sys.argv[1], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(json.dumps(summ, ensure_ascii=False))
for x in rows[::8]:
    print(x['start_mhz'], round(x['std_now'], 2), round(x['std_b01'], 2), round(x['db'], 1))
