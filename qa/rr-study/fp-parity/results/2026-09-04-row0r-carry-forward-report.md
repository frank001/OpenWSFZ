# `AWGN-FP` Amendment 3 A3.2 — ROW 0r result: the M1 decode set does **NOT** survive the shim bump

**QA, 2026-09-04 ~13:52Z** (`date -u`, HK-017). Spec:
`qa/rr-study/2026-09-02-1906-architect-to-qa-spec-awgn-fp-offline-replay.md` **Amendment 3, A3.2**.
Execution: `qa/rr-study/2026-09-04-1322-architect-to-qa-execution-pack-post-shim-bump.md`, block
**P2**.

🔴 **Headline: ROW 0r FIRES.** 246 of 4,000 M1 S5 slots (246 of the 435 event slots — 56.6%) have
a decode set that differs between the `20260049` and `20260050` binaries. **Per A3.2: M1–M4, ROW
0q, and ROW 0m are VOID on `20260050`** and must be re-run before P3 proceeds — with one row
(ROW 0q) already re-run below, and one (ROW 0m) flagged for adjudication rather than silently
carried or silently voided (§4).

🛑 **The "additive export, never called in the decode path" argument is explicitly barred from
substituting for this row (A3.2) — and this result is exactly why: something in the decode path
did change.** No root-cause investigation was performed (barred by A3.2 — "do not investigate why
they differ… that is a new pre-registration, not a patch to this one"); §2 below reports *what*
differs, mechanically, without hypothesising *why*.

`git diff --stat -- src/ native/`: **empty** (verified before this report; ROW 0r's own
instrumentation is `tests/OpenWSFZ.Ft8.Tests/Row0rCarryForwardTests.cs` and
`qa/rr-study/fp-parity/*.py` only).

---

## 0. A disclosed deviation from A3.2's literal method, and why

A3.2 reads: *"decode every slot twice, once per binary."* This session could not do that literally,
for a structural reason found while attempting it, disclosed here rather than worked around
silently:

**`Ft8LibInterop`'s ABI self-test (`ExpectedShimVersion`) is a hard-coded compile-time constant —
currently `20260050`.** Loading the old `20260049` DLL through a build of the *current* source
tree throws in `LoadAndVerify()` before any decode call is reachable (`Ft8LibInterop.cs:1192-1197`).
There is no live "old binary, new source" combination reachable without a second checkout/build —
and `AwgnFpReplayTests.cs`'s own `AssertBinaryPin()` hard-codes the *old* pin on every Fact in that
class (by design — AWGN-FP Amendment 3 Ruling 1: *"the pin moves behind its trait; it is NOT
re-pinned… stays the `20260049` identity of every landed row"*), so that class cannot decode on
`20260050` either.

**What was done instead**, methodologically equivalent, chain-of-custody verified at each step:

1. **"Before" (`20260049`):** the already-recorded, git-tracked
   `qa/rr-study/awgn-fp-replay/results/m1m4_s5_{slots,decodes}.csv`, produced by commit `4a7fb3d`
   (`qa(awgn-fp): run M1-M4 at full N`), whose own build's `ROW 0a` passed against `20260049` at
   the time. **Re-verified today**, not assumed:
   - `git diff --stat 4a7fb3d HEAD -- <those two files>` → **empty** (byte-identical since).
   - The `20260049` win-x64 DLL extracted as a real artefact
     (`git show 3b52608:src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll`) and its SHA256 asserted
     against `PinnedShaWinX64` (`ce02c7ba…153e`) → **MATCH**.
2. **"After" (`20260050`):** a **fresh** decode of the identical `_work/m1m4_s5/` WAV population
   (4,000 files, same corpus, unmodified), run by a **new** test class,
   `tests/OpenWSFZ.Ft8.Tests/Row0rCarryForwardTests.cs` (current `main`, current binary, **no**
   worktree, **no** second checkout) — chosen as a *new* file rather than a Fact appended to
   `AwgnFpReplayTests.cs` precisely so as not to touch that class's own historical pin. Same
   process configuration as the original M1M2M4 Fact: `SetApBits([], [])` cleared before every
   slot, one `DecodeAll` per slot, **no** `NormalisePcm` applied (that repair is ROW 0n, explicitly
   out of scope here per the P2/P3 split). Its own SHA256 (`6b2e16a6…4f85c`) asserted against the
   currently-committed win-x64 DLL before decoding. **4,000/4,000 slots decoded, 0 failures, 3m48s.**

This is **not** a substitute for A3.2's method — it is the same comparison (identical population,
identical process configuration, two binaries) with the "before" decode pass supplied by an
already-verified prior run instead of a repeated live one, because a repeated live one is not
reachable without disproportionate machinery for what A3.2 calls a carry-forward check.

## 1. Step 3 — population match (prerequisite for a valid diff)

Both CSVs cover the same **4,000** slots (`(scenario, part, trial, seed)` keys) — verified equal
as sets before any per-slot compare was attempted, per A3.2's own step 3 discipline (no sampling,
no truncation, and no diff attempted against a mismatched population).

## 2. Step 4–5 — the decode-set diff, mechanically

**Population:** 4,000 slots. **435 carry a decode** (an "event," unchanged from the original M1
report). **0 of those 435** have a *different number* of decodes between binaries — every event
slot decodes the same **count** on both. **0 of those 435** have any change to `freq_hz`, `dt_s`,
or `reported_snr_db` — every decode's numeric fields are bit-for-bit identical across the bump.

**246 of the 435 event slots (56.6%) have a different decoded *message text*.** This is the entire
content of the fire — no slot appears or disappears, no frequency, timing, or SNR value moves; the
difference is confined to what string the decoder reports for the callsign portion of the message.
Characteristically (visible in the sample already inspected, not re-quoted here — see §3 on NFR-021
handling), the `20260049` decodes frequently carry an **unresolved-hash placeholder** token where
the `20260050` decodes carry a **resolved-looking** (but, on this noise-only population, still a
false-accept) token. **This is a factual description of what changed, not a hypothesis about why —
no root-cause investigation was performed, per A3.2's explicit bar.**

**FIRES iff any slot's decode set differs → confirmed: 246 > 0 → ROW 0r FIRES.**

## 3. NFR-021

Both new artefacts (`qa/rr-study/fp-parity/results/m1m4_s5_20260050_decodes.csv`, and this
finding's own raw `row0r_carry_forward_results.txt`, which printed the first 10 differing slots'
message text for the working diagnosis) contained callsign-shaped tokens — **361** in the decode
CSV, **13** in the results text, all decoder output on a noise-only population (guard-checked
against the render's own `truth.csv`, whose `message_text` column is empty for every S5 row — 0 of
0 possible collisions). Redacted via `qa/rr-study/fp-parity/redact_row0r_decodes.py` (same method
as the existing `redact_m1_m4_decodes.py`: import the scanner, not reimplement it; byte-level
UTF-8/CRLF-preserving rewrite; re-scan to 0/0), using a **new placeholder infix `<RDCTRnn>`**
distinct from ROW 0's `<RDCTnn>` and M1–M4's `<RDCTMnn>` so the three passes' tokens are never
confused if read together. Map: `qa/rr-study/fp-parity/REDACTION-MAP-ROW0R.md`. **Re-scanned to
0/0 across every file under `qa/rr-study/fp-parity/`.**

🔴 **A consequence of this redaction, disclosed rather than silently accepted:** because the
"before" (`<RDCTMnn>`) and "after" (`<RDCTRnn>`) CSVs were redacted **independently**, each against
only its own distinct-token list, their placeholder numbering is **not** comparable to each other
post-redaction — a slot showing `<RDCTM05>` before and `<RDCTR12>` after is not thereby shown to
carry a *different* underlying token; the redacted files are archival records of *that* run's own
output, not inputs to any further message-level diff. **The FIRE verdict and the 246 count above
were computed once, in-memory, on the pre-redaction data, before any file was rewritten** — they do
not depend on and are not affected by the redaction step.

## 4. Consequence, per A3.2 — and one row re-run now, one flagged for adjudication

**M1–M4:** void on `20260050` for anything reading `m1m4_s5_decodes.csv`'s message text; the
numeric columns (used by M1/M2/M4's own rate/histogram statistics) are **unaffected** — 0/435
numeric differences — but per A3.2's letter, re-verification rather than silent reliance is the
right call, and M1/M2/M4 have not been recomputed against the fresh CSV in this report (out of
this row's own scope — a P3-adjacent task, not requested here).

**ROW 0q — re-run now, cheaply, since it is pure analysis:**
`fp_parity_checks.row0q_int_snr_conversion_rule()` re-executed against the fresh
`m1m4_s5_20260050_decodes.csv` (paired with the **original**, not-yet-carry-forward-checked
`m3_s1_decodes.csv` — flagged as mixed provenance, since M3/ROW 0d is explicitly **not** in ROW
0r's scope per A3.2 point 6). **Result: unchanged.** `round_half_away_from_zero` is still the
unique 100%-agreement rule across all 3,510 rows. This is expected on mechanical grounds (ROW 0q
depends only on `reported_snr_db` vs. `signal_db − local_noise_db`, both numeric fields, and §2
above shows 0/435 numeric differences) — but it is reported as a **re-run result**, not an
assumption, per the standing "re-run before P3 proceeds" instruction. **ROW 0q's ratified
conclusion (round-half-away-from-zero, used by this session's own ROW 1 report) is RE-CONFIRMED on
`20260050`.**

**ROW 0m — flagged, not decided here.** A3.2's text names ROW 0m among the rows this fire voids,
but ROW 0m's own computation (`row0m_independent_recount`) reads **in-chain sweep data**
(`owsfz-all.txt`/`truth.csv` from the five named sweeps) and **never touches the M1 offline
corpus** ROW 0r examined — the two rows have no data dependency on each other. This is reported as
a **classification question for the Architect**, not resolved unilaterally here (HK-021(k) /
HK-025 territory: refusing to silently decide a validity-vs-precision question that isn't mine to
close): either (a) A3.2's grouping is a blanket "the arm's whole evidence base is provisional until
0r closes clean" caution and ROW 0m's own number stands untouched on its mechanical merits, or (b)
the letter of A3.2 is meant literally and ROW 0m is void regardless of its own data independence.
**No citation of the 12/360 = 3.333% comparator should be treated as newly-unsettled by this
report** pending that adjudication — it is flagged, not retracted.

**ROW 1 (this session's own P4a report, `2026-09-04-row1-excess-floor-report.md`) is UNAFFECTED**:
it reads the five sweeps' `owsfz-all.txt`/`truth.csv` directly, the same in-chain population as ROW
0m, with no dependency on the M1 offline corpus or either binary examined here.

## 5. What's next

Per the execution pack: **P3 (ROW 0o, 0p, 0n) proceeds on `20260050`** — ROW 0r found no numeric
(freq/dt/SNR) discrepancy, so there is no blocking reason P3 cannot run on the current binary, but
P3's own report should note this row's finding and the ROW 0m adjudication flag rather than treat
`20260050` as silently equivalent to `20260049` for every purpose. **P4b (ROW 2/ROW 3) continues to
hold**, unchanged, for P3 to close.
