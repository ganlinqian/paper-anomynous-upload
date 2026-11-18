"""Replaces guard_wait in both controllers with the cooling variant (exact, counted replacements; prints new hashes)."""
import hashlib, pathlib
E = pathlib.Path(r'<WORKSPACE>/ws_main\results\sp2027\experiments')
OLD = '''def guard_wait(p, limit_s=900):
    """Pre-run precondition (2026-11-06 amendment after the thermal stop of the first S2 test batch): if only the thermal
    limit is exceeded, wait in 30 s steps (at most 15 min) until it is met instead of aborting; anything else aborts."""
    t0 = time.time(); waits = 0
    while True:
        try:
            g = guard(p); g['thermal_waits'] = waits; g['thermal_wait_s'] = round(time.time() - t0, 1); return g
        except RuntimeError as ex:
            if 'thermal precondition' not in str(ex) or time.time() - t0 > limit_s:
                raise
            waits += 1; time.sleep(30)
'''
NEW = '''CPUF = '/sys/devices/system/cpu/cpu0/cpufreq/'

def guard_wait(p, limit_s=1500, cool_to=None):
    """Pre-run precondition (2026-11-06 amendments after the thermal stops of the first S2 test batch and of C27).
    If only the thermal limit is exceeded: with cool_to=(governor, min_khz) the original governor is restored so that
    the idle device actually cools (under the campaign's performance governor it settles near the limit), the
    coordinator waits until CPU <= 46 C and DDR <= 41.5 C (30 s steps), re-applies performance with the 1.8 GHz floor,
    lets it settle for 20 s, and checks the normal precondition again; at most 25 min in total.  Anything else aborts."""
    t0 = time.time(); waits = 0; cycles = 0
    while True:
        try:
            g = guard(p); g.update(thermal_waits=waits, thermal_cool_cycles=cycles, thermal_wait_s=round(time.time() - t0, 1)); return g
        except RuntimeError as ex:
            if 'thermal precondition' not in str(ex) or time.time() - t0 > limit_s:
                raise
        if cool_to is None:
            waits += 1; time.sleep(30); continue
        cycles += 1
        run(p, "sudo -n sh -c 'echo " + cool_to[0] + " > " + CPUF + "scaling_governor; echo " + str(int(cool_to[1])) + " > " + CPUF + "scaling_min_freq'")
        try:
            while time.time() - t0 <= limit_s:
                waits += 1; time.sleep(30); t = thermal()
                if t['cpu_c'] <= 46 and t['ddr_c'] <= 41.5:
                    break
        finally:
            run(p, "sudo -n sh -c 'echo performance > " + CPUF + "scaling_governor; echo 1800000 > " + CPUF + "scaling_min_freq'")
        time.sleep(20)
'''
CALL_OLD = "            row = dict(cfg); row['pre'] = guard_wait(p)\n"
CALL_NEW = "            row = dict(cfg); row['pre'] = guard_wait(p, cool_to=(old[0], old[1]))\n"
for name in ('collect_sp2027_wait.py', 'collect_sp2027_order.py'):
    f = E / name; t = f.read_text(encoding='utf-8')
    assert t.count(OLD) == 1 and t.count(CALL_OLD) == 1, name
    t = t.replace(OLD, NEW).replace(CALL_OLD, CALL_NEW)
    compile(t, name, 'exec'); f.write_text(t, encoding='utf-8')
    print(name, hashlib.sha256(f.read_bytes()).hexdigest())
