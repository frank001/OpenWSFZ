# QA code review: COH-FB-AUDIO B1, `9ef703d0` (branch `dev/coh-fb-audio`, base `origin/main` `453d3d02`, v0.65): APPROVED with notes

Reviewed-commit: 9ef703d0fa81d5c2324a31f3d412fe8c233e7f74
Verdict: APPROVED

Reviewed 2026-10-27 20:00:58Z (`date -u`). Spec `fc642fe2` §5, §5a, §5b (Amendments 1 and 2). Diff `git diff origin/main...9ef703d0`: 13 files, 796 insertions, 20 deletions. **Empty under `native/`** (0 lines). The branch carries the probe pair `e85b6c33` / `e5b90320` (cherry-picked) under the new commit.

## What was checked, and found correct
- **Config key** (`DecoderConfig.cs`, `Abstractions/CoherentFallbackAudio.cs`): constructor default `Residual`, init property default `Residual`, enum serialised by name through `JsonStringEnumConverter<T>`; an absent key (and a missing `decoder` section) reads `Residual`. Plumbed at `Program.cs` initial and `OnSaved`, read once per cycle in the decoder (`audioMode`). The bare decoder object starts at `Original`, so any host that does not call the setter behaves as `main`; the daemon sets the configured value before the first cycle. No Settings control. Overlay test present (HK-035).
- **Env switch removed**; `Select()` keeps the probe's step-down (third pass `ran` and buffer present, else residual pass completed, else original).
- **Original** hands the fallback the same array reference as `normalisedPcm` (decoder test on the reference).
- **Both**: sequential, residual first, then the original audio on `budgetMs` minus the first run's elapsed; not started if nothing is left (candidates counted abandoned); original run once when the residual is unavailable; first-run fault publishes nothing, second-run fault leaves the first. The merge equals the offline union QA computed (distinct payloads of either run; residual row kept where both found it); `CoherentFallbackSelector.Select` only reads `NewGated` rows, so handing it the merged set equals handing it a single run's rows in the one-run cases. `PayloadKeyBytes` is a named constant. No threading hazard: the arrays are read-only and the runs are sequential.
- **Log line**: trailing `audio=` plus, in Both, `fromOriginal`, `fromResidual`, `inBoth`; the final period is kept.
- **VERSION** 0.66, README and REQUIREMENTS anchors, FR-099/FR-100, changelog row 1.62; Developer ran the version-doc, bump (will demand the OpenSpec proposal, QA's), G3 and delay-sync checks. `pre_merge_check.py` is the Captain's, run by QA later from a clean checkout.
- **Tests**: Developer reports the full Windows suite green (Ft8 643, Daemon 929, Web 437, Config 185, Rig 41, Audio 40, E2E 9, TestSupport 12, LicenseInventory 24, Traceability 34); not re-run by QA. Selector, label, merge (fixed result sets), decoder-level (Original reference, Residual/Both buffers, Both with the residual unavailable run once), config and API overlay tests are present.

## Notes (none blocks R0 or the B2 replay)
- **N-1:** no decoder-level test of the Both path where the shared budget is spent before the second run (only `Stats_CombineAndNotRun` on the stats). B2 will show whether it ever happens (margin to 13 s); add the test before merge if the Captain picks Both.
- **N-2:** where the residual run's row for a payload is an edge row and the original run's row is not, the merge drops the original (non-edge) row, so `publishedEdge` can read slightly high. No effect on which payloads are published.
- **N-3:** in Both, if the residual run (first) faults, the original run is not attempted and nothing is published, as for a single faulting run today. Acceptable; stated for the record.
- **Harness (QA's, not the Developer's):** Replay81 needs `--cohaudio`, the `both(...)` label and the three counts in its fallback-line regex; QA adopts the Developer's scratch patch (`HAS_COHAUDIO`) before B2.
- Not in this review and still to come: QA's OpenSpec change (the proposal the bump check wants), `pre_merge_check.py`, the Captain's push go and merge sign-off.
