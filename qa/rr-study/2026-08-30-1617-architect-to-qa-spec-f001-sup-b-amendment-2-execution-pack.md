# F-001 `SUP-B` — AMENDMENT 2 EXECUTION PACK: PREDICATES, HARNESS, BOOTSTRAP, ORDER

**Architect → QA.** Executable companion to
`qa/rr-study/2026-08-30-1608-architect-to-qa-spec-f001-sup-b-amendment-2-cluster-instrumentation.md`
("Amendment 2"). Branch `qa/sup-b-2026-08-30`. Committed locally, **not pushed** (HK-014).

**Author:** Architect · **Written:** 2026-08-30 16:17Z (mechanically derived, HK-017)
**Against HEAD:** `848fea1` (Amendment 2)

**Amendment 2 says WHAT and WHY. This says WITH WHICH LINES, IN WHICH ORDER, AND WHAT COUNTS AS
FAIL.** Where the two disagree, Amendment 2 governs on intent and this governs on mechanics —
**report the disagreement, do not reconcile it silently.**

---

## Sec.C0 — The PO's two rulings, 2026-08-30

| # | question | **RULED** |
|---|---|---|
| **R1** | FR-064's branch | ✅ **OWN SHORT BRANCH OFF `main`.** Not on `qa/sup-b-2026-08-30`. Sec.C1. |
| **R2** | a third reading band | ✅ **`S-17M` IS PRE-REGISTERED AS A THIRD READING BAND, NOW, BEFORE ANY LEG RUNS.** Sec.C6. |

🔴 **R2's timing is the whole point of R2, and it is a methodology constraint, not a preference.**
The 17 m table falls out of ROW 0 at zero machine cost, so the tempting move is to look at 80 m and
20 m first and decide afterwards whether 17 m "also counts". **That is a garden of forking paths: a
band admitted after its result is visible is not evidence, it is selection.** It is therefore
pre-registered here, in advance, with the same status as the other two — **and it is admitted
whichever way it reads, including a reading that embarrasses the arm.**

🛑 **Three bands is three INDEPENDENT verdicts, never a bigger `n`.** Sec.6.3's prohibition on
pooling across bands is unchanged and is not weakened by there now being three of them.

---

## Sec.C1 — R1: FR-064, its own branch, and it does not wait for us

**Sequence, and it runs INDEPENDENTLY of everything else in this pack:**

1. Branch off **`main`** (not off `qa/sup-b-2026-08-30`). Suggested name `fix/fr064-heartbeat-race`.
2. Apply the 2026-08-14 root-cause fix already specified in
   `flaky-externalreportingservice-fr064-absoluteexclusion-todo.md` — seed `_lastHeartbeatSentUtc`
   at `StartAsync`, **or** make the test drain the startup Heartbeat deterministically. **The TODO
   names the fix; this pack does not re-derive it and does not authorise a third design.**
3. Full suite green, then **stop** — Captain's merge call (HK-010), `pre_merge_check.py` on the
   Captain's initiative only (HK-006).

⚠️ **Zero file overlap with the SUP-B diff** (`ExternalReportingService.cs` + its tests vs native
shim + interop). Verify it rather than trust it: `git diff --stat main` on each branch, confirm
disjoint. **If they are not disjoint, STOP and escalate — that would mean one of the two diffs is
out of the scope its spec pre-registered.**

🔴 **If FR-064 merges to `main` before `SUP-B` does, `qa/sup-b-2026-08-30` goes one commit behind.
RE-PIN ROW 0's Sec.4 manifest AFTER that merge, never before.** A manifest pinned to a
superseded HEAD is a green gate pointed at the wrong tree (HK-022).

---

## Sec.C2 — The dev-task's content (QA authors the file, HK-015)

**Eight files. Pre-registered so scope creep is visible, not to be padded.**

| # | file | change |
|---|---|---|
| 1 | `src/OpenWSFZ.Ft8/Native/ft8_shim.c` | The three edits, Amendment 2 Sec.B2.1 — tls code beside `:776-779`, table beside `:718-720`, increments inside the **unchanged guard** at `:1574-1578`. |
| 2 | `src/OpenWSFZ.Ft8/Native/ft8_shim.h` | Declare `ft8_get_h12_by_code`; `FT8_SHIM_VERSION` → `20260048`. |
| 3 | 🔴 `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs` | **LINE 385, `ExpectedShimVersion` → `20260048`** + its changelog comment. **NOTHING ELSE.** |
| 4 | `native/ft8_lib_build/rebuild_shim.bat` | One `/EXPORT:ft8_get_h12_by_code` after line 157. |
| 5 | `src/OpenWSFZ.Ft8/Native/BUILD.md` | Same entry in its export list. |
| 6 | `src/OpenWSFZ.Ft8/Native/libft8.version.txt` | New entry: `20260048`, both SHA256, date. |
| 7 | `src/OpenWSFZ.Ft8/Native/libft8.dll` | Rebuilt (Windows). |
| 8 | `src/OpenWSFZ.Ft8/Native/libft8.so` | Rebuilt (WSL2 Debian, `build_linux.sh`). |

🛑 **`IFt8NativeInterop.cs`, `Ft8NativeInteropAdapter.cs`, `Ft8Decoder.cs` and all 11 implementers
are NOT in this list and MUST NOT be touched** (Amendment 2 Sec.B3). If the Developer finds
themselves editing a test double, **the design has been misread — stop and escalate.**

**Developer verifies before handing back:** 20 exports on **both** platforms (`dumpbin` / `nm -D`),
`dotnet test` green, both SHA256 recorded, committed on `qa/sup-b-2026-08-30`, **not pushed, no
`pre_merge_check.py`** (HK-006/HK-011/HK-014).

⚠️ **Expected: a bare `ExpectedShimVersion` bump with no other managed edit is the CORRECT outcome
here, not an oversight.** It was an oversight last time because the version was *missed*; it is
correct this time because nothing else in managed code touches the new export. Say so in the
dev-task so the Developer does not "helpfully" wire the interface.

---

## Sec.C3 — The harness extension: `g3_h12_replay.py`, two edits

**Confirmed by reading it, not assumed:** the arm's replay driver is
`qa/cycleframer-alignment-replay/g3_h12_replay.py` (added `bb13c8b`), which deliberately wires its
own `build_decoder` rather than calling `g2_verification_replay`'s. **Keep that separation.**

### C3.1 Bind the getter in `build_decoder()` (beside the three existing h12 lines, ~`:81-83`)

```python
# Amendment 2: per-code cluster table. Five args, c_int return.
d.ft8_get_h12_by_code.restype = ctypes.c_int
d.ft8_get_h12_by_code.argtypes = [ctypes.POINTER(ctypes.c_int),
                                  ctypes.POINTER(ctypes.c_int),
                                  ctypes.POINTER(ctypes.c_int),
                                  ctypes.c_int,
                                  ctypes.POINTER(ctypes.c_int)]
```

### C3.2 Read it ONCE, at end of run, into the `out` dict (~`:168-184`)

```python
H12_CODE_SPACE = 4096
Buf = ctypes.c_int * H12_CODE_SPACE
_disp, _amb, _div = Buf(), Buf(), Buf()
_oor = ctypes.c_int(-1)
_n = dec.dll.ft8_get_h12_by_code(_disp, _amb, _div, H12_CODE_SPACE, ctypes.byref(_oor))
if _n != H12_CODE_SPACE:                      # -1 => capacity/NULL rejection
    raise RuntimeError(f"ft8_get_h12_by_code returned {_n}, expected {H12_CODE_SPACE}")
```

then, into `out`:

```python
"h12_by_code": {"displaying": list(_disp), "ambiguous": list(_amb), "divergent": list(_div)},
"h12_code_out_of_range": _oor.value,
```

🛑 **Do NOT call the getter per cycle.** It copies 48 KB; per-cycle it would add ~90 MB of copying
per leg and buys nothing — **the per-cycle series comes from the three scalars, which are already
read per cycle at `:136-138`, and the table is only ever needed in aggregate.** The Sec.6.2
trajectory (`S` at 1/2/4/6/8 h) is computed from those scalars, not from the table.

⚠️ **`_oor` is initialised to `-1`, not `0`,** so a getter that silently fails to write it cannot
be mistaken for a clean run (ROW 0c-ii would then read `-1` and FAIL, which is correct).

⚠️ **BASE (shim 20260046) has none of these exports.** `build_decoder` is shared, so **bind the h12
getters only when the loaded `shim_version >= 20260048`, or run BASE through the existing
un-extended path.** A `ctypes` attribute lookup on a missing export raises at bind time — the
script's own docstring at `:24` already warns about exactly this for the three scalars. **Do not
"fix" that by wrapping the binds in a bare `try/except`:** a silently unbound getter on an INST run
would make ROW 0c-ii/0c-iii unevaluable while looking green.

### C3.3 Where the output goes

🛑 **`out_json` carries `"m": r["message"]` at `:155` — real off-air message text. It goes to
`artefacts/` ONLY, never `qa/`.** Unchanged by this amendment; the table adds no text and does not
change the classification. NFR-021 has now fired **four** times, once inside the ROW 0 session
itself.

---

## Sec.C4 — ROW 0, amended, in strict order, each row mechanical (HK-021)

**Evaluate in this order. A FAIL stops the run — no partial evaluation, no "carry on and report at
the end" (HK-021, HK-025).** Extend `qa/cycleframer-alignment-replay/row0_evaluate_s17m.py`
(added `9621540`) rather than writing a second evaluator.

| order | row | predicate — **evaluated as an assertion** | on FAIL |
|---|---|---|---|
| 1 | **0a** | for every leg and both replays: `out["dll_sha256"] == manifest[label].sha256` **and** `out["shim_version"] == manifest[label].shim_version` | 🛑 STOP |
| 2 | **0b** | 🔴 load-bearing. Two independent comparators, BASE vs INST, over `per_file[*]` gated fields `ts`, ordered `decodes[]`, `av`, `truncated`. Unchanged from Amendment 1 Sec.A5. | 🛑 STOP |
| 3 | **0c** | for **every** `per_file` entry: `h12Divergent <= h12Ambiguous <= h12Displaying` | 🛑 STOP |
| 4 | **0c-ii** | 🆕 **INST only:** `out["h12_code_out_of_range"] == 0` | 🛑 STOP |
| 5 | **0c-iii** | 🆕 **INST only, three exact equalities:** `sum(h12_by_code.displaying) == h12_displaying_count_final`, and the same for `ambiguous` and `divergent` | 🛑 STOP |
| 6 | **0d-i** | `h12_displaying_count_final <= Σ len(decodes)`; **and** per cycle, `Δh12Displaying <= len(decodes)` for that cycle | 🛑 STOP |
| 7 | **0d-ii** | static: the increment block sits after the dedup commit and after every discarding `continue`. **Re-verify against the NEW commit SHA and the NEW line numbers** — the block moves. | 🛑 STOP |
| 8 | **0e** | two INST replays: all per-cycle `(displaying, ambiguous, divergent)` triples identical; **and** all three `h12_by_code` arrays identical elementwise; **and** `h12_code_out_of_range` identical | 🛑 STOP |
| 9 | **0f** | `nfr021_pre_merge_scan.py --against main` CLEAN, **run on a COMMITTED tree** (Sec.C7.2) | 🛑 STOP |

### C4.1 🔴 Why `0c-ii` precedes `0c-iii`, and why it exists

**Masking preserves the sum.** `c = code & 0xFFF` on an oversized code still writes exactly one
increment — into the **wrong bucket**. So `0c-iii`'s three totals reconcile **perfectly** while
cluster identity, the entire product of this amendment, is silently scrambled. `0c-iii` is
structurally blind to the one failure that would destroy the thing it appears to protect. That is
why the violation is **counted** rather than silently masked, and why it is its own row, evaluated
first.

### C4.2 ⚠️ What these rows CANNOT detect — disclosed, per HK-022

- **`0c-iii` proves indexing and plumbing, NEVER siting.** Scalar and table increment at the same
  site under the same condition, so a wrong *condition* corrupts both identically and reconciles
  green. **Siting is `0d-i`/`0d-ii`'s job — a second, independent reason neither may be inherited.**
- **`0e` proves determinism, never correctness.** Two identically-wrong runs agree.
- **`0a` proves the binary is the pinned one, never that the pin is the right binary.** That is
  Sec.C7's manifest discipline.
- **`0b` cannot detect a change that alters no emitted field** — which is precisely why it is
  paired with the static `0d-ii`, not trusted alone.

### C4.3 What does NOT carry forward

🔴 **Every row above re-runs. The 15:39Z ALL-SEVEN-PASS is evidence about a binary that will not
exist.** It buys a **prior** — instrumenting at this site did not perturb 29,696 decodes — and a
prior is not a result.

---

## Sec.C5 — The bootstrap, fully pinned before any leg runs (HK-021(o), HK-021(p))

### C5.1 The population

```python
H12_CODE_SPACE = 4096
disp = out["h12_by_code"]["displaying"]
amb  = out["h12_by_code"]["ambiguous"]
participating = [c for c in range(H12_CODE_SPACE) if disp[c] > 0]
N = len(participating)
```

🔴 **A cluster is a code with `displaying > 0`. Codes with zero displays are EXCLUDED from the
resample population — they are not clusters, and they are not zeros.** Including them would inflate
`N` toward 4,096 and **silently narrow the interval**, defeating the correction this whole
amendment exists to make.

✅ **Sort discipline is satisfied BY CONSTRUCTION**: `participating` is built by iterating a dense
`range`, so it is ascending and process-independent. 🛑 **Do not build it from a `set` or `dict`** —
hash-randomised iteration defeats a pinned seed, the defect already found in `x4`/`x3`.

### C5.2 The draw — pinned here, in advance

- **RNG:** `numpy.random.default_rng(20260830)` · **seed `20260830`, pinned in the harness, not
  passed on the command line** (a CLI default is not a pin).
- **Draws:** exactly **10,000**.
- **Each draw:** `idx = rng.integers(0, N, size=N)` — resample **`N` codes with replacement from the
  `N` participating codes**; the draw's statistic is `Σ amb[participating[i]] / Σ disp[participating[i]]`
  over `i in idx`.
- **Interval:** the **percentile method** — `numpy.percentile(ratios, [2.5, 97.5])`, default linear
  interpolation. Pinned so it is reproducible; do not substitute BCa or basic-bootstrap.
- **Point estimate:** `h12_ambiguous_count_final / h12_displaying_count_final` — **the Sec.6.1
  lookup-weighted `S`, NOT the mean of the bootstrap draws.**

✅ **No degenerate draw is possible:** every participating code has `disp[c] >= 1`, so every draw's
denominator is `>= N >= 1`. **Assert it anyway** — a zero denominator means the population was
built wrong, and the assertion is how you find that out.

### C5.3 The bootstrap's own determinism check

**Run it twice on the same input file; both bounds must be identical.** Byte-compared, not asserted
by eye. A pinned seed that still moves means the sort discipline in C5.1 was violated somewhere
upstream.

---

## Sec.C6 — R2: three bands, ROW 0g, and what a band that fails it gets

**Reading legs: `S-17M`, `S-80M`, `S-20M` — all three pre-registered, now.**

⚠️ **Corpus windows are Amendment 1 Sec.A4's and are NOT re-cut here:** `S-20M` uses
`260808_001605` → `260808_081605` (three process starts made the original window invalid);
`S-17M`/`S-80M` are single-process and stand as they are, 80 m's 8.27 h overrun disclosed rather
than trimmed.

**ROW 0g, per band, evaluated BEFORE that band's interval is computed:**

```
N = len(participating)      # Sec.C5.1
ROW 0g:  N >= 30
```

🛑 **A band that fails ROW 0g gets NO verdict. Not a wider interval, not a caveated one — none.**
Report its `N`, its `h12Displaying`, and stop for that band. **Do not pool it into another band to
reach 30** (Sec.6.3, unchanged).

📌 **`S-17M`'s table falls out of the ROW 0 run itself** — the same two INST replays that satisfy
`0e`. **No fourth leg is needed for it**, and its reading must be computed from the ROW 0 INST run
rather than a fresh replay, so that the binary, window and corpus are provably the ones ROW 0
passed on.

---

## Sec.C7 — Order, hard stops, and the manifest

### C7.1 The sequence

1. **QA authors the dev-task** (Sec.C2) — HK-015, it is QA's file, not mine.
2. **Developer session** (HK-011): builds both platforms, 20 exports verified, both SHA256 recorded,
   `dotnet test` green, **commits on `qa/sup-b-2026-08-30`, does not push.** In parallel and
   independently: FR-064 on its own branch (Sec.C1).
3. **QA pins the new `INST` SHA256 into spec Sec.4's manifest** — *after* the commit, *before*
   ROW 0. ⚠️ Sec.4's **`git diff --stat` EMPTY at run start** precondition applies again; it cost
   this arm a session once already. 🛑 **`BASE` stays `bc8efcf1…`.** ⚠️ **`p23_common.DLL_SHA256`
   = `39aa1031…` is NEITHER leg — never re-enable that pin.**
4. **QA extends the harness** (Sec.C3) and the evaluator (Sec.C4). Qa-tooling — **HK-011 does not
   apply.**
5. **QA runs the FULL amended ROW 0 on `S-17M`** — BASE ×1, INST ×2.
6. 🛑 **HARD STOP. Captain reviews the diff and the ROW 0 result TOGETHER and rules on the merge**
   (HK-010 — green CI necessary, never sufficient). **No push, no merge, no `pre_merge_check.py`.**
7. **Then** the reading legs `S-80M` / `S-20M`, ROW 0g per band, and the Sec.6.4 verdict per band
   with `MARGINAL` evaluated **first**.

### C7.2 ⚠️ `nfr021_pre_merge_scan.py` does not see untracked files

**Found in-session while writing Amendment 2:** the scan returned `CLEAN — 11 text files` on a tree
whose new document was untracked, and `12` only after committing. It diffs committed state.

**Consequence for ROW 0f: run it on a COMMITTED tree, and check the file count is the one you
expect.** Inside ROW 0 this is already guaranteed by Sec.4's empty-`git diff --stat` precondition —
but **a green scan on a dirty tree answers a smaller question than it appears to** (HK-022), and
that is exactly how a fifth NFR-021 fire would arrive.

### C7.3 NFR-021, ruled in advance so no judgement is needed at read time

- 🛑 Raw `out_json`, including `h12_by_code` → **`artefacts/` ONLY** (blanket-gitignored). It carries
  `"m": message`.
- ✅ Committed to `qa/`: `S`, the CI bounds, `N` (cluster count), `h12Displaying`, the per-cycle `S`
  trajectory. **Derived figures only.**
- 🔴 **Every comparator, evaluator and dumper FAIL branch reports counts, booleans and non-message
  fields ONLY.** That is what fired at ROW 0b and was fixed in `e34a665`; the new rows inherit it
  from birth, not by retrofit.
- ⚠️ **Scan the PROSE, not just the files.** The 12:04Z blocker was a report that correctly said the
  CSVs were gitignored *while naming three real callsigns in that same sentence*. Images cannot be
  grepped.

---

## Sec.C8 — QA's authority, restated

✅ **QA MAY REFUSE ANY ROW ABOVE ON HK-021(k) GROUNDS WITHOUT MY AGREEMENT (HK-025).** Classify the
precondition (validity vs precision), evaluate **both** branches — **same row either way ⇒
DIAGNOSTIC ⇒ REFUSE**, name the row and the evaluation, and stop. No partial run. **ROW 0d was
circular once already and QA would have been right to refuse it; I would rather that happen again
than have a decorative row pass.**

Every other HK-021 fault stays flag-and-escalate.

🛑 **Standing, unchanged, and not reopened by this pack:** `S_max` = **40%**, frozen. **MEASURE-ONLY**
— no unique-match rule is implemented, enabled or flagged. `SUP-A`'s exploratory `S`/`D` remain
**VOID and uncitable**. **No pooling across bands.** Sec.6.5's three `D` prohibitions travel with
`D` every time it is quoted. 🛑 **`S-17M`'s `1,582 / 847` is a DIAGNOSTIC — it has no interval, its
cluster count is unknown until this pack runs, and it belongs to a binary about to be replaced.
Do not divide it into a verdict.**

⚠️ **And the disclosure that must survive into the reading report:** a correct cluster interval is
**wider** than the naive one, so **`MARGINAL` is MORE likely, not less** — it is evaluated first, it
governs, it escalates to the PO, and it **does not auto-trigger the narrowed rule.** Sec.7.1's power
disclosure is unchanged and is not improved by any of this.

---

## Cross-references

- Amendment 2: `qa/rr-study/2026-08-30-1608-architect-to-qa-spec-f001-sup-b-amendment-2-cluster-instrumentation.md`
- Amendment 1: `qa/rr-study/2026-08-30-1432-architect-to-qa-spec-f001-sup-b-amendment-1-row0-pre-merge.md`
- The spec: `qa/rr-study/2026-08-30-1149-architect-to-qa-spec-f001-sup-b-instrumented-suppression-sizing.md`
- ROW 0 manifest: `qa/rr-study/2026-08-30-1507-qa-sup-b-row0-manifest.md`
- ROW 0 result: `qa/rr-study/2026-08-30-1735-qa-to-architect-f001-sup-b-row0-result.md`
- Harness: `qa/cycleframer-alignment-replay/g3_h12_replay.py` (`build_decoder` ~`:63-84`, `out` ~`:168-184`, `"m"` at `:155`)
- Evaluator: `qa/cycleframer-alignment-replay/row0_evaluate_s17m.py`
- FR-064: `flaky-externalreportingservice-fr064-absoluteexclusion-todo.md`, `TESTING_STRATEGY.md` §11.3
- Counting site: `src/OpenWSFZ.Ft8/Native/ft8_shim.c:1574-1578` · scratch `:776-779` · scalars `:718-720`
- ABI sentinel: `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs:385`
