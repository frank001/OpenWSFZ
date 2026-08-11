# QA WORK QUEUE — D-001 sync refinement (R0 → R1 → R2)

**Author:** Architect → QA
**Date:** 2026-08-11 19:38:16Z (mechanically derived, HK-017)
**Status:** 🔴 **THE SINGLE ENTRY POINT FOR QA. This is the document to hand over.**
**Supersedes:** `2026-08-10-2028-architect-to-qa-consolidated-work-queue.md` — **fully closed out**
(all four items A/B/C/D done). Read it for provenance only.
🔴 **Where this queue disagrees with a spec, the SPEC WINS.**

✅ **Every path in this document was verified to exist on disk before it was written** (16/16),
and the baseline DLL SHA was re-computed, not copied from memory.

---

## §0 — What changed, in four lines

1. **The Captain has closed the statistics phase.** *"just resolve the issue, we have been staring
   at statistics enough."* **Developer work is explicitly authorised.**
2. **D-001 has been re-localised**, and the previous framing was wrong in an important way — §0.5.
3. **Three build specs are live: R0 → R1 → R2.** They are **build specs with acceptance criteria**,
   not measurement arms with ROWs.
4. **A binding licence policy now exists** and applies to all future work, not just this programme.

---

## §0.5 — 🔴 Statements previously believed that are now KNOWN WRONG

Read this before anything else. Each was believed and acted on; each is corrected in the linked
document rather than quietly dropped.

| previously believed | corrected to |
|---|---|
| "D-001 is in the decode stage, sub-stage demodulation" — used as a settled localisation | **Too loose.** "Decoder" meant three different things. **ERROR CORRECTION is ruled out and is genuinely STRONG** (`E` = 4.28; corrects to 11.3% BER) while misses arrive at **44% median BER** — indistinguishable from noise, i.e. the signature of *reading in the wrong place*. The failure is **upstream of where the bits are formed.** |
| The waterfall/front end was implicitly a fixed given | 🔴 **Stage 4 (FFT → `uint8_t` magnitude waterfall, phase discarded) is the ONLY pipeline stage no D-001 arm has ever touched.** Every arm ran downstream of it or on `ALL.TXT` statistics. |
| "ft8_lib is MIT, so copying WSJT-X would relicense our decoder" | ❌ **Premise wrong — OpenWSFZ is AGPL-3.0** (repo-root `LICENSE`). |
| …therefore "GPL→AGPL is compatible, so copying WSJT-X is available" | ❌ **Superseded by the Captain's POLICY** — §4. Correct legally, irrelevant in practice. |
| "The native sources are modified and uncommitted" (Architect alarm, this session) | ❌ **Overstated.** `git diff --ignore-cr-at-eol` is **empty** — all ~27 are line-ending noise; the tree is content-identical to `d18ed84`. **The real defect is narrower and still disqualifying** — see R0. |
| `WATERFALL_USE_PHASE` looks like a one-line unlock | ❌ **Dead switch.** Zero `#ifdef` branches in `decode.c`. Enabling it yields a `.phase` field no code reads. |
| `ft8_decode_multi_symbols()` is a disabled coherent metric | ❌ **Dead code AND wrong** — it adds **dB magnitudes**, not complex values. Not a model to follow. |

---

## §1 — The document set

| # | document | what it is |
|---|---|---|
| 1 | `2026-08-11-1900-architect-route-memo-where-d001-lives-wsjtx-method-comparison.md` | **Background.** Pipeline laid out stage by stage with each stage's evidence status; the WSJT-X method comparison; three cheap options checked and killed. **Read for context; it is not a spec.** |
| 2 | `2026-08-11-1910-architect-to-qa-programme-d001-sync-refinement.md` | 🔴 **The programme.** The ladder, the licence policy (§2.1), prohibitions, pins, escalation list. **Read this second.** |
| 3 | `2026-08-11-1910-architect-to-qa-spec-r0-reproducible-native-build.md` | **TASK 1** |
| 4 | `2026-08-11-1910-architect-to-qa-spec-r1-sync-refiner-instrument-validation.md` | **TASK 2** |
| 5 | `2026-08-11-1910-architect-to-qa-spec-r2-refinement-in-decode-path.md` | **TASK 3** |

All five committed locally at **`d5ce602`** (not pushed — HK-014). **R3 is deliberately not
specced**; its inputs do not exist until R2 reports.

**Reading order: 2 → 1 → 3 → 4 → 5.** Start with the programme, then the memo for background.

---

## §2 — The tasks

**Run strictly in order. Do not overlap them, and do not merge R1 into R2.**

### TASK 1 — R0: reproducible native build
**Goal:** be able to rebuild the production decoder from version-controlled sources.
**Why it blocks:** nine of eleven linked `.obj` files are untracked artefacts dated 2026-05-29 to
06-14 with no provenance; `rebuild_shim.bat` recompiles only `decode.c` and `ft8_shim.c`. **The
pinned DLL cannot be rebuilt from source today**, and R1/R2 would link new code against those
opaque artefacts — so an R2 null could be caused by them rather than by the change. Same defect
class that already confounded P2/P3/P1a via the `39aa1031…` DLL.
**Deliverables:** D1 vendor sources · D2 rebuild every TU · D3 fix `p23_common.py:182` · D4
`--assert-dll-sha` · **D5 `THIRD-PARTY-NOTICES.md`** (a real, pre-existing compliance gap — the
repo ships no attribution of any kind).
**Acceptance:** AC-1 **behavioural equality** vs the pinned DLL on ≥200 cycles, mechanically
diffed · AC-2 reproducibility · AC-3 shim 20260039 · AC-4 licence hygiene.
🔴 **AC-1 FAIL ⇒ STOP AND ESCALATE** — it would mean the shipped DLL does not match its nominal
sources, which is a finding about everything already published off it, X3 included.

### TASK 2 — R1: the refiner, validated as an instrument
**Goal:** build per-candidate complex-baseband downconversion + coherent Costas refinement, and
**prove it finds known offsets** — without touching the decode path.
**Why it is separate, and why QA must refuse any request to fold it into R2:** 🔴 **an
implementation bug and a falsified hypothesis look identical.** Only an instrument validated
against a synthetic oracle makes an R2 null interpretable.
**Oracle:** `qa/rr-study/synth/` (encoder-only — truth known by construction). Offsets placed
deliberately across a full lattice cell, six SNR strata, n ≥ 200 per cell.
**Acceptance:** AC-1 accuracy (RMS ≤ 0.30 Hz / 7.7 ms — **3× better than the lattice quantisation
it replaces**, derived not guessed) · **AC-2 no systematic bias** (hunts the sign-convention bug —
see that spec's §5) · **AC-3 noise-only control** (must not lock on noise) · AC-4 monotone in SNR ·
AC-5 determinism · AC-6 cost, reported not gated.
🔴 **AC-3 FAIL ⇒ STOP, do not proceed to R2.**

### TASK 3 — R2: refinement in the decode path — **the arm that resolves D-001**
**Goal:** extract symbols **from the complex baseband at the refined position** and measure.
🔴 **The design point that must not be got wrong:** refining to 0.5 Hz / 5 ms and then reading
symbols off the 3.125 Hz / 0.08 s magnitude waterfall throws the refinement away. Extraction must
happen on the baseband.
**Scope:** non-coherent single-symbol extraction at the refined position. 🛑 **Coherent
multi-symbol is R3 and is OUT OF SCOPE.**
**Metrics:** M1 recovery (co-primary) · **M2 false positives (co-primary, NOT deferred)** · **M3
`mean_r`** — the cheap independent end-to-end confirmation · M4 cost.
**Pre-flight ROW 0a–0e**, including 🔴 **0d: assert the refiner is actually firing on the
production path** (≥50% of decoded candidates carry a non-zero applied refinement). A correctly
computed but unconsulted refiner produces a *perfect null that looks like a falsification*.

🔴 **M3 is the most valuable single check in the set and it is nearly free.** Our decoder currently
reports **on-grid** (`mean_r` = 0.2397 — pure integer-Hz rounding); WSJT-X reports **off-grid**
(0.7398, indistinguishable from the closed-form uniform null of **0.780**). After R2 our `mean_r`
must move off 0.24. **It tells us refinement reached the output independently of whether it
helped** — which is exactly what separates "hypothesis falsified" from "integration bug."

---

## §3 — Pins, corpora, harness reuse

| item | value |
|---|---|
| baseline DLL | `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll` — SHA256 **`f2f30c890b253eb6b69aa1a89c26d2991ee70aa2a202c68361130344bb7d4015`** ✅ *re-verified 2026-08-11*, shim **20260033** |
| 🛑 never use | `39aa1031…` — unmerged `d001-rc4-decode-depth` three-pass diagnostic build |
| shim integers | G2 holds **20260038**. This programme: **R0 = 20260039, R1 = 20260040, R2 = 20260041** |
| corpus | `artefacts/20260808_live_run_0016-8080/` + `-8081/`, 20m, **2 529 cycles** |
| `REF` | **69 222** (two-instance intersection) |
| baseline recovery | **≈57.8%** (H1a retired the bracket; `V` = 0.9968) |
| baseline FP | **4.24–4.90%**, best estimate ~4.7% |
| native upstream | `github.com/frank001/ft8_lib`, **MIT**, HEAD `d18ed84`, at `C:\Temp\ft8_lib_headers` (⚠️ **outside version control** — R0 fixes this) |
| oracle | `qa/rr-study/synth/` |
| 🔴 fix before R2 | `qa/cycleframer-alignment-replay/p23_common.py:182` — `a.keys() & b.keys()` hash-randomised iteration. **P2/P3/P1a determinism was never actually verified.** R0 D3. |
| `ALL.TXT` fields | `[4]` SNR · `[5]` **DT** · `[6]` **freq Hz** — ⚠️ confusing 5/6 inverts a result exactly |

---

## §4 — 🛑 Licence policy — Captain's ruling, 2026-08-11, binding on all future work

**Permissive only: MIT / BSD-2 / BSD-3 / ISC. No GPL-derived code may be copied in, from WSJT-X or
anywhere else. WSJT-X may be READ for method; not one line copied, transliterated, or ported.**

| question | ruling |
|---|---|
| BSD-3-Clause acceptable? | ✅ **Yes.** **KISS FFT stays** — attribution, not replacement. |
| WSJT-X-derived LDPC tables in `ft8/constants.h` (lines 75, 78), linked into the shipped DLL | ✅ **FLAG, DO NOT BLOCK** — protocol constants; inherited from upstream. 🛑 Do not delete the attribution comments: they are the only provenance record. |
| `ft4_ft8_public/` (Fortran, **no licence header**) | 🛑 **Do not vendor.** Nothing we build compiles Fortran. The Captain's original "we need the FT8 fortran decoder" was **withdrawn** (*"skip it, i misunderstood"*). |
| Repo attribution | 🔴 **None exists today.** R0 D5 creates `THIRD-PARTY-NOTICES.md`. |

⚠️ Not legal advice — a reading of licence texts on disk, recorded so the policy can be applied
mechanically.

---

## §5 — Standing prohibitions (unchanged) and one new trap

🛑 **NEW TRAP — `subtractft8` / subtract-and-resynthesise terminates the WSJT-X pipeline and is DEAD
for us.** Three builds, three reverts, **−17 pp at worst.** 🔴 **Called out because this programme
sends QA and a Developer to read WSJT-X's decoder end to end and they WILL find it and be tempted
to "complete the method." DO NOT. Adding it voids the arm.**

Unchanged: input scaling / normalisation / AGC / equalisation **CLOSED** (P2, `P` = 0.007 pp over
±18 dB) · candidate-budget family **closed twice** · `A` = 15.55 **DEAD, uncitable in every form**;
the depth caveat stays exactly as worded · **spectral locality RETIRED PERMANENTLY** (X5) · hash
saturation costs **message TEXT only** · **`K_FREQ_OSR`/`K_TIME_OSR` 2→4 barred** on P3's evidence
— needs its own pre-registration with **FP primary**; **refinement supersedes it**, and if a
Developer proposes OSR as a shortcut, **refuse and escalate**.
🛑 **Citation blacklist:** `k_50 = 13`, `c_bottom = 0.476%`, `E_sep` = +46.039 pp,
`Δ_local`/`Δ_cycle`, `sensitivity_25_100`, "17m runs 2–3 pts above 20m."

---

## §6 — Escalate, do not settle in session

1. **R0 AC-1 FAIL** — a finding about everything already published, not just this programme.
2. **Any request to skip R1** or fold it into R2 — **HK-025 permits outright refusal.**
3. **R2 recovery up AND FP up** — a real engineering trade; **the Captain's call, not QA's.** Do
   not tune parameters to make a bar pass.
4. **Any proposal to add subtract-and-resynthesise, or an OSR change.**
5. 🔴 **G2 sequencing — see §7. This one needs a ruling before R0 starts.**

---

## §7 — 🔴 The one open conflict: G2 vs this programme

**G2 was the only item on the previous open queue** (`dev-tasks/2026-08-10-g2-hash-table-sizing-and-candidate-passband.md`
— authored, no `src/` touched, awaiting a Developer session). It is **not superseded** by this
programme, but it **collides with it** and the collision is not addressed in any spec:

- G2 (b) widens the hardcoded `[200, 3000)` Hz candidate passband ⇒ **changes decoder behaviour**
  ⇒ **moves R2's baseline.**
- R2 measures both legs in one session, so a G2-shipped baseline is *internally* fine — but if G2
  lands **between** R0 and R2, the pins and the 57.8% baseline in every document above go stale
  mid-programme.

**Architect recommendation (the Captain's decision, not QA's): G2 either ships BEFORE R0 — so the
whole programme baselines against it once — or WAITS until after R2 reports.** 🛑 **Do not let it
land in the middle.**
⚠️ G2's own §0 shim-version blocker is resolved (**20260038**); that is separate from this.

---

## §8 — Reporting standard and constraints

**Per task:** a QA→Architect report, HK-017 timestamps, the acceptance criteria evaluated **in
order**, mechanical evidence for every claim (byte-diffs, not assertions), clustered CIs where a
CI is quoted (HK-021(i): cluster, **never binomial**), predictions scored, and **explicit citation
limits** — what may and may not be quoted.

🔴 **HK-011 in full** — QA authors `dev-tasks/*.md` and **STOPS**; a separate Developer session
runs `opsx:apply`; the Captain reviews the diff. **The Captain's "I don't care if there is
developer work involved" authorises the WORK, not a shortcut through the PROCESS.**
🔴 **HK-014** no push/merge by Architect · **HK-010** merge needs explicit sign-off · **HK-006**
`pre_merge_check.py` on the Captain's initiative only · **HK-024** update `BOARD.md` in the same
edit as any board-changing result · **HK-022** verify claimed downstream edits by opening them.

⚠️ **Architect calibration, quote wherever a bar turns on a prediction:** categorical 5/7, ranges
8/15, **DIRECTIONAL 1/3**, mechanical 2/2. 🔴 **No gate in R0/R1/R2 turns on an Architect
prediction** — every bar derives from the corpus, a measured baseline, or a closed-form null. If
you find one that does, that is a drafting defect: **name it and refuse the spec** (HK-025).
