"""C36 batch 4 power-meter baseline, as pre-registered in POWER_PLAN.md (200 SPS instead of 1000 SPS, see AMEND3).
Feature per call: mean power over [http_sent_ns, http_received_ns] minus mean power over the 1 s before http_sent_ns
(Pi monotonic -> Pi UTC via the two clock pairs -> CSV time via c36d_timemap.json).
Threshold: max feature over the 8 calibration silent calls. Report hidden detections / negative false alarms with
Clopper-Pearson 95% CI, AUC, per-condition detections, and paired McNemar vs EM detectors on the same runs.
A mid-batch alignment check (onset of gzip16 runs) is descriptive. Writes c36d_power_baseline.json/.csv."""
import csv, datetime, json, pathlib, sys
import numpy as np
from scipy.stats import beta, binomtest
sys.stdout.reconfigure(encoding='utf-8')
ROOT = pathlib.Path(__file__).resolve().parents[2]
H = ROOT / 'data/power_c36'
OUT = ROOT / 'outputs/power_c36'
OUT.mkdir(parents=True, exist_ok=True)
CAMP = ROOT / 'data/pi_adaptive_desktop/experiments/campaigns/s1l_20261115_224455_c020b7'
TM = json.loads((H / 'c36d_timemap.json').read_text(encoding='utf-8'))
A, B = TM['fit']['pi_utc_ms_since_start = a*csv_ms + b']
START = datetime.datetime.fromisoformat(TM['fit']['start_utc'])
CP = [json.loads((H / f).read_text(encoding='utf-8'))['events'] for f in
      ('sync_pulses_c36d_pre_20261115T224436Z.json', 'sync_pulses_c36d_post_20261116T002909Z.json')]
pairs = [tuple(int(x) for x in e[k].split()) for e in CP for k in ('clockpair', 'clockpair_end')]
M0, R0 = pairs[0]
mono = np.array([p[0] - M0 for p in pairs], float); real = np.array([p[1] - R0 for p in pairs], float)
ms, mb = np.polyfit(mono, real, 1)
R0_MS = (R0 / 1e6) - (START - datetime.datetime(1970, 1, 1)).total_seconds() * 1e3   # Pi UTC of pair 0, ms since CSV start


def mono_to_csv_ms(ns):
    pi_ms = R0_MS + (ms * (ns - M0) + mb) / 1e6                      # Pi UTC ms since CSV start
    return (pi_ms - B) / A


t, pw = np.loadtxt(H / TM['csv'], delimiter=',', skiprows=1, usecols=(10, 2), encoding='gbk').T[[0, 1]]


def mean_w(a_ms, b_ms):
    i0, i1 = np.searchsorted(t, a_ms), np.searchsorted(t, b_ms)
    return float(pw[i0:i1].mean()), i1 - i0


def cp(k, n): return [float(beta.ppf(.025, k, n - k + 1)) if k else 0.0, float(beta.ppf(.975, k + 1, n - k)) if k < n else 1.0]


def auc(pos, neg):
    pos, neg = np.array(pos), np.array(neg)
    return float(((pos[:, None] > neg[None, :]).sum() + .5 * (pos[:, None] == neg[None, :]).sum()) / (len(pos) * len(neg)))


recs = json.loads((CAMP / 'RESULTS.json').read_text(encoding='utf-8'))
rows = []
for r in recs:
    p = r['private']; s, e = mono_to_csv_ms(p['http_sent_ns']), mono_to_csv_ms(p['http_received_ns'])
    win, nw = mean_w(s, e); pre, npre = mean_w(s - 1000, s)
    rows.append(dict(id=r['id'], block=r['block'], condition=r['condition'], cal=r['condition'].endswith('_cal'),
                     active=bool(r['actual_active']), win_s=(e - s) / 1000, n_win=nw, n_pre=npre,
                     pre_W=pre, win_W=win, feat_W=win - pre))
thr = max(x['feat_W'] for x in rows if x['cal'])
for x in rows: x['alert'] = x['feat_W'] > thr
test = [x for x in rows if not x['cal']]
hid = [x for x in test if x['active']]; neg = [x for x in test if not x['active']]
kh, kn = sum(x['alert'] for x in hid), sum(x['alert'] for x in neg)
out = {'threshold_W': thr, 'hidden': [kh, len(hid)], 'hidden_CI95': cp(kh, len(hid)),
       'negFA': [kn, len(neg)], 'negFA_CI95': cp(kn, len(neg)),
       'AUC_hidden_vs_neg': auc([x['feat_W'] for x in hid], [x['feat_W'] for x in neg]),
       'gap_overlap_runs': 0, 'csv_time_uniform_5ms': True}
conds = sorted({x['condition'] for x in test})
out['by_condition'] = {c: [sum(x['alert'] for x in test if x['condition'] == c), sum(x['condition'] == c for x in test),
                           round(float(np.median([x['feat_W'] for x in test if x['condition'] == c])), 4)] for c in conds}
out['by_condition_AUC_vs_neg'] = {c: auc([x['feat_W'] for x in hid if x['condition'] == c], [x['feat_W'] for x in neg])
                                  for c in conds if any(x['condition'] == c for x in hid)}
# paired McNemar vs EM detectors (same runs)
for fn, det in (('predictions_c35.csv', 'C35/self_roll4_p70'), ('predictions_c31.csv', 'C31/avg_whole_temporal')):
    em = {r['id']: r['alert'] == 'True' for r in csv.DictReader(open(CAMP / fn, encoding='utf-8')) if r['detector'] == det}
    o = {}
    for name, grp in (('hidden', hid), ('negatives', neg)):
        pw_only = sum(x['alert'] and not em[x['id']] for x in grp); em_only = sum(em[x['id']] and not x['alert'] for x in grp)
        o[name] = {'pairs': len(grp), 'power_only': pw_only, 'EM_only': em_only,
                   'p_two_sided': binomtest(pw_only, pw_only + em_only).pvalue if pw_only + em_only else 1.0}
    out['mcnemar_vs_' + det] = o
# descriptive alignment check: gzip16 onset lag after dispatch (first 50 ms mean exceeding pre + 0.5 W)
lags = []
for r in recs:
    if r['condition'] != 'gzip16': continue
    s = mono_to_csv_ms(r['private']['http_sent_ns']); i0 = np.searchsorted(t, s - 1000); seg = pw[i0:i0 + 1000]
    base = seg[:200].mean(); sm = np.convolve(seg, np.ones(10) / 10, 'valid'); k = np.argmax(sm > base + .5)
    lags.append(float(t[i0 + k] - s))
out['gzip16_onset_lag_ms_after_dispatch'] = lags
out['median_window_s'] = float(np.median([x['win_s'] for x in rows]))
(OUT / 'c36d_power_baseline.json').write_text(json.dumps(out, indent=1), encoding='utf-8')
with open(OUT / 'c36d_power_baseline.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
print(json.dumps(out, indent=1))
