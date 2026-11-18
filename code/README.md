# Code entry points

Run commands from the repository root using the environment described in [README.md](../README.md).

| Purpose | Entry point | Inputs | Output directory |
|---|---|---|---|
| Integrity and saved endpoints | `python verify_artifact.py` | Released files and manifests | Console |
| Selected core-study numbers | `python check_numbers.py` | Stored C08–C29 and x86 statistics | Console |
| Frozen C35/C38 score replay | `python code/extended/fixed_feature_replay.py` | Released features, parameters and hash map | `outputs/replay/` |
| C30–C36 statistics | `python code/pi_adaptive_desktop/scripts/c30_stats.py`, through `c36_stats.py` | Campaign predictions | `outputs/stats/` |
| C37 valid EM results | `python code/extended/analyze_c37.py` | Campaign records and features | `outputs/power_c37/` |
| C38 prospective results | `python code/extended/analyze_c38.py` | Frozen detector predictions | `outputs/c38/` |
| C36 power comparison | Scripts in `code/power_c36/` and `code/extended/power_matched_fa.py` | Reconstructed meter CSV and clock pairs | `outputs/power_c36/` |
| R1 public-call coverage | `python code/r1/r1_coverage.py external/r1 outputs/r1 v2` | SHA-256-pinned public inputs | `outputs/r1/r1-rules-v2/` |
| Selected stored-data figures | `python tools/reproduce_figures.py` | Released statistics and frame features | `outputs/figures/selected/` |

These entry points perform offline analysis without fitting models or using acquisition hardware. R1 inputs require a separate public download. Reconstruct the meter CSV before power analysis with `python tools/reassemble.py`. Optional figure generation uses `requirements-figures.txt`.

Campaign `source/` directories and acquisition/coordinator scripts preserve the collection and processing procedures. New acquisition needs the documented hardware, capture libraries, device addresses and local configuration. They are source evidence rather than additional steps in the offline reproduction sequence.

The figure command regenerates core detector comparisons, burst-budget curves, temporal examples, x86 mixed-contract scores and exploratory received-power comparisons. Other historical plotting scripts remain source snapshots; this command does not regenerate every manuscript illustration.
