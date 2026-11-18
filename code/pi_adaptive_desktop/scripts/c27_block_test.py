"""C27: exact block-level sign-flip test, diverse primary vs single-workload primary (same 64 runs, 8 blocks)."""
import collections, csv, itertools, json, pathlib
E = pathlib.Path(r'<WORKSPACE>/ws_main\results\sp2027\experiments')
d = pathlib.Path(json.loads((E / 'campaigns' / 'LATEST_s1b.json').read_text(encoding='utf-8-sig'))['directory'])
rows = list(csv.DictReader((d / 'predictions.csv').open(encoding='utf-8'))) + list(csv.DictReader((d / 'predictions_diverse.csv').open(encoding='utf-8')))
def acc(det, subset=None):
    b = collections.defaultdict(list)
    for r in rows:
        if r['detector'] == det and (subset is None or r['condition'] in subset):
            b[r['block']].append((r['alert'] == 'True') == (r['actual_active'] == 'True'))
    return {k: sum(v) / len(v) for k, v in b.items()}, sum(sum(v) for v in b.values()), sum(len(v) for v in b.values())
def flip(a, b):
    ks = sorted(set(a) & set(b)); dd = [a[k] - b[k] for k in ks]; obs = abs(sum(dd)); c = t = 0
    for s in itertools.product([1, -1], repeat=len(dd)):
        t += 1; c += abs(sum(x * y for x, y in zip(dd, s))) >= obs - 1e-12
    return {'blocks': len(ks), 'mean_diff': sum(dd) / len(dd), 'p_two_sided': c / t}
out = {}
for name, sub in (('all', None), ('throttled_or_new_input', {'silent', 'gzip3_d19', 'gzip4_d25', 'gzip6_d37', 'json8'})):
    a, ka, na = acc('C27_diverse/call_temporal', sub); b, kb, nb = acc('C10_transfer/temporal_260/plain', sub)
    out[name] = {'diverse_correct': [ka, na], 'one_workload_correct': [kb, nb], 'test': flip(a, b)}
(pathlib.Path(r'<WORKSPACE>/ws_main\results\sp2027\stats') / 'c27_block_test.json').write_text(json.dumps(out, indent=1), encoding='utf-8')
print(json.dumps(out, indent=1))
