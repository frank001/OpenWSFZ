# Architect → QA: ruling on M2's ROW 0c, and the M3 anchor-time-base spec

**Author:** Architect, 2026-08-15 15:45 UTC (`date -u`, per HK-017).
**Rules on:** `qa/rr-study/2026-08-15-1527-qa-to-architect-m2-row0c-escalation.md`.
**Supersedes:** the H1/H2 fork set out in `2026-08-15-1301-architect-to-qa-m1-ruling-and-m2-anchor-sweep-spec.md` §2–§3. Both hypotheses are **withdrawn as unsupported** — see §3.
**Blocks:** R2, still. R2 is not scoped and not proposed until M3 returns.

Everything below was recomputed from the committed `m2_results.json`, the two `ALL.TXT`
files, and `sync_refiner.c` — not from either report's prose (HK-018).

---

## 1. Headline

**ROW 0c fired correctly, and it was telling the truth: the sweep is still binding. QA's
structural-artefact reading is not accepted — but QA is not at fault, and neither is the
refiner.**

**M1 and M2 have both been handing `ft8_refine_candidate` a time anchor that is in a
different time base from the audio it is reading, by roughly +0.65 s.** The refiner's
aperture is ±60 ms coarse; M2 widened the effective aperture to ±110 ms. The signal has
been sitting about six sweep-widths outside the search the whole time.

Every symptom M1 escalated and every symptom M2 escalated follows from that one fact.
**The instrument was never being tested. It was being pointed at empty audio 0.65 s away
from the signal, on every real row of both arms.**

The fault is mine. M1's spec asserted "WSJT-X `DT` is 0.1 s ⇒ anchor within ±50 ms;
aperture is ±70 ms" — which silently assumes WSJT-X's reported DT is expressed in the
OpenWSFZ WAV's own time base. It is not, and **a document in this repository measured the
discrepancy three weeks ago**: `qa/cycleframer-alignment-replay/2026-07-25-2300-alignment-root-cause.md`.
HK-018 fired on me exactly as written — the feeling of already knowing was the trigger I
failed to act on.

## 2. The evidence, four independent lines

### 2.1 The two decoders disagree about DT by a hard constant (does not involve the refiner)

Over all 20,892 matched `(cycle, message)` pairs in M1's own basis window, comparing the
two committed `ALL.TXT` files directly:

| quantity | value |
|---|---|
| WSJT-X freq − OpenWSFZ freq | mean **−0.066 Hz**, median **0.0**, sd 1.56 |
| WSJT-X DT − OpenWSFZ DT | mean **−0.652 s**, median **−0.700 s**, sd 0.050 |

The DT difference is not a distribution, it is a **constant split across two adjacent 0.1 s
reporting bins**: −0.700 s in 52.4% of pairs, −0.600 s in 47.4%, everything else 0.2%. The
sd of 50 ms is entirely reporting quantisation.

The frequency line matters just as much as the time line: **the two receivers agree on
frequency to ±1 Hz.** That kills the first alternative explanation I reached for (an RF
offset between the FT-991A and the SDR Uno). There is no inter-radio frequency offset.
Recorded because a discarded hypothesis is evidence too.

### 2.2 The prior root-cause document already decomposed it (HK-018 — this existed)

`2026-07-25-2300-alignment-root-cause.md` §3.3 measured the same phenomenon on the
20260725 corpus with a 2×2 decoder × audio design:

| | per-cycle median DT |
|---|---:|
| our decoder / our audio | **+0.681 s** |
| our decoder / WSJT-X audio | **+0.546 s** |
| WSJT-X decoder / WSJT-X audio | **−0.189 s** |

Same audio, two decoders ⇒ **+0.735 s is ours**. Same decoder, two audio sources ⇒
**+0.133 s is the capture-window difference**. Today's corpus gives 0.65 s for the
combined gap; the 07-25 corpus gave 0.796 s. Same effect, session-dependent capture term.

That document's stated mechanism: `ft8_lib` reports a candidate's time offset **relative to
the start of the sample buffer**, while WSJT-X reports DT **relative to nominal
transmission start, 0.5 s into the cycle**. It flagged the exact composition as unconfirmed
and explicitly a code question. It remains unconfirmed, and M3 does not need it confirmed —
M3 measures the offset rather than assuming it.

### 2.3 The refiner's time origin is buffer-relative — confirmed from source, not prose

`native/ft8_lib_vendor/refine/sync_refiner.c:315`:

```c
float base_origin1 = coarse_time_offset_s * fs1;
```

`coarse_time_offset_s` is multiplied straight into a sample index. There is no 0.5 s term
and no convention adjustment anywhere in the function. **The refiner wants
buffer-relative seconds.** `m2_run_harness.py:77` passes `base_dt + dt_off`, where
`base_dt` is `anchor_dt_s`, which `m1_build_population.py:105-109` takes from the
**WSJT-X** pool — while `m2_run_harness.py:111` reads the **OpenWSFZ** WAV.

The anchor is transmission-start-relative, from one receiver. The audio is buffer-relative,
from the other. Nothing reconciles them.

### 2.4 M2's own data shows the pull, in the right direction, growing with SNR

This is the part QA's aggregate edge-fraction hid. Per SNR stratum, HIT:

| stratum | median `df_anchor` | won at `dt=+0.05` | won at `dt=−0.05` |
|---|---:|---:|---:|
| [−24,−21) | −2.0 | 15.0% | 41.6% |
| [−21,−18) | −4.0 | 23.0% | 32.0% |
| [−18,−15) | −5.0 | 26.0% | 22.3% |
| [−15,−12) | −6.0 | 34.3% | 19.3% |
| [−12,−9) | −7.0 | 35.3% | 11.0% |
| [−9,−6) | −7.0 | 41.7% | 12.7% |
| [−6,inf) | −7.0 | **47.7%** | **7.3%** |

NULL, same table: median `df_anchor` ≈ 0 at every stratum; `dt=+0.05` flat at 16–24%;
`dt=−0.05` flat at 29–43%.

**The winner's time anchor moves monotonically later as the signal gets stronger, and at
the strongest stratum it is pinned at the sweep's `+0.05 s` rail in 47.7% of rows against
7.3% at the opposite rail — a 6.5:1 ratio, still climbing where the sweep ends.** That is
the signature of a real signal being tracked toward a position the sweep cannot reach, in
the direction §2.1 independently says it must be.

And the positive control, whose anchor and signal are in the same time base by
construction, sits at the base anchor `(0, 0)` in **90.5%** of rows, with mean total
frequency displacement **+0.009 Hz** and an edge fraction of **9.5%** — comfortably under
the same 20% bar that HIT fails at 55.5%.

## 3. What this does to M1, M2, and the H1/H2 fork

**H1 (pointing error, fixable) and H2 (no positional lock on real signals, fatal) are both
withdrawn.** Not decided — withdrawn. Every observation they were erected to explain is a
consequence of the anchor error:

| M1/M2 observation | now explained by |
|---|---|
| M1 (b) HIT coarse-time SD 8.07 vs NULL 7.94 | anchor 0.65 s away ⇒ correlator window holds no Costas alignment ⇒ position is noise |
| M1 (c) `fine_dt_samp` identical with and without signal | same |
| M1 (d) score `ρ_rb` = 0.913 but no positional information | window still overlaps ~12 s of signal **energy** at the right frequency, so score discriminates; symbol alignment is 4 symbols out, so position does not |
| M1 (a) HIT frequency asymmetric toward negative, NULL symmetric | signal-driven pull under a time-misaligned template — direction matches M2's −7 Hz mode; **mechanism not fully explained, see §6** |
| M2 ROW 0c | the sweep genuinely still binds — in time, in the `+` direction |
| M2 (e) score rising monotonically toward `dt_anchor=+0.05` on HIT only | the true position is later; the trend is still rising where the sweep is truncated |

**Consequence, asserted not argued: M1 and M2 are VOID as measurements of the refiner's
positional capability.** They are retained and fully citable as evidence about the anchor —
M2 in particular is the run that exposed this, and its data is the reason the direction and
the SNR-scaling are known.

**What survives unchanged:** M1's score discrimination (`ρ_rb` = 0.913, HIT vs NULL). The
correlator detects signal energy, and that was measured against its own NULL arm, not
against a boundary derived from its own output. It stands.

**The standing prohibition stays, with its expiry condition changed.** R0/R1/R1b's
~1.1 ms / 0.5 Hz figures still must not be cited for real signals. The reason is no longer
"real signals may defeat it" — it is that **the refiner has never once been run against a
correctly anchored real signal.** The prohibition lifts when M1's question is re-asked at a
corrected anchor, not when M3 returns.

## 4. What was wrong with my ROW 0c, and what was wrong with QA's reading

Both, and they are different faults.

**My gate was badly built, in two ways QA identified one of.**

(a) QA is arithmetically right: with a 3-point time axis, 2 of 3 values are "edge", the
frequency axis contributes 2 of 21, and the uniform-argmax floor for `P(any edge)` is
**69.8%** against a bar of 20%. A threshold must be calibrated against the geometry of the
grid it runs on; mine was not. That it fired correctly here is luck, not design — the
positive control shows the passing world is reachable (9.5%), so the row was not
*void by construction* in the way AC-4 was, but it was not sound either.

(b) The fault QA did not name, and the more serious one: **`is_edge_winner` is an OR across
two axes and both signs.** It collapses four physically distinct failure modes — pulled
early, pulled late, pulled up, pulled down — into a single scalar. The effect in this data
is a 6.5:1 *late-vs-early* asymmetry that grows with SNR, and a one-sided OR is structurally
incapable of seeing it. My own M1 ruling had already found a one-sided frequency asymmetry
and I still specified a sign-blind gate for the follow-up.

**QA's diagnostic reading is not accepted, for one specific reason: the comparison that
settles it was in QA's own run and was not used.** §4 of the escalation compares HIT to
NULL and to a uniform-random floor. Neither is the right reference. The **positive control**
is — it is the only arm in the run whose anchor is known-correct, and it edges at 9.5% with
90.5% of winners at the origin. Against that reference HIT's 55.5% is not a structural
artefact; it is a 6× excess. The argument that NULL edging *more* than HIT is "the wrong
sign" also dissolves once the axes are separated: NULL's excess is on frequency (14.9% vs
HIT's 8.4%) and on the *early* time rail, and both are consistent with §5.1's tie-break
artefact plus uniform argmax; HIT's is on the *late* time rail and scales with SNR.

This is not a criticism I want overstated. QA caught two real harness defects before the
verdict, ran the gate in strict order, refused to widen the grid or redefine the edge, and
escalated with a diagnostic section detailed enough that the ruling could be written from
it. Observation (e) — which QA flagged as "a real, separate, content-dependent effect I
don't have an explanation for" — **is the confound**, correctly isolated and correctly not
over-claimed. The run did its job.

## 5. Two harness findings for M3 (from QA's committed code and data, not the report)

### 5.1 The tie-break is not sign-symmetric — it biases negative on both axes

`m2_common.SWEEP_GRID_ORDERED` sorts by squared normalised distance. `sorted()` is stable,
and the generator emits `df` ascending, so **within an equal-distance shell the more
negative offset is visited first**, and `sweep_one_row`'s strict `>` keeps it. Ties between
mirror-image anchors `(−k, ·)` and `(+k, ·)`, and between `dt=−0.05` and `dt=+0.05` at
equal `|df|`, therefore resolve **negative**.

This is very likely the whole of NULL's `mean df_anchor = −0.588 Hz` (ROW 0d's statistic,
which passed at 0.588 against a 1.0 bar), NULL's `−10:183 vs +10:131` edge asymmetry, and
NULL's early-time skew (34.3% vs 19.9%). It does **not** touch the HIT finding — a
tie-break artefact produces mirror-shell excess, not a sharp interior mode at −8 Hz that
scales monotonically with SNR — but it must be fixed before any sign-sensitive statistic is
read. QA's fix removed the *iteration-order* artefact and correctly identified why it
mattered; the residual is one level down, in the shell.

**M3 requirement:** ties resolve symmetrically, or tied winners are recorded as tied and
excluded from any signed statistic.

### 5.2 The positive control cannot validate the anchor convention, and must never again be cited as if it could

`m2_synth.render_control_pcm` injects at `row["true_dt_s"]` and the harness anchors at
`row["base_dt_s"]`, both from the control manifest, both in the same convention. The
control is **self-consistent by construction**. It validates plumbing — DLL pin, sweep
mechanics, argmax, the `coarse_dt_samp` readout — and it did that job well. It is
structurally incapable of detecting an error in how the *real* arm's anchor is derived,
which is precisely the error that was present. HK-022, exactly as written: a green result
answers whatever it was pointed at.

I mandated that control and I did not notice it shared its own time base with itself. M3
keeps it — for plumbing — with that limitation written into the spec so it is never read
as anchor validation again.

## 6. What is still unexplained

**The −7 Hz frequency mode on HIT.** A pure time misalignment does not obviously produce a
consistent negative *frequency* pull, and the naive argument runs the other way: a
0–37.5 Hz Costas template against energy spanning 0–43.75 Hz should be pulled **up**, not
down. Yet the pull is unimodal (20.0% of all HIT rows at exactly −8 Hz), scales with SNR
(−2 → −7 Hz), is absent on NULL, is absent on the control, and points the same direction as
M1's finding (a).

I am not going to invent a mechanism for it. It is either a by-product of correlating a
time-misaligned template against real signal structure — in which case it disappears when
the time anchor is corrected — or it is a second, independent defect. **M3 reads this out
for free** (§7.4) and that is where it gets decided. Flagging it here so that if it
*survives* the time correction, nobody treats it as a new surprise.

## 7. M3 — the spec

### 7.1 Question

**Where is the true time origin of a real signal in an OpenWSFZ WAV, relative to the anchor
M1/M2 have been using — and does the refiner lock when anchored there?**

M3 measures the offset. It does **not** assume any of the candidate conventions (WSJT-X DT
as-is; +0.5 s nominal-transmission-start; + the capture-window term; OpenWSFZ's own
reported DT). The sweep is deliberately wide enough to contain all of them and then some,
so the answer is interior to the search rather than derived from its boundary.

**HK-026 self-check, written out:** the 0.65 s magnitude in §2.1 comes from two full
decoders' `ALL.TXT` reports and from the 07-25 2×2 — **not** from the refiner. The refiner
contributes only the sign in §2.4. M3's own bound is not taken from the refiner's saturated
output either: the sweep runs to ±1.2 s, ~1.8× the largest candidate offset, and **ROW 0c
fires if the winner reaches that edge**. The instrument is not being asked to bound its own
blind spot.

### 7.2 Method

No `src/` change. No Developer session. No ABI bump. No new DLL. No capture run. Pure
harness work, same shape as M2 — HK-011 not engaged.

- **Corpus:** `20260803_live_run_1713`, same 18.96 h window, same basis (`A∩B`, `<...>`
  excluded, 200–3000 Hz). Same DLL, pinned by **SHA256 `04cedc59…` / shim 20260041**,
  asserted at startup. Never by `FT8_SHIM_VERSION` alone.
- **Assert the `ALL.TXT` field mapping** against a hand-checked row before anything else:
  `[4]` SNR, `[5]` DT, `[6]` freq. Confusing 5/6 inverts this entire result.
- **Sweep:** time anchor only. `dt_offset ∈ {−1.20, −1.15, …, +1.20}` in 0.05 s steps =
  **49 points**. Step is below the refiner's own ±60 ms coarse aperture so the sweep cannot
  step over the peak. **Frequency anchor fixed at `df = 0`** — the frequency question is
  confounded until the time origin is right, and fixing it keeps the run cheap.
- **Winner:** argmax `out_sync_score` over the 49 calls, ties resolved per §5.1.
- **Record every call**, not just the winner: `(row_id, dt_offset, score, coarse_dt_samp,
  fine_dt_samp, delta_freq_hz)`. M2 could not answer "what does score look like across the
  sweep *within* a row" because only winners were stored. 49 × 1,800 ≈ 88k rows is nothing.
- **Population:** 100 HIT + 100 NULL per SNR stratum × 7 = 1,400 rows, subsampled from M1's
  committed manifest exactly as M2 did. **MISS is not run.** The effect being measured is
  large; this is not the arm that needs 300/stratum.
- **Positive control:** the existing 400-row control, unchanged, **for plumbing validity
  only** (§5.2). Its limitation is to be restated in the report.
- **Cost:** 1,800 rows × 49 calls × ~21.5 ms ≈ **32 min**. Cap 90 min. If breached,
  subsample rows — 🛑 **never trim the sweep grid.**

### 7.3 Gate — evaluate in strict order, first match wins

Primary statistic: **`dt_win`**, the winning `dt_offset`, per row.

- **ROW 0a — harness invalid.** Control median `dt_win` outside ±0.10 s, **or** control
  median `|coarse_dt_samp|` > 2 samples. The control's signal is at a known position in its
  own anchor's time base; if a ±1.2 s sweep cannot find it, the sweep machinery is broken.
  ⇒ Fix the harness, re-run. QA owns this outright.
- **ROW 0b — underpowered.** Fewer than 4 strata with ≥80 rows in **both** HIT and NULL.
  ⇒ Instrument failure, not a null. Escalate.
- **ROW 0c — sweep still binds.** More than **10%** of HIT rows win at `|dt_win| ≥ 1.20 s`.
  Bar is calibrated to the grid this time: 2 of 49 points ⇒ uniform-argmax floor 4.1%, so
  10% is 2.4× the no-information rate rather than a third of it. ⇒ The true origin is
  outside even this sweep. **Stop sweeping; bypass is the raw WAV spectrum.** Escalate.
- **ROW 0d — sweep artefact.** NULL median `dt_win` outside ±0.15 s. NULL has no signal;
  its winner must be uninformative. A systematic NULL pull means the sweep itself is
  directional (see §5.1). ⇒ Escalate.
- **ROW 1 — ANCHOR TIME-BASE CONFOUND CONFIRMED.** HIT median `dt_win` **≥ +0.30 s**, and
  **≥ 30%** of HIT rows have `dt_win` within ±0.10 s of that median (a mode, not a smear).
  ⇒ M1 and M2 are void as measurements of the refiner, as ruled in §3. The corrected anchor
  is `current + measured median offset`. **Next round re-asks M1's question at the corrected
  anchor.** R2 stays unscoped until it returns.
- **ROW 2 — NO CONFOUND.** |HIT median `dt_win`| **≤ 0.10 s** and no mode with ≥30% of rows
  outside ±0.10 s. ⇒ The anchor was right, §1–§3 of this ruling are wrong, M1 and M2 stand
  as written, and H1/H2 go back on the table as the live fork.
- **ROW 3 — partial.** Anything else: a mode present but below +0.30 s, or a diffuse
  distribution with no mode. ⇒ Escalate with the full `dt_win` distribution and the
  per-stratum breakdown. Do not average your way to a verdict.

**HK-025 classification, all four ROW 0s, written out:** each is a VALIDITY check — if it
fires, the primary statistic is not an estimate of "where is the true time origin" at all
(0a: the sweep cannot find a known position; 0b: no population; 0c: the answer is outside
the search; 0d: the search has its own direction). None is a PRECISION complaint. Both
branches of each evaluate to different rows with different actions, so none is diagnostic.
No refusal indicated. **QA re-runs this classification independently before arming and
refuses under HK-025 if it disagrees** — including with this paragraph.

### 7.4 Recorded, explicitly NOT gating

- **Post-correction concentration:** `|coarse_dt_samp|` at the winning anchor, HIT vs NULL,
  stratified. This is M1's question and it is **not** being answered here — M3 only locates
  the anchor. Record it; do not read it as a verdict. Re-asking M1 properly is the next
  round's job.
- **Frequency residual at the corrected anchor (§6):** `delta_freq_hz` and the fraction
  railed at the internal ±2.5 Hz aperture, HIT vs NULL vs control. M2 gives the
  pre-correction baseline: HIT 47.0% railed, NULL 42.2%, control 0.0%. If the −7 Hz mode is
  a by-product of time misalignment, HIT's rail fraction should collapse toward the
  control's. If it does not, that is a second defect and it gets its own round.
- **Per-call score profile** vs `dt_offset`, HIT and NULL, averaged within stratum. This is
  the direct readout of the thing M2 could only infer.

### 7.5 Scope limits

No `src/` change · no Developer session · no capture run · no MISS arm · no frequency sweep
· no re-reading M1 or M2 with a better metric (this is a **new** pre-registration, which is
the correct route) · no pedestal adjudication · no R2 proposal.

### 7.6 Architect's prediction

🛑 **Nothing gates on this.** Recorded for calibration, scored on the **consequence**, not
the interval.

- **P(ROW 1) ≈ 90%** — categorical, calibration 5/7.
- **HIT median `dt_win` = +0.60 to +0.70 s** — range, calibration 8/15. Derived from §2.1's
  measured 0.65 s gap on this exact corpus, not from the refiner.
- **P(the −7 Hz frequency mode largely disappears at the corrected anchor) ≈ 65%** —
  🛑 **DIRECTIONAL, calibration 1.5/3.5, my weakest class. Nothing may turn on it**, which
  is why §7.4 records it rather than gating it.

What would argue against me: §6. If the frequency mode is independent of the time anchor,
the single-cause story in §3 is incomplete even if ROW 1 fires.

## 8. Next action

**QA runs M3** (HK-025 refusal available on any row, this document included). R2 is not
scoped, not proposed, and not estimated until M3 returns and the corrected-anchor re-run of
M1's question returns after it.

**A2** (AC-4 still has no ROW 0) and **A3** (re-run D3 emitting slope + SE + p) remain open,
remain cheap, and still must not become a round. **A1 is done.**

---

*Per HK-014 nothing here is pushed or merged. Per HK-015 this is written for QA; `tasks.md`
and `dev-tasks/` are untouched, and QA authors the next spec, not me.*
