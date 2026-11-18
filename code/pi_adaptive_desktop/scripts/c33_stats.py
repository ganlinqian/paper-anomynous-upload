"""C33 (stage s1h) pre-specified analyses, fixed before any C33 run (2026-11-10).

Generalisation to unseen hidden tools/sizes and false alarms under contract-permitted background work.  No model is
trained for C33: every detector was frozen before (primary = the C31 ensemble, frozen 2026-11-10 15:57 UTC).
Hidden cells (in no training set): zstd16, xz2, ossl16, sha32 (unseen tools), gzip1_full, gziptxt32 (unseen sizes).
Amended 2026-11-10 before any valid C33 hidden data were evaluated: stage s1h stopped at run 10 (gzip32 output fsync ran
past the wait); stage s1i replaces zstd32 by zstd16 and gzip32 by gziptxt32 (gzip on 32 MiB text).
Negative cells: silent (16 runs), bg_log and bg_download (8 runs each; permitted background work, no hidden work).
  primary    C31/avg_whole_temporal: alerts per hidden cell (n=8, exact 95% CI) and pooled over the 48 hidden runs;
             false alarms on silent (16) and on each background cell (8), pooled background (16)
  secondary  (1) the same table for C32/avg_whole_temporal, C29/call_whole_sesscal and every other frozen branch
             (2) per hidden cell: a cell with <= 4/8 primary alerts is reported as 'not detected'
             (3) exact two-sided Fisher test: primary alert rate on background vs on silent
Calibration calls never count.  Interpretation is descriptive; no model, threshold or condition is changed after C33.
"""
import csv, json, pathlib, sys
from scipy.stats import fisher_exact
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import c28_stats as S  # noqa: E402
PRIMARY = 'C31/avg_whole_temporal'
HIDDEN = ['zstd16', 'xz2', 'ossl16', 'sha32', 'gzip1_full', 'gziptxt32']; BG = ['bg_log', 'bg_download']

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
        r['alert'] = r['alert'] == 'True'; r['actual_active'] = r['actual_active'] == 'True'; out.append(r)
    return out

def table(rows, det):
    c = {k: S.cell(rows, det, k) for k in HIDDEN + BG + ['silent']}
    kh = sum(c[k]['alerts'] for k in HIDDEN); nh = sum(c[k]['n'] for k in HIDDEN)
    kb = sum(c[k]['alerts'] for k in BG); nb = sum(c[k]['n'] for k in BG)
    return {'by_condition': {k: [c[k]['alerts'], c[k]['n'], c[k]['cp95']] for k in c},
            'hidden': [kh, nh, S.cp(kh, nh)], 'silent_fa': [c['silent']['alerts'], c['silent']['n'], c['silent']['cp95']],
            'background_fa': [kb, nb, S.cp(kb, nb)], 'not_detected': [k for k in HIDDEN if c[k]['alerts'] <= 4],
            'fisher_bg_vs_silent_p': float(fisher_exact([[kb, nb - kb], [c['silent']['alerts'], c['silent']['n'] - c['silent']['alerts']]])[1])}

def main(stage='s1i', out_name='c33_stats.json'):
    d = S.campaign(stage); rows = load(d); dets = sorted({r['detector'] for r in rows})
    out = {'campaign': d.name, 'primary': PRIMARY, 'detectors': {det: table(rows, det) for det in dets}}
    S.OUT.mkdir(parents=True, exist_ok=True); (S.OUT / out_name).write_text(json.dumps(out, indent=1), encoding='utf-8')
    for det in [PRIMARY, 'C31/whole_C0.1', 'C31/temporal_C0.1', 'C32/avg_whole_temporal', 'C29/call_whole_sesscal', 'C30/call_whole_sesscal', 'C27_diverse/call_temporal']:
        if det in dets:
            t = out['detectors'][det]
            print('  %-26s hidden %d/%d  silentFA %d/%d  bgFA %d/%d  not_detected %s' % (det, t['hidden'][0], t['hidden'][1], t['silent_fa'][0], t['silent_fa'][1],
                  t['background_fa'][0], t['background_fa'][1], t['not_detected']))
            print('      ' + ' '.join('%s:%d/%d' % (k, v[0], v[1]) for k, v in t['by_condition'].items()) + '  fisher bg vs silent p=%.3f' % t['fisher_bg_vs_silent_p'])
    return out

if __name__ == '__main__':
    main(*(sys.argv[1:3]))
