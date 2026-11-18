"""Run one figure script in-process and record every file it touches: audit-hook 'open' events,
directory listings (os.listdir / os.scandir), and successful os.stat calls (existence and mtime checks).

Usage: python -I trace_fig_inputs.py LOG.json SCRIPT [args ...]
The caller redirects figure outputs with TELLTALE_FIGURES so that project figure folders are not touched.
"""
import json
import os
import runpy
import sys

log_path, script, *args = sys.argv[1:]
events = []


def _p(x):
    if isinstance(x, int) or x is None:
        return None
    try:
        return os.fsdecode(os.fspath(x))
    except TypeError:
        return None


def hook(ev, a):
    if ev == 'open':
        p = _p(a[0])
        if p is not None:
            events.append(['open', p, a[1] if isinstance(a[1], str) else ('' if a[1] is None else str(a[1]))])
    elif ev in ('os.listdir', 'os.scandir'):
        p = _p(a[0]) if a else None
        events.append([ev, p if p is not None else '.', ''])


sys.addaudithook(hook)
_stat = os.stat


def _traced_stat(path, *a, **k):
    r = _stat(path, *a, **k)
    p = _p(path)
    if p is not None:
        events.append(['stat', p, ''])
    return r


os.stat = _traced_stat
sys.argv = [script] + args
status = 'ok'
try:
    runpy.run_path(script, run_name='__main__')
except SystemExit as e:
    status = f'exit {e.code}'
    raise
except BaseException as e:  # record the failure, then re-raise
    status = f'error {type(e).__name__}: {e}'
    raise
finally:
    os.stat = _stat
    with open(log_path, 'w', encoding='utf-8') as fh:
        json.dump({'script': script, 'args': args, 'status': status, 'events': events}, fh)
