# `FP-REGRESSION` — Architect → QA spec: locate the change(s) that raised the in-chain S5 false-accept rate

**Architect, 2026-09-04 14:32Z** (`date -u`, HK-017). New arm, pre-registered before any binary is
extracted or any replay is run. **Nothing in this spec has been executed.**

**Provenance of the ask:** the PO, 2026-09-04, after the Architect twice concluded "no regression"
from the board's truncated four-sweep line without opening Section 6 of the sweep report. New
standing rule **[HK-031]**. This arm exists because the regression is real; the analysis that denied
it is recorded there, not here.

---

## 0. What this arm is, and the two things it must not become

**It is:** a search for *which change* moved the in-chain S5 AWGN false-accept rate, using paired
offline replay through historical binaries — the machinery `AWGN-FP` ROW 0r built and proved.

🛑 **It is NOT a fix.** No candidate parameter is reverted, tuned, or "restored" under this arm. It
locates; a repair is a separate pre-registration with its own gate.

🛑 **It is NOT permission to reopen the candidate-budget family.** `s_k_min_score_pass2`,
`K_MAX_CANDIDATES*` and the pass table are **closed twice** and stay closed. If a row implicates
them, that is a finding to *report*.

---

## 1. What is already established — do not re-derive it (HK-018)

Read from Section 6 of `results/2026-09-03-35378b9/report.md`, restricted to the ratified
Clopper–Pearson gate era at N≥60 (Section 6's own footnotes exclude the June plain-decode-rate rows
and the 0/12 INFO row — that exclusion is inherited, not re-argued):

| Window | OpenWSFZ | Rate | 95% CI |
|---|---|---|---|
| 2026-08-05 → 08-21 | **2/360** | 0.556% | [0.099%, 1.738%] |
| 2026-08-22 → 09-03 | **13/480** | 2.708% | [1.609%, 4.272%] |

**4.88×, Fisher one-sided p = 0.0154.**

**Control, on the identical slots, same audio, same rig:** WSJT-X **0/840** (95% UB 0.356%) vs
OpenWSFZ **15/840 = 1.786%**, Fisher one-sided **p = 2.9×10⁻⁵**. WSJT-X has produced **zero** false
accepts in **every** sweep in the study's history. ⇒ **the rig, the noise generator and the scenario
design are excluded as causes.** This control is the single most valuable fact this arm inherits;
do not re-measure it.

🔴 **`12/360 = 3.333%` MUST NOT be used as the baseline here.** It is pooled from `7d36038`
(2026-08-21) onward — **inside** the regressed window. It describes the post-regression rate. See
`FP-PARITY` A2.2/A2.4.

---

## 2. The candidate windows — and there are probably TWO steps, not one

Per-sweep counts, ratified-gate era (`k`/`N`):

| Date | Sweep | OpenWSFZ | Reading |
|---|---|---|---|
| 2026-08-05 | `3bd4cd0` | **0/120** | last clean sweep |
| 2026-08-15 | `8d6e1b1` | **1/120** | first non-zero |
| 2026-08-21 | `7d36038` | 1/120 | |
| 2026-08-22 | `f5dec23` | **4/120** | first clearly elevated |

🔴 **A single-change-point bisect will mislocate this.** The series is consistent with **two**
events: a departure from zero between 08-05 and 08-15, and a further rise between 08-21 and 08-22.
**Every row below is scoped to a window, never to "the" change point**, and ROW 2 explicitly admits
a two-step outcome.

`git log --since=2026-08-04 --until=2026-08-23 -- native/ src/OpenWSFZ.Ft8/`, substantive commits
only (documentation and Linux/macOS-only rebuilds dropped — the in-chain rig is win-x64):

**Window A — 08-05 → 08-15 (departure from zero):**

| Date | Commit | Change |
|---|---|---|
| 08-12 | `9500e03` | **`HASH_TABLE_SIZE` 256 → 4096** (shim 20260038) |
| 08-14 | `3bc2b9d` | r0-reproducible-native-build — **vendored ft8_lib, all 11 objects rebuilt from source** |
| 08-14 | `af2f466` | r1 sync-refiner instrument validation |
| 08-14 | `aa434cb` | r1b sync-refiner instrument correction |

**Window B — 08-21 → 08-22 (the rise):**

| Date | Commit | Change |
|---|---|---|
| 08-22 | `7ed8b0c` | Phase B build — origin fix (B1), **fusion normalisation (B2)**, `ft8_ldpc_decode_llrs` export |
| 08-22 | `c3a9ea8` | **negative `time_offset` SNR collapse fix** (shim 20260046) |

⚠️ `3bc2b9d` is a **whole-toolchain** change, not a logic change. If the bisect lands there, the
finding is "the rebuild changed decode behaviour", which is a different and more serious result than
a parameter change — and it would retroactively bear on every binary-identity claim the project
holds. Do not treat it as a null candidate.

---

## 3. Instrument validity — this gates everything (HK-026)

The offline replay rate (**10.875%**) and the in-chain rate are **not the same measurement** — the
ratified gap is ≈3.26×. **An instrument that is flat where the effect lives cannot locate that
effect.** So the offline replay must first be shown to *move* before it is trusted to bisect
(HK-021(q): a unit whose metric MOVES first).

That is ROW 0a, and it is a real STOP branch, not a formality.

---

## 4. Pre-registered rows

Every predicate ships as code (HK-021(r)) in one script under `qa/rr-study/fp-regression/`, printing
each row's inputs, threshold and verdict. Print **every** row, then the first firing verdict.

**Population, frozen here:** the **full 4,000-slot M1 S5 AWGN offline corpus** at
`qa/rr-study/awgn-fp-replay/_work/m1m4_s5/` — noise-only, already on disk, and the exact population
ROW 0r ran at this size. ⚠️ **Check `qa/ARTEFACT_INVENTORY.md` before concluding any WAV is missing**
(HK-018, violated 4×). No re-render without reporting it.

**Design: paired.** Every binary decodes the **same** WAVs, so all comparisons are McNemar-style on
discordant slots, never two independent samples. ROW 0r established this design works and that
decode **counts** were invariant across `20260049`→`20260050`.

🛑 **Binary identity: assert the SHA256 of every extracted DLL against a manifest recorded in the
report BEFORE it decodes anything. A mismatch is STOP, not a note** (`FT8_SHIM_VERSION` identifies
nothing — pin the hash).

### ROW 0 — the instrument

- **0a — can the offline instrument see the effect?** Decode the frozen corpus through the
  **pre-regression** win-x64 binary (from `3bd4cd0`, the last 0/120 sweep) and through the
  **current** binary. Compare offline false-accept rates, paired.
  **FIRES iff** the two rates' paired difference is **not** signed in the same direction as the
  in-chain series (i.e. current − pre-regression **≤ 0**).
  ⇒ **Consequence, asserted either way:** does not fire ⇒ the offline instrument is responsive and
  ROW 1 may proceed. **Fires ⇒ STOP. The bisect is void and may not be run** — the offline seam is
  blind to whatever moved in-chain, and the arm re-scopes to an in-chain instrument, which is a new
  pre-registration. **Report the signed difference and its paired CI, never `|Δ|`** (HK-021(l)).
  ⚠️ **What this row cannot detect** (HK-022): that the offline and in-chain effects share a
  *mechanism*. Same direction is necessary, not sufficient — ROW 3 carries that caveat forward.

- **0b — is the change even in our tree?** Enumerate every commit in Windows A and B touching
  `native/` or `src/OpenWSFZ.Ft8/`, with its shim version and the win-x64 DLL SHA256 at that commit.
  **FIRES iff** the win-x64 DLL SHA256 is **unchanged across an entire window** in which the in-chain
  rate moved.
  ⇒ **Consequence:** fires ⇒ the movement in that window is **not** attributable to the native
  binary, and attention moves to managed `src/` or to harness/config state; does not fire ⇒ the
  window contains a real binary change and ROW 1 can bisect it.

### ROW 1 — the bisect

Decode the frozen corpus through the win-x64 binary at each **substantive** commit in §2, oldest
first, paired throughout.
**FIRES iff** any adjacent pair of builds shows a paired difference in offline false-accept rate
whose 95% CI **excludes zero**.
⇒ **Consequence, asserted either way:** the set of firing adjacent pairs **is** the located change
set, and is reported as such. **No fire anywhere ⇒ ROW 3.**

### ROW 2 — one step, or two

Evaluated **only** if ROW 1 fires.
- **2a — a single change point:** exactly one adjacent pair fires.
- **2b — two or more:** ⇒ **report all of them.** 🔴 The series in §2 predicts this; a report naming
  one commit when two pairs fired is a defective report.

### ROW 3 — the offline seam cannot locate it

ROW 0a passed but ROW 1 fires nowhere.
⇒ The regression is real in-chain and invisible offline ⇒ **the offline replay is the wrong
instrument for it**, notwithstanding 0a. Re-scope to an in-chain arm — new pre-registration.
🛑 **Do NOT respond to ROW 3 by widening the corpus or re-reading ROW 1 with a better metric.**

### ROW 4 — anything else

Report and stop.

---

## 5. What QA does, in order

1. Verify the corpus against `qa/ARTEFACT_INVENTORY.md`. Report any gap; do not re-render silently.
2. Extract each candidate win-x64 DLL via `git show <sha>:src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll`,
   record its SHA256 in the report's manifest, and **assert it before use**.
3. ROW 0b (cheap, no decode) — it can retire candidates before any replay runs.
4. **ROW 0a. If it fires, STOP and report.** Do not proceed to ROW 1 on a blind instrument.
5. ROW 1, then ROW 2 / ROW 3 / ROW 4.
6. NFR-021 scan every artefact before committing — the corpus is noise-only, so decoder output is
   hallucinated callsign-shaped tokens by construction. Import the shipped scanner's own
   `scan()`/`classify()` (HK-022); it cannot scan an uncommitted directory.

🛑 **HARD STOP after ROW 0a if it fires, and again after ROW 2/3/4.** QA commits locally and stops.
**QA does not push, branch, open a PR, or merge** (HK-014/HK-011). **[HK-030]: a hard stop means
pause and hand back — a note elsewhere that a later step is "not blocked" does not override it.**

⚠️ This arm is `tests/` + `qa/` only and needs **zero `src/`/`native/` diff** — extracted binaries
are read from git history into a scratch dir, never committed and never copied over
`src/OpenWSFZ.Ft8/Native/`. **Verify with `git diff --stat -- src/ native/` and say so in the
report.** If a candidate cannot be tested without a rebuild, that is an **HK-011 Developer session**,
not something to improvise.

---

## 6. Standing bars this arm does not lift

- No capture run is proposed or authorised. Everything here is offline replay of existing WAVs.
- The candidate-budget family stays closed (§0).
- `jt9 -d 3` offline is not a valid reference decoder.
- Permissive-licence policy unchanged; read-for-method only.

---

## 7. Blind prediction — 🔴 recorded so it can be scored against, and so it cannot quietly steer the arm

**I have already seen §1 and §2, so this is a post-hoc hypothesis, not a blind one.** It is written
down **because** it is the kind of hypothesis that otherwise collapses a bisect into "just test the
commit I like."

**Leading candidate: `9500e03`, `HASH_TABLE_SIZE` 256 → 4096.** Mechanism: an FT8 false accept on
pure noise is very often a hashed-callsign message that *resolves* against the hash table. A 16×
larger table changes which 12-bit hashes find an occupied slot, so noise that previously produced an
unresolvable placeholder can now render as a plausible callsign — and be counted as a false accept.
Two independent things point the same way: the `F-001` family (h12 ambiguity, unique-match
suppression) is entirely about this surface, and **ROW 0r's fire was confined to hash-placeholder
resolution/display**.

**P(Window A's step is `9500e03`) ≈ 0.5. P(a second, distinct step in Window B) ≈ 0.6.**

🛑 **This prediction gates nothing.** ROW 1 tests **every** substantive commit in both windows in
order. **QA must not test `9500e03` first, and must not stop when it fires** — scoring a prediction
is worth nothing next to mislocating a regression, and a bisect that stops at the first hit cannot
detect the two-step case ROW 2b exists for.
