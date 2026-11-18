# Telltale — anonymous research artifact

This repository accompanies **What Did Your AI Agent Really Run? Out-of-Band Electromagnetic Evidence for Agent Tool Calls Auditing**.

Extracted features and sanitized run metadata of all recordings
(1.06 GB; Raspberry Pi and x86 desktop):
<https://figshare.com/s/b540ed95b88d720ed455>

See the dataset README there for file formats, labels, and record associations.
The raw IQ archive (9.99 TB) is too large for the review release and will follow.

The release includes the earlier C07–C29 and x86 studies, C30–C38, the C36 inline power-meter comparison, and R1 contract-family coverage of public coding-agent trajectories. Models, trial records, frame/envelope features, predictions, statistics, pre-registration receipts, and available interrupted-run records are included. The raw-IQ release consists of two examples; the released numerical features and predictions support the statistical reproduction described below. See [DATASET.md](DATASET.md) for the corpus boundary.

## Start here

- [Directory map](#layout): locate code, measurements and models.
- [Runnable entry points](code/README.md): distinguish offline reproduction from hardware collection snapshots.
- [Experiment navigation](#experiment-navigation): find the evidence for a paper result.
- [Batch index](BATCHES.md): exact campaign paths, test counts, calibration and interrupted attempts.
- [Dataset boundary](DATASET.md): included features, raw examples and omitted recordings.
- [Validation record](VALIDATION.md): reproduced results, integrity checks and limitations.
- [Quick verification](#quick-verification): check the download without scientific Python dependencies.
- Reproduction: [extended EM results](#reproduce-the-extended-results), [power comparison](#c36-power-comparison), [public trajectories](#r1-public-trajectories).

Run commands from the repository root. Scripts write generated results under `outputs/` and downloaded public inputs under `external/`; both are excluded from the release. Offline EM and power analysis needs no acquisition hardware, account credentials or model training.

## Quick verification

Python 3 is sufficient for hashes, batch sizes, saved endpoints, and recording chunks:

```sh
python verify_artifact.py
```

Successful verification ends with `ALL CHECKS PASSED` and exits with code 0. A failed integrity or endpoint check exits with a nonzero code. Run without Python optimization flags (`-O` or `-OO`); the verifier rejects modes that disable assertions.

The distributed files are covered by `ARTIFACT_MANIFEST.json`. `ORIGINAL_HASHES.json` contains only repository-relative paths and source/release SHA-256 digests. It connects the source digests recorded in freeze receipts to the corresponding distributed files.

## Reproduce the extended results

The validated environment is Linux with Python 3.12. The dependency versions are pinned to the versions used for the checks in [VALIDATION.md](VALIDATION.md). A virtual environment is recommended; for example, in a Linux shell:

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
export OPENBLAS_NUM_THREADS=4 OMP_NUM_THREADS=4 MKL_NUM_THREADS=4
python code/extended/fixed_feature_replay.py
python code/extended/analyze_c37.py
python code/extended/analyze_c38.py
```

The fixed-feature replay uses saved frame/envelope features and frozen C35/C38 parameters, performs no fitting, and checks the saved predictions. It reproduces C38's composite endpoint: sustained load 31/32, false alarms 2/32, ordinary hidden work 24/24. Original frozen model and feature-code hashes are checked through `ORIGINAL_HASHES.json`.

For C30–C36, run `python code/pi_adaptive_desktop/scripts/c30_stats.py`, and analogously `c31_stats.py` through `c36_stats.py`. These read the released predictions, recompute the registered statistics and descriptive comparisons, and write to `outputs/stats/`. The common data paths and latest-campaign pointers are repository-relative. No collection or model training is needed.

Typical local validation runs take a few minutes after dependencies and inputs are available. The release contains approximately 716 MB of files; recording reconstruction adds approximately 181 MB. Allow additional space for the Python environment and generated figures.

| Analysis | Main generated result |
|---|---|
| C35/C38 score replay | `outputs/replay/fixed_feature_replay.json` |
| C30–C36 | `outputs/stats/c30_stats.json` through `c36_stats.json` |
| C37 valid EM | `outputs/power_c37/c37_results.json` |
| C38 | `outputs/c38/c38_results.json` |
| C36 power | `outputs/power_c36/c36d_power_baseline.json` |
| R1 | `outputs/r1/r1-rules-v2/r1_coverage.json` |

`python check_numbers.py` prints selected C08–C29 and x86 desktop results from saved statistics.

## C36 power comparison

Large recordings are stored as individually checksummed chunks below 7 MB for anonymous hosting. Reassemble them first:

```sh
python tools/reassemble.py
python code/power_c36/c36d_power_baseline.py
python code/power_c36/c36d_power_explore.py
python code/extended/power_matched_fa.py
```

These use the same valid 95 C36 calls (87 test plus 8 calibration), the meter CSV with English column labels, original clock pairs and alignment parameters. Only the CSV header was translated; every numerical data row is byte-identical to the source recording. `assets/chunks.json` records both the original and distributed CSV digests. The difference baseline is pre-specified; the alternative features are exploratory. Matched-false-alarm thresholds use the test negatives and describe separability, not a deployable frozen operating point.

The attempted C37 power endpoint failed timebase QA and is **excluded**. Its saved historical analysis and QA remain under `data/extended/power_c37/` for transparency; the invalid raw meter recording is not included. `analyze_c37.py` reproduces the valid EM analyses and skips unavailable invalid power inputs.

## R1 public trajectories

`data/r1/` contains the saved v1/v2 rule outputs and spot checks. The upstream public inputs are specified by pinned revisions, SHA-256 and file sizes in `data/r1/public_sources.json`; both upstream object hashes were checked against the exact original inputs.

```sh
python tools/fetch_public_r1.py
python code/r1/r1_coverage.py external/r1 outputs/r1 v2
```

This deterministic descriptive rule analysis uses no model labels. The 200-trajectory samples and full public shards were reproduced for this release. The script also computes the published trajectory-cluster bootstrap intervals. The public trajectory files remain upstream rather than being republished here.

## Selected figure reproduction

Five figures can be regenerated from the released statistics and features without raw-IQ processing:

```sh
python -m pip install -r requirements-figures.txt
python tools/reproduce_figures.py
```

Outputs are PDF/PNG files and `figure_report.json` under `outputs/figures/selected/`: core detector comparisons (`fig_results`), burst-budget curves (`fig_budget`), temporal examples (`fig_traces`), x86 mixed-contract scores (`fig_contracts`) and exploratory received-power comparisons (`fig_loadpower`). This is the supported stored-data subset; additional historical plotting scripts are preserved as source snapshots.

## Layout

| Path | Contents |
|---|---|
| `code/pi_core/` | Earlier coordinator, capture, feature, model and evaluation code |
| `code/pi_adaptive_desktop/` | C24–C38 collection/processing snapshots, statistical scripts, x86 analysis |
| `code/desktop_capture/` | Desktop HackRF capture helpers |
| `code/extended/` | C37/C38 analyses, fixed-feature replay, matched-power and spectrum checks |
| `code/power_c36/` | Meter alignment and power analyses |
| `code/r1/` | Fixed public-trajectory classification rules |
| `code/third_party/` | Plotting style helpers |
| `data/` | Records, models, features, predictions, freezes, statistics, power alignment and R1 outputs |
| `protocols/` | C37/C38 preregistrations; the C37 amendment is also retained with its analysis data |
| `assets/chunks.json` | Original recording sizes/digests and chunk digests |
| `samples/` | Raw-IQ descriptions and inspection script; restore recordings from chunks |
| `tools/` | Checksum-verified recording reconstruction and public-input download tools |
| `ARTIFACT_MANIFEST.json` | Paths, sizes and SHA-256 of distributed files, excluding the manifest itself |
| `ORIGINAL_HASHES.json` | Original-to-release digest mapping for added source materials |
| `verify_artifact.py` | Integrity, batch-count and saved-endpoint checks |

## Experiment navigation

| Result or material | Location |
|---|---|
| Earlier Pi studies | [`data/pi_core/`](data/pi_core/), [`code/pi_core/`](code/pi_core/) |
| C24–C38 records | [`campaigns/`](data/pi_adaptive_desktop/experiments/campaigns/); exact IDs in [BATCHES.md](BATCHES.md) |
| Frozen models and receipts | [`models/`](data/pi_adaptive_desktop/experiments/models/), [`freeze_receipts/`](data/pi_adaptive_desktop/experiments/freeze_receipts/), campaign-local `FREEZE.json` |
| C30–C36 statistics | [`stats/`](data/pi_adaptive_desktop/stats/), [`analysis scripts/`](code/pi_adaptive_desktop/scripts/) |
| C37 and C38 analyses | [`power_c37/`](data/extended/power_c37/), [`c38/`](data/extended/c38/), [`extended scripts/`](code/extended/) |
| Valid C36 power comparison | [`power data/`](data/power_c36/), [`power scripts/`](code/power_c36/); restore the CSV with `tools/reassemble.py` |
| R1 coverage | [`classification rules`](code/r1/r1_coverage.py), [`saved outputs and input hashes`](data/r1/) |
| Desktop experiments | [`desktop data/`](data/pi_adaptive_desktop/desktop_em/), [`desktop code/`](code/pi_adaptive_desktop/desktop_em/) |
| Prospective registrations | [`protocols/`](protocols/), campaign-local freeze receipts and source snapshots |

Within each campaign, `RESULTS.json` lists calls and acquisition metadata, `FREEZE.json` identifies frozen analysis inputs, and `source/` preserves source snapshots. Available `features/`, `env/` and `predictions*.csv` files hold derived inputs and detector outputs. File availability varies by study. Interrupted attempts and failed QA must not be counted as completed tests. The C37 folder name contains `power`, but its power endpoint is invalid; only its labelled valid EM results are used.

`BATCHES.md` maps paper IDs to exact directories and separates tests, calibration, training and interrupted attempts. `DATASET.md` describes the corpus boundary. `VALIDATION.md` records what was reproduced.

## Raw examples and hardware scripts

After `python tools/reassemble.py`, `samples/*.iq.gz` contain signed 8-bit interleaved I/Q at 20 MS/s for one compliant and one violating C26 installer call. `samples/crops.json` supplies crop boundaries and uncompressed digests. `python samples/inspect_sample.py samples/*.iq.gz` computes frame spectra; this is optional raw processing, not part of the quick check.

Hardware acquisition scripts are preserved as source/protocol evidence and require your own equipment and configuration. Hardware settings use documentation addresses and explicit configuration parameters such as `<WORKSPACE>`, `<SSH_KEY>`, `<CAPTURE_ROOT>`, `<CAPTURE_LIBRARY>` and `<CALIBRATION_ROOT>`. Configure these parameters for your own equipment before new collection; offline reproduction above needs no hardware or SSH access.

## Licensing and review snapshot

Original software and its documentation are licensed under MIT. Original experimental data, derived numerical features, predictions, detector parameters and analysis outputs are licensed under CC BY 4.0. Third-party code and public datasets retain their upstream licenses. [LICENSE](LICENSE) defines the scope and attribution requirements for each material type. The vendored plotting helpers include their [upstream MIT notice](code/third_party/scientific-visualization/LICENSE.md).

Measurements use controlled devices and synthetic workloads. This artifact provides a fixed snapshot for peer review of the accompanying manuscript.
