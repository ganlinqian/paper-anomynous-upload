"""C32 (stage s1g) pre-specified analyses, fixed before any C32 run (2026-11-10).

False-alarm control: prospective test of the C32 model (C31 ensemble with negative weight x2) in a new session with
32 test silents (4 per block) and the six C27 hidden cells (48 runs).  Calibration calls never count.
  primary    C32/avg_whole_temporal: false alarms on the 32 test silents (exact 95% CI) and hidden alerts (48 runs)
  secondary  (1) paired block sign-flip tests on the same 80 test runs and on the 32 silents alone:
                 C32 vs C31/avg_whole_temporal (frozen C31 ensemble), vs C29/call_whole_sesscal
             (2) exact one-sided McNemar on the 32 silents, C32 vs C31 (false alarms only C31 vs only C32)
             (3) every frozen branch per cell (descriptive)
"""
import csv, json, sys, pathlib
from scipy.stats import binom
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import c28_stats as S  # noqa: E402
from c30_stats import summary, HIDDEN  # noqa: E402
PRIMARY = 'C32/avg_whole_temporal'; C31P = 'C31/avg_whole_temporal'
OTHERS = [C31P, 'C29/call_whole_sesscal']

def load(d):
    rows = []
    for name in ('predictions.csv', 'predictions_diverse.csv', 'predictions_c29.csv', 'predictions_c30.csv', 'predictions_c31.csv', 'predictions_c32.csv'):
        p = d / name
        if p.exists():
            with p.open(encoding='utf-8') as f:
                rows += list(csv.DictReader(f))
    out = []
    for r in rows:
        if r['condition'] == 'silent_cal':
            continue
        r['alert'] = r['alert'] == 'True'; r['actual_active'] = r['actual_active'] == 'True'
        out.append(r)
    return out

def main(stage='s1g', out_name='c32_stats.json'):
    d = S.campaign(stage); rows = load(d); dets = sorted({r['detector'] for r in rows})
    out = {'campaign': d.name, 'primary': PRIMARY, 'primary_summary': summary(rows, PRIMARY),
           'primary_by_condition': {c: S.cell(rows, PRIMARY, c) for c in HIDDEN + ['silent']}}
    bt = {}
    for other in OTHERS:
        if other not in dets:
            continue
        a, ka, na = S.block_acc(rows, PRIMARY); b, kb, nb = S.block_acc(rows, other)
        asl, kas, nas = S.block_acc(rows, PRIMARY, {'silent'}); bsl, kbs, nbs = S.block_acc(rows, other, {'silent'})
        bt[PRIMARY + ' vs ' + other] = {'all': {'a_correct': [ka, na], 'b_correct': [kb, nb], 'test': S.signflip(a, b)},
                                        'silent_only': {'a_correct': [kas, nas], 'b_correct': [kbs, nbs], 'test': S.signflip(asl, bsl)}}
    out['block_tests'] = bt
    sp = {r['id']: r['alert'] for r in rows if r['detector'] == PRIMARY and r['condition'] == 'silent'}
    so = {r['id']: r['alert'] for r in rows if r['detector'] == C31P and r['condition'] == 'silent'}
    only31 = sum(so[k] and not sp[k] for k in sp); only32 = sum(sp[k] and not so[k] for k in sp)
    out['mcnemar_silent_vs_c31'] = {'fa_only_c31': only31, 'fa_only_c32': only32,
                                   'p_one_sided': float(binom.sf(only31 - 1, only31 + only32, .5)) if only31 + only32 else 1.0}
    out['all_detectors'] = {det: summary(rows, det) for det in dets}
    S.OUT.mkdir(parents=True, exist_ok=True); (S.OUT / out_name).write_text(json.dumps(out, indent=1), encoding='utf-8')
    for det in [PRIMARY, 'C32/whole_C0.1', 'C32/temporal_C0.1'] + OTHERS + ['C30/call_whole_sesscal', 'C27_diverse/call_temporal']:
        if det in dets:
            s = out['all_detectors'][det]
            print('  %-28s hidden %d/%d  FA %d/%d (CI %s)  correct %d/%d  %s' % (det, *s['hidden_alerts'], *s['silent_false_alarms'], s['silent_fa_cp95'], *s['correct'], json.dumps(s['by_condition'])))
    for k, v in bt.items():
        print('  block test', k, json.dumps(v['all']['test']), 'silent', json.dumps(v['silent_only']['test']))
    print('  mcnemar silents vs C31', json.dumps(out['mcnemar_silent_vs_c31']))
    return out

if __name__ == '__main__':
    main(*(sys.argv[1:3]))
