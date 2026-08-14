# Architect → QA: handoff — document index and work queue

**Author:** Architect, 2026-08-06 (23:46 UTC, `date -u`, per HK-017). Repo `main` at `9c4a4a0`.
**For:** QA. §7 is for the Captain.
**Purpose:** single entry point for everything produced 2026-08-06 evening. Read this first, then
open only what your next task needs.

**Per HK-015 this is not a task breakdown.** `tasks.md` and `dev-tasks/*.md` remain yours to
author. §4–§6 are the work I believe exists and its ordering; converting them into tasks is your
call, and you should push back where you disagree.

---

## 1. Where things stand, in one paragraph

The decoder deficit is real, measured, and now localised. On identical replayed audio with no
contention, WSJT-X decodes 752/cycle-window to our 461 — we miss **40.4%**, reproducibly across
five runs. The miss is concentrated at **low SNR** (miss rate 0.166 at ≥0 dB rising monotonically
to 0.792 below −20 dB) and worsens with **density at fixed SNR**. D-009's 45-point parameter sweep
returned **+0.109 pp**, so the deficit is not parametric. The leading mechanism, found late and
from data already on disk, is that **both candidate caps are saturated on ~95% of cycles** and the
budget is allocated backwards — pass 1 converts at 16.4% and is capped at 140, pass 2 converts at
0.80% and is given 200. That family was excluded from D-009's grid by construction.

---

## 2. Document map

Read in this order if you are picking this up cold. Tonight's Architect notes are `arch:` commits
`1135406`, `f7717e3`, `420bebf`, `9c4a4a0` — all local, none pushed.

| # | document | what it is | still current? |
|---|---|---|---|
| 1 | `2026-08-06-2323-architect-where-the-decode-gap-actually-lives.md` | The stratification — SNR, density, passband, size of the prize | **Yes**, except §4 and §7.2 — see the corrections in `9c4a4a0`'s §0.4 |
| 2 | `2026-08-06-2336-architect-to-qa-spec-d001-root-cause-rc1-rc4.md` | **The active spec.** RC1–RC4, gates, sequencing, cost | **Yes** — this is the live one |
| 3 | `2026-08-06-2249-architect-to-qa-m3-void-preflight-desync.md` | Why M3 is void; the fix; M1/M2 dispositions | **Yes** |
| 4 | `2026-08-06-2144-architect-to-qa-spec-reference-suppression-m0-m4.md` | M0–M4 spec | Partly — see §5 below for what survives |
| 5 | `2026-08-06-2115-…-full-anova-results.md`, `…-2022-…-replay-results.md` | QA's five-run replay + ANOVA. The instrument's validation | **Yes** |
| 6 | `2026-08-06-2123-…-overlap-flip.md` | QA's overlap analysis | Yes, with the §3 prose correction applied |
| 7 | `qa/rr-study/2026-08-06-0024-qa-to-architect-d009-recalibration-results.md` | D-009 outcome (+0.109 pp) | **Yes** |
| 8 | `2026-08-07-reference-suppression-m0-m4/ORCHESTRATION_REPORT.md` | M0–M4 execution record | Yes, with M3 marked void |

**Supporting data, all on disk:** `artefacts/20260806_cross_decode_replay_2009/` (M0 preservation),
`qa/cycleframer-alignment-replay/2026-08-06-live-cross-decode-replay/_work/run{1..5}/`
(our `ALL.TXT` and — the part nobody had used — the **daemon debug logs carrying per-cycle
candidate/decode/LLR diagnostics**).

---

## 3. The numbers worth having in one place

| quantity | value | source |
|---|---|---|
| our decodes / WSJT-X, identical audio | 461 / 752 = **61%** | 5 runs |
| miss rate | **0.399 – 0.406** across 5 runs; pooled 1,526/3,779 = 40.4% | 2323 §1 |
| miss rate at ≥ 0 dB → below −20 dB | **0.166 → 0.792**, monotone across 8 buckets | 2323 §2 |
| below −12 dB | 29.9% of traffic, **47.9% of all misses** | 2323 §2 |
| density effect at fixed SNR | monotone in **all four** SNR bands; +64% relative at mid SNR | 2323 §3 |
| pass-1 candidate saturation | **95/100** cycle-observations at `K_MAX_CANDIDATES = 140` | RC spec §0.2 |
| pass-2 candidate saturation | **90/100** at `K_MAX_CANDIDATES_PASS2 = 200` | RC spec §0.2 |
| pass-1 yield | 2,184 / 13,300 = **16.42%**, 93.5% of our output | RC spec §0.3 |
| pass-2 yield | 151 / 18,972 = **0.80%**, 6.5% of our output | RC spec §0.3 |
| D-009 best grid point | **+0.109 pp** on a 41.508% baseline | D-009 results §1 |
| the prize | our own strong-signal miss rate at all SNRs ⇒ **83% of WSJT-X**, from 61% | 2323 §5 |

### 3.1 Citation limits — enforce these

- **`s_low = 0.217` — never cite.** Void, harness defect.
- **`41.508%` — do not cite as "our recall."** Its reference is the corpus `wsjt-x/ALL.TXT`,
  restricted to low-SNR decodes, and that log is the one found suppressed ~2.3× on the busy
  window — i.e. biased in exactly the population it measures.
- **Everything in §3 is one window**, the busiest in the corpus. Density results hold over
  30–49 decodes/cycle and are silent outside that range.
- The pre-existing limits still stand: `F_dec = 1.2455` never citable; "drift explains *most*",
  never "~83%"; no D-number quoted without opening
  `project-state-2026-07-31-d001-competition-confirmed.md` first — **which I have still not done.**

---

## 4. Work queue — free, no authorisation needed

Nothing here touches `src/`.

| # | task | notes |
|---|---|---|
| **W1** | **Resolve the `_work_recal/` commit question before committing anything.** | `qa/rr-study/d001-param-sweep-2026-07-22/_work_recal/` is **not gitignored** and would stage decode output including `fp.csv`, per-arm decode logs and manifests. I began an NFR-021 callsign scan and **did not finish it** — treat this as unresolved, not clear. If any of it derives from the recall arm (real off-air audio from `20260803_live_run_1713`) it carries real callsigns and must be ignored, not committed. Sibling `_work/` dirs in `cycleframer-alignment-replay/` are already ignored; this one looks like the gap. |
| **W2** | Verify the two corrections landed. | (a) `2026-08-06-2123` §3 prose — the label swap, corrected text in `f7717e3` §0.1. (b) `ORCHESTRATION_REPORT.md` M3 — provenance note present, "instrument suspect" struck, addendum hypothesis withdrawn. Both appear done in the working tree; confirm. |
| **W3** | Fix `play_pass_guarded()`. | `2249` note §5: move the liveness check one cycle later, delete `PREFLIGHT_EXTRA_WAIT_S` rather than zeroing it, and add the §5.1 phase-lock assertion (`excess < 3.0 s`). Verified against known-good (1.63/1.62 s) and known-bad (11.49–11.50 s). |
| **W4** | Record the corrected M3 window-selection rule. | **This exists only in conversation and is not yet in any document** — capture it wherever you keep the M3 spec state. See §5.1 below for the rule and the evidence. |

---

## 5. Work queue — M0–M4, what survives

| step | disposition |
|---|---|
| **M0** | **Complete.** Preserved, inventory regenerated. |
| **M1** | **ROW 4, stands.** `delta = −2.000` dB, `p = 0.00425`. Gate correctly evaluated; my threshold design was at fault (`2249` §7). **No re-scoring.** If the truncation-vs-log question is still wanted it needs a fresh, better-powered M1b — not proposed. |
| **M2** | **ROW 1, stands, citable.** `R_owsfz = 0.9534`, `R_wsjtx_self = 0.9645`, any-of-5 vs all-of-5 gap 0.0036. On the busy window, "OpenWSFZ finds decodes WSJT-X cannot" is false. |
| **M3** | **Void, fixed, re-runnable — but see §7.** After W3 and §5.1, it is 15 min of playback. My recommendation is that it is now archaeology; the Captain's call. |
| **M4** | **Blocked** on the M1 gate, and I recommend against it regardless (RC spec §0.4a). |

### 5.1 Corrected M3 window-selection rule (replaces spec §5.2 and the `2249` §6.1 revision)

Both prior versions failed. The original minimised density *subject to* a density floor, which
always returns the floor. My replacement — 10th percentile above a raised floor — ignored the
contrast constraint entirely and produced `contrast = 1.937` against a required `3.0`.

> Among windows satisfying **both** `contrast >= 3.0` **and** `wsjtx_total >= 60`, select the one
> with the **maximum `wsjtx_total`**. Tie-break: earliest UTC.

A constrained optimisation with the objective on denominator stability rather than fighting the
constraint. Measured over all 4,716 candidate windows, it selects
`260803_234000 .. 260803_234445` — `wsjtx_total = 105`, `owsfz_total = 157`,
`mean_combined = 13.10`, `contrast = 3.03` — and **returns the same window at every floor from 40
to 100**, so it is invariant to the parameter that broke both earlier attempts.

Two honest notes: `contrast = 3.03` is thin, but that is the corpus's real Pareto frontier, not a
rule artifact — the feasible set tops out at `wsjtx_total = 105`. And `owsfz/wsjtx = 157/105 =
1.50` matches the 1.51× corpus-wide ratio, so the window behaves like the corpus rather than an
outlier.

**§5.4's verdict gate is unchanged** (`1.00 / 1.25 / 2.00` on `S_low`). Repairing an instrument
and re-running a pre-registered gate is not moving a threshold.

---

## 6. Work queue — RC1–RC4, all blocked on the Captain

**Every item requires a `src/` change ⇒ a separate Developer session ⇒ the Captain's sign-off
(HK-011). QA proposes and stops.** Full gates in
`2026-08-06-2336-architect-to-qa-spec-d001-root-cause-rc1-rc4.md`.

| # | what | `src/` change | playback | order |
|---|---|---|---:|---|
| **RC1** | Per-decode attribution — split the 1,526 misses into *never offered to the decoder* vs *offered and failed* | diagnostic getter for candidate `(time_offset, freq, score)`; no logic change | 15 min | **first — this is the diagnosis** |
| **RC2** | Candidate budget — is the cap the constraint? | caps → runtime-settable ⚠️ plus array sizing, see below | 30–45 min | after RC1 |
| **RC3** | Widen search band 200→150, 3000→3100 Hz | two constants | 15 min | **after RC2 only** |
| **RC4** | Depth, `K_MAX_PASSES` 2→3 | one constant | 15 min | recommended: don't |

**Three things to carry into the Developer session:**

- **RC1's getter and RC2's runtime-settable caps are independent edits in the same file.** One
  session, one build, one review covers both.
- ⚠️ **`ft8_shim.c:514-525` documents a latent array-overflow in exactly the area RC2 touches** —
  `candidates[]` is sized `K_MAX_CANDIDATES_ANY_PASS` and `K_MAX_DECODED` is the sum of both caps.
  Raising either past 200 requires sizing to be driven from the runtime maxima. It was found once
  already; it must be handled deliberately, not rediscovered.
- **RC3 must not precede RC2.** Widening the band adds candidates to a list saturated 95% of the
  time; under a binding cap it can displace stronger candidates and *reduce* decodes.

---

## 7. Open decisions — the Captain's, not QA's or mine

1. **Authorise the RC1 (+RC2) Developer session?** RC1's 15 minutes decides whether RC2/RC3's
   45 are worth spending.
2. **D-009 parameter decision** (Option A/B/C, `report.md` §5) — plus QA's §2.1 finding that
   `k10_*_n40` ties baseline recall with **zero FP on both synthetic arms**, strictly dominating
   the shipped baseline for one changed parameter. It is not the nominee only because I wrote the
   rule with a strict `>`. That is a different proposition from +0.109 pp and my rule structure is
   what obscured it.
3. **Is M3 still worth running?** We now have a working reference instrument, so whether the
   *archived* log was suppressed is largely archaeology. My recommendation: park it.
4. **Is Arm R.D still worth running?** M2 undermines its reciprocity premise on this window, and
   the 2323 note §3 already delivers a density asymmetry result reference-free. Still unauthorised.
5. **Should HK-016 widen to cover WSJT-X's AppData `ALL.TXT`?** It does not today, which is why a
   five-run experiment ended with its reference leg living outside the repo until M0.

---

## 8. Closed — do not reopen

- **M3's `s_low = 0.217`**, the "instrument suspect" reading, and the marginal-signal hypothesis in
  its addendum. All withdrawn (`f7717e3`).
- **The D-009 grid as scoped.** 45 points, +0.109 pp. Any future sweep must include the candidate
  caps and be scored against the replay instrument, not the archived `ALL.TXT`.
- **S.1 / S.1b** remain parked — ask the Captain, do not re-derive.
- **`jt9 -d 3`** remains barred as a reference decoder.
- **The 2026-07-31 three-decoder run** remains closed.
- **S.2a's "blocked on instrumentation" status should be revisited** — candidate counts, pass
  counts and LLR stats are exported, P/Invoked, called per decode and logged per cycle. Whatever
  S.2a still lacks, it is not those.

---

*Per HK-015 this is Architect → QA and is an index, not a task breakdown — `tasks.md` and
`dev-tasks/*.md` remain yours. Per HK-014 committed locally, not pushed, no merge implied or
requested. Per HK-011 every RC item requires a Developer session and the Captain's authorisation
before any `src/` edit. Per NFR-021 no message text or callsign appears here — and W1 flags an
unresolved exposure question I did not finish checking. Per HK-021 every gate referenced here
lives in its own spec with hard thresholds, assertions, and boundary values falling to the
inconclusive row.*
