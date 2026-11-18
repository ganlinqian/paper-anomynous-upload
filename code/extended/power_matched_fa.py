"""Post-hoc (reviewer P1 'fair baseline'): C36 batch 4, inline 200 SPS power vs contactless EM on the SAME 87 test runs.
Reports (a) AUC, (b) detections at matched false-alarm budgets (0/39 and 1/39; oracle threshold on test negatives, so
this is a separability comparison, not a deployable operating point), (c) a power analogue of EM rolling
self-referencing (feature minus mean of the 4 most recent non-work calls) with the calibration-max threshold rule.
Reuses the alignment code of ws_power/results/power_c36/c36d_power_baseline.py (read-only)."""
import csv, json, pathlib, sys
import numpy as np
sys.stdout.reconfigure(encoding='utf-8')
ROOT = pathlib.Path(__file__).resolve().parents[2]
PB = ROOT / 'code/power_c36/c36d_power_baseline.py'
OUT = ROOT / 'outputs/power_c36'
OUT.mkdir(parents=True, exist_ok=True)
src = PB.read_text(encoding='utf-8')
head = src.split('\nrecs = json.loads')[0]
ns = {'__file__': str(PB)}
exec(compile(head, 'pb_head', 'exec'), ns)
t, pw, conv, CAMP, auc = ns['t'], ns['pw'], ns['mono_to_csv_ms'], ns['CAMP'], ns['auc']
recs = json.loads((CAMP / 'RESULTS.json').read_text(encoding='utf-8'))


def seg(a, b):
    return pw[np.searchsorted(t, a):np.searchsorted(t, b)]


rows = []
for r in recs:
    s, e = conv(r['private']['http_sent_ns']), conv(r['private']['http_received_ns'])
    w = seg(s, e)
    rows.append(dict(id=r['id'], condition=r['condition'], cal=r['condition'].endswith('_cal'),
                     active=bool(r['actual_active']), abs_win=float(w.mean()),
                     peak500=float(np.convolve(w, np.ones(100) / 100, 'valid').max()),
                     win_minus_idle=float(w.mean() - seg(s - 4000, s - 2500).mean())))
# power rolling self-reference (analogue of EM self_roll4): subtract mean of the 4 most recent non-work calls
for f in ('abs_win', 'peak500'):
    hist = []
    for x in rows:  # RESULTS.json is in collection order
        x[f + '_roll4'] = x[f] - float(np.mean(hist[-4:])) if hist else float('nan')
        if not x['active']:
            hist.append(x[f])


def em_scores(fname, det):
    return {r['id']: float(r['score']) for r in csv.DictReader(open(CAMP / fname, encoding='utf-8')) if r['detector'] == det}


em = {'EM C31 ensemble': em_scores('predictions_c31.csv', 'C31/avg_whole_temporal'),
      'EM C35 self_roll4': em_scores('predictions_c35.csv', 'C35/self_roll4_p70')}
for name, sc in em.items():
    for x in rows:
        x[name] = sc.get(x['id'], float('nan'))

test = [x for x in rows if not x['cal']]
cal = [x for x in rows if x['cal']]
hid = [x for x in test if x['active']]
neg = [x for x in test if not x['active']]


def det_at_fa(f, k):
    """detections when the threshold admits at most k false alarms among test negatives (oracle, post hoc)"""
    nv = sorted((x[f] for x in neg), reverse=True)
    thr = nv[k]  # alert iff score > thr  -> exactly <= k negatives above
    return sum(x[f] > thr for x in hid)


out = {'label': 'POST HOC separability comparison on C36 batch 4; oracle matched-FA thresholds',
       'n_hidden': len(hid), 'n_neg': len(neg), 'n_cal': len(cal), 'features': {}}
feats = ['abs_win', 'peak500', 'win_minus_idle', 'abs_win_roll4', 'peak500_roll4', 'EM C31 ensemble', 'EM C35 self_roll4']
for f in feats:
    d = {'AUC': round(auc([x[f] for x in hid], [x[f] for x in neg]), 3),
         'det_at_FA0': det_at_fa(f, 0), 'det_at_FA1': det_at_fa(f, 1)}
    if f in ('abs_win_roll4', 'peak500_roll4'):
        thr = float(np.nanmax([x[f] for x in cal]))
        d['calmax_rule'] = {'hidden': sum(x[f] > thr for x in hid), 'negFA': sum(x[f] > thr for x in neg)}
    out['features'][f] = d
    print(f, d)
(OUT / 'power_matched_fa.json').write_text(json.dumps(out, indent=1), encoding='utf-8')
