"""C31 (stage s1f) pre-specified analyses, fixed before any C31 run (2026-11-10).

Prospective test of the C31 ensemble selected by the exploratory LOSO search (scripts/explore_c31_loso.py) on the
C27/C30 cells in a new session.  Calibration calls ('silent_cal') never count.
  primary    C31/avg_whole_temporal: hidden alerts over the 6 hidden cells (48 runs) and false alarms on the 16 test
             silents, exact 95% CIs
  secondary  (1) paired block sign-flip tests on the same 64 test runs: C31 primary vs C29 primary
                 (C29/call_whole_sesscal), vs C30/call_whole_sesscal, vs C27_diverse/call_temporal
             (2) the two C31 parts alone; every frozen branch per cell (descriptive)
Comparisons with the C30 session (41/48, 1/16) are descriptive only.
"""
import csv, json, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import c28_stats as S  # noqa: E402
from c30_stats import summary, HIDDEN  # noqa: E402
PRIMARY = 'C31/avg_whole_temporal'
OTHERS = ['C29/call_whole_sesscal', 'C30/call_whole_sesscal', 'C27_diverse/call_temporal']

def load(d):
    rows = []
    for name in ('predictions.csv', 'predictions_diverse.csv', 'predictions_c29.csv', 'predictions_c30.csv', 'predictions_c31.csv'):
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

def main(stage='s1f', out_name='c31_stats.json'):
    d = S.campaign(stage); rows = load(d); dets = sorted({r['detector'] for r in rows})
    out = {'campaign': d.name, 'primary': PRIMARY, 'primary_summary': summary(rows, PRIMARY) if PRIMARY in dets else None,
           'primary_by_condition': {c: S.cell(rows, PRIMARY, c) for c in HIDDEN + ['silent']} if PRIMARY in dets else None,
           'reference_c30_session': {'C29/call_whole_sesscal': {'hidden': [41, 48], 'fa': [1, 16]}, 'note': 'different session; descriptive only'}}
    bt = {}
    for other in OTHERS:
        if PRIMARY not in dets or other not in dets:
            continue
        a, ka, na = S.block_acc(rows, PRIMARY); b, kb, nb = S.block_acc(rows, other)
        ah, kah, nah = S.block_acc(rows, PRIMARY, set(HIDDEN)); bh, kbh, nbh = S.block_acc(rows, other, set(HIDDEN))
        bt[PRIMARY + ' vs ' + other] = {'all': {'a_correct': [ka, na], 'b_correct': [kb, nb], 'test': S.signflip(a, b)},
                                        'hidden_only': {'a_correct': [kah, nah], 'b_correct': [kbh, nbh], 'test': S.signflip(ah, bh)}}
    out['block_tests'] = bt
    out['all_detectors'] = {det: summary(rows, det) for det in dets}
    S.OUT.mkdir(parents=True, exist_ok=True); (S.OUT / out_name).write_text(json.dumps(out, indent=1), encoding='utf-8')
    for det in [PRIMARY, 'C31/whole_C0.1', 'C31/temporal_C0.1'] + OTHERS:
        if det in dets:
            s = out['all_detectors'][det]
            print('  %-28s hidden %d/%d  FA %d/%d  correct %d/%d  %s' % (det, *s['hidden_alerts'], *s['silent_false_alarms'], *s['correct'], json.dumps(s['by_condition'])))
    for k, v in bt.items():
        print('  block test', k, json.dumps(v['all']['test']), 'hidden', json.dumps(v['hidden_only']['test']))
    return out

if __name__ == '__main__':
    main(*(sys.argv[1:3]))
