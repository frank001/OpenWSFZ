# Architect → QA: pre-registration AO1 — the production time-origin offset

**Author:** Architect
**Date:** 2026-08-19 10:58Z (mechanically derived via `date -u`, HK-017; filename timestamp agrees)
**Repo state at authoring:** `qa/n1-ber-results` @ `c2aee4b`, working tree clean
**Authorised by:** the Captain, 2026-08-19 — *"do the anchor-offset"*, against §10 item 1 of the
D-001 investigation ledger (`2026-08-18-1902-…-ledger-and-route-probabilities.md`) and the
19:21Z ruling's instruction that the anchor-offset question **earns its own pre-registration**.

**Arm name:** **AO1**. Not "A1" — that label is already in use for amendments
(`2026-08-15-1301-…-m1-ruling…` §A1). Route A's own arm numbering is untouched.

---

## 0. Status, and what this document is

This is a **pre-registration**, written and committed **before the harness exists** (the H1a
discipline: spec, gate and predictions committed at a SHA that predates any measurement code).

🛑 **It is not a ruling.** No arm's status changes here. N5 stays HELD, Stage 1 stays WITHDRAWN,
Stages 3 and 4 stay BLOCKED, N1's ROW 2 and Stage 2's ROW 3 stand as reported.

🛑 **P-LIVE may not be retro-fitted into this** (16:16Z ruling §7). AO1 runs on its own population
with its own instruments. Nothing here rehabilitates a withdrawn number.

🛑 **No `src/` change is authorised by this document.** AO1 is re-analysis plus one diagnostic
sweep against the already-pinned DLL. Any fix to `CycleFramer.cs` is a Developer session and the
Captain's sign-off (HK-011), and is out of scope until AO1 reports.

**NFR-021:** counts, rates, statistics, file paths. The matched-pair join reads message text
in-process only; no emitted file or stdout line may carry a callsign or message text.

---

## 1. Why this arm exists

The 19:21Z combined pre-registration barred Part A from claiming the +0.65 s offset was a
**production** defect, for a correct reason: *the harness anchoring is not the production framer,
and nothing in Stage 1R or Stage 2 measures the production framer.* Both rounds measured a QA
harness feeding an anchor into `ft8_extract_llrs_at`.

**AO1 is the instrument that ruling said was missing.** It measures the production decoder's own
committed output and the production daemon's own archived audio. It is the only thing on the board
that can promote the offset from "harness convention mismatch" to "production defect", or retire it.

Three findings make it answerable cheaply, all already on disk:

1. **`ft8_extract_llrs_at` carries no hidden constant.** `ft8_shim.c:1550-1590`: `time_offset_s` is
   converted by the **exact inverse** of `ft8_decode_all`'s own forward mapping
   (`dt = (time_offset + time_sub / time_osr) × symbol_period`). The harness argument and our
   production `dt` are therefore **the same quantity in the same convention**. Any offset between
   them is a property of the audio buffer or of the mapping's origin — it cannot be an API artefact.
2. **The buffer is the file, sample for sample.** Every WAV in both legs of PRIMARY is **exactly
   180 000 frames / 12 kHz / mono / 16-bit = 15.0000 s** (measured, 400-file sample per leg). There
   is no padding, no truncation, and therefore no length artefact in `p23_common.read_wav`'s
   pad-tail/truncate-to-first-180 000 behaviour.
3. **ROW 0a already aligned the two legs' audio**: median `|r|` = 0.987, `|lag|` ≤ 34 ms, five
   corpora, 2026-08-18 14:46Z. The two legs' files start at the same instant to within 34 ms.

⚠️ **The single strongest inference available before any measurement, and it needs no absolute UTC
reference:** both legs run on **one machine, one clock, one antenna, one audio device** (standing
board fact since the project began). A wrong PC clock, or a propagation effect, moves **both** legs
identically and cancels. Only an **implementation** difference can move one leg relative to the
other. So a leg-to-leg `dt` difference is, by construction, a statement about our decoder's time
origin versus the reference implementation's — not about the host clock, not about the band.

---

## 2. Architect scouting disclosure — read this before drafting anything downstream

🔴 **I ran four exploratory measurements while drafting** (HK-018: prefer a five-minute measurement
to a paragraph of reasoning). They are disclosed in full so the gate cannot be accused of having
been drawn around a number I had already seen without saying so.

🛑 **NONE of the following is citable. Not one figure. They exist to establish identifiability
(HK-021(c)) and resolution (HK-021(m)), and to size the arm.** QA re-derives every one of them
under the gate below, with its own harness, and QA's numbers are the ones that count.

| # | what I measured | result |
|---|---|---|
| S1 | WAV geometry, both legs, PRIMARY | 180 000 frames exactly, 12 kHz mono 16-bit, **15.0000 s**, no exceptions in 400 files/leg |
| S2 | Reported `dt` population, PRIMARY, per leg, unmatched | reference median **+0.20 s** (mean +0.233, n=43 423) · ours median **+0.80 s** (mean +0.869, n=64 417) |
| S3 | **Matched-pair** signed `dt` difference (ours − reference), unique matches only, four corpora | median **+0.65 to +0.70 s**, IQR **+0.60 to +0.70 s** in *every* corpus — 20m/17m/80m, three days, ~103 000 matched pairs |
| S4 | Recovery stratified by reference `dt`, PRIMARY, **SNR not controlled** | bulk (0.0/+0.5 s) **59.0%**; +1.0 s **54.9%**; +1.5 s **53.1%**; +2.0 s **34.8%**; −0.5 s **52.4%** |

**What S3 means and does not mean.** The spread is 0.10 s — precisely the reporting quantisation of
the two instruments (reference 0.1 s, ours 0.08 s). The underlying quantity is a **constant**, not a
distribution, and it is the **same constant** Stage 1R and Stage 2's Part A found by an entirely
different route. It has been sitting in our own committed production output since the programme
began. It does **not** yet tell us whether the buffer is misplaced or only mislabelled — §3.

**What S4 means and does not mean.** There is a recall gradient at both `dt` tails. Naively
attributing it all to the offset gives roughly **+0.5 pp** of recoverable recall on a 42 pp gap.
🛑 **That arithmetic is not admissible and I am not offering it as an estimate** — high-`dt` signals
are also physically different (long path, weak, late transmitters), so the gradient is confounded
with SNR and signal quality. Part C exists to measure it at matched SNR. I record the naive figure
only so that nobody re-derives it and mistakes it for a finding.

🔴 **Consequence for my own predictions in §8: I have seen S3. My value for `R` is therefore NOT a
prediction and MUST NOT be scored.** Recording this explicitly because my calibration note already
says my ranges are *"under-dispersed and skewed toward whatever measurement I saw last"*, and here
I have literally seen it.

---

## 3. The question, split into three claims that must not be conflated

| claim | statement | consequence if true |
|---|---|---|
| **R — reporting** | Our published `dt` is offset from the FT8 convention by a constant | User-visible product defect. Every `dt` we display and log is wrong by that constant. **No recall consequence on its own.** |
| **B — placement** | Our decode **buffer** starts off the UTC grid by that constant | Production framing defect. Route A territory. Recall consequence at the population's `dt` tails. |
| **C — cost** | The placement costs recall, at matched SNR | Sizes B. Determines whether a framing fix is a D-001 treatment or a product fix. |

**R and B are separable and the separation is the point of this arm.** If the buffer sits correctly
at `[G, G+15]` and only the label is wrong, the signal physically sits at its true `dt` inside our
buffer and there is nothing to recover. If the signal physically sits ~0.65 s later inside our
buffer than the grid says, the buffer itself is misplaced.

**The discriminator.** `R` is derived from the **live** decode path (`owsfz/ALL.TXT`, written by the
running daemon). `K` (below) is derived from the **archived** audio by physically locating the
signal. They are different code paths reaching the same quantity:

- `R ≈ K` ⇒ the archive faithfully represents the live buffer, and the offset is **placement**.
- `R` large, `K ≈ 0` ⇒ the signal is physically where the grid says and the offset is **labelling**.
- `R` and `K` disagree in sign or by more than the tolerance ⇒ one instrument is broken; **no
  verdict**, escalate.

🔴 **HK-022 drafting question — what error could this design NOT detect?** One: an error shared by
the archive writer and the live decoder, such that the archived WAV is not the buffer that was
decoded. That is exactly why `R` is taken from the live path and `K` from the archive, and why their
agreement is a gated row rather than an assumption. If both were archive-derived the design would be
decorative.

---

## 4. Instruments, populations, clustering

**PRIMARY (confirmatory):** `20260803_live_run_1713`. **EXTENSION (descriptive replication, reported
per corpus, NEVER pooled or summed — Sec.5.2 leg-handling rule):** `20260808_live_run_0016-8080`,
`20260808_live_run_1154-8080-17m`, `20260809_live_run_0155-8080-80m`.
🛑 `-8081` legs are excluded from AO1: they observe the same cycles as their `-8080` twin at median
Jaccard ~1.000 and would double-count. 🛑 `20260809_…-80m`'s `-8081` leg carries the G1 hardlink
defect; the `-8080` leg is the sound one.

**Matched pair:** a reference decode whose hash-normalised message appears **exactly once** in our
own `ALL.TXT` for the same `ts`. Uniqueness is required — ambiguous pairings are dropped and
**counted**, not resolved.

**`D_i` = `dt_ours,i` − `dt_ref,i`.** 🔴 **SIGNED. Report the signed value everywhere.**

**Cluster = `ts`.** Cluster bootstrap, 2 000 draws, seeded, reusing `n1_stats`'
`cluster_bootstrap_median_diff` verbatim where the statistic matches. 🔴 **Report cluster counts,
never bare row counts** (HK-021(i)).

**`K` — the physical-position sweep.** On **our own** `owsfz/wav/<ts>.wav`, anchored at the
**reference's** reported `(freq, dt)`, sweep the offset argument on M3's grid and take the argmin of
median `BER_V0`. This is Stage 1R's method, re-pointed at our own audio — the step neither Stage 1R
nor Stage 2 performed, and the load-bearing new measurement in AO1.

**Sample:** seeded, ≥600 rows for the sweep (Stage 2's Part A precedent measured 556/600). The `R`
statistic runs on the **full** matched population, not the sample — it is free.

⚠️ **`c2_phase2c_ber_measurement.parse_all_txt` drops the SNR field** (`:105` keeps `tok[0,5,6,7:]`;
SNR is `tok[4]`). Part C needs it. Extending the parser is **QA tooling — no Developer session**
(HK-011 not engaged). 🔴 Do not confuse `[5]` DT with `[6]` freq: it inverts a result exactly.

⚠️ **`compute_matched_hit_control(cycles, limit=N)` truncates in file order** — if any helper with a
`limit=` is reused, check what it does before trusting the cluster count (HK-021(i)).

---

## 5. The gate — Part B (the offset), on PRIMARY, strict order

**ROW 0 — pre-gate. HK-025 classification and both-branch evaluation in §6.**

| row | class | condition (fires if) | consequence |
|---|---|---|---|
| **0a** | instrument | DLL SHA256 ≠ pin, re-hashed and asserted before arming, both bindings | STOP |
| **0b** | power | PRIMARY matched pairs < 2 000 rows **OR** < 500 clusters | STOP |
| **0c** | validity | cluster-median `dt_ref` outside **[−0.35, +0.35] s** (two-sided) | STOP — the reference's own grid lock is in question |
| **0d** | validity | median `BER_V0` at the swept argmin outside **[1.0%, 15.0%]** (two-sided, HK-021(n)) | STOP — the sweep is not reading |
| **0e** | instrument | sign unit test fails: anchor displaced by a known delta, sweep must land at its **negation**, both signs | STOP |
| **0f** | precision | any of 4 chronological `ts`-quartiles' own argmin differs from pooled by **> 0.05 s** | Report as drift; Part B reports per-quartile, Part C does not run |
| **0g** | precision | SNR field unparseable on **> 5%** of reference rows | Part C is descriptive only, gates nothing |

**Main rows — mutually exclusive and exhaustive over `(|R|, |K|, signs)` by construction.**
Threshold `θ = 0.10 s` — **the reporting resolution of the reference instrument**, i.e. the finest
distinction available. 🔴 **It is not derived from any scouted value.**

| row | condition | verdict and consequence — stated as an assertion |
|---|---|---|
| **ROW 1** | `\|R\| < θ` **AND** `\|K\| < θ` | **No production offset.** Stage 1R's +0.65 s is a harness-only artefact, fully explained and fully contained. Route A is **not** re-routed. The anchor-offset question **CLOSES**. |
| **ROW 2** | `\|R\| ≥ θ` **AND** `\|K\| < θ` | **Labelling defect only.** Our published `dt` is wrong by `R`; the buffer is correctly placed. This is a **product defect with no recall consequence** — a reporting constant, plus a permanent correction in every harness that anchors from a foreign `dt`. D-001 **unaffected**. Part C does not run. |
| **ROW 3** | `\|R\| ≥ θ` **AND** `\|K\| ≥ θ` **AND** `sign(K) = sign(R)` **AND** `\|K − R\| ≤ 0.15 s` | **Production framing defect, archive faithful to the live buffer.** Our decode buffer is misplaced against the UTC grid by `R`. **Route A is promoted from open to confirmed-in-part**, and `CycleFramer`'s realignment does not achieve its own documented intent (`:184` — "spans the wall-clock interval `[G, G+15]`"). **Part C runs** and sizes it. A Developer session becomes justified — but is **not** authorised by this document. |
| **ROW 4** | `\|R\| ≥ θ` **AND** `\|K\| ≥ θ` **AND** (`sign(K) ≠ sign(R)` **OR** `\|K − R\| > 0.15 s`) | **Incoherent — the live path and the archive path disagree.** One instrument is broken, or the archive is not the decoded buffer. **NO VERDICT.** Escalate. Do not report a number for either. |
| **ROW 5** | `\|R\| < θ` **AND** `\|K\| ≥ θ` | **Incoherent, reverse.** Reported `dt` agrees with the reference while the signal physically sits elsewhere in our own audio. **NO VERDICT.** Escalate. |

### 5.1 On the magnitude tests — HK-021(l) addressed head-on, not sidestepped

A reviewer will reach for sibling (l) — *never gate on `|x|` where a signed statistic exists* — on
sight of `|R|` and `|K|`. Six occurrences, all mine, one of which nearly buried a p = 0.000 harm.

**It does not apply here, and here is the test I applied.** (l)'s failure mode is **pooling opposite
signs so that a real effect reads as null**. That requires the two signs to carry *different*
verdicts. In AO1 an early buffer and a late buffer are the **same defect class** — both are "our
origin is off the grid", both cost recall at a `dt` tail, both need the same fix. The sign is not
pooled away: it is **carried explicitly into ROWS 3, 4 and 5**, where a sign disagreement between
the two instruments is itself a firing condition and a no-verdict.

🔴 **Binding on the report regardless: `R` and `K` are reported SIGNED, with signed CIs, in every
table. The magnitude appears only inside the row conditions, never in a reported figure.**

### 5.2 Resolution — HK-021(m), stated while drafting

`D_i` carries ±0.05 s of reference quantisation and ±0.04 s of ours. With ≥500 clusters the
cluster-bootstrap SE on a median of `D` is on the order of **0.001–0.005 s**, so `1.96·SE ≈ 0.01 s`
against a **0.10 s** bar — the gate resolves its own threshold by roughly an order of magnitude.
**A straddle on Part B is not a realistic outcome.**

⚠️ **Part C is the opposite case and I will not pretend otherwise.** Its resolution depends on the
`dt`-tail cell counts after SNR stratification, and those cells are small (S4's +2.0 s stratum held
198 rows *before* stratification). 🔴 **QA must compute and report Part C's own `1.96·SE` against
its bars BEFORE reading the verdict**, and if the resolution does not separate the bars, Part C
reports **ROW C0 — underpowered**, which is an instrument failure, **not a null** (HK-021(i)).

---

## 6. HK-025 classification — both branches, every pre-gate row

The refusal test: *classify (does the row, when it fires, still leave an estimate of what the gate
names?), then evaluate BOTH branches. Same row either way ⇒ diagnostic ⇒ refuse and stop.*

| row | fires ⇒ | does not fire ⇒ | classification |
|---|---|---|---|
| **0a** | wrong binary; every number describes an unknown build | the pinned build | **VALIDITY** — branches differ |
| **0b** | CI too wide to separate 0.10 s | powered | **PRECISION** — branches differ |
| **0c** | reference origin suspect ⇒ `R` measures an unknown sum of two origins, not ours | reference is the grid | **VALIDITY** — branches differ |
| **0d** | sweep is reading noise ⇒ `K`'s argmin is not a position | `K` is a position | **VALIDITY** — branches differ |
| **0e** | sweep sign convention unverified ⇒ `K`'s sign is uninterpretable, and sign drives ROWS 3/4/5 | sign verified | **VALIDITY** — branches differ |
| **0f** | offset is not constant ⇒ a pooled `K` is a mixture, but a per-quartile `K` is still an estimate | constant | **PRECISION** — branches differ |
| **0g** | Part C cannot control SNR ⇒ Part C descriptive; **Part B unaffected either way** | Part C gated | **PRECISION**, scoped to Part C only |

🔴 **No row above evaluates to the same verdict on both branches. There is no HK-021(k) diagnostic
row in this gate and therefore no HK-025 refusal is expected.** That is a claim to **check**, not a
conclusion to adopt — given §1/§2 of the 19:21Z ruling, treat my classification as an assertion QA
tests, and refuse if any row evaluates the same both ways.

---

## 7. The gate — Part C (recall cost). Runs ONLY if ROW 3 fired and 0f/0g cleared.

**Statistic `L`** — recall attributable to `dt`-tail loss, **at matched SNR**, using the
standardisation method already proven in X1/X2: within each SNR stratum, compare each `dt` stratum's
recovery against the **modal** `dt` stratum's, weight by the `dt` stratum's share of the reference
population, and sum. Cluster-bootstrap CI by `ts`. 🔴 **`L` is SIGNED.**

| row | condition | consequence |
|---|---|---|
| **C0** | `1.96·SE(L)` ≥ 1.0 pp (resolution does not separate the bars) | **UNDERPOWERED — an instrument failure, not a null.** No verdict. |
| **C1** | `L ≥ +2.0 pp` **AND** `CI_lo > 0` | Material recall cost. A framing fix becomes a **D-001 treatment candidate in its own right** and is sized against Route B. |
| **C2** | `+0.2 pp ≤ L < +2.0 pp` **AND** `CI_lo > 0` | Real but small. **Fix on product grounds, not as a D-001 route.** Do not let it displace Route B in any sizing document. |
| **C3** | `L < +0.2 pp` **OR** `CI` contains 0 | No measurable recall cost at matched SNR. The offset is a reporting/product defect only. |
| **C4** | `L ≤ −0.2 pp` **AND** `CI_hi < 0` | **The offset APPEARS to help.** The model is wrong. Report it loudly and stop — do not rationalise it. |

C0 is evaluated **first** and strictly. C1–C4 are mutually exclusive by construction.

**HK-021(n) two-sidedness:** `L`'s degenerate direction is toward 0 (recovery flat across `dt`), and
`BER_V0`'s is toward 50%. Both are gated two-sided — C3/C4 for `L`, ROW 0d for `BER_V0`.

---

## 8. Predictions, recorded before the harness exists

🔴 **Architect calibration, quoted because this gate turns on my predictions: categorical 7/12 ·
ranges 10/18 · directional 2.5/5.5 · mechanical 3/4.** My ranges are under-dispersed and skewed
toward the last measurement I saw.

| quantity | my call | scoreable? |
|---|---|---|
| Part B row | **ROW 3** (buffer misplaced), P ≈ **0.70**; ROW 2 (labelling only) P ≈ 0.25; ROW 1 P ≈ 0.03; ROW 4/5 P ≈ 0.02 | **YES — categorical** |
| `R` | +0.65 s | 🛑 **NO. I scouted it (S3). Not a prediction. Do not score it.** |
| `K` | +0.55 to +0.75 s | **YES — range.** I have *not* measured `K` on our own audio; only on the reference's. |
| `\|K − R\|` | ≤ 0.05 s | **YES — range** |
| ROW 0f | clears (quartile deviation ≤ 0.05 s) | **YES — categorical** |
| Part C row | **C2**, `L` ∈ **[+0.2, +1.0] pp** | **YES — categorical + range** |
| Part C power | ~50/50 that C0 fires instead | **YES — directional** |

**Where I expect to be wrong.** The honest weak point is `K`. Everything I have that bears on it is
*indirect*: the shim's mapping has no constant, the WAVs are exactly 15 s, and ROW 0a aligns the two
legs to 34 ms. Those make ROW 3 the natural reading, but **nobody has ever located an FT8 signal
physically inside our own archived audio.** If `K ≈ 0`, ROW 2 fires and this becomes a labelling
bug — and I would rather that be the finding than defend a 0.70.

---

## 9. Consequences, as assertions

- **ROW 1 fires** ⇒ the anchor-offset question **CLOSES**. Stage 1R's correction remains a
  harness-only constant, correctly applied. Route A's 12% is unchanged. Nothing propagates.
- **ROW 2 fires** ⇒ a **product defect** is confirmed and D-001's route selection is **unchanged**.
  The `dt` we display and log is wrong by `R`; every future harness anchoring from a foreign `dt`
  applies `R` permanently. **Route A is not promoted.** I would expect the Captain to route the
  display fix as ordinary product work, not as D-001.
- **ROW 3 fires** ⇒ a **production framing defect** is confirmed, `CycleFramer`'s realignment does
  not achieve its documented intent, and **Part C's row decides whether it is a D-001 treatment
  (C1) or a product fix (C2/C3)**. 🛑 Even on C1 this document does not authorise the fix: HK-011,
  Developer session, Captain's sign-off.
- **ROW 4 or ROW 5 fires** ⇒ **no verdict**, escalate, and the archive-vs-live-buffer question
  becomes the next arm. Do not report `R` or `K` as findings.
- **In every branch:** D-001's headline recovery figures, N1's ROW 2, Stage 2's ROW 3, N4's
  knife-edge, N5's HELD status and Route B2's sizing are **untouched**. AO1 cannot move them and
  must not be cited as though it had.

---

## 10. What AO1 may NOT claim

- 🛑 **May not claim D-001 is explained.** The largest credible recall figure in play is ~2 pp
  against a ~42 pp gap. If ROW 3 and C1 both fire, that is a *contributing* defect, not the cause.
- 🛑 **May not rehabilitate any withdrawn number.** Stage 1's `f_cross` = 0/15 389, the 0.0765%
  bound and "N5 CONFIRMED" stay uncitable whatever AO1 finds.
- 🛑 **May not be used to reopen limb 1, R2, or N1's ROW 2.** N1's anchor was convention-clean.
- 🛑 **May not extend to the sub-lattice time residual.** T1's prohibition stands: reference `dt`
  resolution (0.1 s) is coarser than our 0.08 s step, so the *residual* is not identifiable.
  ⚠️ **AO1 measures a BULK offset of ~6.5× that resolution — a different quantity by construction,
  and this is a NEW pre-registration, not a closed gate re-read with a better metric.** State that
  distinction in the report; someone will raise T1 against it.
- 🛑 **May not claim the two-instance control proves absolute UTC alignment.** It proves the offset
  is an *implementation* difference, not a host-clock or propagation difference. Absolute alignment
  inherits the reference's grid lock as an assumption, checked only for plausibility by ROW 0c.

---

## 11. Execution order

1. ROW 0a — re-hash the DLL, assert against the pin, **before arming**.
2. ROW 0e — the sign unit test (reuse Stage 2's construction verbatim; it passed both signs there).
3. ROW 0b — matched-pair dry count on PRIMARY, rows **and** clusters.
4. ROW 0c — reference `dt` grid-lock check.
5. Compute `R` on the full PRIMARY matched population, cluster-bootstrapped, **signed**.
6. Sweep `K` on our own archived audio, seeded sample ≥600 rows. Then ROW 0d, then ROW 0f.
7. Evaluate Part B ROWS 1–5 in strict order. Stop at the first that fires.
8. Part C **only** if ROW 3 fired and 0f/0g cleared. Evaluate C0 first.
9. Replicate `R` (and `K` if affordable) on the three EXTENSION corpora — **descriptive, per corpus,
   never pooled**, HK-021(k): it gates nothing, PRIMARY decides regardless.
10. Report. **STOP.** No fix, no `src/`, no follow-on arm without a ruling.

🔴 **HK-025 refusal is available on every row and needs no agreement from me.** Given that nine of
the defects found in the recent N/P series were in my own specs, treat §5, §6 and §7 as claims to
check, not conclusions to adopt.

---

## 12. Housekeeping

- No `src/` touched, no Developer session, no DLL rebuild, no capture run. **HK-011 not engaged.**
- HK-014: committed **locally only**. The Architect never pushes or merges, and does not ask.
- HK-024: `memory/BOARD.md` updated in the same edit as this document.
- HK-017: filename `2026-08-19-1058-…` and the byline both derive from a real `date -u` and agree.
- NFR-021: no callsigns, no message text, in this document or in any file AO1 emits.
- Scouting harnesses used in §2 were throwaway one-liners and are **not** committed; QA's harness is
  the one that counts and is the one that gets committed.
