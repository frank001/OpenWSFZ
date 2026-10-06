# REVIEW — A′ (D-001 limb 2, coherent multi-symbol bit formation): why it stalled twice, and whether it should restart

- **To:** the Captain (cc QA)  **From:** Architect  **Date:** 2026-10-06 16:10Z (`date -u`, HK-017)
- **Branch:** `arch/coherent-limb2` (cut from `origin/main` `be3cc5ac`). Docs plus one exploratory script (`qa/rr-study/a-prime-review/recall_shape.py`); `git diff --stat -- src/ native/` empty.
- **Asked by:** the Captain, 2026-10-06 (*"Yes, review first"*, then *"go ahead with the A′ review"*). This is the review that priority #1 required before any A′ spec. **It is not a spec, and nothing here is gated.**

---

> ⛔ **SUPERSEDED 2026-10-06 ~16:2xZ (`date -u` 16:22Z): the Captain rejected §1's recommendation and REOPENED limb 2.** Captain: *"after pushing on the most probable improvement for the decoding we find we can maybe close the 30.2 pp gap with 17.88% and your advice is to park it. right."* **The Architect withdraws the recommendation: it applied the wrong bar** ("does it close the gap", C-GAP-D's framing) instead of the programme's ("what improves decoding most"). By this review's own §4, A′ is the largest sized lever left. The history (§2), the corrections (§3) and the figures (§4) stand. Next is **step 1, `COH-GAIN`**: `2026-10-06-1625-architect-to-qa-spec-coh-gain-step1.md`. Option (ii) is taken, with step 1 replacing "re-run ROW 0g-2 first" as the deciding measurement.

## 1. Answer first

~~**Recommendation: do NOT restart A′ as a build. Keep it parked.**~~ *(withdrawn, see the note above)* The reason is not that it doesn't work. It is that **the remaining gap is still not shaped like an SNR deficit**, so a better-bits lever is capped well below the gap:

- I re-asked, on the newest night (2026-10-04, subtraction ON), the question that stopped limb 2 in August. **The answer has not changed.**
- A realistic coherent gain (≈ 2–3 dB) is worth **at most ≈ 3.8–5.4 pp** of today's **30.2 pp** gap. **Even the theoretical ceiling (4.8 dB) is worth at most ≈ 8.3 pp.** These are upper bounds by construction, and exploratory (§4).
- **A standing ruling already bars presenting limb 2 as a gap treatment** (C-GAP-D, 2026-08-22, §3). This review gives no new evidence that would lift it, and some that supports it.
- That is still a real number, larger than anything else on the table except subtraction. But it comes at weeks of native work on an extractor that **still reads worse than the one we ship** (§2) and needs a native fine-frequency stage that does not exist. **If the Captain wants it anyway, §6 gives the cheapest honest first step**, and it is not a build.

---

## 2. Why it stalled: two different stops, not one

### Stop 1 (2026-08-16 → 08-21): instrument defects, not physics

The coherent extractor (`coherent_llr.c`, exported as `ft8_coherent_llr_at`, merged in PR #128) and the fine sync refiner (`sync_refiner.c`, `ft8_refine_candidate`) were built. Every attempt to measure them hit a **measurement-geometry defect**:

- **N2:** read at chance (48 % BER) until a **one-symbol (0.16 s) time-origin displacement** was found and calibrated out.
- **N2 ruling:** an integer-Hz rounding helper, reused on my own instruction, became a live error once the extractor stopped snapping to the lattice. Total anchor error was up to ±2.06 Hz.
- **N3:** the frequency-error curve never flattened inside ±4 Hz, because the coherent metric's own feature scale is 6.25 Hz. In the NumPy ladder, coherent order was **worse** than the shipped extractor without fine frequency (V0 2.87 % vs V3 8.05 % median BER, as recorded on the board). ⇒ **fine frequency is a prerequisite, not an option.**
- **ROW 0g** (the instrument-gain check guarding Phase 1's kill gate) **fired**. Three confounds favoured the passing limb (exact-lattice frequency, swept vs unswept timing, channel).
- **Phase B** fixed the origin and the 1/2/3-symbol fusion scaling. ROW 0g-2's deficit went from −67 to **−3 bits** (median), CI `[−5, −2]`. **That is still worse than the shipped grid extractor on real rows.** The kill gate (Phase 1 task 4.3) is **VOID**, and the Phase B re-run (`tasks.md` §11) was **never scheduled**.
- `sync_refiner.c:161–212` records why the refiner **retreated to non-coherent** cross-symbol combining: CPFSK phase between symbols depends on the unknown intervening data. WSJT-X's answer is hypothesis enumeration over 8ⁿ symbol patterns (its 2- and 3-symbol `bmetb`/`bmetc`). **That is unbuilt here.**

**State today:** the code is on `main`, linked, and **unwired** (no production call site). The exports **snap to the 3.125 Hz / 0.08 s lattice** (measured, B-pos-A), so fine frequency cannot be tried through them without a native change.

### Stop 2 (2026-08-22 → 09-14): a sizing verdict, deliberately taken

This one was **not** a defect. **C-GAP-D** asked what a *perfect* bits improvement would be worth:

- Recall against WSJT-X's SNR was a **shallow ramp that never saturates**, not a sigmoid displaced sideways.
- A uniform `s`-dB improvement is bounded by shifting that ramp: **3 dB ⇒ 7.00 pp of a 43.8 pp gap**, replicated across 3 bands and both legs (`[4.66, 7.17]` pp, CIs far under the 10 pp bar).

**The ruling, as pre-registered:** *"extraction quality is NOT D-001's route. Route B2's remaining limb (coherent-LLR) may NOT be described as a D-001 treatment in any subsequent proposal. Phase C is NOT authorised on gap-closing grounds"* (archive 2026-08-22). **Explicitly not "dead"**: a statement about magnitude, not viability.

**THRESH-A** (2026-09-13) then found the *isolated-threshold* loss is in bit formation, not candidate acquisition, and offered "reopen Route B2 on sensitivity grounds". **I recommended parking, and the Captain accepted** (2026-09-14 15:16Z, *"proceed with the recommendations"*).

⇒ **Limb 2 did not stall twice for the same reason.** It stalled once on measurement, then was **parked on a sizing result**. Restarting the build fixes the first and ignores the second.

---

## 3. A correction to priority #1's own case for A′ (mine)

The priority-1 to-do argued that A′ *"matches where GAP-LOCATE put the loss (bit formation; THRESH-A, DENSITY-MECH M1)"*. Two problems:

1. 🛑 **`DENSITY-MECH` is VOID and must never be cited as "M1/extraction"** (`workstream-guards-2026-09-24.md:30`). I cited it anyway. Withdrawn; the to-do is corrected in the same pass.
2. **GAP-LOCATE does not point at A′.** Its N = 17.06 pp of 19.27 pp are signals in the **strong-miss pool** (`H10`), with N still 1,347 rows at ≥ +10 dB, that we cannot decode **even at WSJT-X's position**, and D5 says **another transmission dominates the cell** (1,150 CRC-valid same-type different messages). That is **interference-limited** loss. Coherent combining is a **noise-limited sensitivity** gain. These are different mechanisms. GAP-LOCATE locates the loss in "extraction plus LDPC/OSD". It does **not** say better-SNR bits would recover it.

And the board line *"WSJT-X earns its whole lead without AP, so A′ is its documented non-AP advantage"* is true about WSJT-X. It does not tell us which part of the 30 pp that advantage covers. §4 answers that part.

---

## 4. The August question, re-asked on the newest night (EXPLORATORY)

`recall_shape.py` (this branch). Night `20261004_1634` (40 m, `main` `040613d9`, shim 20260058, flag ON, `nhard` 40). Both live `ALL.TXT`s, Test B's match rule (same cycle, same text, |Δf| ≤ 10 Hz, one-to-one). **One night, one band, no clustering, no CI.** HK-037: message text never leaves the reading function; only binned counts are printed.

**3,099 cycles, 98,156 WSJT-X decodes, 69.81 % matched** (Test B rule, so not the Section 4 figure).

| WSJT-X SNR (dB) | −24 | −20 | −16 | −12 | −8 | −4 | 0 | +4 | +8 | +12 | +16 | +20 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| our recall | 0.28 | 0.42 | 0.54 | 0.63 | 0.71 | 0.78 | 0.85 | 0.90 | 0.94 | 0.95 | 0.95 | 0.97 |

**Same shape as August**, lifted by subtraction (August: 0.50 @ −11, 0.77 @ −1, 0.93 @ +19). It is still a ramp that does not saturate.

**C-GAP-D's shift estimator** (upper bound: it credits the shift with every other failure mode too; linear interpolation between 2 dB bins):

| better bits by | 1 dB | 2 dB | 3 dB | 4.8 dB (coherent theoretical max) | 6 dB | 10 dB |
|---|---|---|---|---|---|---|
| gain, pp of WSJT-X decodes | 1.88 | 3.76 | **5.40** | **8.26** | 10.09 | 15.29 |
| share of today's 30.19 pp gap | 6 % | 12 % | **18 %** | 27 % | 33 % | 51 % |

**High-SNR misses vs band load** (WSJT-X SNR ≥ 0 dB, by WSJT-X-decodes-per-cycle quintile): recall 0.922 → 0.907 → 0.895 → 0.903 → 0.894. **Only a mild load trend.** Part of the high-SNR residue is probably text-rendering mismatch (hashed calls), not a missed decode (C-GAP-D's own second finding). I have not separated that here.

**Reading:** an SNR lever of realistic size is worth **≲ 5 pp** of a 30 pp gap at most, about **the same share as in August (16 → 18 %)**. Subtraction raised the curve and did not change its shape. **The C-GAP-D conclusion replicates, exploratorily, on the post-subtraction build.** 🛑 Do not cite these figures as a result: they are an Architect drafting check (the C-GAP-D precedent). A citable version is §6 option (i).

---

## 5. What A′ would really cost (for the Captain's weighing)

| step | what | owner | native? |
|---|---|---|---|
| a | a fine-frequency stage the coherent metric can use (the exports snap to the lattice today) | Developer | yes (new shim) |
| b | 2/3-symbol coherent metrics by data-hypothesis enumeration (WSJT-X's `bmetb`/`bmetc` approach; `sync_refiner.c` had to retreat from naïve combining) | Developer | yes |
| c | close the open instrument gate: ROW 0g-2 must stop reading −3 bits vs the shipped extractor (Phase B `tasks.md` §11) | QA | no |
| d | wire it in, flag-gated, default OFF; offline flag-OFF/ON replay vs WSJT-X (the SUB-FEAS pattern) | Developer + QA | yes |

**Weeks, not days.** Twice already the measurement geometry, not the physics, took the time. **Licence policy:** WSJT-X is GPL, so steps a/b must be **clean-room** from published descriptions (`standing-licence-policy.md`), as `sync_refiner.c` was.

---

## 6. Options for the Captain

| option | what | cost | recommended |
|---|---|---|---|
| **(o) Park A′ again** | Keep limb 2 parked under the C-GAP-D ruling. Priority #1 continues with B (`NHARD-REP`, running) and C (latency). | none | ✅ **yes** |
| **(i) Make §4 citable** | QA replicates C-GAP-D on two post-subtraction nights (`20261004_1634`, `20260930_1930`) with cycle-clustered CIs and a frequency-shift null for the text-mismatch residue, using the archived logs. **It decides A′ on evidence, not on my exploratory table.** | ≈ ½ day QA, no PC-exclusive time, no build | if you want the parking on record with a citable figure |
| **(ii) Restart A′ on "sensitivity" grounds** | Accept a ≲ 5 pp ceiling as worth weeks of native work. **First step:** QA re-runs ROW 0g-2 on today's binary (step c). No build until the coherent path at least matches the shipped one. | weeks overall; first step ≈ ½ day | not now |

**What I would look at instead, if decode rate stays priority #1:** the part of the gap that is **not** SNR-shaped. At WSJT-X SNR ≥ +8 dB we still miss ≈ 5–6 %, and GAP-LOCATE says those signals can't be decoded at the right position because another transmission dominates the cell. **Subtraction is the only lever that has moved that.** Its open items (Stage B speed, §8.2 extras, a second residual pass) are where the next pp most plausibly lives. That is a separate proposal. I am not making it here.

---

## 7. Predictions on record (blind to any (i) result; scored if (i) runs)

| # | prediction | P | class |
|---|---|---:|:---:|
| AP1 | (i) replicates: the 3 dB shift bound is < 7 pp on both nights, with `CI_hi` < 10 pp | 0.80 | H |
| AP2 | (i): the frequency-shift null attributes ≥ ⅓ of the ≥ +8 dB misses to text mismatch rather than a missed decode | 0.50 | H |

My ledger leans toward *"a findable defect is there"*. Recommending **no build** runs against that lean. That is not evidence it's right, but it is not the usual bias at work.
