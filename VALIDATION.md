# Artifact validation

Validation was performed on this artifact, with Python 3.12.16, NumPy 2.5.5, SciPy 1.18.1, scikit-learn 1.9.1 and PyArrow 26.0.1. Offline verification uses at most four numerical-library threads; no model was trained and no new experiment was collected.

- C30–C36: all seven statistical scripts completed. Recomputed numerical fields matched the saved original analyses within 1e-10.
- C37: valid EM results matched the original analysis; invalid power results are deliberately excluded from reproduction. Historical invalid values and failed timebase QA remain labelled as such.
- C38: all numerical fields of the prospective analysis matched the saved original result. Frozen-feature replay differed from saved C35 scores by at most 6.7e-15 and from C38 scores by 0. Both frozen model hashes and both envelope feature-code hashes were verified through the source-to-release hash map.
- C38 composite: sustained masking 31/32, ordinary hidden work 24/24, false alarms 2/32. SHA-256 calls are 5/8 for C35, 3/8 for C38, and 8/8 for their OR rule.
- C36 power: the pre-specified baseline, exploratory feature analyses and post-hoc matched-false-alarm comparison were recomputed from the exact meter CSV. Their numerical fields matched the stored originals within 1e-10.
- R1 v2: both 200-trajectory samples and both full public sets were rerun from the original input files whose hashes match the pinned upstream objects. Counts, shares and bootstrap intervals matched the stored original output within 1e-10.
- Every chunked recording was reconstructed and checked against its original SHA-256. Each distributed chunk is at most 7,000,000 bytes.

The checks reproduce the supplied measurements and analysis outputs. Source freeze hashes are retained in their receipts; `ARTIFACT_MANIFEST.json` covers the distributed files. Run `python verify_artifact.py` for the integrity and endpoint checks; success prints `ALL CHECKS PASSED` and exits with code 0.

- A clean checkout without reconstructed recordings, downloaded public inputs or prior outputs passed all 16 offline entry checks. Public R1 analysis passed using inputs whose SHA-256 matches the pinned upstream objects.
- Five selected figures were regenerated from stored statistics and features with the packaged plotting helpers. Both cropped raw-IQ examples were inspected successfully.
- A modified README fails integrity verification. Python optimization modes are rejected explicitly rather than reporting a false success.
- Corpus accounting was checked independently: 819 core contract calls plus 607 C30–C36 calls gives 1,426; 16,481 core receiver streams plus 1,214 additional streams gives 17,695.
