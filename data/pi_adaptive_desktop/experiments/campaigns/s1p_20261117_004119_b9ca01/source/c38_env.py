"""C38 envelope-modulation detector (2026-11-17, session ws_revision).  Features from win4_envelope.py (same folder):
per run, the Welch modulation spectrum (9 log bins, 4.77-2442 Hz) of the 204.8-us log-power envelope of each of the 64
bands plus the wideband sum, for the pre-dispatch window (last 1.0 s before the dispatch mark) and the call window
(dispatch mark to reply mark).  Recipe 'grp16' (selected by the exploratory search results/c38/env_variants.py of
session ws_revision on C35 s1k + C37 s1m): the 64 bands averaged in 16 groups of 4 adjacent bands, plus the wideband
row, for both windows: 2 x (16 + 1) x 9 = 306 values.
References: 'roll4' (primary) subtracts the mean of the last 4 EARLIER reference runs ('silent' / 'silent_cal'; the
calibration runs and the first test run use the calibration mean), as C35; 'cal' (secondary) subtracts the mean of
the session's 8 calibration silents (trusted initialisation, A5).  Evaluation-only variant 'roll4_admit': the same
roll4 model, but a reference run enters the pool only if its own score did not alert (P <= 0.5), computed causally.
Model per reference: StandardScaler + LogisticRegression(C=0.1), class-balanced sample weights, label actual_active
(any hidden work inside the call window, incl. background load spanning it).  Training pool = all silent/silent_cal.
Primary rule: roll4, alert if P > 0.5.  Secondary: P > 0.7; cal; roll4_admit; composite with frozen C35 primary.
Commands (python c38_env.py ...):
  envlist  --campaign DIR             write env_list.json for win4_envelope.py
  envrun   --campaign DIR             run win4_envelope.py on capture_pc in bounded chunks until complete, then fetch *_env.npz
  train    --out MODEL --campaign DIR [--campaign DIR ...]   fit and freeze (never overwrites)
  eval     --model MODEL --campaign DIR                       frozen evaluation (model must be in the campaign FREEZE)
"""
import argparse, hashlib, json, pathlib, subprocess, sys, time
import numpy as np
B = pathlib.Path(__file__).resolve().parent
KEY = '<SSH_KEY>'; WIN = 'win@192.0.2.4'
sha = lambda p: hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def rows_of(d):
    return [x for x in json.loads((d / 'RESULTS.json').read_text(encoding='utf-8-sig')) if x['condition'] != 'bg_download']


def winroot(d):
    return json.loads((d / 'FREEZE.json').read_text(encoding='utf-8-sig'))['winroot']


def cmd_envlist(d):
    lst = []
    for x in json.loads((d / 'RESULTS.json').read_text(encoding='utf-8-sig')):
        r2 = next(r for r in x['rf']['radios'] if r['radio'] == '930c')
        lst.append({'path': r2['raw'].replace('\\', '/'), 'id': x['id'],
                    'before': next(m['bytes'] for m in x['before']['marks'] if m['radio'] == '930c'),
                    'after': next(m['bytes'] for m in x['after']['marks'] if m['radio'] == '930c')})
    (d / 'env_list.json').write_text(json.dumps(lst), encoding='utf-8'); return len(lst)


def capture_pc(code, timeout=175):
    import base64
    b64 = base64.b64encode(code.encode('utf-16-le')).decode()
    r = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=12', '-i', KEY, WIN, 'powershell -NoProfile -NonInteractive -EncodedCommand ' + b64],
                       capture_output=True, text=True, timeout=timeout)
    return r.stdout.strip() + r.stderr.strip()


def cmd_envrun(d, max_rounds=12):
    n = cmd_envlist(d); wr = winroot(d)
    subprocess.run(['scp', '-q', '-o', 'BatchMode=yes', '-i', KEY, str(d / 'env_list.json'), str(B / 'win4_envelope.py'), WIN + ':' + wr + '/'], check=True, timeout=60)
    log = []
    for k in range(max_rounds):
        out = capture_pc("Set-Location '" + wr + "'; $p = Start-Process python -ArgumentList 'win4_envelope.py','--list','env_list.json','--out','env','--workers','6' "
                   "-NoNewWindow -PassThru -RedirectStandardOutput env_run.log -RedirectStandardError env_err.log; $null = $p.WaitForExit(150000); "
                   "'N=' + @(Get-ChildItem env -Filter *_env.npz).Count", timeout=175)
        log.append(out)
        if ('N=%d' % n) in out:
            break
    (d / 'env').mkdir(exist_ok=True)
    subprocess.run(['scp', '-q', '-o', 'BatchMode=yes', '-i', KEY, WIN + ':' + wr + '/env/*_env.npz', str(d / 'env')], check=True, timeout=170)
    got = len(list((d / 'env').glob('*_env.npz'))); assert got == n, (got, n, log[-1:])
    return {'files': n, 'rounds': len(log)}


POOL = ('silent', 'silent_cal')


def raw_X(d, rows, envdir=None):
    """grp16 features (n, 306) for rows in time order."""
    envdir = pathlib.Path(envdir) if envdir else d / 'env'
    t = [x['dispatch_desktop_ns'] for x in rows]; assert all(b > a for a, b in zip(t, t[1:])), 'rows not in time order'
    X = []
    for x in rows:
        with np.load(envdir / (x['id'] + '_930c_env.npz')) as z:
            g = [z[k][:64].reshape(16, 4, 9).mean(1).ravel() for k in ('mod_call', 'mod_pre')]
            X.append(np.r_[g[0], g[1], z['mod_call'][64], z['mod_pre'][64]])
    X = np.array(X); assert np.isfinite(X).all() and X.shape[1] == 306
    return X


def reference(X, rows, kind, admit=None):
    cal = np.array([x['condition'] == 'silent_cal' for x in rows]); assert cal.sum() == 8; cm = X[cal].mean(0)
    if kind == 'cal':
        return X - cm
    assert kind == 'roll4'
    pool = np.array([x['condition'] in POOL for x in rows]); out = np.empty_like(X); P = np.where(pool)[0]
    for i in range(len(X)):
        prev = P[P < i]
        out[i] = X[i] - (cm if cal[i] or len(prev) == 0 else X[prev[-4:]].mean(0))
    return out


def roll4_admit(X, rows, m, thr=.5):
    """Causal: score run i against the last 4 earlier ADMITTED reference runs; a reference run is admitted if P <= thr."""
    cal = np.array([x['condition'] == 'silent_cal' for x in rows]); cm = X[cal].mean(0); adm = []; q = np.zeros(len(X))
    for i, x in enumerate(rows):
        r = cm if cal[i] or not adm else X[adm[-4:]].mean(0)
        q[i] = score(m, (X[i] - r)[None])[0]
        if x['condition'] in POOL and (cal[i] or q[i] <= thr):
            adm.append(i)
    return q


def env_X(d, rows, kind='roll4', envdir=None):
    X = raw_X(d, rows, envdir); cal = np.array([x['condition'] == 'silent_cal' for x in rows])
    return reference(X, rows, kind), cal


def fit(Xs, ys):
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    X = np.vstack(Xs); y = np.concatenate(ys)
    sw = np.where(y, len(y) / (2 * y.sum()), len(y) / (2 * (~y).sum()))
    return make_pipeline(StandardScaler(), LogisticRegression(C=0.1, max_iter=5000, random_state=1111)).fit(X, y, logisticregression__sample_weight=sw), X, y


def score(m, X):
    z = ((X - np.array(m['mean'])) / np.array(m['scale'])) @ np.array(m['coefficient']) + m['intercept']
    return 1 / (1 + np.exp(-z))


def cmd_train(out, campaigns):
    out = pathlib.Path(out)
    if out.exists():
        raise FileExistsError('frozen model exists; never overwrite')
    sess = []; ids = []
    for d in campaigns:
        rows = rows_of(d); assert all(x['valid'] for x in rows); sess.append((d, rows, raw_X(d, rows))); ids += [x['id'] for x in rows]
    mj = {'utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'training_campaigns': [d.name for d, _, _ in sess], 'training_ids': ids,
          'recipe': 'grp16', 'primary': 'roll4_p50', 'thresholds': {'p50': .5, 'p70': .7}, 'models': {},
          'feature_code_sha256': {'win4_envelope.py': sha(B / 'win4_envelope.py'), 'c38_env.py': sha(__file__)}}
    for kind in ('roll4', 'cal'):
        Xs = [reference(X, rows, kind) for _, rows, X in sess]; ys = [np.array([bool(x['actual_active']) for x in rows]) for _, rows, _ in sess]
        m, X, y = fit(Xs, ys); s, c = m[0], m[1]
        mm = {'mean': s.mean_.tolist(), 'scale': s.scale_.tolist(), 'coefficient': c.coef_[0].tolist(), 'intercept': float(c.intercept_[0]),
              'classes': [bool(v) for v in c.classes_], 'C': 0.1, 'n_train': len(y), 'n_pos': int(y.sum()),
              'train_accuracy_p50': float(np.mean((m.predict_proba(X)[:, 1] > .5) == y))}
        assert mm['classes'] == [False, True]; mj['models'][kind] = mm
    out.write_text(json.dumps(mj), encoding='utf-8'); h = sha(out)
    out.with_suffix('.sha256').write_text(h + '  ' + out.name + '\n' + mj['utc'] + '\n', encoding='utf-8')
    return {'sha256': h, **{k: {kk: v[kk] for kk in ('n_train', 'n_pos', 'train_accuracy_p50')} for k, v in mj['models'].items()}}


def cmd_eval(model, d):
    model = pathlib.Path(model); mj = json.loads(model.read_text(encoding='utf-8')); h = sha(model)
    freeze = json.loads((d / 'FREEZE.json').read_text(encoding='utf-8-sig'))
    assert any(pathlib.Path(k).name == model.name and v == h for k, v in freeze['source_sha256'].items()), 'model not frozen before collection'
    rows = rows_of(d); assert not ({x['id'] for x in rows} & set(mj['training_ids'])); assert all(x['valid'] for x in rows)
    X = raw_X(d, rows); cal = np.array([x['condition'] == 'silent_cal' for x in rows]); assert cal.sum() == 8
    Q = {'roll4': score(mj['models']['roll4'], reference(X, rows, 'roll4')), 'cal': score(mj['models']['cal'], reference(X, rows, 'cal')),
         'roll4_admit': roll4_admit(X, rows, mj['models']['roll4'])}
    by = {}; preds = []
    for kind, q in Q.items():
        for x, s, c in zip(rows, q, cal):
            preds.append({'detector': 'C38/' + kind, 'id': x['id'], 'block': x['block'], 'condition': x['condition'], 'calibration': bool(c),
                          'host_persist': float(x.get('host_persist') or 0), 'actual_active': bool(x['actual_active']), 'score': float(s),
                          'alert_p50': bool(s > .5), 'alert_p70': bool(s > .7)})
            if not c:
                b = by.setdefault(kind, {}).setdefault(x['condition'], [0, 0, 0]); b[0] += int(s > .5); b[1] += int(s > .7); b[2] += 1
    out = {'utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'campaign': d.name, 'model': model.name, 'model_sha256': h,
           'n': len(rows), 'primary': mj['primary'], 'alerts_p50_p70_n_by_condition': by, 'no_fit': True}
    (d / 'EVALUATION_C38.json').write_text(json.dumps(out, indent=1), encoding='utf-8')
    import csv
    with (d / 'predictions_c38.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(preds[0])); w.writeheader(); w.writerows(preds)
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('cmd', choices=['envlist', 'envrun', 'train', 'eval'])
    ap.add_argument('--campaign', action='append', required=True); ap.add_argument('--out'); ap.add_argument('--model')
    a = ap.parse_args(); ds = [pathlib.Path(c) for c in a.campaign]
    if a.cmd == 'envlist':
        r = cmd_envlist(ds[0])
    elif a.cmd == 'envrun':
        r = cmd_envrun(ds[0])
    elif a.cmd == 'train':
        r = cmd_train(a.out, ds)
    else:
        r = cmd_eval(a.model, ds[0])
    print(json.dumps(r, indent=1))


if __name__ == '__main__':
    main()
