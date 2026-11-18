# C37 pre-registration amendment 1 (2026-11-16 ~16:57 UTC, before any C37 feature, prediction, or power sample was read)

Trigger: a code dry run of `analyze_c37.py --dry` on the OLD C36 campaign `s1l_20261115_224455_c020b7` (no C37 data).
- G1 (pre-dispatch admission guard, calibration-maximum rule): 0/31 alerts on clean `silent` probes; unchanged.
- G2 (post-reply gap detector, calibration-maximum rule): 10/31 alerts on clean `silent` probes, i.e. the
  calibration maximum over 8 calls does not bound the post-reply window of single 8 s captures.

Amendment (G2 only; everything else in C37_PREREG.md stands):
- G2 primary metric becomes the AUC of `g` (deferred16 vs clean `silent` of s1m), with detections / false alarms
  reported at the calibration maximum (as pre-registered) AND at calibration maximum + 0.05 dB (secondary).
- The paper may describe gap auditing only through this AUC and both operating points; no threshold is tuned on C37.

Also recorded: the 3.0 s -> 3.4 s deferred-validity amendment (written into C37_PREREG.md before s1m started).
