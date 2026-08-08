# Architect → QA: consolidated work queue — everything from the 2026-08-07 evening session, in one place

**Author:** Architect, 2026-08-07 (22:41 UTC, `date -u`, per HK-017). Repo `main` at `856352d`,
20 commits ahead of `origin/main`, all local (HK-014).
**For:** QA. §0 and §6 are for the Captain.
**Replaces as the entry point:** the four documents this session produced (2117, 2140, 2206, 2220).
They remain the evidence; **this is the index and the queue.** Where they disagree with this, this
wins — 2206 in particular is **retracted**.
**Authorisation:** **NOTHING BELOW IS AUTHORISED TO RUN.** Per HK-015 the `dev-tasks/*.md` are
QA's to author; this is the Architect's handoff, not a task file. W1's blocker is an **escalation**,
not a decision for a session to make.

🔴 **AMENDED 2026-08-08 21:15 UTC (`date -u`, HK-017). Repo `main` at `f4045bb`, 26 commits ahead of
`origin/main`, all local (HK-014). READ §0.5 BEFORE §1–§5 — most of the queue below is CLOSED and
several of its statements are now known-wrong. §0.5 names them.**

---

## 0. Read this before anything else — two withdrawn claims

| claim | status |
|---|---|
| **`k_50 = 13/174 = 7.47%`** — "our BP/OSD correction threshold" | 🛑 **RETRACTED.** Not a decoder property. **Do not cite, do not build on.** §1.1 |
| **`c_bottom = 0.476%`** — "bottom-decile candidates barely convert, so RC3 displaces nothing" | 🛑 **ROW 0, no verdict.** The data cannot identify which candidate decoded. **Not evidence for or against RC3.** §5 |

Both were Architect errors, published and then withdrawn within the same session. Neither reflects
anything QA or the Developer did.

---

## 0.5 STATUS 2026-08-08 — what is closed, what this document now gets WRONG, and the one live item

**This queue was written 2026-08-07 evening. Everything it queued has since been run.** It is kept as
the evidence trail; **§0.5 is the current state and wins wherever it disagrees with anything below.**

### Queue status

| item | status | where |
|---|---|---|
| **W1** — the §5 calibration | ✅ **DONE.** `E = 4.28` of 135 (Arm B) ⇒ the "1–15" row. Self-check passed, control median BER 2.9%. | `2026-08-07-2319-qa-w1-sec5-calibration-results.md` |
| **W2** — `FT8_SHIM_VERSION` collisions | ✅ **DONE.** Audit + renumbering proposal, **not applied** — awaits sign-off (HK-011). | `2026-08-07-2249-qa-to-architect-w2-shim-version-audit-and-renumbering-proposal.md` |
| **W3** — HK-016 widening | ✅ **CLOSED — it was already implemented** since `a60b015` (2026-07-30), five days before it was asked for. No change was needed. | addendum in `hk016-…standard.md` |
| **W4** — RC3 / `c_bottom` | unchanged: **ROW 0**, needs a `src/` change, still behind D-001. | §5 below |
| **T1** — frequency quantisation | ✅ **CLOSED 2026-08-08.** `G = 3.16 pp` → **ROW 3**, real but small. | `2026-08-08-2046-qa-to-architect-t1-frequency-quantisation-results.md` |
| 🔴 **T2** — offset-curve shape | **SPECCED, NOT RUN. The only live QA item.** | §2.5, spec `2026-08-08-2102-architect-to-qa-spec-t2-offset-curve-shape.md` |

### 🛑 Four statements below that are now known-wrong — do not act on them

| where | says | correction |
|---|---|---|
| §1 table | *"the §5 calibration — **NEVER RUN**"* | **Wrong.** It ran on 2026-07-26 as **B.2** (`E = 5.69` Arm B / 4.45 Arm A, same reading row, never retracted), and again as W1 on 08-07 (`E = 4.28`). Two independent runs, different synth and noise model, 12 days apart, same order of magnitude. **Treat `E ≈ 4–6` as reasonably established**, not one fragile number. |
| §2.2 | *"W1 is **BLOCKED**"* | **Unblocked and executed.** The Captain chose option (a): run from `d001-c4-min-score-sweep` in an isolated worktree; **`main` was never touched.** |
| §3 | *"**Six** unmerged `d001-*` branches"* | **Five.** W2's individual audit confirmed it; the collision table itself always had five rows. `d001-c1-candidate-cap-sweep`'s `libft8.dll` is **byte-identical to `main`'s** — a fully-superseded stale branch, recommend deletion, not renumbering. |
| §7 | *"the replay corpus is the busiest by construction"* / no sparse regime | **Stale.** The 2026-08-08 17m leg delivered Q1 density **9.7** and a minimum of **3**, below the 20m corpus floor of 15.3. **A sparse regime is on disk.** Still: 🛑 **do not propose a capture run** — open `qa/ARTEFACT_INVENTORY.md` first. |

### Where D-001 has moved since §1 was written

**The failing sub-stage is DEMODULATION, not error correction.** Three numbers that were each already
on the board and never placed side by side: matched-hit control BER **median 2.9%**; our BP+OSD
corrects to `B50` = **11.3%**; THE 135's own BER **median 44.0%** (p10 17.2%). That is **bimodal, not
a gradient** — the misses sit at ~4× the correction threshold. `E = 4.28` of 135 is the complement:
**~97% of the missed population was never correctable by any error-correction change.** W1 reported
`E` correctly and stopped because its reading rule forbade editorialising; the inference was simply
never drawn.

Code basis, read not inferred: **there is no sync refinement.** `ft8_shim.c:1314-1335` — candidates
go straight into `ftx_decode_candidate()` at their quantised grid position (**25% of a tone, 25% of a
symbol**), and the reported `freq_hz`/`dt` are reconstructed from those same indices. Architectural,
not parametric — which is why D-009 swept 45 points for **+0.109 pp**. See `architecture-ft8-lib.md`.

---

## 2.5 🔴 T2 — the shape of the offset-vs-recovery curve — **the one live QA item**

**Spec:** `qa/cycleframer-alignment-replay/2026-08-08-2102-architect-to-qa-spec-t2-offset-curve-shape.md`
(committed `f4045bb`). **Read the spec — this section is the index entry, not the instructions.**

**Not authorised to run** (this document authorises nothing, §0 header). Pure re-analysis of
`ALL.TXT` already on disk: no capture, no `src/` change, no rebuild, no Developer session. ~1 QA pass.

**The question.** T1 closed at ROW 3 and **T2 does not reopen it.** T1 asked *does* frequency
quantisation cost decodes (yes, small). T2 asks **what shape that cost has and where the worst case
sits** — which T1's own metric could not resolve.

**Why it is worth a pass — a mechanism that predicts a specific, falsifiable shape.** At residual
`r → 1.5625 Hz` a signal is **equidistant between two lattice points**, so `ftx_find_candidates()`
may return both and the decoder gets two attempts at equal (bad) offset; at `r ≈ 1.0` it is firmly in
one bin, badly offset, with a useless neighbour 2.1 Hz away. **The worst case should therefore be
INTERIOR, not at the bin edge** — and T1's curve is indeed non-monotone (Q4 low at 53.5%, Q5
recovering to 55.6%).

**Gated metric:** `U = recovery(MID) − recovery(INT)` on **globally fixed rung groups**, replicated
across a **cycle-parity** split-half. ROW 1 at `U ≥ 1.5 pp` with both halves positive; ROW 2 at
`U ≤ 0.5 pp` closes the two-candidate hypothesis dead; otherwise ROW 3. Full ROW 0 block in spec §4.

**Architect's recorded predictions:** ROW 1; `D_int` 4–6 pp; 13 distinct rungs; `mean_r_ours`
0.24–0.25; kept population 67 243. Four are wired into ROW 0, **so my being wrong voids the run
rather than producing a finding.** On T1 I predicted ROW 1 and it came back ROW 3 — score prediction
7 against the outcome plainly, whichever way it goes.

### 2.5.1 🛑 Prohibitions — binding, and the reason each exists

1. **`D_int` is NOT `G` and may never be substituted into T1's gate.** The sentence *"using the
   interior minimum, T1 would have been ROW 1"* is forbidden. A better metric earns a **new**
   pre-registration, never a re-read of the old gate — that is the exact HK-021 sin.
2. **Never produce a de-attenuated or corrected `G`.** `G = 3.16 pp` is a **floor** (see 2.5.2), but
   correcting for attenuation means inventing an error model, which means measuring that parameter —
   HK-021(d), the failure that produced §1.1.
3. **17m is out of scope.** Void under its own ROW 0b; it contributed only confusion to T1 §5. The
   split-half replicates *inside* the citable leg, which is strictly better than a void one.
4. **Do not extend anything to the time axis.** Reference DT resolution is 0.1 s, **coarser** than our
   own 0.08 s grid step — not identifiable from `ALL.TXT`, an HK-021(c) failure by construction.

### 2.5.2 Two instrument facts QA should have before starting

**The reference reports INTEGER Hz.** Since `3.125 = 25/8`, the residual `r` can take **exactly 13
values** — `{0, 0.125, … 1.5}` — and nothing else. Confirmed independently: that ladder's uniform-null
mean is **exactly 0.780** against T1's measured control of 0.781. Two consequences: `G` is measured
with ~3 resolution elements per lattice cell so it is a **floor**; and 🛑 **`r` must never be
quantile-binned** — that is what produced T1's unequal 2/3/2/2/4-rung "quintiles".

**`mean_r_ours = 0.2404` is exactly right, not approximately right.** An on-lattice quantity rounded
to integer Hz gives **0.250** in closed form. Our decoder is *provably* on-grid; the 0.24 is reporting
rounding, not estimator sloppiness. Spec §4 uses `0.20–0.30` as the ROW 0c instrument check.

### 2.5.3 Two corrections to T1 that T2 carries out

- **T1 §4.1's SNR table is not like-for-like.** `t1_frequency_quantisation.py:214` re-derives the
  r-quintile edges *inside each stratum*, so "Q1"/"Q5" mean different rungs per band. **The tell was
  free arithmetic:** the weighted mean of the five `G_sub` (**3.97 pp**) does not reconcile with the
  pooled `G` (**3.16 pp**). Spec §5.2 restates it on fixed rungs. ⚠️ **No measurement was needed — the
  code answered it.** That is HK-018 extended to harness code.
- **The T1 binning defect is the Architect's, not QA's.** Quintiles over a discrete 13-value ladder;
  the rule that should have fired was **HK-021(d)** *(let the physical system supply the parameter)*,
  not **(b)** *(stratify by quantiles)* — (b) governs continuous variables of unknown scale. QA
  executed the spec verbatim, including the trap it flagged. Recorded as HK-021(f).

---

## 1. Where D-001 actually stands

**RC1 fired ROW 2.** Of 894 pooled misses: **3.1% out-of-band** (known, unrelated defect),
**8.9% no-candidate**, **87.9% candidate-present-and-failed**. In 9 of 10 misses we located the
signal and failed to read it. Cite the decomposition, never "40% unexplained."

| arm | status | why |
|---|---|---|
| RC1 candidate generation | **CLOSED** | ROW 2, `f_nocand = 0.0924`, uniform across every stratum |
| RC2 candidate budget | **CLOSED twice** | excluded by RC1; already bounded at **+0.93%** by C.1 in July |
| RC4 decode depth | **CLOSED** | ROW 2, `d = +0.70` pp |
| C.2 Phase 2 LLR shrinkage | **CLOSED on evidence** | 0/135 recovered at every weight; harm rose 0/0/1/2/5 |
| RC3 search band | **deferred** | worth **3.1%**; its objection is unresolved, see §5 |
| **the §5 calibration** | 🛑 ~~**NEVER RUN**~~ **— WRONG, see §0.5** | It ran twice: **B.2** on 07-26 (`E = 5.69`/4.45) and **W1** on 08-07 (`E = 4.28`). **DONE.** |

### 1.1 Why C.5a is retracted

`2026-07-26-2230-architect-sec6-redesign-ruling.md` §4 declined that exact bench as **ill-posed**
three weeks before I built it. `bp_decode` takes 174 floats, not bits — so "inject k bit errors"
forces a choice of *how wrong* each bit is, and **that choice is the answer**. Transmitting a
corrupted codeword at 20 dB SNR silently pins it at "confidently wrong," the extreme its own table
says makes the threshold read very low.

Three tells: it landed **below** the (174,91) hard-decision capacity limit of **10.2%**, which a soft
decoder cannot really be; its x-axis (injected bit count) is **not** the corpus BER axis (raw LLR
signs vs true codeword); and the caveat was written but priced as mild when it is dominant.

**What survives and is reusable:** `qa/rr-study/synth`'s `assemble_symbols()` takes a **174-bit
codeword**, so `codeword → tones → GFSK → ft8_decode_all` drives the real decoder with no native
change. ⚠️ **Distinct messages per buffer are mandatory** — the hash dedup at `ft8_shim.c:1387`
silently collapses repeats and every duplicate reads as a failure.

---

## 2. W1 — the §5 calibration ✅ **DONE 2026-08-07, `E = 4.28` → the "1–15" row (see §0.5)**

> 🛑 **This section is HISTORICAL — do not re-run it.** Kept for its method and its reading rule,
> both of which held. §2.2's blocker was resolved: the Captain chose option (a), run from
> `d001-c4-min-score-sweep` in an isolated worktree, `main` untouched.

**Goal:** measure `P(decode | measured BER)` for our own decoder, so every BER reading in this
project stops being read against a number the Architect invented.

**Principle: stop choosing the LLRs and let the channel generate them.**

**Method** (unchanged from `2026-07-26-2230-…` §5; I am pointing at it, not redesigning it):

1. Plant 8–10 synthetic **Q-prefix** signals per 15 s buffer at known freq/dt, **≥150 Hz apart**,
   each at its own SNR. Add AWGN.
2. Decode with `ft8_decode_all` at the **shipped** configuration —
   `ft8_set_decode_params(10, 0.10f, 60)`, `K_MAX_CANDIDATES` 140, **no constant swaps**.
3. For each planted signal read its candidate's **174 raw LLRs** and its `decoded` flag.
4. Sweep SNR downward until BER spans **0% to ≳55%**.
5. Bin by **measured** BER; plot `P(decode | BER)` with Wilson intervals.

**Two arms — the comparison between them is itself a result:**
- **Arm A** — isolated signal in AWGN. The clean calibration.
- **Arm B** — co-channel: two overlapping signals at **Δf ∈ {0, 3, 7, 15} Hz** at similar SNR. This
  is the D-001 condition and the one THE 135 actually live in.
- **If A and B diverge, compute `E` from Arm B** — and say so loudly, because it would mean BER is
  not a sufficient statistic for correctability and every band framing in this thread is keyed on the
  wrong axis.

**Sample size:** ≥40 measured candidates per 2.5% BER bin **through the transition region**. If the
transition proves narrow, concentrate a second SNR pass there rather than widening bins.

**Cost:** ~250 buffers, ≈20 min of synthetic decode. No corpus, no live audio, no NFR-021 exposure.

### 2.1 Reading rule — pre-registered, `E`, not a threshold count

> **`E = Σ over THE 135 of P(decode | BER_i)`** — the expected number of THE 135 our own decoder
> should have recovered, given the LLR quality we actually presented it with.

| `E` (of 135) | reading | consequence |
|---:|---|---|
| **< 1** | nothing we located was ever correctable — front-end limited | ⚠️ **E is a LOWER bound. State the artefact-suppression risk explicitly; do not read 0 as proof.** The decoder-scope question goes to the Captain with `N` as its denominator. |
| **1 – 15** | a real but small decode-path residue | Chase only if the cause is a single constant or gate. Captain's call, **with a number**. |
| **> 15** | **dropping correctable codewords at material scale** | 🛑 **STOP. This is a defect, not a structural gap, and it outranks everything else on the D-001 board.** Re-decompose around it. |

Report alongside, **for interpretability and not for the verdict**: B50 / B10 / B90 from the curve,
and `N = |{THE 135 : BER ≤ B50}|`.

**Why `E` and not a count below a threshold:** a mismatched candidate reads ≈50% BER where
`P(decode) ≈ 0`, so it contributes ≈0 to `E`. The ≥12.9% contamination QA measured is concentrated
exactly where `E` is insensitive. Both known biases push measured BER *up*, which pushes `E` *down* —
so a large `E` is trustworthy and a small `E` could be suppression.

**Architect's prior, on record so it can be falsified:** B50 in **12–20%**, `E` in **5–15** (middle
row). ⚠️ **This must not influence how the measurement is read.** C.5a produced a number that
flattered a conclusion I already held and I published it without checking; that is the failure this
queue exists to avoid repeating.

### 2.2 ~~🔴 W1 is BLOCKED~~ — ✅ **RESOLVED: Captain chose (a). Historical.**

**The per-candidate raw-LLR exports are not on `main`.**

| ref | `FT8_SHIM_VERSION` | raw-LLR capture |
|---|---:|---|
| `main` | 20260033 | **none** |
| `d001-c2-llr-normalization` | **20260034** | partial (`candidate_diag` only) |
| `d001-rc1-rc2-candidate-diagnostics` | **20260034** | no (different getter) |
| **`d001-c4-min-score-sweep`** | **20260035** | **all of it, + `ft8_set_llr_shrinkage`** |
| `d001-rc4-decode-depth` | **20260035** | no |

**The decision — genuinely a decision, not a formality:**
- **(a)** run W1 from `d001-c4-min-score-sweep` as-is — fastest, but that branch is unmerged,
  unreviewed, and carries `ft8_set_llr_shrinkage`, a knob whose mechanism was closed on evidence; or
- **(b)** rebase the two exports onto current `main` — cleaner, but that is `src/` work under HK-011
  and needs a Developer session plus the Captain's diff review.

**Escalate this to the Architect or the Captain. Do not settle it inside a session.** Routing around
a boundary instead of stopping at it is what produced §1.1 — and when QA hit this exact boundary in
July, stopping and asking was the correct call and caught a defect.

### 2.3 ⚠️ Do NOT re-run — already done 2026-07-26 and accepted

| item | result |
|---|---|
| decile tables, all three arms | **done** |
| control-arm mismatch rate | **done — 12.9%** |
| BER vs sync score, BER vs `postnorm_mean_abs_llr` | **done — r = −0.135**, essentially nothing |

Only **item 3** (the count that matters) was ever blocked, and only on the missing curve.

**Machinery already exists:** `c2_phase2c_ber_measurement.py` (sign convention already found and
fixed — do not re-derive it) and `c2_phase2c_ber_distribution_analysis.py`, at commit `7a604b4`,
⚠️ **reachable only from `d001-c4-min-score-sweep`**.

**Two accepted readings — do not re-derive:** **THE 135 ≈ a 567-like half plus a distinctly better
half** (~48% sits cleaner than 90% of the noise-like population) — only the lower half is in play;
and **mismatch inflates BER toward 50% and never down**, so the low tail is artefact-proof while THE
567's truncation biases it optimistically.

---

## 3. W2 — `FT8_SHIM_VERSION` collides twice ✅ **AUDITED 2026-08-07; renumbering awaits sign-off**

> 🛑 **"Six" is WRONG — there are FIVE.** The W2 audit confirmed it individually; the collision table
> itself always had five rows. `d001-c1-candidate-cap-sweep`'s DLL is **byte-identical to `main`'s**
> (its fix shipped by squash) — recommend **deletion**, not renumbering. See §0.5.

~~Six~~ **Five** unmerged `d001-*` branches, each carrying a rebuilt `libft8.dll`, and **two version
collisions** (table in §2.2). **Version alone will not tell you which binary you are running**, and two pairs
collide outright if both land.

⚠️ **`d001-c1-candidate-cap-sweep` is not an ancestor of `main`, yet its `K_MAX_CANDIDATES_ANY_PASS`
fix *is* on `main`** — it landed by squash. `git merge-base` will mislead about what shipped. Per
HK-003, verify individually before deleting any of these branches.

**Ask:** an audit and a proposed renumbering, reported up. No pushing, no merging.

---

## 4. W3 — HK-016 widening ✅ **CLOSED — it was ALREADY IMPLEMENTED**

> `tools/gather_live_run_artefacts.py` has gathered WSJT-X's AppData `ALL.TXT` by default since
> `a60b015` (2026-07-30) — **five days before this item asked for it.** No `src/` or `tools/` change
> was ever needed. A textbook HK-018: the work was on disk before it was queued.

Widen the live-run artefact-gather standard. **No preconditions** — the NFR-021 concern I attached to
it was withdrawn (`artefacts/` is blanket-gitignored at `.gitignore:105`, 0 tracked files). Small,
approved, unstarted.

---

## 5. W4 — RC3 is deferred, and the cheap route to unblocking it does not exist

C.5c tried to settle RC3's displacement objection from RC1's retained `_work/` and returned **ROW 0**:
`c_bottom` reads **0.476%** under one attribution policy and **36.5%** under the other, with the top
decile *inverting* (83.7% vs 0.36%).

**Root cause:** `candidate_lists.json` records which candidates **existed**, not which one
**decoded** — RC1's getter runs before any LDPC attempt, correctly. A median of **4** candidates sits
within tolerance of every decode. No matching rule over frequency and timing can recover the link.

**Consequence:** answering RC3's objection needs a **per-decode originating-candidate index** — a
`src/` change. **It is worth 3.1% and must not jump ahead of W1**, which bears on the 87.9%.
Not scoped here.

---

## 6. For the Captain — decisions, not QA work

- **RC4 branch** — recommend **reverting `K_MAX_PASSES` to 2** (a third pass costs CPU inside a 15 s
  budget and `K_MAX_DECODED` 340→540 for a measured no-effect) but **landing the test fix** that
  removes a hardcoded two-pass literal, broken twice now (20260007, 20260035).
- **D-009 Option B (`osd_nhard_max` 60→40)** — recommend **HOLD**. Its "after RC2" sequencing is
  void, and it makes OSD **shallower** at exactly the stage RC1 localised. Fairly stated: recall tied
  exactly (`recall_dpp = 0.000`), but on synthetic arms only, never the live window.
  🔴 **Updated 2026-08-08 — live evidence now cuts BOTH ways and the Captain should rule on it.** The
  four-decoder run measured a **~4% live FP rate** (arguing *for* shallowing OSD) against a **55.5%
  recovery deficit** (arguing *against*) — both on real off-air audio rather than synthetic S5/S7.
  See §7.3 of `2026-08-08-1942-qa-to-architect-four-decoder-live-comparison-two-legs.md`.
  ⚠️ **Note the direction of travel:** D-001's failing sub-stage is now localised to **demodulation**,
  upstream of OSD entirely — which weakens the case for spending a Developer session on either side
  of this knob before the demodulation question is settled.
- **RC1 and RC4 branches** both await HK-011 pre-push diff review. **`main` is 20 commits ahead of
  `origin/main`, all local.**

---

## 7. Lower priority — carried, not queued

- **Mechanism 1 (~34%) needs a low-density WINDOW**, not just a reference. 🛑 **"The replay corpus is
  the busiest by construction" is STALE** — the 2026-08-08 17m leg delivered Q1 density **9.7** and a
  minimum of **3**, under the 20m floor of 15.3. **A sparse regime is already on disk**; the voided
  pre-registration simply could not see it. ⚠️ **Open `qa/ARTEFACT_INVENTORY.md` before proposing
  anything, and do NOT propose a capture run.**
- 🔴 **Better than either, and newly possible:** the 20m and 17m legs **overlap at density ~13–28 on
  different bands**, so band and density can finally be separated (fit recovery ~ density + band, test
  whether the band term survives). Neither leg alone could do this. ⚠️ **Mandatory disclosure in any
  pre-registration: QA has already seen 17m running ~2–3 pts above 20m at matched density** — the
  direction is no longer blind, only the magnitude and the survival of the density slope are.
- **The 60-signal `co_channel_sweep` subset** of the current sweep has never been computed. Cheap,
  needs a small fresh S7 sub-run.
- **The post-fix FP surge is still open** — Tasks 2–4 didn't close it and **no Task 5 ruling exists**.
- **S5's OpenWSFZ-only fallback** — spec'd, not coded; would silently miscount real off-air decodes
  as false positives. ~1 h `qa/` fix, priced, not authorised.

---

## 8. Standing warning for whoever picks this up

**HK-018 fired ten times on 2026-08-07.** Three of the four RC arms re-derived work that already
existed on disk; one published a retracted number. **Every instance was a failure to open a file that
existed, in the directory already being written into.**

Before speccing or running anything on this board:

1. Open the D-001 branches — `d001-c1-*`, `d001-c2-*`, `d001-c4-*`.
2. Open `qa/ARTEFACT_INVENTORY.md`.
3. **Grep `qa/cycleframer-alignment-replay/` by topic and read the results in date order** — the July
   thread ran to a dozen dated rulings and revisions, several superseding each other within hours.
   The 22:30 ruling that retracted C.5a sat four documents after the 20:30 one that specified it.

**Treat the feeling of already knowing as the trigger to go and look.**

---

*Per HK-015 this is Architect → QA; `dev-tasks/*.md` remain QA's to author, and §2.2's blocker is an
escalation rather than a session decision. Per HK-014 committed locally, no push, no merge, and I am
not asking for one. Per HK-011 nothing here changes `src/`. Per HK-006 `pre_merge_check.py` is the
Captain's to run. Per NFR-021 all planted signals are Q-prefix synthetic; the corpus BER data stays
inside git-ignored `artefacts/`.*

---

*Amended 2026-08-08 21:15 UTC by the Architect. **The 08-07 queue is now closed out end to end** —
W1/W2/W3 done, T1 run and closed, and **T2 (§2.5) is the single live QA item.** §0.5 lists the four
statements this document originally made that are now known-wrong; where §0.5 and the body disagree,
**§0.5 wins.** Struck-through text is kept deliberately rather than deleted, so the record shows what
was believed and when. Still Architect → QA, still nothing authorised to run, still no push (HK-014).*
