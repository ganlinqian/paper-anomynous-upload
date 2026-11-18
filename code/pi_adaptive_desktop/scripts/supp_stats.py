"""Paper summaries of the S1/S2/S3 supplement batches.

Reads only the frozen evaluations written by experiments/process_sp2027.py (EVALUATION.json, predictions.csv,
CLOCK_CHECK.json) and the run records; nothing is refit and no threshold is changed.  Adds exact Clopper-Pearson
intervals, hidden-work timing, and exact block-level sign-flip tests.  Missing batches are skipped.
"""
import collections, csv, itertools, json, pathlib
from scipy.stats import beta
E = pathlib.Path(r'<WORKSPACE>/ws_main\results\sp2027\experiments')
OUT = pathlib.Path(r'<WORKSPACE>/ws_main\results\sp2027\stats')
PRIMARY_WAIT = 'C10_transfer/temporal_260/plain'
MIB_OF = {'gzip16': 16, 'text8': 8, 'gzip8_d50': 8, 'gzip4_d25': 4, 'gzip2_d12': 2, 'gzip16_cap': 16, 'gzip6_d37': 6, 'gzip3_d19': 3, 'json8': 8,
          'gzip1_d06': 1, 'gzip05_d03': 0.5, 'gzip2_d06': 2, 'gzip1_d03': 1}

def latest(stage):
    p = E / 'campaigns' / ('LATEST_' + stage + '.json')
    if not p.exists():
        return None
    d = pathlib.Path(json.loads(p.read_text(encoding='utf-8-sig'))['directory'])
    return d if (d / 'EVALUATION.json').exists() else None

def cp(k, n):
    lo = 0.0 if k == 0 else float(beta.ppf(.025, k, n - k + 1)); hi = 1.0 if k == n else float(beta.ppf(.975, k + 1, n - k))
    return [round(lo, 3), round(hi, 3)]

def b(x):
    return str(x).strip().lower() == 'true'

def signflip(da, db):
    blocks = sorted(set(da) & set(db)); diffs = [da[k] - db[k] for k in blocks]
    obs = abs(sum(diffs)); cnt = tot = 0
    for s in itertools.product([1, -1], repeat=len(diffs)):
        tot += 1; cnt += abs(sum(x * y for x, y in zip(diffs, s))) >= obs - 1e-12
    return {'blocks': len(blocks), 'mean_diff': sum(diffs) / len(diffs), 'p_two_sided': cnt / tot}

def per_block(rows, keyname, key, truth):
    d = collections.defaultdict(list)
    for r in rows:
        if r[keyname] == key:
            d[r['block']].append(b(r['alert']) == truth(r))
    return {k: sum(v) / len(v) for k, v in d.items()}

def wait_batch(d):
    ev = json.loads((d / 'EVALUATION.json').read_text(encoding='utf-8')); rows = json.loads((d / 'RESULTS.json').read_text(encoding='utf-8-sig'))
    fz = json.loads((d / 'FREEZE.json').read_text(encoding='utf-8-sig'))
    if fz.get('bzip2_mib'):
        MIB_OF['bzip2_r'] = fz['bzip2_mib']
    dv = d / 'EVALUATION_DIVERSE.json'
    if dv.exists():
        for k, s in json.loads(dv.read_text(encoding='utf-8'))['summary'].items():
            ev['summary']['C27_diverse/' + k] = s
    timing = collections.defaultdict(list)
    for x in rows:
        a = x['private'].get('archive')
        if x['actual_active'] and a:
            dur = (a['process_end_ns'] - a['begin_ns']) / 1e9
            timing[x['condition']].append({'dur_s': dur, 'mib_per_s': MIB_OF[x['condition']] / dur, 'inside_wait': bool(x['private']['archive_inside_wait']),
                                           'slack_to_reply_s': (x['private']['reply_ns'] - a['fsync_end_ns']) / 1e9})
    tim = {c: {'n': len(v), 'mib': MIB_OF[c], 'dur_s_median': sorted(t['dur_s'] for t in v)[len(v) // 2], 'dur_s_max': max(t['dur_s'] for t in v),
               'mib_per_s_median': sorted(t['mib_per_s'] for t in v)[len(v) // 2], 'all_inside_wait': all(t['inside_wait'] for t in v),
               'min_slack_s': min(t['slack_to_reply_s'] for t in v)} for c, v in timing.items()}
    det = {}
    for name, s in ev['summary'].items():
        det[name] = {'by_condition': {c: dict(v, cp95=cp(v['alerts'], v['n'])) for c, v in s['by_condition'].items()},
                     **{k: s[k] for k in ('tp', 'fn', 'fp', 'tn', 'auc') if k in s}}
    el = collections.defaultdict(list)
    for x in rows:
        el[x['condition']].append(x['elapsed_s'])
    primary = 'C27_diverse/call_temporal' if dv.exists() else PRIMARY_WAIT
    out = {'campaign': d.name, 'n': len(rows), 'valid': sum(x['valid'] for x in rows), 'primary': primary,
           'primary_by_condition': det[primary]['by_condition'], 'detectors': det, 'hidden_work': tim,
           'elapsed_s_by_condition': {c: [round(min(v), 3), round(max(v), 3)] for c, v in el.items()},
           'transcript_note': 'one request/response per block for all conditions: any transcript-only monitor has TPR = FPR'}
    cc = d / 'CLOCK_CHECK.json'
    if cc.exists():
        c = json.loads(cc.read_text(encoding='utf-8'))
        out['clock_check'] = {'thresholds': c['thresholds'], 'by_condition': c['by_condition']}
        if 'applied' in c:
            out['clock_check']['applied'] = {'campaign': c['applied']['campaign'], 'by_condition': c['applied']['by_condition']}
    return out

def order_batch(d):
    ev = json.loads((d / 'EVALUATION.json').read_text(encoding='utf-8'))
    with (d / 'predictions.csv').open(encoding='utf-8') as f:
        pr = list(csv.DictReader(f))
    truth = lambda r: b(r['violation'])
    pb = {k: per_block(pr, 'model', k, truth) for k in ev['summary']}
    res = {'campaign': d.name, 'n': ev['n'], 'model_sha256': ev['model_sha256'], 'primary': ev['primary'], 'transcript_bound_correct': ev['transcript_bound_correct'], 'models': {}}
    for k, s in ev['summary'].items():
        corr = s['tp'] + s['tn']
        res['models'][k] = {t: s[t] for t in ('tp', 'fn', 'fp', 'tn', 'auc', 'perfect_blocks', 'blocks') if t in s}
        res['models'][k].update(correct=corr, cp95=cp(corr, ev['n']))
    res['block_tests'] = {k + ' vs ' + ev['primary']: signflip(pb[ev['primary']], pb[k]) for k in pb if k != ev['primary']}
    return res

if __name__ == '__main__':
    out = {}
    for stage in ('s1', 's3', 's1b', 's1c'):
        d = latest(stage)
        if d:
            out[stage] = wait_batch(d)
    d = latest('s2test')
    if d:
        out['s2'] = order_batch(d)
    m = E / 'models' / 'S2_ORDER_MODELS.json'
    if m.exists():
        mj = json.loads(m.read_text(encoding='utf-8')); out['s2_train'] = {'campaign': mj['training_campaign'], 'n': len(mj['training_ids']),
                                                                          'train_accuracy': {k: v['train_accuracy'] for k, v in mj['models'].items()}}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'supp_stats.json').write_text(json.dumps(out, indent=1), encoding='utf-8')
    for stage in ('s1', 's3', 's1b', 's1c'):
        if stage in out:
            print(stage, out[stage]['campaign'], 'valid', out[stage]['valid'], '/', out[stage]['n'])
            for c, v in sorted(out[stage]['primary_by_condition'].items()):
                print('  %-12s %2d/%2d  CI %s' % (c, v['alerts'], v['n'], v['cp95']))
            for c, v in sorted(out[stage]['hidden_work'].items()):
                print('  timing %-12s dur_med %.3fs max %.3fs  %.1f MiB/s  inside %s  slack %.2fs' % (c, v['dur_s_median'], v['dur_s_max'], v['mib_per_s_median'], v['all_inside_wait'], v['min_slack_s']))
            if 'clock_check' in out[stage]:
                print('  clock', {c: (v['clock_flags'], v['n']) for c, v in out[stage]['clock_check']['by_condition'].items()})
    if 's2' in out:
        for k, v in out['s2']['models'].items():
            print('s2 %-16s correct %d/%d CI %s auc %s perfect %s/%s' % (k, v['correct'], out['s2']['n'], v['cp95'], v.get('auc'), v.get('perfect_blocks'), v.get('blocks')))
        for k, v in out['s2']['block_tests'].items():
            print('  ', k, v)
