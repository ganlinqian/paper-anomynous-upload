"""C35 (stage s1k) pre-specified analyses, fixed before any C35 run (2026-11-11 UTC; session ws_followup).

Prospective test of the C35 false-alarm control.  User approval 2026-11-11 ("").
Selected by the EXPLORATORY forward-chaining search scripts/explore_c35_fa.py over C24..C34 (rule fixed in its docstring
before it ran; stats/explore_c35_fa.json), frozen 2026-11-11T15:25:33Z as models/C35_SELFROLL_MODELS.json (SHA d3fd4760...,
664 runs of nine sessions, C34 included).  C35 runs the C34 cells with a new seed in the same boot and probe placement,
~13-14 h after C34 (a training session) and at a different time of day; it is NOT the reboot + re-placement cross-day test.

Cells (8 blocks, shuffled per block; 8 calibration silents first, never counted):
  negatives  silent x4 per block (32), bg_log x1 (8; contract-permitted log writes; never part of the reference pool)
  hidden     gzip16, gzip3_d19, zstd16, xz2, ossl16, sha32 (48; all six cells occur in the C35 training set via C34)
Primary detector: C35/self_roll4_p70 = features minus the run's own pre-dispatch reference, minus the mean of the last 4
earlier reference runs (calibration silents and silents = verifier-issued no-work calls), mean P of whole and
phase-resolved logistic models > 0.7.
Primary endpoints:
  P1 false alarms on the 40 negatives; met if <= 3/40 (exact 95% CI)
  P2 alerts on the 48 hidden runs;     met if >= 44/48 (the exploration accepted up to ~5% detection loss)
  CONFIRMED improvement over the deployed C31 ensemble only if P1 and P2 are met AND the exact one-sided McNemar test
  on the 40 negatives (C35 fewer alarms than C31/avg_whole_temporal) gives p < 0.05.
Secondary (descriptive):
  S1 the same table for every frozen branch (C31, C32, C29, C30, C27 ...)
  S2 exact McNemar C35 primary vs C31 on negatives (one- and two-sided) and on hidden (two-sided); same vs C32
  S3 decomposition with the frozen variants in the same model file: self_roll4_p50 (threshold), sess_p70 and sess_p50
     (session-mean reference, C31 pipeline refit on the same nine sessions); McNemar sess_p70 vs primary on negatives
  S4 false alarms in blocks 0-3 vs 4-7 for the primary and C31
  S5 bg_log (never used as reference) reported separately from silent
Calibration calls never count.  Nothing is changed after C35 data exist.
"""
import csv, json, pathlib, sys
from scipy.stats import binomtest
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / 'experiments'))
import c28_stats as S  # noqa: E402
PRIMARY = 'C35/self_roll4_p70'; C31 = 'C31/avg_whole_temporal'; C32 = 'C32/avg_whole_temporal'
HIDDEN = ['gzip16', 'gzip3_d19', 'zstd16', 'xz2', 'ossl16', 'sha32']; NEG = ['silent', 'bg_log']
PRED = ('predictions.csv', 'predictions_diverse.csv', 'predictions_c29.csv', 'predictions_c30.csv', 'predictions_c31.csv', 'predictions_c32.csv', 'predictions_c35.csv')


def load(d):
    rows = []
    for name in PRED:
        p = d / name
        if p.exists():
            with p.open(encoding='utf-8') as f:
                rows += list(csv.DictReader(f))
    out = []
    for r in rows:
        if r['condition'] in ('silent_cal', 'bg_download'):
            continue
        r['alert'] = r['alert'] == 'True'; r['actual_active'] = r['actual_active'] == 'True'; r['block'] = int(r['block']); out.append(r)
    return out


def count(rows, det, conds, blocks=None):
    v = [r for r in rows if r['detector'] == det and r['condition'] in conds and (blocks is None or r['block'] in blocks)]
    return [sum(r['alert'] for r in v), len(v)]


def table(rows, det):
    by = {c: count(rows, det, [c]) for c in HIDDEN + NEG}
    fa = count(rows, det, NEG); hd = count(rows, det, HIDDEN)
    return {'by_condition': by, 'negatives_fa': fa + [S.cp(*fa)] if fa[1] else fa, 'silent_fa': count(rows, det, ['silent']),
            'bg_log_fa': count(rows, det, ['bg_log']), 'hidden': hd + [S.cp(*hd)] if hd[1] else hd,
            'P1_met': bool(fa[1] and fa[0] <= 3), 'P2_met': bool(hd[1] and hd[0] >= 44),
            'negatives_fa_blocks_0_3': count(rows, det, NEG, range(0, 4)), 'negatives_fa_blocks_4_7': count(rows, det, NEG, range(4, 8))}


def mcnemar(rows, a, b, conds):
    ra = {r['id']: r['alert'] for r in rows if r['detector'] == a and r['condition'] in conds}
    rb = {r['id']: r['alert'] for r in rows if r['detector'] == b and r['condition'] in conds}
    ids = sorted(set(ra) & set(rb)); na = sum(ra[i] and not rb[i] for i in ids); nb = sum(rb[i] and not ra[i] for i in ids)
    two = 1.0 if na + nb == 0 else float(binomtest(na, na + nb, .5).pvalue)
    less = 1.0 if na + nb == 0 else float(binomtest(na, na + nb, .5, alternative='less').pvalue)   # H1: a alerts less than b
    return {'pairs': len(ids), a + '_only': na, b + '_only': nb, 'p_two_sided': two, 'p_one_sided_a_fewer': less}


def main(stage='s1k', out_name='c35_stats.json', campaign_dir=''):
    d = pathlib.Path(campaign_dir) if campaign_dir else S.campaign(stage); rows = load(d); dets = sorted({r['detector'] for r in rows})
    out = {'campaign': d.name, 'primary': PRIMARY, 'label': 'same-boot same-placement ~13-14 h after C34 (not reboot cross-day)',
           'detectors': {det: table(rows, det) for det in dets}}
    if PRIMARY in dets and C31 in dets:
        mn = mcnemar(rows, PRIMARY, C31, NEG)
        out['S2_mcnemar_vs_C31'] = {'negatives': mn, 'hidden': mcnemar(rows, PRIMARY, C31, HIDDEN)}
        t = out['detectors'][PRIMARY]
        out['confirmed_improvement_over_C31'] = bool(t['P1_met'] and t['P2_met'] and mn['p_one_sided_a_fewer'] < .05)
    if PRIMARY in dets and C32 in dets:
        out['S2_mcnemar_vs_C32'] = {'negatives': mcnemar(rows, PRIMARY, C32, NEG), 'hidden': mcnemar(rows, PRIMARY, C32, HIDDEN)}
    if PRIMARY in dets and 'C35/sess_p70' in dets:
        out['S3_mcnemar_sess_p70_vs_primary_negatives'] = mcnemar(rows, 'C35/sess_p70', PRIMARY, NEG)
    S.OUT.mkdir(parents=True, exist_ok=True); (S.OUT / out_name).write_text(json.dumps(out, indent=1), encoding='utf-8')
    for det in [PRIMARY, 'C35/self_roll4_p50', 'C35/sess_p70', 'C35/sess_p50', C31, C32, 'C29/call_whole_sesscal', 'C30/call_whole_sesscal', 'C27_diverse/call_temporal']:
        if det in dets:
            t = out['detectors'][det]
            print('  %-26s hidden %s | negFA %s silent %s log %s | blocks0-3 %s 4-7 %s | P1 %s P2 %s' % (det, t['hidden'][:2], t['negatives_fa'][:2], t['silent_fa'],
                  t['bg_log_fa'], t['negatives_fa_blocks_0_3'], t['negatives_fa_blocks_4_7'], t['P1_met'], t['P2_met']))
    for k in ('S2_mcnemar_vs_C31', 'S2_mcnemar_vs_C32', 'S3_mcnemar_sess_p70_vs_primary_negatives', 'confirmed_improvement_over_C31'):
        if k in out:
            print(k, json.dumps(out[k]))
    return out


if __name__ == '__main__':
    main(*(sys.argv[1:4]))
