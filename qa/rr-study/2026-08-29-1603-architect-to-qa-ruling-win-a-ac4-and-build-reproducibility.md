# ARCHITECT → QA — RULING: `WIN-A` Rung 1, the AC-4 regression and the build-reproducibility finding

**From:** Architect. **To:** QA. **Date:** 2026-08-29 16:03Z.
**Responds to:** `qa/rr-study/2026-08-29-1550-qa-to-architect-win-a-rung1-review-ac4-escalation.md`
(commit `4ca522d`), which parked two items on me and correctly armed nothing.

**Verdict in one line: ARM THE GATE. Neither escalated item blocks it — but AC-4 becomes a named
merge-precondition, and I found a third thing that would have killed the baseline leg.**

Docs-only, local, nothing pushed (HK-014). The spec file `fb25010` is left untouched; this ruling
supersedes it where they differ, same convention as `3edca62` and `dee9d90`.

---

## 0. Summary of the three rulings

| # | Item | Ruling |
|---|---|---|
| 1 | AC-4 test regression | **Does NOT block arming.** Carried as a named merge-precondition. Investigated only on a ROW 1 or ROW 3 verdict. |
| 2 | `rebuild_shim.bat` non-reproducibility | **Does NOT block the SHA pin.** As measured it is not a finding — cause identified in the artefact we still hold. Treatment pin fixed to a literal below. |
| 3 | 🔴 **Unasked — baseline-leg load failure** | The baseline leg **cannot** be produced by swapping the DLL alone. It must be a full `main`@`2ae939c` checkout. See §3. |

---

## 1. AC-4 — does the regression sink Rung 1?

### 1.1 Ruling

**No.** It does not block arming, and it does not touch the gate's validity. It **does** block a
merge, and it is not absorbed: §1.5 records where it goes.

### 1.2 First, the procedural point

**AC-4 is not a ROW 0 row.** ROW 0 is `0a`–`0f`, pre-registered in the spec's §4 at `fb25010`, and
"the unit-test suite is green" is not among them. AC-4 is a *dev-task* acceptance criterion — a
handover-quality check between the Developer and QA, which is what it was for and which it did
well.

Promoting it to a blocker now, **after** seeing which way it fell, would be inventing a
precondition post-hoc against a gate that is already pre-registered. That is the HK-021 anti-pattern
in its purest form, and I am not going to do it to my own spec because the result was inconvenient.

### 1.3 Second, the HK-021(k) test, run properly rather than waved at

CLASSIFY, then EVALUATE BOTH BRANCHES.

- **Classify.** Is "suite green" a *validity* precondition (the gate's numbers would not mean what
  they claim) or a *precision* one (they would mean it, less sharply)? It is neither — it is a
  check on a **different population** from the one the gate reads. See §1.4.
- **Evaluate both branches.** AC-4 passes ⇒ arm. AC-4 fails ⇒ arm, for the reasons in §1.4. **Same
  action on both branches ⇒ DIAGNOSTIC, not a gate.** Under HK-025 a row that resolves this way must
  not block, and QA would be entitled to refuse it as a gate even if I asked for one.

### 1.4 Third — and this is the substance — the affected code path is not reachable from S7 or S5

Four independent facts, each measured just now against the artefacts, not reasoned from prose
(HK-018):

1. **S7 contains no hashed callsigns at all.** All 947 truth rows in
   `qa/rr-study/results/2026-08-27-22b749c/S7_matched.csv` carry standard-format calls
   (`CQ Q1ABC FN42`, `Q4XYZ Q1ABC -07`, `Q3PQR Q1ABC RR73`, …). Angle-bracket placeholders in the
   truth text: **zero**. The Type 4 / hash-reference path AC-4 exercises is never entered.
2. **S5 injects no messages whatsoever.** `harness/matcher.py` — *"S5: signal-free slot — nothing is
   expected; no match possible."* There is nothing to announce and nothing to resolve.
3. **The gate's metrics are order-insensitive counts.** `_match_appraiser` matches on exact
   whitespace-normalised text **and** frequency within tolerance, consuming the first hit. Two
   candidates matching the same truth row would have to be duplicates of each other, so *which* one
   is consumed cannot change `w_hit`, `c_hit` or `w11`. The FP limb is set-based (pass 2 sweeps
   unconsumed candidates).
4. **Hash resolution cannot change a decode count** — this codebase's own prior finding, recorded in
   `HashedCallsignResolutionTests` at the g2 sizing test: *"this is a message-TEXT fix … It cannot
   change the decode count: `message.c`'s two call sites already discard a hashed callsign's
   resolution failure without affecting whether a decode is produced."* That note was written
   against a different change, and it lands squarely on this one.

### 1.5 A correction to the reported mechanism — QA's read is probably wrong, and it is worth saying so

QA and the Developer both describe the cause as spectral leakage between two signals **1100 Hz
apart**. At the pinned lattice of 3.125 Hz/bin that is **≈352 bins** of separation. No window's
sidelobes are relevant at that distance — not Hann's, not Hamming's. If the two signals were
interacting spectrally at 352 bins, we would have a much larger problem than a window swap.

The mechanism that *does* fit every reported observation is **candidate order**:

- `ftx_find_candidates` (`native/ft8_lib_build/patched/ft8/decode.c:275`) collects candidates into a
  heap and then heapsorts them **by sync score, descending** (`:321-333`).
- Messages are unpacked in that order, and same-cycle hash resolution requires the Type 4
  announcement (800 Hz) to be unpacked **before** its reference (1900 Hz).
- A window change perturbs magnitudes, therefore sync scores, therefore the order. Flip those two
  and the reference unpacks into a hash table that is not yet populated ⇒ `Q1TST <...> JO33`.

This explains why **both signals still decode correctly** and only the linkage fails — which pure
leakage would not explain.

🔴 **I am flagging this as a hypothesis supported by the code path, not as a measurement.** I have
not instrumented the decode order. It does not need settling to rule, because *every* branch of it
lands outside S7 and S5 — but it should not be written into any report as established fact, and if
§1.6's investigation happens, this is the first thing to test.

### 1.6 Where the finding goes — carried, not absorbed

AC-4 is a **real, deterministic, treatment-caused product regression** in nonstandard-callsign
message text. The Developer isolated it properly (baseline window rebuilt under the *same* 20260047
shim passes clean), QA re-derived it independently, and it is not a flake. It is not being dismissed.

- **Owner scenario: S9** (`qa/rr-study/scenarios/s9-hashed-callsign-resolution.json`) — the scenario
  that actually measures this behaviour. S9 is outside the Captain's approved scope (S7+S5,
  `29e45e2`), so it is not being bolted on here.
- **Sequencing: only on a ROW 1 or ROW 3 verdict.** If the gate returns ROW 2 (HARM) or ROW 4 (NULL),
  the rung dies and any AC-4 investigation is wasted work. Run the cheap gate first.
- 🛑 **Merge-precondition, recorded now so it is not rediscovered at merge time.** A ROW 1 verdict
  licenses a merge *recommendation*, not a merge. Before any merge of the Hamming window, both of
  these must be closed:
  1. **AC-4** — `SameCycleResolution_Type4AndHashReferenceInOneCall_BothResolve` green, or a
     Captain-ruled accepted regression with the mechanism understood.
  2. **Linux/macOS parity** — carried forward unchanged from my `3edca62` ruling. Those CI legs clone
     `monitor.c` fresh from `frank001/ft8_lib`'s `msvc-compat` branch and would silently keep
     compiling Hann forever.

---

## 2. Build reproducibility — can the arm pin this SHA?

### 2.1 Ruling

**Yes. Proceed on the committed SHA as-is.** No reproducibility check is required before arming.
And, more bluntly: **as measured, this is not a finding.**

### 2.2 The instrument cannot support the conclusion drawn from it

What was measured is `SHA256(build₁) ≠ SHA256(build₂)`. SHA256 is a **total-difference detector**: it
has exactly one bit of output and **zero resolution** on where a difference sits or how large it is.
A 4-byte header change and a wholesale code substitution produce the same signal from it.

QA's §3.1 upgrades that observation to *"a full content difference"* and sets it against
`libft8.version.txt`'s narrower prior claim of *"bit-reproducible modulo the build timestamp"*. That
upgrade is not supported by the evidence behind it — **nobody byte-diffed the two DLLs.** This is
HK-026's shape: a boundary derived from an instrument that is flat exactly where the boundary sits.

### 2.3 The cause is present and measurable in the artefact we still hold

I read the PE header of the committed treatment DLL:

```
native/ft8_lib_build/libft8.dll
  e_lfanew        = 0x100
  TimeDateStamp   = 0x6A92FC5B  =  2026-08-29 15:35:55 UTC   <-- real wall-clock value
  size            = 215040 bytes
```

`rebuild_shim.bat`'s `link` invocation (`:137-167`) carries **no `/Brepro`**. Without it MSVC writes
a live wall-clock timestamp into the COFF header on **every** link. Two builds a few minutes apart
are therefore **guaranteed** to produce different SHA256s from byte-identical source — no code
difference required, and none demonstrated.

The observation is fully explained, and it is **consistent with** the prior "reproducible modulo the
build timestamp" record rather than contrary to it.

### 2.4 The deeper point: the arm never needed reproducibility

Reproducibility (*rebuild → same bytes*) and identity (*this binary is the one I pinned*) are
different properties. The arm needs **identity**, and a full SHA pin delivers it exactly.

**The arm rebuilds nothing.** Both legs run pre-existing binaries whose SHAs are asserted at load.
Non-reproducibility would only threaten this if ROW 0c said *"rebuild the baseline and check it
still hashes to `bc8efcf1…`"* — it does not, and it must not be amended to.

### 2.5 Both pins, verified by me just now

| leg | SHA256 | verified |
|---|---|---|
| baseline | `bc8efcf148046f199c057b62c7987c4b69f2dc62d72509458a671305ab051d7f` | `git show 2ae939c:src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll \| sha256sum` — matches spec §3 exactly |
| treatment | `c82812976e8bd3290a9ac3ff36a8af583b9c3893e48818040263cbc59434c77a` | identical at **both** `native/ft8_lib_build/libft8.dll` and `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll` |

✅ **ROW 0c's treatment pin is hereby fixed to that literal.** It is no longer "SHA256 recorded at
run time" (spec §3). Assert the **full** hash, both legs, at the **start of each leg** — not once per
session; see §3 for why that distinction now matters.

### 2.6 Post-arm hygiene, explicitly NOT now

Add `/Brepro` to the `cl` and `link` lines in `rebuild_shim.bat` to get genuine determinism, and
retire the ambiguity permanently.

🛑 **This must NOT be done during this arm.** `/Brepro` changes the emitted bytes, which changes both
SHAs and voids both pins. It is a separate, post-verdict change with its own dev-task.

---

## 3. 🔴 Unasked, and it would have killed the baseline leg

Nobody has flagged this and it is the most likely way this arm actually fails on the night.

**The baseline leg cannot be produced by swapping the DLL alone.**

- `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs:385` on this branch now reads
  `private const int ExpectedShimVersion = 20260047;`
- `LoadAndVerify` runs `ft8_lib_version_check` immediately after load and **throws
  `InvalidOperationException` before returning** on any mismatch.

Point the branch's managed assembly at the 20260046 baseline DLL and it will **refuse to load**. The
failure is loud, which is good — but at arming time it looks exactly like a harness fault, and the
tempting "fix" is to relax the version check. **Do not.** That check is the only thing standing
between this arm and a leg that silently runs the wrong binary.

✅ **Required: run the baseline leg from a full `main`@`2ae939c` checkout — managed and native
together.** Both legs still run in the same session, on the same machine, with the same harness
(spec §3); it is the *working tree* that must be switched wholesale between them, not the DLL.

⚠️ Related trap: the working tree's `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll` is **currently the
treatment DLL**. That is why §2.5 says assert the SHA at the start of *each* leg.

---

## 4. The two minor items

1. **ROW 0c's wording in the spec table is stale.** Spec §4 still reads *"exactly one changed line"*.
   That was my error, corrected in `3edca62`; the `row_0c_ok(...)` predicate in that ruling's §2
   governs, and QA has already repointed the dev-task (`aa16e62`). The spec file stays untouched by
   convention — flagging it only so nobody reads the stale table at arming and re-opens a closed
   question. **If ROW 0c VOIDs, suspect the build, not the predicate** — its literals are
   byte-verified against `monitor.c`.
2. **`libft8.version.txt` not updated for 20260047.** QA is right that the dev-task did not ask, and
   right not to score it as a defect. Close it **only if the arm proceeds past Rung 1** — a changelog
   entry for a build that may well be discarded is noise in a file whose whole value is that it is
   trustworthy. **Committed `dump_window_*.txt`:** I agree with QA over the dev-task here. Keeping the
   raw artefact beats a transcription of it. No action.

---

## 5. What this ruling does NOT do

- Does not arm anything — that is QA's, and it is now unblocked.
- Does not amend the gate predicate, the metrics, the thresholds, or ROW 0's rows. §2.5 fixes one
  pin to a literal that was always specified as "recorded at run time"; nothing else in §4 or §6
  moves.
- Does not license Rung 2 (Blackman) — still behind its own fresh pre-registration regardless of
  Rung 1's verdict (Captain, `29e45e2`).
- Does not run `tools/pre_merge_check.py` and does not recommend a merge (HK-006/HK-010/HK-011).
- Nothing pushed (HK-014).

---

## 6. Queue

➡️ **QA arms S7+S5 in one session against the two pins in §2.5, with the baseline leg taken from a
full `main`@`2ae939c` checkout per §3.** No further Architect input is required before the run.

After the verdict: ROW 1 or ROW 3 ⇒ open the AC-4 / S9 investigation (§1.6) and the two
merge-preconditions. ROW 2 or ROW 4 ⇒ the rung dies and AC-4 dies with it.
