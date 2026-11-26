# LC-BASE: where the lean decoder stands against the classic one (recorded audio)

**To:** QA (Engineer may run any part as a QA peer)
**From:** Architect, 2026-11-26
**Why:** the Product Owner wants the lean decoder as the base for new decode-rate work, and asked first for "where we are now". This is a measurement, not a gate: no bars, no verdict. QA reports the numbers; he decides what to work on.
**Approved:** Product Owner, 2026-11-26 ("yes to both": include the 20 m slice; leave the 18 and 19 November nights unused).
**Process:** the light process of [`plan.md`](plan.md) §6 and the minimal-test rule (2026-11-24): one run per arm, no confidence intervals, no amendments. If something here is wrong or cannot be done, QA fixes the obvious and notes it in the result.
**Limit:** recorded audio only. Total run time under 2 h (the Product Owner's limit), so no separate go is needed.
**Not needed first:** DR-3. The harness selects the engine per run (`--engine`); the station's default does not matter here.

---

## 1. Build and harness

- **One build for both arms:** `feat/threads-default-auto` `9027616e` (QA-reviewed, HK-039 record `eb86d2fe`), the harness `Ft8.FitProbe.exe` built with `-p:HasLean=true` as for DR-2d/2e. Pin the `libft8.dll` SHA-256 and assert it before and after every run, as `dr2d_run.py` does.
- **Read CI on `feat/threads-default-auto` first.** If it is red for a reason other than infrastructure, stop and tell the Architect.
- Station PC, nothing else heavy running (the runner's `busy()` check).

## 2. The arms

| Arm | Engine | Flags |
|---|---|---|
| **C** | classic | DR-0's A6 exactly: `dr2d_run.py`'s `COMMON` + `--threads 8` + `--xc-prior 1` and the XC threshold from the station's config, as A6 |
| **L** | lean | `COMMON` + `--engine lean --lean-threads 16 --effort normal` (= DR-2e arm L5; decodes are identical at every thread count) |

## 3. The slices

| Slice | Night (`artefacts/`) | Band | Window |
|---|---|---|---|
| **S40** | `20261114_2312_endurance_run-gathered` | 40 m | **Not re-run.** Reuse A6 (`dr0-result.md`) and L5 (`dr2e-result.md`), 170 cycles from `261115_072930` |
| **H40** | `20261028_2233_endurance_run-gathered` | 40 m | 240 cycles `261029_021045` to `261029_031030` (QA's busiest-hour search, `test-set.md`: 8,983 WSJT-X decodes) |
| **H20** | `20260808_live_run_0016-8080` | 20 m | QA finds the busiest 240 contiguous cycles, same method as `test-set.md` (per-cycle count of `wsjt-x/ALL.TXT` timestamps, every cycle's `owsfz/wav/` file present), and records it in `test-set.md` |

- Audio replayed: `owsfz/wav/`, scored against the same night's `wsjt-x/ALL.TXT`, as DR-0. Warm-up: the cycle before the window.
- 🛑 `20261118_1954` and `20261119_2204` stay unused (held back as fresh audio for checking the first improvement).
- **H20 caveat, to repeat in the result:** recorded 2026-08-08, before today's audio routing. The C-vs-L comparison is fair (same audio); its rate against WSJT-X is not comparable with the 40 m slices.

## 4. Pilot, then length

1. **Pilot:** 10 cycles of C and of L on H40, and 10 of C and L on H20. This checks that the harness reads the August WAVs and gives the time per cycle.
2. **Reproduction check (free with the pilot):** also 10 cycles of C on S40. Its `matched` and `ours` for those cycles must equal A6's first 10 cycles (A6 reproduced itself exactly in DR-0). If they differ, the new build's classic path is not A6's: stop and tell the Architect.
3. **Length:** if the pilot projects all four runs under 100 min, run 240 cycles per slice. Otherwise cut both slices to the same shorter length, never below 120 cycles, and state it.

Expected from the DR-0/DR-2e logs: C about 7 to 8 s per cycle, L about 1.6 s, so about 75 min in total.

## 5. What is reported (per slice, aggregates only)

### 5.1 The headline table (S40 rows copied, H40 and H20 measured)

As DR-0: `rate`, `ours_only`, `matched`, `ours`, `cpu_net`, `last_p95`, `abandoned`, for C and L, and **L − C** for `rate` and `ours_only`.

### 5.2 Where the decodes differ

Computed by code over the per-row files in `D:\Projects\claude\_qa-scratch\lc-base\` (HK-037: message text never leaves the function that reads it; the working files are KEPT). Counts only:

1. **Overlap of matched decodes:** both, C only, L only.
2. **WSJT-X-only for L** (WSJT-X decoded it, L did not): this is the room for improvement. Also **C-only** (what L gave up). Split each by:
   - **SNR** (WSJT-X's `ALL.TXT` field): ≥ −10, −10 to −15, −15 to −18, −18 to −21, < −21 dB
   - **crowding:** another WSJT-X decode within ±50 Hz in the same cycle (crowded) or not (alone)
3. **L's matched decodes by where they came from:** round 0 tier A, tier B, CQ-AP; rounds 1, 2, 3; XC. Use whatever tag the harness already writes; if it writes none for a split, say so and skip that split (no code change for this).
4. **`ours_only` for L**, split the same way as item 2 (SNR, crowding).

### 5.3 Close-out

- Result file `qa/decoder-rebuild/lc-base-result.md`, in DR-0's result format. Copy the run folders to the root `qa/rr-study/results` (standing rule) and name the path.
- No ruling is needed. The Architect reads the result and proposes the first improvement step from the §5.2 split.

## 6. The Architect's expectation (written before the run)

L about 2 to 4 pp below C on H40, similar on H20; `ours_only` about equal. Most of L's WSJT-X-only decodes are crowded signals and signals weaker than about −18 dB. (The bias to watch: I tend to expect one findable local cause.)
