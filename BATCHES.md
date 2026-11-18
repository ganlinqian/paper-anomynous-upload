# Batch IDs of the paper and their directories

| Paper ID | Contract family | Runs | Directory |
|---|---|---|---|
| C08 | order; presence (1 s) | 40 + 40 | [data/pi_core/confirmation_study/confirm_20261105_035739_c92be0](data/pi_core/confirmation_study/confirm_20261105_035739_c92be0) |
| C08-I | same, interrupted (reported apart) | 42 | [data/pi_core/confirmation_study/confirm_20261105_032747_8137bb](data/pi_core/confirmation_study/confirm_20261105_032747_8137bb) |
| C09 | hidden bursts, with/without short load | 72 | [data/pi_core/burst_confirmation_study/burstconfirm_20261105_043818_8bdb76](data/pi_core/burst_confirmation_study/burstconfirm_20261105_043818_8bdb76) |
| C10 | hidden `gzip`, with/without legitimate load, traced | 64 | [data/pi_core/wait_confirmation_study/waitconfirm_20261105_051433_3df228](data/pi_core/wait_confirmation_study/waitconfirm_20261105_051433_3df228) |
| C13 | hidden `gzip`, untraced | 32 | [data/pi_core/untraced_wait_study/untracedwait_20261105_061041_b80fac](data/pi_core/untraced_wait_study/untracedwait_20261105_061041_b80fac) |
| C15 | hidden bursts under sustained load | 24 | [data/pi_core/sustained_burst_study/sustainedburst_20261105_063509_c737ee](data/pi_core/sustained_burst_study/sustainedburst_20261105_063509_c737ee) |
| C07, features of C08--C15 | training/held-out, per-run features and predictions | -- | [data/pi_core/confirmation_processing_20261105](data/pi_core/confirmation_processing_20261105), `untraced_processing_20261105`, `sustained_processing_20261105` |
| C24 | adaptive hidden work, next day | 56 | [data/pi_adaptive_desktop/experiments/campaigns/s1_20261106_021046_a5bd83](data/pi_adaptive_desktop/experiments/campaigns/s1_20261106_021046_a5bd83) |
| C25 | clock capping | 24 | [.../campaigns/s3_20261106_024815_0b8db7](data/pi_adaptive_desktop/experiments/campaigns/s3_20261106_024815_0b8db7) |
| C26-T | verify-then-extract, training | 16 | [.../campaigns/s2train_20261106_030428_10f38e](data/pi_adaptive_desktop/experiments/campaigns/s2train_20261106_030428_10f38e) |
| C26-I | verify-then-extract, interrupted by the thermal guard | 11 | [.../campaigns/s2test_20261106_031520_1af941](data/pi_adaptive_desktop/experiments/campaigns/s2test_20261106_031520_1af941) |
| C26 | verify-then-extract, test | 40 | [.../campaigns/s2test_20261106_032920_dddf78](data/pi_adaptive_desktop/experiments/campaigns/s2test_20261106_032920_dddf78) |
| C27 | seen and unseen hidden-work variants | 64 | [.../campaigns/s1b_20261106_035740_995bcb](data/pi_adaptive_desktop/experiments/campaigns/s1b_20261106_035740_995bcb) |
| C28 | duty cycles down to 3.125% | 64 | [.../campaigns/s1c_20261106_065736_99d08a](data/pi_adaptive_desktop/experiments/campaigns/s1c_20261106_065736_99d08a) |
| C29 | low duty with per-session calibration (8 calibration + 64 test) | 72 | [.../campaigns/s1d_20261106_083646_2fa3ac](data/pi_adaptive_desktop/experiments/campaigns/s1d_20261106_083646_2fa3ac) |
| D-T, D, D2 | x86 desktop: training, test, second session | 48, 80, 80 | [data/pi_adaptive_desktop/desktop_em/runs](data/pi_adaptive_desktop/desktop_em/runs) |

Frozen models of C24--C38 are in [data/pi_adaptive_desktop/experiments/models](data/pi_adaptive_desktop/experiments/models), and their freeze receipts in
[data/pi_adaptive_desktop/experiments/freeze_receipts](data/pi_adaptive_desktop/experiments/freeze_receipts); every `FREEZE.json` records the freeze time, the digest of the
model and of the feature code, and the identifiers of the training runs.

## Additional experiment batches

The following directories are below [data/pi_adaptive_desktop/experiments/campaigns/](data/pi_adaptive_desktop/experiments/campaigns/). Test counts exclude the 8 `silent_cal` calls in each complete session.

| Paper batch | Test runs | Directory |
|---|---:|---|
| C30 | 64 | [s1e_20261110_145813_cae180](data/pi_adaptive_desktop/experiments/campaigns/s1e_20261110_145813_cae180) |
| C31 | 64 | [s1f_20261110_160225_823f00](data/pi_adaptive_desktop/experiments/campaigns/s1f_20261110_160225_823f00) |
| C32 | 80 | [s1g_20261110_174804_582e24](data/pi_adaptive_desktop/experiments/campaigns/s1g_20261110_174804_582e24) |
| C33 | 80 | [s1i_20261110_195752_fcf10d](data/pi_adaptive_desktop/experiments/campaigns/s1i_20261110_195752_fcf10d) |
| C34 | 88 | [s1j_20261111_010022_812ec9](data/pi_adaptive_desktop/experiments/campaigns/s1j_20261111_010022_812ec9) |
| C35 | 88 | [s1k_20261111_152850_04b832](data/pi_adaptive_desktop/experiments/campaigns/s1k_20261111_152850_04b832) |
| C36 | 87 | [s1l_20261115_224455_c020b7](data/pi_adaptive_desktop/experiments/campaigns/s1l_20261115_224455_c020b7) |
| C37 | 99 + 16 = 115 | [s1m_20261116_165318_f72e62](data/pi_adaptive_desktop/experiments/campaigns/s1m_20261116_165318_f72e62), [s1n_20261116_175725_b7bebc](data/pi_adaptive_desktop/experiments/campaigns/s1n_20261116_175725_b7bebc) |
| C38 | 88 | [s1p_20261117_004119_b9ca01](data/pi_adaptive_desktop/experiments/campaigns/s1p_20261117_004119_b9ca01) |
| C38 training session | not C38 test | [s1o_20261116_235119_469cca](data/pi_adaptive_desktop/experiments/campaigns/s1o_20261116_235119_469cca) (68 recorded calls) |

C38 envelope training uses 271 recorded calls: C35 (96) + the first C37 session (107) + the separate training session (68). C37/C38-related valid Pi records total 295 (107+24+68+96), including calibration/training; do not label all 295 as test trials.

The interrupted C33 attempt [s1h_20261110_194501_ca1dad](data/pi_adaptive_desktop/experiments/campaigns/s1h_20261110_194501_ca1dad) and interrupted C36 attempts [s1l_20261115_162746_babc18](data/pi_adaptive_desktop/experiments/campaigns/s1l_20261115_162746_babc18), [s1l_20261115_172344_ee1d0d](data/pi_adaptive_desktop/experiments/campaigns/s1l_20261115_172344_ee1d0d), and [s1l_20261115_203602_883fbb](data/pi_adaptive_desktop/experiments/campaigns/s1l_20261115_203602_883fbb) are retained with available records/failure logs, but are not included in the completed test counts. C36's accepted batch contains 95 valid calls: 87 tests and 8 calibration calls.

For C33, the five unseen-tool cells are 40 calls; the reported AUC uses all 80 tests, including 8 full-speed 1 MiB gzip calls. Keep these denominators separate.

C36 power data, synchronization and outputs are under [data/power_c36/](data/power_c36/); C37 failed-power QA and historical analyses are under [data/extended/power_c37/](data/extended/power_c37/). C37 power is invalid and excluded from paper endpoints. C38 analysis and pre-collection analysis freeze are under [data/extended/c38/](data/extended/c38/).

R1 public-trajectory rules are [code/r1/r1_coverage.py](code/r1/r1_coverage.py); saved v1/v2 outputs and exact upstream input specifications are under [data/r1/](data/r1/).
