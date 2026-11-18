"""C34 (stage s1j) pre-specified analyses, fixed before any C34 run (2026-11-11 UTC; session ws_followup).

Time-separated hold-out of the frozen detectors.  User approval 2026-11-11: collect now, no Pi reboot, no probe
re-placement (nobody on site).  C34 starts ~4 h after C33 ended (20:57 UTC 11-10) and ~8-9 h after the last session in
any frozen training set (C31 session, ended 16:52 UTC 11-10).  It is therefore a SAME-BOOT, SAME-PLACEMENT, ~8 h
time-separated hold-out, NOT the cross-day (reboot + re-placement) test; it must be reported as such.
No model is trained or changed for C34.  Primary detector = C31 ensemble (C31/avg_whole_temporal, frozen 15:57 UTC 11-10).

Cells (8 blocks, shuffled per block; 8 calibration silents first, never counted):
  negatives  silent x4 per block (32), bg_log x1 (8; contract-permitted log writes during the wait)
  hidden     seen in training: gzip16, gzip3_d19 (16);  unseen tools: zstd16, xz2, ossl16, sha32 (32)
Primary endpoints (C31 ensemble, per-session calibration with all 8 calibration silents, alert if mean P > 0.5):
  P1 false alarms on the 40 negatives; criterion met if <= 3/40 (exact 95% CI reported)
  P2 alerts on the 48 hidden runs;     criterion met if >= 45/48
Secondary (descriptive unless stated):
  S1 per-cell table and the same endpoints for every other frozen branch (C32, C29, C30, C27, ...)
  S2 exact McNemar (two-sided binomial on discordant pairs) C32 vs C31 on the 40 negatives and on the 48 hidden
  S3 calibration budget k=4: C31 ensemble re-calibrated with the FIRST four calibration silents (collection order),
     and the mean over all 70 four-subsets; same endpoints
  S4 two-sided Fisher test: C31 ensemble silent false alarms in C34 vs the pooled same-day prospective sessions
     C31 (s1f) + C32 (s1g)
Calibration calls never count.  Nothing is changed after C34 data exist.
"""
import csv, itertools, json, pathlib, sys
import numpy as np
from scipy.stats import binomtest, fisher_exact
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / 'experiments'))
import c28_stats as S  # noqa: E402
PRIMARY = 'C31/avg_whole_temporal'
SEEN = ['gzip16', 'gzip3_d19']; UNSEEN = ['zstd16', 'xz2', 'ossl16', 'sha32']; HIDDEN = SEEN + UNSEEN; NEG = ['silent', 'bg_log']
PRED = ('predictions.csv', 'predictions_diverse.csv', 'predictions_c29.csv', 'predictions_c30.csv', 'predictions_c31.csv', 'predictions_c32.csv')

def load(d):
    rows = []
    for name in PRED:
        p = d / name
        if p.exists():
            with p.open(encoding='utf-8') as f:
                rows += list(csv.DictReader(f))
    out = []
    for r in rows:
        if r['condition'] == 'silent_cal':
            continue
        r['alert'] = r['alert'] == 'True'; r['actual_active'] = r['actual_active'] == 'True'; out.append(r)
    return out

def count(rows, det, conds):
    v = [r for r in rows if r['detector'] == det and r['condition'] in conds]
    return [sum(r['alert'] for r in v), len(v)]

def table(rows, det):
    by = {c: count(rows, det, [c]) for c in HIDDEN + NEG}
    fa = count(rows, det, NEG); hd = count(rows, det, HIDDEN)
    return {'by_condition': by, 'negatives_fa': fa + [S.cp(*fa)] if fa[1] else fa, 'silent_fa': count(rows, det, ['silent']),
            'bg_log_fa': count(rows, det, ['bg_log']), 'hidden': hd + [S.cp(*hd)] if hd[1] else hd,
            'hidden_seen': count(rows, det, SEEN), 'hidden_unseen': count(rows, det, UNSEEN),
            'P1_met': bool(fa[1] and fa[0] <= 3), 'P2_met': bool(hd[1] and hd[0] >= 45)}

def mcnemar(rows, a, b, conds):
    ra = {r['id']: r['alert'] for r in rows if r['detector'] == a and r['condition'] in conds}
    rb = {r['id']: r['alert'] for r in rows if r['detector'] == b and r['condition'] in conds}
    ids = sorted(set(ra) & set(rb)); n01 = sum(ra[i] and not rb[i] for i in ids); n10 = sum(rb[i] and not ra[i] for i in ids)
    p = 1.0 if n01 + n10 == 0 else float(binomtest(n01, n01 + n10, .5).pvalue)
    return {'pairs': len(ids), a + '_only': n01, b + '_only': n10, 'p_two_sided': p}

def apply8(feats, mj, cal, ps):
    q = np.mean([ps.predict(feats[p] - feats[p][cal].mean(0), m)[1] for p, m in mj['models'].items()], axis=0)
    return q > .5

def budget_k4(d):
    import process_sp2027 as ps
    mj = json.loads(ps.ENSEMBLE.read_text(encoding='utf-8')); rows = ps.rows_of(d)
    cond = np.array([x['condition'] for x in rows]); calidx = np.where(cond == 'silent_cal')[0]; assert len(calidx) == 8
    test = cond != 'silent_cal'; neg = np.isin(cond, NEG); hid = np.isin(cond, HIDDEN)
    feats = {part: ps.c29_X(d, rows, m['temporal']) for part, m in mj['models'].items()}   # same as ps.c31_apply, computed once
    ref = np.zeros(len(rows), bool); ref[calidx] = True
    assert np.array_equal(ps.c31_apply(d, rows, ref, mj)[ps.C31_PRIMARY][0], apply8(feats, mj, ref, ps))

    def ep(idx):
        cal = np.zeros(len(rows), bool); cal[list(idx)] = True
        a = apply8(feats, mj, cal, ps)
        return [int(a[test & neg].sum()), int((test & neg).sum()), int(a[test & hid].sum()), int((test & hid).sum())]
    first4 = ep(calidx[:4]); allk = np.array([ep(s) for s in itertools.combinations(calidx, 4)], float)
    return {'first_four': {'negatives_fa': first4[:2], 'hidden': first4[2:]}, 'mean_over_70_subsets': {
            'negatives_fa': [float(allk[:, 0].mean()), int(allk[0, 1])], 'hidden': [float(allk[:, 2].mean()), int(allk[0, 3])],
            'negatives_fa_range': [int(allk[:, 0].min()), int(allk[:, 0].max())]}, 'all_eight': ep(calidx)}

def main(stage='s1j', out_name='c34_stats.json', with_budget='1'):
    d = S.campaign(stage); rows = load(d); dets = sorted({r['detector'] for r in rows})
    out = {'campaign': d.name, 'primary': PRIMARY, 'label': 'same-boot same-placement ~8 h time-separated hold-out (not cross-day)',
           'detectors': {det: table(rows, det) for det in dets}}
    if 'C32/avg_whole_temporal' in dets:
        out['S2_mcnemar_C32_vs_C31'] = {'negatives': mcnemar(rows, 'C32/avg_whole_temporal', PRIMARY, NEG),
                                        'hidden': mcnemar(rows, 'C32/avg_whole_temporal', PRIMARY, HIDDEN)}
    if with_budget == '1':
        out['S3_budget_k4'] = budget_k4(d)
    same = [r for st in ('s1f', 's1g') for r in load(S.campaign(st)) if r['detector'] == PRIMARY and r['condition'] == 'silent']
    ks, ns = sum(r['alert'] for r in same), len(same); kc, nc = count(rows, PRIMARY, ['silent'])
    out['S4_fisher_silent_vs_same_day'] = {'c34': [kc, nc], 'same_day_s1f_s1g': [ks, ns],
                                           'p_two_sided': float(fisher_exact([[kc, nc - kc], [ks, ns - ks]])[1]) if nc else None}
    S.OUT.mkdir(parents=True, exist_ok=True); (S.OUT / out_name).write_text(json.dumps(out, indent=1), encoding='utf-8')
    for det in [PRIMARY, 'C32/avg_whole_temporal', 'C29/call_whole_sesscal', 'C30/call_whole_sesscal', 'C27_diverse/call_temporal']:
        if det in dets:
            t = out['detectors'][det]
            print('  %-26s hidden %s seen %s unseen %s | negFA %s silent %s log %s | P1 %s P2 %s' % (det, t['hidden'][:2], t['hidden_seen'], t['hidden_unseen'],
                  t['negatives_fa'][:2], t['silent_fa'], t['bg_log_fa'], t['P1_met'], t['P2_met']))
    for k in ('S2_mcnemar_C32_vs_C31', 'S3_budget_k4', 'S4_fisher_silent_vs_same_day'):
        if k in out:
            print(k, json.dumps(out[k]))
    return out

if __name__ == '__main__':
    main(*(sys.argv[1:4]))
