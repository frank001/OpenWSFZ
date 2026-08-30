# F-001 `SUP-B` — AMENDMENT 2: THE CLUSTER DATA SEC.6.2 REQUIRES, AND THE ROW 0 RE-RUN IT COSTS

**Architect → QA.** Amends
`qa/rr-study/2026-08-30-1149-architect-to-qa-spec-f001-sup-b-instrumented-suppression-sizing.md`
(hereafter "the spec") and
`qa/rr-study/2026-08-30-1432-architect-to-qa-spec-f001-sup-b-amendment-1-row0-pre-merge.md`
("Amendment 1"). Branch `qa/sup-b-2026-08-30`. Committed locally, **not pushed** (HK-014).

**Author:** Architect · **Written:** 2026-08-30 16:08Z (mechanically derived, HK-017)
**Against HEAD:** `836368e2bdeea70c38961a38997c50d49c48c8fb` (`836368e`, the ROW 0 result commit)

---

## Sec.B0 — What this amendment changes, and what it does not

| # | section | change |
|---|---|---|
| **B1** | Sec.3.1–3.3 vs Sec.6.2 | 🔴 **THE GAP IS REAL AND IT IS MINE.** Sec.6.2 requires cluster identity per lookup; Sec.3 specified three scalars that carry none. No verdict is computable from the current instrument. |
| **B2** | Sec.3 | ✅ **THE FIX, PRE-REGISTERED BEFORE IT IS BUILT (HK-021(p)):** a fixed 4,096-row per-code table. The 12-bit code is already in scope at the counting site. |
| **B3** | Sec.3.3 | ✅ **THE C# INTEROP DOES NOT NEED IT** — the reading is produced by the Python/ctypes replay harness. The 11-implementer cascade is avoided. One new export, one version bump. |
| **B4** | Sec.5 | 🔴 **ROW 0 RE-RUNS IN FULL. NOTHING BINARY-DEPENDENT CARRIES FORWARD** from the 15:39Z PASS. Two new rows (`0c-ii`, `0c-iii`), one widened row (`0e`). |
| **B5** | Sec.6.2 | ✅ Bootstrap input specified as a sufficient statistic — cluster totals, not per-lookup rows. Determinism requirements restated. |
| **B6** | Sec.7.1 | ⚠️ **HONEST DISCLOSURE: correcting this makes a clean verdict LESS likely, not more.** A correct cluster interval is wider than the naive one. That is the point. |
| **B7** | NFR-021 | ✅ Ruled: raw per-code dump → `artefacts/` (gitignored). Derived `S`/CI/cluster count → `qa/`. No new judgement at read time. |
| **B8** | Sec.A8 / process | ✅ Sequencing under the PO's 2026-08-30 ruling: **hold the merge, extend, one ROW 0.** FR-064 recommended onto its own branch. |

🛑 **UNCHANGED AND NOT REOPENED:** `S_max` = **40%**, frozen, immovable in either direction
(Sec.2.2). `SUP-A`'s exploratory `S`/`D` remain **VOID and uncitable**. **MEASURE-ONLY** — the
unique-match rule is not implemented, enabled, or flagged (Sec.3.4). **Pooling across bands remains
FORBIDDEN.** Sec.6.1's statistic, Sec.6.4's verdict table and Sec.6.5's three `D` prohibitions are
untouched. Amendment 1's corrected `S-20M` window stands. **This amendment changes WHAT IS
RECORDED and WHAT MUST BE RE-VERIFIED. It changes no bar and no number.**

---

## Sec.B1 — The gap, stated plainly, and whose it is

QA's 17:35Z result report flagged it against Sec.A8 step 7 rather than discovering it mid-leg. That
was the right call and it deserves saying: **the arm was one hard stop away from spending machine
time on a reading that could not produce a verdict.**

The defect is in my spec, between two of my own sections:

- **Sec.6.2** requires a 95% cluster bootstrap **resampling distinct `n12` codes**, because one
  ambiguous code generates many lookups and a lookup-level interval would be far too narrow
  (HK-021(i): observation ≠ independence).
- **Sec.3.1–3.3** specified **three cumulative scalars**. They record how many, never which.

There is no cluster identity in three integers, and **I have no defensible derivation from them.**
I considered and reject the obvious substitute:

🔴 **Clustering by decode cycle is NOT a substitute and I will not offer it as one.** The hash table
is session-scoped and persists across cycles (`ft8_shim.c:766-768`), so the same ambiguous code
recurs in cycle after cycle. Cycle-clustering absorbs within-cycle correlation and leaves the
across-cycle correlation — which is the *dominant* term and the exact one Sec.6.2 was written to
absorb. It would yield a narrower interval that looks like the specified one and is not.

**Consequence, stated without hedging: as the instrument stands today, Sec.6.4's verdict table
cannot be evaluated at all.** Every one of its three outcomes is decided by where the interval
sits (HK-021(w)-amended: an interval gate is decided by POSITION, not width). No interval, no
verdict — and the reading legs would have to be re-run afterwards regardless.

---

## Sec.B2 — The fix, pre-registered before it is built (HK-021(p))

**Measured at the source, not estimated.** The 12-bit code is already in scope at the lookup
callback, and the code space is exactly 4,096 values, so the complete cluster table is a
**fixed-size static array — no allocation, no growth, no hashing, no iteration order.**

### B2.1 The three edits to `ft8_shim.c`

**(1) One new thread-local, set beside the existing scratch** (`ft8_shim.c:776-779`, inside the
existing `if (t == FTX_CALLSIGN_HASH_12_BITS)` block at `:785-793`):

```c
static _Thread_local uint32_t tls_h12_code = 0;
/* ... in cb_lookup_hash, beside tls_h12_lookup_performed = true; */
tls_h12_code = h;   /* set unconditionally within the 12-bit branch, read only when resolved */
```

**(2) The table, beside the three scalars** (`ft8_shim.c:718-720`), same
best-effort/not-thread-local convention as `g_hash_table_reject_count` and the existing counters —
**the identical trade-off, for the identical reason, and no new one:**

```c
#define H12_CODE_SPACE 4096          /* 12-bit hash type: codes are 0..4095 by construction */
static int      g_h12_by_code_displaying[H12_CODE_SPACE];
static int      g_h12_by_code_ambiguous [H12_CODE_SPACE];
static int      g_h12_by_code_divergent [H12_CODE_SPACE];
static int      g_h12_code_out_of_range = 0;   /* MUST stay 0 — see ROW 0c-ii */
```

**(3) The increment, inside the existing emission-site block** (`ft8_shim.c:1574-1578`) — **the
block's guard condition is UNCHANGED**, the new lines sit inside it:

```c
if (tls_h12_lookup_performed && tls_h12_resolved) {
    g_h12_displaying++;
    if (tls_h12_multiplicity >= 2) g_h12_ambiguous++;
    if (tls_h12_divergent)         g_h12_divergent++;

    /* SUP-B Amendment 2: cluster identity for Sec.6.2. Mask defensively so an
     * out-of-range code can never write out of bounds -- and COUNT the violation,
     * because masking alone would hide it (ROW 0c-ii is why this counter exists). */
    if (tls_h12_code >= H12_CODE_SPACE) g_h12_code_out_of_range++;
    uint32_t c = tls_h12_code & (H12_CODE_SPACE - 1u);
    g_h12_by_code_displaying[c]++;
    if (tls_h12_multiplicity >= 2) g_h12_by_code_ambiguous[c]++;
    if (tls_h12_divergent)         g_h12_by_code_divergent[c]++;
}
```

🛑 **`hash_table_lookup`'s body stays byte-for-byte unchanged (TRAP 1), the counting site stays
where ROW 0d-ii pinned it — after the dedup commit, after every discarding `continue` — and the
guard condition is not touched.** The non-perturbation argument this arm rests on is unchanged in
kind. **It is still not inherited: ROW 0b re-runs (Sec.B4).**

### B2.2 One new export, not two

```c
/* Returns H12_CODE_SPACE (4096) on success; -1 if capacity < H12_CODE_SPACE or any
 * pointer is NULL. *out_of_range receives g_h12_code_out_of_range (ROW 0c-ii). */
int ft8_get_h12_by_code(int* displaying, int* ambiguous, int* divergent,
                        int capacity, int* out_of_range);
```

Folding the out-of-range count into this call keeps the export list at **19 → 20**, not 21.
`native/ft8_lib_build/rebuild_shim.bat` (`/EXPORT:` list, currently lines 139-157) and
`src/OpenWSFZ.Ft8/Native/BUILD.md` both take the one new entry; the Developer verifies **20 exports
on both platforms** (`dumpbin` / `nm -D`), matching the precedent set at 14:17Z.

### B2.3 🔴 The managed edit that is NOT optional, named explicitly

**`src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs:385` — `ExpectedShimVersion` → `20260048`, plus its
changelog comment.** This is the ABI self-test. **It was missing from the last handoff's edit list
and cascaded into 131 `Daemon.Tests` + 76 `Web.Tests` failures** before anyone found it. It is
named here, in its own subsection, with its line number, so that cannot repeat. `FT8_SHIM_VERSION`
in `ft8_shim.c`/`.h` bumps to the same value.

---

## Sec.B3 — ✅ The C# interop needs NOTHING ELSE, and this is the finding that shrinks the diff

**Checked, not assumed (HK-018).** The Sec.6 reading is produced by
`qa/cycleframer-alignment-replay/g2_verification_replay.py`, which drives the named DLL **directly
by ctypes** — the same route that read the three scalars for ROW 0. It does not go through
`IFt8NativeInterop`.

**Therefore `ft8_get_h12_by_code` is NOT added to `IFt8NativeInterop`.** A 4,096-row table has no
place in an FR-019 log line, which is the only thing the managed counters serve.

Consequences, all of them good:

- ✅ **The 11-implementer cascade does not happen.** No test double changes. `Ft8Decoder.cs`,
  `Ft8NativeInteropAdapter.cs`, `IFt8NativeInterop.cs` and all 11 implementers are **untouched**.
- ✅ The managed diff is **one constant and its comment** (Sec.B2.3).
- ✅ `H12InstrumentationLoggingTests` and `HashTableRejectCountLoggingTests` keep their current
  shape; the reviewer's 14:17Z note about tightening `.Contains(value.ToString())` to the
  positional `"h12Displaying=17"` style is **still open and still non-blocking** — QA's call whether
  to fold it into this pass while the file is being touched anyway.
- ⚠️ **QA extends the replay harness with the one new getter** (`restype`/`argtypes` for five
  parameters, three `(c_int * 4096)` buffers). Qa-tooling, **HK-011 does not apply** — same finding
  as Amendment 1 Sec.A3.

**Expected diff shape, pre-registered so scope creep is visible:** `ft8_shim.c`, `ft8_shim.h`,
`Ft8LibInterop.cs`, `rebuild_shim.bat`, `BUILD.md`, `libft8.version.txt`, both platform binaries
= **8 files.** Anything beyond that is a scope question for the Captain, not a silent addition.

---

## Sec.B4 — 🔴 ROW 0 re-runs in full. Nothing binary-dependent carries forward.

**The 15:39Z ALL-SEVEN-PASS is evidence about a binary that will no longer exist.** `INST` becomes
shim `20260048` with a new SHA256, which voids ROW 0a by construction and — far more importantly —
voids **ROW 0b, the load-bearing non-perturbation identity.** That row is this diff's acceptance
test, not a formality.

⚠️ **What the 15:39Z result DOES buy, stated precisely so it is neither wasted nor over-claimed:**
it establishes that instrumenting at this site, with this guard, does not perturb the decoder —
29,696 decodes byte-identical, two independent comparators. That materially lowers the *prior* that
the extended build fails 0b, because the extension adds array writes inside an already-proven
block. **It is a prior, not a result. It substitutes for nothing.**

### B4.1 The amended ROW 0, in strict order

| row | claim | status under this amendment |
|---|---|---|
| **0a** | binary identity vs the Sec.4 manifest | **RE-RUN.** `BASE` pin unchanged (`bc8efcf1…`/20260046). **`INST` pin is NEW** — see Sec.B4.2. |
| **0b** | 🔴 non-perturbation, load-bearing | **RE-RUN IN FULL, BOTH INDEPENDENT MEANS.** Unchanged predicate, unchanged field scope (Amendment 1 Sec.A5). Not inheritable under any circumstances. |
| **0c** | `h12Divergent ≤ h12Ambiguous ≤ h12Displaying`, every cycle | **RE-RUN.** Unchanged. |
| **0c-ii** | 🆕 **code-width invariant** | `out_of_range == 0` at end of run. **Hard threshold, exact.** Any non-zero ⇒ **FAIL, STOP** — the 12-bit assumption the whole clustering rests on is false and every bucket is suspect. |
| **0c-iii** | 🆕 **table ↔ scalar reconciliation** | `Σ_c by_code_displaying[c] == h12Displaying`, and the same for ambiguous and divergent. **Three exact equalities.** Any mismatch ⇒ **FAIL, STOP.** |
| **0d-i** | denominator is displays, not attempts | **RE-RUN.** Unchanged (Amendment 1 Sec.A6). |
| **0d-ii** | increment site is the emission point | **RE-RUN, statically, against the NEW commit SHA and NEW line numbers.** The block moves; the claim does not. |
| **0e** | determinism | **RE-RUN AND WIDENED** — see Sec.B4.3. |
| **0f** | NFR-021 pre-merge scan | **RE-RUN** (`nfr021_pre_merge_scan.py --against main`). Plus Sec.B7's dump-location rule. |
| **0g** | distinct `n12` codes ≥ 30, per band | **UNCHANGED, and now COMPUTABLE for the first time.** Reading precondition, per band, not part of this build gate. |

### B4.2 🔴 Why `0c-ii` must be evaluated BEFORE `0c-iii`, and why it exists at all

Order here is load-bearing, and the reason is the HK-022 question — *what error could this row
NOT detect?*

**Masking preserves the sum.** If a code arrived wider than 12 bits, `c = code & 0xFFF` writes into
the **wrong bucket** — but it still writes exactly one increment, so **`0c-iii`'s three totals
reconcile perfectly and the row passes green over silently corrupted cluster identity.** Cluster
identity is the entire product of this amendment. `0c-iii` is structurally blind to the one failure
that would destroy it.

That is precisely why `g_h12_code_out_of_range` exists as a *counted* violation rather than a
silent mask, and why `0c-ii` is a separate row evaluated first. **Rows stay mutually exclusive in
strict order (HK-021).**

⚠️ **And what `0c-iii` cannot detect, disclosed rather than left implicit:** the scalar and the
table are incremented at the same site under the same condition, so a wrong *condition* corrupts
both identically and reconciles green. **`0c-iii` proves indexing and plumbing, never siting.**
Siting is `0d-i` and `0d-ii`'s job — which is a second, independent reason both must re-run rather
than be inherited.

### B4.3 `0e` determinism, widened

Two `INST` replays over `S-17M`. The prior predicate compared the per-cycle counter triple. It now
additionally requires **the full 4,096 × 3 table identical between runs**, compared mechanically —
a byte-level diff of the dumped table, **not an assertion that it matched** (standing rule:
"byte-identical" is proven by a mechanical diff, never asserted).

⚠️ **Sort at construction.** Any set/dict iteration feeding the dump or the bootstrap must be
sorted, or a pinned seed still draws different indices per process. The table is a dense array
indexed 0..4095, which sidesteps this by construction for the dump itself — **the bootstrap's
resampling is where the defect can still land.**

### B4.4 The Sec.4 manifest, pre-registered as procedure since the SHA cannot exist yet

1. Developer builds Windows **and** Linux, records both SHA256 in `libft8.version.txt` (the 14:17Z
   precedent), verifies 20 exports on both.
2. **QA pins the new `INST` SHA into Sec.4's manifest BEFORE ROW 0 starts**, exactly as at 15:07Z.
3. `0a` asserts the running DLL against that pin, on **every** leg, both replays.

🛑 **`BASE` stays `bc8efcf1…`.** ⚠️ **`p23_common.DLL_SHA256` = `39aa1031…` is NEITHER leg — never
re-enable that pin.** ⚠️ Sec.4's `git diff --stat` **EMPTY at run start** precondition applies
again: **ROW 0 cannot start until the Developer commits.** That blocker cost the arm a session
once already.

---

## Sec.B5 — Sec.6.2's input, now that it exists

**The 4,096-row table is a complete sufficient statistic for the specified bootstrap.** Per-lookup
rows are not needed and SHALL NOT be produced — which is also what keeps NFR-021 trivial (Sec.B7).

A **cluster** is one distinct `n12` code with `by_code_displaying[c] > 0`. Codes with zero displays
never participated and are not clusters — **they are excluded from the resample population, not
counted as zeros.** Including them would inflate the cluster count toward 4,096 and silently
narrow the interval, defeating the correction this amendment exists to make.

- **point estimate:** lookup-weighted `S = h12Ambiguous / h12Displaying` (Sec.6.1, unchanged)
- **interval:** 95% bootstrap, **resample distinct participating codes with replacement**, 10,000
  draws, **seed pinned in the harness before the run**; each draw sums the drawn codes'
  `displaying` and `ambiguous` and takes the ratio
- **always reported beside it:** `h12Displaying`, **the distinct participating cluster count**, and
  per-cycle `S` at 1 h, 2 h, 4 h, 6 h, 8 h elapsed

**Report CLUSTER counts, never row counts.** Sec.6.3 (per band, never pooled across bands) and
Sec.6.4's verdict table are unchanged.

📌 **`D` may take the same treatment** — `by_code_divergent` is recorded for exactly that symmetry —
**but Sec.6.5's three prohibitions travel with it every single time it is quoted.** A cluster
interval around `D` changes none of them.

---

## Sec.B6 — ⚠️ The honest disclosure: this makes a clean verdict LESS likely

**A correct cluster interval is wider than the naive lookup-level one — that is the entire reason
Sec.6.2 asked for it.** Sec.6.4 evaluates `MARGINAL` **first, and it governs**: a wider interval is
more likely to span 40%, and `MARGINAL` escalates to the PO and **does not auto-trigger the
narrowed rule.**

So the plain statement: **I am specifying work that reduces our chance of coming back with a clean
answer.** The alternative is a narrower interval that is not the one the spec promised, and a
verdict that would not survive being asked how it was computed. **Sec.7.1's power disclosure is
unchanged and remains uncomfortable; this amendment does not improve it and does not pretend to.**
`SUP-B` is a replay arm over a fixed corpus — **machine time cannot move `n`.**

📌 **Diagnostic, NOT a reading, and it may not be cited as one:** `S-17M`'s 15:39Z raw counters were
`h12Displaying=1,582`, `h12Ambiguous=847`. Anyone can divide those. **Do not.** It is not the
Sec.6.1 statistic evaluated per Sec.6.3, it has no interval, its cluster count is **unknown**, ROW
0g is therefore **unsatisfied for every band**, and Sec.6.4's verdict is decided by interval
position — never by a point estimate held up against the bar. 🛑 **A ratio is not a verdict, and
this one belongs to a binary that is about to be replaced.**

---

## Sec.B7 — NFR-021, ruled here so no judgement is needed at read time

The per-code table carries **no message text and no callsign text** — only integer counts indexed
by a 12-bit value. A 12-bit space over the amateur callsign population is massively many-to-one, so
a non-zero bucket identifies no individual. **But the indices are derived from real off-air
callsigns, and this programme has fired NFR-021 four times, the most recent inside the ROW 0
session itself.** The zero-risk path costs nothing, so it is the rule:

- 🛑 **The raw 4,096-row dump goes to `artefacts/` — blanket-gitignored — and never to `qa/`.**
- ✅ **Only derived figures are committed to `qa/`:** `S`, the CI bounds, the distinct cluster
  count, `h12Displaying`, the per-cycle `S` trajectory.
- ⚠️ **The harness's `out_json` carries `"m": message`** — the existing `artefacts/`-only rule on
  replay output is unchanged and still applies.
- ⚠️ **Scan the PROSE, not just the files.** The 12:04Z blocker was a report that correctly said the
  CSVs were gitignored while naming three real callsigns in the same sentence. Images cannot be
  grepped.
- 🔴 **Every comparator's and dumper's FAIL branch reports counts, booleans and non-message fields
  ONLY.** That is exactly what fired in-session at ROW 0b and was fixed in `e34a665`. The new table
  dumper and the reconciliation rows inherit that rule from birth.

---

## Sec.B8 — Sequencing, under the PO's ruling of 2026-08-30

**PO ruled: hold the merge, extend, one ROW 0.** No binary reaches `main` that cannot produce the
reading it was built for, and ROW 0 runs once, against the binary that will actually produce it.

1. **Architect (this document)** — Amendment 2 committed locally on `qa/sup-b-2026-08-30`, **not
   pushed** (HK-014). ✅ done at commit time of this file.
2. **QA authors the dev-task** from this amendment (HK-015 — `dev-tasks/*.md` are QA's to author,
   not mine). Sec.B2/B3 are the edit list; **Sec.B2.3 is not optional and must appear in it.**
3. **Developer session (HK-011)** applies it: build both platforms, verify 20 exports, record both
   SHA256, `dotnet test` green, commit on `qa/sup-b-2026-08-30`. **Does not push, does not merge,
   does not run `pre_merge_check.py`** (HK-006/HK-014).
4. **QA pins the new `INST` SHA into Sec.4** (Sec.B4.4), confirms `git diff --stat` empty, runs
   **the full amended ROW 0** on `S-17M`.
5. 🛑 **HARD STOP. Captain reviews the diff + ROW 0 result together and rules on the merge**
   (HK-010 — green CI necessary, never sufficient).
6. **Then** step 7: reading legs + ROW 0g per band.

### B8.1 FR-064 — my recommendation, and it is a recommendation, not a ruling

The Captain has already directed a Developer session to apply the 2026-08-14 fix (seed
`_lastHeartbeatSentUtc` at `StartAsync`, or drain the startup Heartbeat deterministically). It is
the **second** recorded occurrence, so §11.3 makes it a blocker on **any** `main` merge — including
this branch's, once its own content is ready.

➡️ **Recommend: FR-064 lands on its own short branch off `main`, not on `qa/sup-b-2026-08-30`.**
Reasons: it gates `main` on its own account and should not wait behind a merge decision that is
deliberately being held; there is **zero file overlap** with the SUP-B diff (Daemon service/tests vs
native shim + interop), so nothing couples them; and it keeps the SUP-B diff at the 8 files Sec.B3
pre-registers, so scope creep stays visible. Same Developer session may carry both — **two
branches, two commits, two independent merges.**

⚠️ If it lands on `main` first, `qa/sup-b-2026-08-30` goes one commit behind. That is a trivial
merge with no overlapping files — **but ROW 0's manifest pins the branch HEAD, so re-pin after any
such merge, never before.**

### B8.2 📌 A third band, free, for the PO to rule on at step 7

The reading legs are `S-80M` and `S-20M` (Sec.A8 step 7). But **ROW 0 re-runs on `S-17M` with the
extended binary, so 17 m's per-code table will exist at zero additional machine cost.**

Sec.6.3 states verdicts per band and forbids pooling, so a third band is a third independent
verdict, not a bigger `n`. **Flagged for the PO at step 7, deliberately not decided here** — and it
does not change what ROW 0 or the two specified legs must do either way.

---

## Sec.B9 — What the Architect owes, recorded as mine

- ✅ **This amendment.** The Sec.6.2/Sec.3 gap was my defect — the interval method and the
  instrument were specified in the same document and did not meet.
- ✅ **The `MARGINAL`-likelihood disclosure (Sec.B6)** stated before the run, not after a result
  that lands badly.
- ⬜ **The step-7 reading review**, once the legs land: the bootstrap's seed and sort discipline
  re-derived independently, cluster counts checked against ROW 0g per band, and Sec.6.4 applied in
  its stated order with `MARGINAL` evaluated first.

---

## Cross-references

- The spec: `qa/rr-study/2026-08-30-1149-architect-to-qa-spec-f001-sup-b-instrumented-suppression-sizing.md`
- Amendment 1: `qa/rr-study/2026-08-30-1432-architect-to-qa-spec-f001-sup-b-amendment-1-row0-pre-merge.md`
- ROW 0 manifest: `qa/rr-study/2026-08-30-1507-qa-sup-b-row0-manifest.md`
- ROW 0 result (all seven PASS, `S-17M`): `qa/rr-study/2026-08-30-1735-qa-to-architect-f001-sup-b-row0-result.md`
- FR-064: `flaky-externalreportingservice-fr064-absoluteexclusion-todo.md` (memory), `TESTING_STRATEGY.md` §11.3
- Counting site: `src/OpenWSFZ.Ft8/Native/ft8_shim.c:1574-1578`; lookup callback `:782-795`; scalars `:718-720`
- ABI sentinel: `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs:385`
- Exports: `native/ft8_lib_build/rebuild_shim.bat:139-157`, `src/OpenWSFZ.Ft8/Native/BUILD.md`
- Replay harness: `qa/cycleframer-alignment-replay/g2_verification_replay.py`
