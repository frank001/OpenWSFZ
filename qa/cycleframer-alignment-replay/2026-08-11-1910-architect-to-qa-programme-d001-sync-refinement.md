# PROGRAMME — D-001 resolution by sync refinement (R0 → R3)

**Author:** Architect
**Date:** 2026-08-11 19:10:21Z (mechanically derived, HK-017)
**Captain's direction, verbatim:** *"I need you to create specifications for QA to resolve D-001.
I don't care if there is developer work involved at all. just resolve the issue, we have been
staring at statistics enough."*
**Supersedes:** the Route A (observational framing study) recommendation in
`2026-08-11-1900-architect-route-memo-where-d001-lives-wsjtx-method-comparison.md` §6.
**Status:** 🔴 **AUTHORISED BY THE CAPTAIN. Developer work is explicitly in scope.**

---

## 0. Read this first — what changed, and what did not

**What changed:** this programme **builds a fix**. It is not another measurement arm. Three
consecutive measurement arms (X3 ROW 4 → X4 no row → X5 ROW 0d stop) produced zero readings, and
the Captain has ruled that the statistics phase is over.

**What did NOT change, and QA should not infer otherwise:**

- **HK-011 still governs the mechanics.** "I don't care if there is developer work involved" is a
  **scope authorisation** — stop avoiding native work to keep arms cheap — **not a process
  waiver.** QA authors the `dev-tasks/*.md`; a separate Developer session runs `opsx:apply`; the
  Captain reviews the diff. If QA reads it as a waiver, escalate rather than assume.
- **HK-014** — Architect commits locally and stops. **HK-010** — merge needs explicit sign-off.
- **HK-025** — QA may still REFUSE any spec in this set on HK-021(k) grounds. That mandate is
  standing and this programme does not suspend it.
- 🛑 **The standing prohibition list is untouched** (§5).

---

## 1. The framing shift QA must understand before reading any spec in this set

🔴 **These are BUILD specs with ACCEPTANCE CRITERIA, not experiments with pre-registered ROWs.**

The distinction is load-bearing and it is why HK-021's row machinery is largely absent below:

| measurement arm (X1–X5, P1–P3, T1/T2…) | this programme (R0–R3) |
|---|---|
| asks "what is true?" | asks "does the thing we built work?" |
| a null is a finding | a null is **either** a finding **or** an implementation bug |
| gate rows decide the reading | acceptance criteria decide ship / fix / stop |
| technique is unproven | 🔴 **technique is proven — WSJT-X has run it for years over millions of decodes** |

⚠️ **The one genuine hazard this creates, and R1 exists solely to defeat it:** *an implementation
bug that produces no gain is indistinguishable from a falsified hypothesis.* If we wire refinement
into the decode path and recovery does not move, we cannot tell whether refinement doesn't help or
whether our refiner is broken. **R1 validates the refiner as an instrument against a synthetic
oracle with known answers, before it is ever allowed to touch the corpus.** Do not skip it, and do
not merge it into R2 to save time — that trade destroys the interpretability of the entire
programme.

---

## 2. What is being built, in one paragraph

For each candidate, go back to the original PCM, downconvert to **complex baseband** at the
candidate's frequency, and refine its (frequency, time) position by **coherent correlation against
the three Costas 7×7 sync arrays** — then extract symbols at the refined position instead of at the
quantised lattice point. This is WSJT-X's method (`ft8_downsample` → `sync8d` → refined `ft8b`
extraction), **reimplemented from the method, never copied**. 🛑 **Method only — see §2.1 for the
Captain's binding licence policy and the two Architect errors it corrects.**

Current resolution **3.125 Hz / 0.08 s**, no refinement. WSJT-X's achieved resolution
**≈0.5 Hz / 5 ms**. Evidence this cashes out: P3's `S_all` = **4.27 pp** from crudely shifting the
input by ⅓ of a lattice cell — the largest single-arm effect in the programme, and P3's own
conclusion was *"refine INSIDE the decoder, not by a union bolted outside it."*

### 2.1 🛑 LICENCE POLICY — CAPTAIN'S RULING, 2026-08-11. Binding on this programme and everything after it.

**Ruling, as given:** *"The project will only use MIT compliant code … nothing else will be used
from non MIT compliant sources, although the project has a GPL licence of sorts."*

🛑 **POLICY: only MIT-compliant third-party code may be incorporated into OpenWSFZ. No exceptions,
and this is stricter than the licences alone would require.**

**Clarified by the Captain, same session — apply these, do not re-litigate them:**

| question | ruling |
|---|---|
| Does **BSD-3-Clause** satisfy "MIT compliant"? | ✅ **YES.** Permissive licences qualify. **KISS FFT (`fft/kiss_fft.c`, `kiss_fftr.c`, BSD-3-Clause, Mark Borgerding) STAYS** — no replacement work. R0 adds the attribution it requires. |
| The WSJT-X-derived **LDPC tables** in `ft8/constants.h` (in the shipped DLL) | ✅ **FLAG, DO NOT BLOCK.** Recorded in R0's notices as a known upstream inheritance. Rationale: LDPC parity matrices are FT8 **protocol constants** — any conformant implementation must use the identical matrix. **Not a blocker. Do not stop the programme for it.** |
| The **Fortran** remark in the original ruling | Withdrawn by the Captain (*"skip it, i misunderstood"*). **There is no Fortran plan.** `ft4_ft8_public/` is simply excluded from vendoring — see R0. |

⇒ **Working rule for QA: permissive (MIT / BSD-2 / BSD-3 / ISC) is acceptable and needs only
correct attribution. GPL-derived code may NOT be copied in.**

**Two Architect errors this corrects, both recorded rather than quietly fixed:**

1. ❌ I asserted across the memo and the first drafts of R0/R1 that *"ft8_lib is MIT and WSJT-X is
   GPLv3, so copying WSJT-X code would relicense our decoder."* **The premise about our own project
   was wrong** — `LICENSE` at the repo root is **AGPL-3.0**, not MIT. I had not looked.
2. ❌ Having found that, I then reasoned that GPLv3→AGPLv3 is licence-compatible and therefore
   *"there is no legal bar to incorporating WSJT-X code."* **That conclusion is now
   SUPERSEDED BY POLICY.** Whether or not it is legally available is beside the point: **the
   Captain has ruled it out.** The project's own AGPL licence does **not** license us to pull GPL
   code in.

🔴 **Consequences QA must apply, without needing to re-derive them:**

- **WSJT-X source may be read for UNDERSTANDING of the method. Not one line may be copied,
  transliterated, or ported.** This is now a prohibition, not a judgement call, and it is not
  negotiable by QA or by a Developer session.
- **"Method, not code" is therefore backed by BOTH policy and engineering.** The engineering
  reasons stand on their own and are worth keeping in view: Fortran→C transliteration of numerical
  DSP is a bug farm (exactly the failure R1 §5 hunts), and borrowed code we do not understand is
  how `ft8_decode_multi_symbols()` came to be dead *and* wrong in the tree already.
- 🔴 **Anything already in the tree that is not MIT-compliant is now a DEFECT to be surfaced, not
  a fact to be lived with.** The audit found candidates; see R0 §2 D5 and the escalation in §7.

⚠️ **I am not a lawyer and none of this is legal advice** — it is a reading of licence texts found
on disk, recorded so the Captain's policy can be applied mechanically.

---

## 3. The ladder

| spec | what it delivers | touches `src/`? | depends on |
|---|---|---|---|
| **R0** | A native build reproducible from pinned sources | build system only, **no behaviour change** | — |
| **R1** | The refiner, validated as an instrument on synthetic signals | new code, **not wired into decode** | R0 |
| **R2** | Refinement wired into the decode path; recovery + FP measured | 🔴 yes, behaviour change | R1 PASS |
| **R3** | Coherent multi-symbol LLRs (`bmetb`/`bmetc` analogue) | yes | R2 ships |

**R3 is deliberately not specced yet.** Its design depends on what R1 measures about achievable
refinement precision and what R2 measures about headroom. Pre-committing its parameters now would
be the HK-021(k) failure mode — writing a gate whose inputs do not exist. It gets a spec after R2.

### 3.1 Why R0 is a blocker and not bureaucracy

🔴 **Established by code read today:** `native/ft8_lib_build/rebuild_shim.bat` recompiles **only**
`decode.c` and `ft8_shim.c`. It links **nine further object files** — `constants`, `crc`, `encode`,
`ldpc`, `message`, `text`, `monitor`, `kiss_fft`, `kiss_fftr` — which are **frozen build artefacts
dated 2026-05-29 to 2026-06-14, untracked in git** (only `message.obj` is tracked). The build
cannot regenerate them.

✅ **One alarm in this document's first draft was WRONG and is corrected here rather than left to
propagate.** It claimed the sources were *"currently modified and uncommitted"*, implying the
objects were built from since-changed code. `git status` does show ~27 modified files in
`C:\Temp\ft8_lib_headers` — but **`git diff --ignore-cr-at-eol` returns empty: every one is
line-ending noise (LF→CRLF).** The tree is content-identical to `d18ed84`. **QA should verify this
in one command and not inherit the panic version.** *(HK-018 working as intended — a five-minute
check beat a paragraph of reasoning.)*

🔴 **The real problem is narrower and still disqualifying: nine of eleven linked objects have no
recorded provenance and cannot be regenerated.** The pinned production DLL `f2f30c89…` cannot be
rebuilt from source today; every replay arm is pinned to a binary we cannot reconstruct; and R1/R2
would link new code against those same opaque artefacts.

⚠️ **This is the same defect class that has already cost this programme once** — the `39aa1031…`
DLL that P2/P3/P1a ran turned out to be `d001-rc4-decode-depth`'s unmerged three-pass diagnostic
build, and the confound could only be bounded "by analogy" at ~+0.70 pp. **Building the largest
native change in the programme on that foundation would make a null result uninterpretable.**

---

## 4. How the ladder resolves D-001 — in BOTH directions

This is the part that answers the Captain's "just resolve the issue", and it matters that it works
whichever way the numbers fall:

- **R1 FAIL** → our refiner is broken. Fix it. **Says nothing about D-001.** (This is the whole
  reason R1 is separate.)
- **R1 PASS + R2 recovery rises, FP flat** → **D-001 is resolved and the fix ships.**
- **R1 PASS + R2 recovery rises, FP also rises** → a real engineering trade, and the Captain rules
  on it. Still a resolution: the cause is confirmed and priced.
- **R1 PASS + R2 recovery flat** → 🔴 **the architectural hypothesis that has organised the last
  month is FALSIFIED**, with a validated instrument behind the null. That is *also* a resolution —
  and a far more valuable one than another inconclusive statistic, because it would mean the
  lattice is not the binding constraint and the programme must look elsewhere with that
  definitively closed.

🛑 **I am putting NO magnitude prediction on R2, deliberately.** My calibration record is
DIRECTIONAL **1/3**, ranges **8/15**, and the last four magnitude calls all missed with the
interval right and the actionable implication wrong. A number from me here would anchor an
acceptance bar it has no business anchoring. **R2's bars are derived from measured baselines, not
from my expectation** — see that spec's §4.

---

## 5. Standing prohibitions — unchanged, and one new trap

🛑 **`subtractft8` (subtract-and-resynthesise) terminates the WSJT-X pipeline and is DEAD for us.**
Three builds, three reverts, **−17 pp at worst.** 🔴 **Called out here because this programme sends
QA and a Developer to read WSJT-X's decoder end to end, and they will find it and be tempted to
"complete the method". DO NOT.** It is not part of R0–R3 and adding it voids the arm.

Also unchanged: input scaling/AGC/normalisation/equalisation **CLOSED** (P2) · candidate-budget
family **closed twice** · `A` = 15.55 **DEAD** · spectral locality **RETIRED PERMANENTLY** (X5) ·
`E_sep` +46.039 pp, `k_50`, `c_bottom`, `Δ_local`/`Δ_cycle`, `sensitivity_25_100` **uncitable** ·
hash-table saturation costs **message TEXT only**.

⚠️ **`K_FREQ_OSR`/`K_TIME_OSR` 2→4 is NOT part of this programme.** It remains barred on P3's
evidence and would need its own pre-registration with FP primary. Refinement **supersedes** it —
OSR 4 costs 4× the waterfall for 1.5625 Hz / 0.04 s and still has no refinement, while R2 targets
WSJT-X's ≈0.5 Hz / 5 ms at a cost proportional to *candidates*. If a Developer proposes OSR as a
shortcut, refuse and escalate.

---

## 6. Pins and provenance binding all four specs

| item | value |
|---|---|
| baseline DLL | `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll`, SHA256 `f2f30c890b253eb6b69aa1a89c26d2991ee70aa2a202c68361130344bb7d4015`, shim `20260033` |
| 🛑 **never** use | `39aa1031…` (unmerged RC4 three-pass diagnostic build) |
| shim versions | **20260038 is G2's.** This programme takes **20260039** (R0), **20260040** (R1), **20260041** (R2). One per spec, asserted at startup. |
| native upstream | `github.com/frank001/ft8_lib`, MIT, currently `d18ed84` + ~27 uncommitted modifications |
| replay corpus | 20m, `artefacts/20260808_live_run_0016-808{0,1}/`, 2 529 cycles, `REF` = **69 222** |
| baseline recovery | **≈57.8%** (H1a retired the `[55.5, 57.8]` bracket; `V` = 0.9968) |
| baseline FP | **4.24–4.90%** (class-rate-weighted estimate, ~4.7% best) |
| 🔴 must fix first | `p23_common.py:182` `a.keys() & b.keys()` — hash-randomised set iteration; **P2/P3/P1a determinism was never actually verified.** R0 fixes it. |

---

## 7. Order, and what QA escalates rather than settles

**Run strictly R0 → R1 → R2.** No overlapping, no merging steps.

Escalate to the Captain, do not settle in session:
1. **R0's behavioural-equality check failing** (§3.1) — that means the shipped DLL differs from its
   nominal sources, which is a finding about everything already published, not just this programme.
2. **Any proposal to skip R1** or to fold it into R2.
3. **R2 showing recovery up and FP up** — that is the Captain's trade to make, not QA's.
4. **Any suggestion to add subtract-and-resynthesise.**

**Specs:**
- `2026-08-11-1910-architect-to-qa-spec-r0-reproducible-native-build.md`
- `2026-08-11-1910-architect-to-qa-spec-r1-sync-refiner-instrument-validation.md`
- `2026-08-11-1910-architect-to-qa-spec-r2-refinement-in-decode-path.md`
