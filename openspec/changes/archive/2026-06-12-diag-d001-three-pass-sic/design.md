## Context

D-001 is a High-severity defect: OpenWSFZ achieves ~47% co-channel recovery in the S7 synthetic
scenario versus WSJT-X's ~76%, and 69.7% decode rate against the 42-WAV S6 corpus replay.
Root-cause analysis (2026-06-12) shows the failures are concentrated at exact co-channel
conditions (0 Hz frequency separation); at ≥3 Hz separation, OpenWSFZ and WSJT-X perform
identically. This is a diagnostic experiment, not a production fix — the goal is to isolate the
contribution of pass count as a single variable before committing to a costlier architectural
change.

**Current shim state:** `FT8_SHIM_VERSION = 20260006`, `K_MAX_PASSES = 2`, two-pass
spectrogram-domain SIC with soft SNR-scaled attenuation (Option B, shipped in `20260004`).

**Previous attempt:** PCM-domain SIC (`fix-D001`, version `20260003`) was reverted due to
`0xC0000005` stack overflow crashes and −0.1 pp R&R improvement. The stack overflow was caused
by a 720 KB automatic (stack) PCM residual buffer in `ft8_decode_all`, which combined with the
managed thread pool thread's stack frame to exceed the 1 MB limit. That failure is irrelevant
to this change — we are staying in the spectrogram domain.

## Goals / Non-Goals

**Goals:**

- Quantify the isolated effect of adding one additional spectrogram-domain suppression pass on
  the S7 co-channel recovery rate.
- Keep the change minimal and low-risk: only the pass count constant and its downstream
  accounting change. No new algorithm, no new data structures beyond the additional slot in the
  existing dedup/accumulator arrays.
- Maintain all existing CI tests green.
- Produce a defensible data point to inform the H2 hypothesis decision.

**Non-Goals:**

- This change does NOT attempt to close D-001 entirely — it is a controlled experiment.
- This change does NOT modify the soft SNR-scaled attenuation formula or constants.
- This change does NOT introduce PCM-domain SIC.
- This change does NOT modify candidate search parameters beyond extending existing constants
  to cover the new pass.
- Re-running S7 is part of the experiment, but the R&R study execution itself is out of scope
  for the code change. The QA engineer will run the study post-merge.

## Decisions

### Decision 1 — Pass 2 uses the same parameters as pass 1 (wider net)

**Chosen:** Pass 2 reuses `K_MIN_SCORE_PASS2 = 1`, `K_MAX_CANDIDATES_PASS2 = 200`,
`K_LDPC_ITERATIONS_PASS2 = 50`. No new constant set for pass 2.

**Rationale:** The purpose of this experiment is to test whether *more passes* help, not
whether *different parameters* on pass 2 help. Varying two things at once would confound the
result. If H2 is supported, parameter tuning per pass becomes a follow-on experiment.

**Alternative considered:** Distinct parameters for pass 2 (e.g., tighter score threshold,
more LDPC iterations). Rejected — confounds the diagnostic.

---

### Decision 2 — K_MAX_DECODED ceiling raised by K_MAX_CANDIDATES_PASS2 (200) for pass 2

**Chosen:** `K_MAX_DECODED = K_MAX_CANDIDATES + K_MAX_CANDIDATES_PASS2 + K_MAX_CANDIDATES_PASS2`
(= 140 + 200 + 200 = 540). The existing formula adds one `K_MAX_CANDIDATES_PASS2` slot per
additional pass.

**Rationale:** The cross-pass dedup hash table must accommodate the maximum possible new
unique messages from all passes. An undersized table silently loses results beyond capacity.

---

### Decision 3 — Suppression accumulator arrays: static sizing

**Chosen:** `all_supp_cands`, `all_supp_msgs`, `all_supp_snrs` remain sized at
`K_MAX_CANDIDATES` (140, the pass-0 maximum). Pass 1 decoded signals are also accumulated
for suppression before pass 2; pass 1 can produce at most `K_MAX_CANDIDATES_PASS2 = 200`
signals, so the accumulator could theoretically overflow.

**Guard:** The existing loop guard `if (pass == 0 && n_all_supp < K_MAX_CANDIDATES)` is
extended to `(pass == 0 || pass == 1) && n_all_supp < K_MAX_CANDIDATES`. Any accumulator
overflow beyond 140 is silently discarded — this is acceptable for a diagnostic experiment
(the strongest 140 pass-0/1 signals are suppressed; weaker overflow signals may not be
suppressed before pass 2, which is conservative rather than destructive).

**Alternative:** Increase accumulator arrays to `K_MAX_CANDIDATES + K_MAX_CANDIDATES_PASS2`.
Rejected for this change — unnecessary complexity for a diagnostic. Can be refined if H2 is
confirmed.

---

### Decision 4 — Ft8Decoder.cs per-pass log: loop replaces two hard-coded lines

**Chosen:** Replace the two explicit `_logger?.LogDebug(...)` calls with a `for` loop over
`passCounts.Length`. The loop format string and semantics are unchanged.

**Rationale:** Correct by construction regardless of pass count; avoids a third hard-coded
line that would need updating again if K_MAX_PASSES ever changes. The change is entirely
cosmetic from a behaviour standpoint.

---

### Decision 5 — MaxResults in Ft8LibInterop raised to 540

**Chosen:** `MaxResults` raised from `340` to `540` (= 140 + 200 + 200) to match the expanded
`K_MAX_DECODED`.

**Rationale:** `MaxResults` is the size of the managed result buffer passed to
`NativeDecodeAll`. If `K_MAX_DECODED` grows but `MaxResults` does not, the native shim writes
up to 540 results but only 340 slots are allocated — this is a buffer overrun. Both constants
must stay in sync.

## Risks / Trade-offs

**[Latency increase] → Acceptable for diagnostic; measure in CI**
A third decode pass adds approximately one additional `ftx_find_candidates` + up to 200
`ftx_decode_candidate` calls. Expected overhead: <50 ms on a typical 15 s FT8 cycle. CI timing
budget is generous (13 s). If latency becomes a concern, K_MAX_CANDIDATES_PASS2 for pass 2
can be reduced in a follow-on change.

**[H2 may not be supported] → Known outcome; experiment terminates cleanly**
If S7 recovery improvement is < +2 pp, the experiment is a negative result and the change
should be reverted (or the constants restored to K_MAX_PASSES = 2). The change is trivially
reversible.

**[Suppression accumulator truncation] → Conservative, not destructive**
If pass 1 decodes more than 140 signals (unlikely in practice; pass 0 typically exhausts the
dominant signals), the excess are not suppressed before pass 2. This means pass 2 may
re-decode already-found signals rather than finding new ones — the cross-pass dedup table will
discard these, so no false positives result. Recovery rate is not harmed; it simply gains less
than the maximum possible.

## Open Questions

**Q1:** Is the S7 re-run to be executed manually (Captain + QA engineer) or automated via the
existing `rr_study.py` harness? *(Assumed: manual R&R study run, consistent with NS-001
trigger conditions.)*

**Q2:** What is the minimum improvement threshold to consider H2 "supported" and justify
further pass-count tuning? *(Working assumption from proposal: ≥ +5 pp = supported,
< +2 pp = rejected, +2–5 pp = inconclusive.)*
