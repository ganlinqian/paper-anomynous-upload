# C38 pre-registration: envelope-modulation detector for persistent low-duty background load (no power meter)

Written 2026-11-16 23:50 UTC (Beijing 11-17 07:50; session ws_revision; user instruction "") BEFORE any
C38 run.  The collector copies this file into each campaign's `source/` and records its SHA-256 in FREEZE.json.

## Motivation (C37, already reported)
Low-duty background gzip that runs across the pre-dispatch reference and the call (persist12 / persist25) evaded the
frozen C35 primary (0/16) and mostly the C31 ensemble (3/16); the wideband-power guard G1 was useless.  Exploratory
analysis on C35 (s1k) and C37 (s1m) raw IQ (session ws_revision, `results/c38/`; NOT a result, only the source of
the recipe): the modulation spectrum of the 204.8-us band-power envelope separates persist12/25 from clean silents
(wideband 1.2-2.4 kHz bin AUC 1.00 within s1m); pooled two-session block CV of the recipe below: persist 16/16, false
alarms 5/64.  Single-session training did not transfer across the C36 probe re-mount (s1m -> s1k FA 17/40), hence a new
training session.

## Design (one boot, same probe placement as C36 batch 4 / C37; power meter NOT used)
Same fixture as C37 (4 s gateway wait, 8 s capture, governor pinned to performance, 25 s cool-down, thermal guard).
Background load = duty-cycled `gzip -n -1` on core 2 from 0.5 s before ready until the reply (SIGSTOP/SIGCONT period
20 ms unless stated).
- **s1o (training session)**: 8 calibration silents, then 6 blocks x 10 cells (seed 2026111701): silent x3, bg_log,
  gzip3_d19, sha32, persist06 (6.25 %), persist12, persist18 (18.75 %), persist25.  Frozen C35 / C31 are evaluated on
  s1o as an additional test session for THEM; for C38 it is training data only.
- **Training (automatic, in the chain, before s1p starts)**: `c38_env.py train` on s1k (C35) + s1m (C37) + s1o -> 
  `models/C38_ENV_MODELS.json` (+ .sha256), never overwritten.  s1n (poisoned calibration, out of scope under A5) and
  smoke sessions are not used.
- **s1p (prospective test)**: 8 calibration silents, then 8 blocks x 11 cells (seed 2026111702): silent x3, bg_log,
  gzip16, gzip3_d19, sha32, persist09 (9.375 %, unseen duty), persist12, persist25, persist12s (12.5 % with an unseen
  50 ms period).  The C38 model file is listed in s1p FREEZE.json `source_sha256` before the first s1p run.

Validity as C37 (Pi-side checks; persist must run from before `http_sent` to `http_received`); acquisition-only invalid
runs are excluded and listed (at most 3 in s1o, 4 in s1p); any Pi-side invalid run stops the batch.

## Detectors fixed now
- **C38 primary** `C38/roll4` P > 0.5 (`c38_env.py`): grp16 envelope features (16 band groups + wideband, 9 modulation
  bins, pre and call windows; 306 values) minus the mean of the last 4 earlier reference runs (silent / silent_cal;
  calibration mean for calibration runs and the first test run); StandardScaler + LogisticRegression(C=0.1),
  class-balanced; label actual_active.
- C38 secondary: same at P > 0.7; `C38/cal` (calibration-mean reference, own model) P > 0.5; `C38/roll4_admit` (primary
  model, reference pool admits only non-alerting runs, causal).
- D1 = frozen C35 `self_roll4_p70`, D2 = frozen C31 `avg_whole_temporal` (unchanged, `process_sp2027.py eval-c35/31`).
- Composite D1 | C38 (alert if either).

## Endpoints (s1p only; Clopper-Pearson 95 % CIs; exact McNemar for paired comparisons)
1. Persistent load: detections of persist12 + persist25 (16, seen duties) and persist09 + persist12s (16, unseen duty /
   period) by C38 primary, D1, D2, D1|C38.  Paired McNemar C38 vs D1 over the 32 persist runs.
2. False alarms: clean test silents (24) + bg_log (8) = 32 negatives, every detector.
3. Ordinary hidden work: gzip16, gzip3_d19, sha32 (24), every detector.
4. Success criterion for the C38 primary, fixed now: persist (all 32) >= 24 detected AND false alarms <= 3/32.
   Reported whatever the outcome; failure goes into the paper as such.
5. Secondary: the C38 secondary variants; per-cell tables; frozen D1/D2 on s1o (persist06/12/18/25 and FA).

Analysis script `results/c38/analyze_c38.py` (session ws_revision) implements exactly these endpoints and is hashed
(`results/c38/ANALYSIS_FREEZE.json`) before s1p starts.
