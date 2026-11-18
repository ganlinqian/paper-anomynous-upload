# The Telltale EM corpus

Data access: [Figshare](https://figshare.com/s/b540ed95b88d720ed455).

The submitted manuscript reports the core archive through C36 as **9.99 TB in 17,695 SHA-256-verified receiver streams**. Its 1,426 Pi captures in completed batches include 158 training/development calls as well as test calls. C37/C38 add a separate 295 valid Pi calls (107+24+68+96), including training and calibration; they are not all tests. See `BATCHES.md` for the 115 C37 and 88 C38 test denominators.

For context, the earlier archive through C29 comprised approximately 9.6 TB in 16,481 receiver recordings:

| Campaign | Host | Receiver streams | Approximate raw IQ |
|---|---|---:|---:|
| Benign and attack skills, April 2026 | x86 desktop and Raspberry Pi | 9,555 | 4.22 TB |
| Tool workloads, April 2026 | Raspberry Pi 4 | 1,193 | 0.95 TB |
| Re-selected bands and adversarial runs, May 2026 | x86 desktop | 3,595 | 3.92 TB |
| Design pilots, October 2026 | Raspberry Pi 4 + OpenClaw | 500 | 0.08 TB |
| Contract batches C07–C29, November 2026 | Raspberry Pi 4 + OpenClaw | 1,638 | 0.42 TB |

The x86 desktop study additionally retains frame features and raw-buffer digests for 236 runs (including pilots, training, D and D2).

## What is distributed here

- The complete extracted-feature release (5,580 NPZ/NPY files, 1.06 GB, with `FILE_MANIFEST.csv`, `SOURCE_ASSOCIATIONS.csv`, and `SHA256SUMS`) is hosted at <https://figshare.com/s/b540ed95b88d720ed455>.
- Capture and analysis source/protocol snapshots; pre-collection freeze receipts and frozen model parameters.
- Per-call records, frame features, C38 envelope-modulation features, predictions and statistics for the paper batches, with available interrupted-attempt records.
- Two cropped C26 raw IQ recordings; each contains signed 8-bit complex samples at 20 MS/s, one compliant and one violating installer execution.
- The valid C36 inline power-meter CSV, synchronization records and analyses. It contains a measurement-column header followed only by numeric telemetry, not account or device-owner fields.
- R1 descriptive rule outputs, code and pinned public input specifications. The original public datasets are fetched separately and verified by SHA-256.

The multi-terabyte raw IQ archive is **not** fully included. Statistical reproduction uses the released numerical features and predictions; the two raw examples demonstrate the recording format. Large distributed recordings are split below 7 MB per chunk; run `python tools/reassemble.py` and verify the original hashes from `assets/chunks.json`.

Source freeze digests are connected to distributed-file digests by `ORIGINAL_HASHES.json`, which contains only repository-relative paths and SHA-256 values. `ARTIFACT_MANIFEST.json` specifies the exact distributed bytes. C37's failed timebase power endpoint remains documented as invalid and is excluded from scientific claims.
