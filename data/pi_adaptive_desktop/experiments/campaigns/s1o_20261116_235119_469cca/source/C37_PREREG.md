# C37 pre-registration: reference poisoning, deferred work, omission mimicry, and a prospective power baseline

Written 2026-11-16 (session ws_revision, user-approved Pi batch) BEFORE any C37 run; the collector copies this file
into each campaign's `source/` and records its SHA-256 in FREEZE.json. Purpose: answer the three-way pre-review P0
(references radiated by an untrusted host; deferred gap work; omission mimicry) and P1 (fair power baseline).
No model is trained or refit. Frozen detectors: C35 `self_roll4_p70` (primary, uses pre-dispatch and rolling
references) and C31 `avg_whole_temporal` ensemble (secondary, uses the session-calibration mean). Both are the files
already listed in FREEZE.json `source_sha256`.

## Stages and cells (collector `collect_sp2027_c37.py`, Pi server `pi_api_sp2027_c37.py`)

Same fixture as C33-C36: 4 s gateway wait, 8 s capture, Pi governor pinned to performance during the campaign, 25 s
cool-down, thermal guard. Hidden work = `gzip -n -1` of 16 MiB random (core 3) unless stated.

**s1z (smoke)**: 1 block (silent, persist12, gzip16_p12, deferred16, gzip16_alt) + 1 poisoned probe. Only checks that
the new Pi-side behaviours validate; never analysed, never pooled.

**s1m** (one session): 8 calibration silents (clean), then
- phase `clean`, 8 blocks x 9 cells (shuffled per block, seed 2026111601):
  - `silent` x2: clean no-work probes (negatives; reference pool of C35)
  - `gzip16`: hidden gzip in the wait (positive control)
  - `persist12`, `persist25`: no call-window gzip, but duty-cycled background gzip (12.5 % / 25 %, core 2) running from
    0.5 s before the worker reports ready (i.e. across the pre-dispatch reference) until the reply. Hidden work is
    present in the call window, so actual_active = True.
  - `gzip16_p12`: hidden gzip16 in the wait plus 12.5 % masking load across pre-window and call.
  - `deferred16`: nothing in the call window; gzip16 starts 0.15 s after the public reply (post-reply gap, inside the
    8 s capture). Call-window label inactive; gap label active.
  - `gzip16_alt` (contract E = 1, "required work"): the required gzip is run on different data of the same size
    (mimicry of a skipped verification). Physically A = 1.
  - `silent_e1` (contract E = 1): required work skipped (omission). Physically A = 0.
- phase `poison`: a lead-in of 4 poisoned probes, then 6 blocks of (silent, silent, gzip16, gzip3_d19) shuffled (seed
  2026111603); every `silent` probe in this phase carries 6.25 % background gzip (host_persist = 0.0625). They keep the
  condition name `silent`, so the frozen C35 code uses them as rolling references, as a poisoning host would arrange.
  By construction each hidden run's last four reference probes are poisoned.

**s1n** (separate session, run right after s1m): the 8 calibration silents carry 25 % background load (poisoned
calibration); then 4 clean blocks of (silent, silent, gzip16, gzip3_d19), seed 2026111602.

Validity: as C36 batch 4, plus (i) background load verifiably running from before `http_sent` to `http_received`
(Pi monotonic, `persist.cycles > 0`), (ii) deferred gzip began after the reply, ended <= 3.4 s after it (amended from 3.0 s after the s1z smoke, before any s1m/s1n run: the smoke deferred run ended 2.63 s after the reply and the capture ends about 3.6 s after it), and its
output decompresses to the input. Acquisition-only invalid runs are excluded and listed (at most 4 in s1m, 2 in s1n);
any Pi-side invalid run stops the batch.

## Detectors and rules fixed now

D1 `C35/self_roll4_p70` and D2 `C31/avg_whole_temporal`: frozen, run by `process_sp2027.py eval-c35 / eval-c31`
unchanged. Contract handling: alert V = A_hat XOR E (E = 1 only for gzip16_alt and silent_e1).

G1 reference-admission guard (new, deterministic, no fitting): for every call, `p_pre` = linear-mean wideband power
(dB) over the complete frames ending before the dispatch mark (the quantity C35 subtracts). Threshold = maximum `p_pre`
over the session's 8 calibration silents. Alert if `p_pre` > threshold. Composite detectors: D1+G1, D2+G1 (alert if
either). Secondary margins +0.05 dB and +0.10 dB are reported, not primary.

G2 gap detector (new): `g` = linear-mean wideband power over complete frames from 2 frames after the reply mark to
the end of the capture, minus `p_pre`. Threshold = maximum `g` over the 8 calibration silents. Alert if exceeded
(intended defense against deferred work under E = 0 for the gap).

Power (ALIENTEK C2 Pro inline on the Pi USB-C supply, 200 SPS, ATK-C priority Normal, new AutoSave file; data port on
capture_pc, same USB controller as the HackRFs, a known confound also present in C36 batch 4; sync pulses
`results/power_c37/sync_pulses.py` before s1m and after s1n; time map = linear fit over the six pulse edges as in C36):
- P1 primary: `peak500_roll4` = max 500 ms moving mean in the call window minus the mean `peak500` of the last 4
  earlier reference probes (`silent` / `silent_cal`; calibration calls use the calibration mean), threshold = maximum
  over the 8 calibration silents.
- P2: `peak500` absolute, same threshold rule.  P3: `abs_win` mean. All also reported at matched FA (post hoc).
- Power G1 analogue: mean power over [-0.3 s, 0 s] before dispatch vs. calibration maximum.

## Endpoints (all on test runs, Clopper-Pearson 95 % CIs; McNemar for paired detector comparisons)

1. Background masking (s1m clean): detections of persist12, persist25, gzip16_p12 by D1, D2, D1+G1, D2+G1, P1.
   Expectation (stated, not a pass criterion): D1 loses sensitivity because its own pre-dispatch reference absorbs the
   load; G1 and D2 should flag it.
2. Rolling-reference poisoning (s1m poison vs clean): D1 detections of gzip16 / gzip3_d19 with poisoned references vs
   gzip16 in phase clean (and gzip3_d19 in C34-C36); alerts on the poisoned probes themselves; G1 alerts on them.
3. Calibration poisoning (s1n): D2 and D1 detections of gzip16 / gzip3_d19 vs s1m clean phase; FA on clean silents.
4. Deferred work: G2 detections on deferred16 vs G2 FA on clean silents; D1/D2 alerts on deferred16 (expected none).
5. Omission and mimicry (E = 1): alerts on silent_e1 (expected: detected) and gzip16_alt (expected: missed, because
   the mimic performs the same physical work); reported as the evidence for the paper's scope statement.
6. False alarms: clean `silent` test probes of s1m clean (16) and s1n (8), for D1, D2, each composite, G2, P1-P3.
7. Power vs EM (prospective): P1 vs D1/D2 detections and FA on every endpoint above, same runs.

Results are reported whatever they are; a successful attack goes into the paper's limitations together with the
guard result. Rules above are fixed now; the analysis script `results/power_c37/analyze_c37.py` (session ws_revision)
implements exactly them and will be hashed before it reads any C37 feature or power file.
