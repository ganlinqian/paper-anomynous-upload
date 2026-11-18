"""EXPLORATORY (written after seeing the pre-registered result): alternative power features on C36 batch 4, same
thresholding rule (max over the 8 calibration silent calls) and same runs. Not a pre-registered endpoint.
  abs_win   : mean power over the call window (absolute level; session calibration via the threshold)
  peak500   : max 500 ms moving mean inside the call window
  win_minus_idle : call-window mean minus mean over [-4 s, -2.5 s] before dispatch (outside the pre-dispatch plateau)"""
import csv, json, pathlib, sys
import numpy as np
sys.stdout.reconfigure(encoding='utf-8')
H = pathlib.Path(__file__).resolve().parent
ROOT = H.parents[1]
OUT = ROOT / 'outputs/power_c36'
OUT.mkdir(parents=True, exist_ok=True)
src = (H / 'c36d_power_baseline.py').read_text(encoding='utf-8')
head = src.split('\nrecs = json.loads')[0]
ns = {'__file__': str(H / 'c36d_power_baseline.py')}; exec(compile(head, 'pb_head', 'exec'), ns)
t, pw, conv, CAMP, auc, cp = ns['t'], ns['pw'], ns['mono_to_csv_ms'], ns['CAMP'], ns['auc'], ns['cp']
recs = json.loads((CAMP / 'RESULTS.json').read_text(encoding='utf-8'))


def seg(a, b): return pw[np.searchsorted(t, a):np.searchsorted(t, b)]


rows = []
for r in recs:
    s, e = conv(r['private']['http_sent_ns']), conv(r['private']['http_received_ns']); w = seg(s, e)
    rows.append(dict(id=r['id'], condition=r['condition'], cal=r['condition'].endswith('_cal'), active=bool(r['actual_active']),
                     abs_win=float(w.mean()), peak500=float(np.convolve(w, np.ones(100) / 100, 'valid').max()),
                     win_minus_idle=float(w.mean() - seg(s - 4000, s - 2500).mean())))
em = {r['id']: r['alert'] == 'True' for r in csv.DictReader(open(CAMP / 'predictions_c35.csv', encoding='utf-8'))
      if r['detector'] == 'C35/self_roll4_p70'}
out = {}
for f in ('abs_win', 'peak500', 'win_minus_idle'):
    thr = max(x[f] for x in rows if x['cal']); test = [x for x in rows if not x['cal']]
    hid = [x for x in test if x['active']]; neg = [x for x in test if not x['active']]
    kh, kn = sum(x[f] > thr for x in hid), sum(x[f] > thr for x in neg)
    conds = sorted({x['condition'] for x in hid})
    out[f] = {'threshold': thr, 'hidden': [kh, len(hid)], 'negFA': [kn, len(neg)], 'negFA_CI95': cp(kn, len(neg)),
              'AUC': auc([x[f] for x in hid], [x[f] for x in neg]),
              'by_condition_det': {c: sum(x[f] > thr for x in hid if x['condition'] == c) for c in conds},
              'by_condition_AUC': {c: auc([x[f] for x in hid if x['condition'] == c], [x[f] for x in neg]) for c in conds},
              'vs_EM_primary_hidden_power_only/EM_only': [sum(x[f] > thr and not em[x['id']] for x in hid),
                                                         sum(em[x['id']] and not x[f] > thr for x in hid)]}
    print(f, json.dumps(out[f]))
(OUT / 'c36d_power_explore.json').write_text(json.dumps({'label': 'EXPLORATORY, post hoc', **out}, indent=1), encoding='utf-8')
