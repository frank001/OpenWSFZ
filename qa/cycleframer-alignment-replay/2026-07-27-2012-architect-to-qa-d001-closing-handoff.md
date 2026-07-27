# D-001: Architect → QA — the closing handoff. The diagnostic programme winds down.
# One measurement remains; the rest of QA's work moves to what ships.

**Author:** Architect, 2026-07-27 (20:12 UTC, `date -u`, per HK-017). **For:** QA (to act on),
and the Captain (§0, §3, §8).
**Supersedes as the single point of reference:** `2026-07-27-1752-architect-to-qa-consolidated-handoff.md`
and every Architect note after it. Those remain the detailed record; **this is the document to work
from.**
**Written to stand alone** — a QA session that has read none of the D-001 thread should be able to
act from this document alone.

---

## 0. The Captain's steer, and my position on it

> *"The research for cheap explanations has already exceeded the costs of the actual solution."*
> — the Captain, 2026-07-27

**I agree, and I want to be direct rather than neutral about it.** §3 puts numbers behind it. The
short form: we have spent three days and six-plus arms buying **exclusions**, and exclusions do not
ship. Meanwhile the solution path — row 4 of the B.3 menu — is already scoped, already priced, and
already replicated on a second corpus. Continuing to hunt the mechanism is now the expensive option.

**This document therefore reverses the standing priority.** Until today, diagnosis led and the menu
decision waited on it. From here, **the menu decision leads**, and diagnosis is reduced to a single
already-built measurement with a hard stop attached (§4).

What we give up by stopping is knowing *why*. That is a real loss and I am not dressing it up. What
we gain is that the 437 messages — which have not moved through any arm — stop being a research
subject and start being an engineering target.

## 1. How to read this

- **§2** where the study stands — the one thing to read if you read nothing else.
- **§3** the cost accounting behind §0.
- **§4** the single remaining measurement, with its design, its pre-registered reading rule, and its
  stop rule.
- **§5** QA's task list, in priority order. **The first item is not the measurement.**
- **§6** numbers and readings that must not be cited. **Two of today's entries are mine.**
- **§7** what is explicitly not QA's.
- **§8** what I owe, and what I am cancelling.

Per HK-015 the `dev-tasks/*.md` files and task specs are QA's to author; where a task needs design
content it is given inline so QA does not have to reconstruct it.

## 2. Where the study stands

### 2.1 The prize, unchanged through everything

**437 messages.** It has not moved through any arm, on either corpus. That stability is the most
reliable thing in the study.

Anchors for every row of the menu: live WSJT-X GUI = **2028**; our decoder offline = **1300**
(64.1% parity; NFR-018 target ≥ 80%, i.e. ≥ 1622 on this corpus); miss population = **789**.

### 2.2 Mechanisms excluded — each a measurement, not an inference

| mechanism | verdict | evidence |
|---|---|---|
| **Pure sensitivity** | Minority contributor | ΔSNR = **2.62 dB** (R.4, corrected); real-corpus marginal shift **7.4% / 6.8%** (R.4b, with a zero-shift control) |
| **Demodulation on clean signals** | Excluded | **147/147** — we match jt9 exactly on isolated synthetic signals across the whole high-SNR plateau |
| **Candidate capacity / cap truncation** | Excluded | C.1: 300 and 600 give **byte-identical** decode sets; population plateaus at ~220–295/cycle; worth **+12 decodes**, 1.6% of the gap |
| **Band limits** | ~1–2%, closed | Below `f_min`: **0.76% / 1.96%**. Above `f_max`: 0.00% / 0.21% |
| **Harmonics / audio-chain distortion** | Excluded | Averaged FFT over 6 cycles: 3000–4000 Hz at **−65 dB**, bounding post-filter nonlinearity at **≤ −49 dBc**. Also a harmonic of 8-FSK has doubled tone spacing (6.25 → 12.5 Hz) and cannot decode as FT8 |
| **Co-channel (cycle-density proxy)** | Not supported; bet withdrawn | +5.8 pts corpus 1, **+1.6 corpus 2** — no replication; the rescue failed (corpus 2 has *more* density spread, p90/p10 **1.84** vs 1.57) |
| **R.6 harness / control arm** | **Excluded today** | Control is healthy: AWGN **0% at −6, 100% at 0/+6/+10**, jt9 offset constant at −18.00 dB. Convention confirmed: measured −17.50 dB vs −17.57 predicted |

### 2.3 The one live statement

> **Whatever costs us the 437 is a property of real received audio that isolated synthetic buffers
> do not have.**

Sharpest form: at −14 dB on isolated synthetic signals we decode **100%**; at ≥ +5 dB on real
corpus audio — far stronger — we decode **89.8% / 89.0%**. That persistent ~10% strong-signal
deficit is the structural core of row 4. Band limits account for 1–2 points of it.

Three named candidates, **none measured directly**: co-channel collision at close frequency
*proximity* (the density proxy failed; proximity itself was never tested); channel effects absent
from the synthetic generator (fading, drift, multipath); something in our own capture/processing
chain ahead of the decoder.

### 2.4 The selection effect worth naming

Every one of the six excluded mechanisms was one we could **construct cheaply in a synthetic
harness**. All six came back negative. The three that remain are precisely the three that are
**hard to construct** — each needs either a realistic channel simulator or instrumentation of the
live capture chain.

That is not a coincidence, it is a selection effect. We have been searching under the streetlight,
and the exclusions are partly telling us where the light was. It is also the strongest technical
argument for the Captain's steer: the remaining candidates cost about what row 4 costs, and unlike
row 4 they deliver no decodes even when they succeed.

### 2.5 Merge-relevant state

- The `libft8` size blocker is **cleared** — the `tls_diag_llr174` compile-time gate took the
  Windows DLL 158,208 → **60,416 bytes**, `.tbss` 100,208 → 2,768. Verified independently.
- The branch is **+4,608 bytes over `main`**, expected (two new exports, small `tls_diag_*`
  scalars). Do not let "back to baseline" harden into "no delta."
- **One pre-merge requirement remains and is NOT done** — see §5 item 1.

## 3. The cost accounting behind §0

Measured from the working tree and git, not estimated:

| | |
|---|---:|
| Analysis/findings/ruling documents in `qa/cycleframer-alignment-replay/` | **81** |
| Diagnostic scripts | **34** |
| Lines of diagnostic Python | **8,228** |
| D-001 commits since 2026-07-25 | **57** |
| Distinct arms/sub-arms run (B.1, B.1b, B.2, B.3, C.1–C.4, R.1, R.1b, R.4, R.4b, R.5, R.6 + phase 0/0b/1a/1b) | **~16** |
| **Decodes recovered by all of it** | **0** |
| Mechanisms excluded | 6 |

Against that, **row 4** is already scoped (`2026-07-27-1730-architect-row4-scoping-design.md`),
already priced (**437 messages measured floor → 83.5% parity ceiling**), and **already replicated
on a second corpus** — B.1b fired all three pre-registered rules and row 4's measured floor clears
NFR-018 on both corpora. It is the only engineering row on the menu whose *measured floor* clears
NFR-018 by itself.

The diagnostic programme's marginal yield has also been falling and its error rate rising. Today
alone: one QA escalation cycle consumed by a self-check misfiring on a truncated grid, and **two
Architect rulings withdrawn — both mine** (§6). That is the signature of a programme past its
useful point, not of one closing in.

## 4. The one measurement that survives — R.6's cliff grid

**Why this one and nothing else:** it is already built, it costs one run, and it is the only
remaining measurement that could *change the scope of row 4* rather than merely satisfy curiosity.

### 4.1 What R.6 now stands at

R.6 is **unblocked**. The control arm is confirmed healthy at ceiling and the SNR convention is
confirmed sound (§2.2 last row). The FT8 decoding threshold, expressed in R.6's own 43.75 Hz
in-band units, is **≈ −3.4 dB** (`−21 dB + 10·log10(2500/43.75)`).

The finding that justifies one more run, from `calibration.json`:

```
   -6 | real | 100.0% (16/16)   jt9 reports -23.5 dB
   -6 | awgn |   0.0% ( 0/16)
```

At a level difference the same run measures as **~0.5–1.0 dB**, the real arm decodes 16/16 and the
control 0/16. Either the FT8 cliff is that steep and we are sitting exactly on it, or real audio is
genuinely *easier* than flat AWGN at threshold — which would be a finding, and pointedly opposite
to D-001's founding worry.

### 4.2 Design

- **Grid:** `R6_SNRS=-8,-7,-6,-5,-4,-3,-2,+10`.
  The **`+10` point is not part of the cliff** — it is there so **SC3 has a ceiling anchor to gate
  on**. The fine grid tops at −2, only ~1.4 dB above threshold, and may not reach 90% on its own.
  Omitting the anchor is how this arm burned a cycle last time.
- **Both arms** (real, AWGN), **both decoders** (ours, jt9), on byte-identical audio.
- **Retain jt9's reported SNR** for every graft — see §5 item 3; it is the only absolute instrument
  in R.6 and the main harness currently discards it.
- Cycles: enough for ≥ 100 grafts per cell. Report Wilson intervals, as the harness already does.

### 4.3 Reading rule — **fixed in advance, before the run**

Locate each arm's 50% point, both decoders. Let **Δ** = (AWGN 50% point) − (real 50% point), in dB.
The measured level offset between arms is **+1.00 dB**.

| outcome | reading | consequence |
|---|---|---|
| **\|Δ − 1.0\| < 1 dB** | The arms are the same curve, displaced by the known level offset. | **Environment is NOT the problem.** R.6's fork resolves to **(B) real signal properties** — GFSK-vs-CPFSK, fading, drift, timing jitter. Row 4's scope should weight signal-realism, not noise handling. |
| **Δ ≫ 1 dB** (AWGN needs materially more SNR) | Real audio is genuinely easier than flat AWGN at threshold. | A finding, opposite to the founding worry. Record it; it does **not** re-open the programme. |
| **Δ < 0 materially** (real needs more SNR) | Environment **is** costing us. | The only outcome that would justify going back to the Captain to re-open. Do not act on it unilaterally. |

No other reading is authorised. If the result does not fit one of these three rows, that is an
escalation, not an interpretation.

### 4.4 Stop rule

**Whatever this grid returns, R.6 ends there.** No follow-on arm, no "one more rung," no new
hypothesis pursued — including from me. Re-opening the diagnostic programme requires the Captain,
explicitly, per §0.

### 4.5 A trap to avoid — do not escalate on this one

The 17:52 handoff §7 records a standing rule: *"flat SNR-independent offsets between two decode
curves are to be treated as suspected harness defects until excluded."* **That rule does not apply
to the AWGN arm's constant −18.00 dB jt9 offset.** That offset is the fixed
43.75 Hz → 2500 Hz bandwidth conversion, and its constancy is *evidence the arm is correct*, not a
defect. Applying the rule here would produce exactly the kind of escalation that cost today's cycle.

## 5. QA's tasks, in priority order

**Item 1 outranks the measurement.** It is a merge blocker; §4 is a curiosity with a scope payoff.

### Q-A — Get the shim version correction applied ⟨pre-merge blocker, NOT done⟩

I checked `src/` directly: **`FT8_SHIM_VERSION` is still `20260035`, `ExpectedShimVersion` is still
`20260035`, and `ft8_get_shim_capabilities` does not exist.** The dev-task
`dev-tasks/2026-07-27-d001-shim-version-correction-and-capabilities.md` is **authored but unapplied.**

This matters because the TLS gate changed the shipped binary's observable behaviour under an
unchanged version: 20260035 before the gate returns real LLR data by default; 20260035 after it
returns zeros. And CI auto-rebuilds the Linux `.so` and macOS `.dylib` from current `ft8_shim.c`
while the Windows DLL is hand-built — so **three platform binaries can differ in capability while
all reporting the same version.**

**QA action:** this needs a **separate Developer session** to apply (HK-011); QA proposes and stops,
then reviews the diff before the Captain sees it. The dev-task content is already written — do not
re-author it.

### Q-B — The `MaxPass0Candidates` truncation guard ⟨long owed⟩

`dev-tasks/2026-07-27-d001-max-pass0-candidates-truncation-guard.md` is likewise **authored but
unapplied**. The underlying pattern — a diagnostic export that fills its capacity taking a silent
head-take — has now bitten **five times** (C.4's 140 truncation, THE 567's 279/567 subsample, C.1's
stale-DLL run, R.4's out-of-band slot 7, the gated-off silent zero). Same routing as Q-A.

### Q-C — Fold R.6's absolute instrument into the main harness

`r5.run_jt9_single` parses jt9's `snr` field and discards it. `r6_jt9_snr_calibration.py` (written
today, `qa/` only) keeps it. **Move that retention into `r6_clean_graft.py` itself** so jt9's
reported SNR is a standing output of the arm, not a side script. This is `qa/` tooling — no
Developer session, no HK-011.

### Q-D — Fix R.6's two self-check defects

Both are `qa/` tooling:

1. **SC3 must gate on an absolute SNR**, not "the top of whatever grid was passed", and must report
   **`SKIPPED — grid does not reach the ceiling point`** rather than `FAIL` when the grid never gets
   there. A gate that says FAIL when it means "you did not give me the data to judge" cost a full
   escalation cycle. **This is the single most valuable fix in the whole R.6 arc.**
2. **`SIG_OCCUPIED_HZ` = 43.75 → 50.0** (8 tones × 6.25 Hz; 43.75 is the *centre-to-centre* span,
   7 intervals, so the band currently misses a tone slot), and **window the signal-RMS measurement
   to the graft's 12.64 s extent** rather than `np.std` over all 15 s. Predicted correction −0.58
   and −0.74 dB, total −1.32 dB, against SC1's unexplained −1.45 dB residual. Re-read SC1's
   **absolute** afterwards, not just the arm-to-arm difference.

### Q-E — Run the cliff grid (§4), then stop

After Q-C and Q-D, not before. Author the task spec (QA's, per HK-015) carrying §4.2's design and
§4.3's reading rule **verbatim and in advance of the run**.

### Q-F — Do NOT build SC5

Ruling `2026-07-27-1946` §7 item 4 asked for an SC5 p10 noise-floor check. **It was designed
against a defect that does not exist** (§6). Do not build it. If it appears in a task spec, that is
a defect in the spec.

## 6. Numbers and readings that must NOT be cited

If any of these appears in a future findings doc, task spec or Captain-facing summary, that is a
defect.

| withdrawn | replacement |
|---|---|
| ΔSNR = **2.86 dB** | **2.62 dB** (verified two ways, agreeing to three decimals) |
| "6.3% / 6.2%" step-model recovery | **7.4% / 6.8%** marginal, from R.4b's shift model *with* its zero-shift control |
| "**Anti-correlation**" (R.1b row 2) | Rows 1 and 2 collapse: *no demonstrable location information at lattice resolution* |
| "Row 4 is an indivisible commitment" | **Not applied.** The curve is small because sensitivity is the *wrong axis* — not evidence for row 5 over row 4 |
| "Symbol demodulation → LLR sign correctness is where the residue lives" | Withdrawn; **147/147** positively contradicts it |
| THE 135 / THE 567's BER **interpretation** | The measurements stand; "our demodulator produces wrong bits on located signals" does not |
| **"R.6's AWGN control arm is broken"** ⟨today⟩ | **False.** The control is healthy; the smoke grid was entirely below the decoding threshold. Measured, §2.2 |
| **"The real arm is planting grafts 6–10 dB hot / gaps are pervasively contaminated"** ⟨today, mine⟩ | **Refuted.** Measured real-minus-AWGN excess = **+1.00 dB**. The mechanism does not exist |
| **"1288 / 793 / 1235"** | **1300 / 789 / 1239** (our offline decodes / miss population / matched) |

Note on the second-to-last row: SC4's structural blindness to *uniform* contamination remains a true
statement about SC4 and should be documented as a known limitation — but it is latent, not an active
defect, and **must not be chased**.

## 7. What is explicitly NOT QA's

- **No `src/` or native edits** (HK-011). Q-A and Q-B are *routing already-authored dev-tasks to a
  Developer session*, not applying them.
- **No push, no merge** (HK-010 / HK-014). **No `pre_merge_check.py`** — Captain's trigger only
  (HK-006), and QA does not declare "ready for merge" unprompted.
- **No new arm.** §2.3 names three candidate mechanisms; **none is authorised as work**, and under
  §0 none will be without the Captain re-opening the programme.
- **The sub-200 Hz band floor** remains a logged non-priority. 0.76% / 1.96% does not buy an
  NFR-018 false-positive exposure plus a Developer session.
- **Branch disposition and the `main` merge remain the Captain's.** 59 commits sit local on
  `d001-c4-min-score-sweep`; that is the agreed posture, not an oversight.
- **The row 4 vs row 5 decision is the Captain's alone** — row 5's GPLv3 consequence for the
  product is a licensing decision, not an engineering one.

## 8. What I owe, and what I am cancelling

- **CANCELLED — the R.3 replacement design.** The 17:52 handoff §6 recorded it as outstanding. Under
  §0 it is a design for an arm we are no longer going to run, and delivering it would be the exact
  cost the Captain is calling out. **I am not writing it.** If the programme re-opens, it comes back.
- **OWED — the row 4 decomposition**, if and when the Captain takes row 4. The menu's own honest
  caveat is that row 4's *"scope is unbounded until the decomposition exists; this is the row where a
  wrong-sized commitment gets made."* Sync detection, candidate scoring and symbol demod are still
  folded together inside "depth-1 jt9". That decomposition is now the highest-value thing I can
  produce, and §4's cliff grid feeds it directly — which is precisely why that one measurement
  survived the cut.
- **The menu decision itself** is unchanged and remains with the Captain: row 1 (accept, re-baseline
  NFR-018) versus row 4 (front-end work, 437 floor, 83.5% ceiling) versus row 5 (adopt WSJT-X's
  core, ~the whole 789, GPLv3).

## 9. Cross-references

**Read these two first if you read anything beyond this document:**

- `2026-07-26-2359-architect-b3-costed-menu.md` — the five-row menu and its measured prizes. The
  decision frame for everything above.
- `2026-07-27-1730-architect-row4-scoping-design.md` — row 4's scoping work as it stands.

Today's R.6 arc, in order:

- `2026-07-27-1921-architect-to-qa-r6-handoff.md` — the handoff whose §5 fallback list was incomplete.
- `2026-07-27-qa-to-architect-r6-control-escalation.md` — QA's escalation. **Correct procedure
  throughout**; its premise was inherited from my handoff, not invented by QA.
- `2026-07-27-1946-architect-r6-control-audit-ruling.md` — §0/§1/§2 stand; **§3/§4 withdrawn.**
- `2026-07-27-1957-architect-r6-calibration-addendum.md` — the measurement that withdrew them.

Prior evidence this handoff rests on:

- `2026-07-26-c1-candidate-cap-sweep-findings.md` §3–§5; `2026-07-27-r4-sensitivity-gap-findings.md`;
  `2026-07-27-r4b-realworld-sensitivity-findings.md`; `2026-07-26-c3-candidate-generation-gap-findings.md`;
  `2026-07-27-0015-architect-b3-addendum-second-corpus.md` (B.1b replication).
- `artefacts/d001_r6_jt9_snr_calibration/calibration.json` — every §4.1 number.

## 10. Process rules carried forward

- **HK-017** — dated filenames and bylines carry real `date -u` / `git log` UTC; the two must agree.
- **HK-018** — open the data already gathered *before* concluding. Two rulings withdrawn today were
  both mine, and both would have been caught by a five-minute measurement run first. This rule is
  not aimed at QA.
- **Band-intersection check** — before any decoder-vs-decoder gap is attributed to algorithm quality,
  state and verify the search band each used. Every arm's output header should carry it.
- **Frequency estimates are clamped at `f_min`/`f_max`** — a decode reported at exactly 200.0 or
  3000.0 Hz is a censored value, not a measurement.
- **Flat SNR-independent offsets** are suspected harness defects until excluded — **with the §4.5
  exception**, which is a known-good constant.
- **Pre-register the reading rule before the run**, not after. §4.3 is the template.

---

*Per HK-015 this is Architect → QA material; the task specs and dev-task routing in §5 are QA's to
author and own. Per HK-014 this note is committed locally and goes no further. Per HK-011 nothing
here touches `src/` or native code — Q-A and Q-B are routed to a Developer session, not applied.
Per HK-006 no `pre_merge_check.py` run is implied or requested; that remains the Captain's trigger.
The decision the study feeds — row 1 vs row 4 vs row 5 — remains the Captain's, on the Captain's
clock.*
