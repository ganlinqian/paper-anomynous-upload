"""Offline test of session_check() in rig_capture_stagger_sp2027.py with canned query/tasklist outputs."""
import importlib.util, subprocess, types
P = r'<WORKSPACE>/ws_main\results\sp2027\experiments\rig_capture_stagger_sp2027.py'
spec = importlib.util.spec_from_file_location('rig', P); rig = importlib.util.module_from_spec(spec); spec.loader.exec_module(rig)
HDR = ' USERNAME              SESSIONNAME        ID  STATE   IDLE TIME  LOGON TIME\n'
CON = ' win                   console             1  Active      none   2026/11/5 16:43\n'
NOTASK = 'INFO: No tasks are running which match the specified criteria.\n'
CASES = {
    'console_only_rc1': ((1, HDR + CON, ''), (0, NOTASK, ''), True),
    'no_users': ((1, '', 'No User exists for *\n'), (0, NOTASK, ''), True),
    'extra_rdp': ((1, HDR + CON + ' alice                 rdp-tcp#3           2  Active          .  2026/11/6 9:00\n', ''), (0, NOTASK, ''), False),
    'disconnected': ((1, HDR + ' win                                       2  Disc        1:02  2026/11/6 9:00\n', ''), (0, NOTASK, ''), False),
    'other_console_user': ((1, HDR + ' bob                   console             1  Active      none   2026/11/6 9:00\n', ''), (0, NOTASK, ''), False),
    'todesk_running': ((1, HDR + CON, ''), (0, '"ToDesk.exe","4412","Services","0","40,000 K"\n', ''), False),
    'query_failed': ((5, '', 'error'), (0, NOTASK, ''), False),
}
ok = True
for name, (q, t, expect) in CASES.items():
    seq = iter([q, t])
    def fake(cmd, **kw):
        rc, so, se = next(seq); return types.SimpleNamespace(returncode=rc, stdout=so, stderr=se)
    rig.subprocess = types.SimpleNamespace(run=fake)
    try:
        rig.session_check(); got = True
    except RuntimeError:
        got = False
    ok &= got == expect
    print(name, 'pass' if got == expect else 'FAIL', 'accepted' if got else 'refused')
print('ALL_OK' if ok else 'SOME_FAILED')
