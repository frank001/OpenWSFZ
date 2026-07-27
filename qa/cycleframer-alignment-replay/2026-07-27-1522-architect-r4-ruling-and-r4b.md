# D-001: R.4 — ΔSNR corrected to 2.62 dB (out-of-band planting slot), the 6.3% conversion rejected, R.4b commissioned

**Author:** Architect, 2026-07-27 (15:22 UTC, `date -u`, per HK-017). **For:** QA (to run), and the
Captain (§9).
**Answers:** `2026-07-27-1510-qa-to-architect-r4-notification.md` §5 — both questions, in §7.
**Ruling: the arm is accepted with one correction and one rejection.** ΔSNR stands in direction but
not in value (§2). The dB-to-messages conversion (§3) must not be quoted to the Captain. R.4b (§4)
replaces it and is arithmetic on data already in hand.

---

## 1. Short answer

R.4's self-check passed and the jt9 plumbing is confirmed. But I audited the arm rather than only
reading its conclusion — the same posture I took on R.1, and for the same reason — and found two
things QA's own numbers contained but did not surface:

1. **A harness defect. All 20 high-SNR failures on our side are the same planted signal — slot 7,
   planted at 2945–3230 Hz, above our decoder's 3000 Hz search ceiling in 40 of 51 buffers.** Remove
   it and our plateau goes from 148/168 (88.1%) to **147/147 (100.0%)**, and **ΔSNR corrects from
   2.86 dB to 2.62 dB.** This is self-check number six in this thread.
2. **The dB-to-messages conversion rests on a step-threshold model that its own companion statistic
   falsifies.** "80.4% of misses sit at or above the threshold" is only sayable if the threshold is
   *not* a threshold. The 6.3% is a floor on the sensitivity contribution, not an estimate of it.

**QA's headline direction survives both.** Sensitivity is a minority contributor to row 4's gap.
That conclusion is robust, independently corroborated by C.3, and 2.62 dB falls just as far short of
jt9-depth-1's 55.4%/55.8% real-world coverage as 2.86 dB did. What does not survive is the specific
number 6.3%, and the invitation in QA's §2/§4 to read this as "row 4 is an indivisible commitment."

The routing decision was right. This is exactly the kind of result that should come back before it
reaches a summary.

## 2. The harness defect — slot 7 is planted outside our search band

The published `ours` curve plateaus at 87.5% from −14 to −20 dB while jt9 sits at 100.0% on
**byte-identical buffers**. A flat, SNR-independent 12.5% deficit is not a sensitivity phenomenon,
and it should have been read as a self-check signal rather than as curve shape.

Tracing it through the persisted artefacts:

| check | result |
|---|---|
| Plateau failures (≥ −20 dB), ours | 20 of 168 |
| Plateau failures, jt9, same buffers | **0 of 168** |
| Failures by slot-within-buffer | slots 0–6: **0/21 each**; slot 7: **20/21** |
| Slot 7 planted frequency range | **2945.1 – 3229.9 Hz**, 40 of 51 buffers above 3000 Hz |

The planting grid divides the band into 8 slots, and the top slot overruns our decoder's 200–3000 Hz
search range. We cannot decode a signal we do not look at. jt9's default range is wider, so it
decodes it, and the difference was being counted as sensitivity.

Recomputing both curves with slot 7 excluded:

| | plateau (≥ −20 dB) | 50% crossing | ΔSNR |
|---|---|---:|---:|
| As published | ours 148/168, jt9 168/168 | ours −21.50, jt9 −24.36 | 2.86 dB |
| **Slot 7 excluded** | **ours 147/147, jt9 147/147** | ours −21.75, jt9 −24.38 | **2.62 dB** |

**Two things follow, and the second matters more than the first.**

**ΔSNR was overstated by 0.24 dB.** Small, and it does not move the dB-to-messages counts (integer
SNR quantisation means 2.62 and 2.86 both land between the same whole-dB boundaries, so 50/120
stands unchanged even before §3's objection). The direction and magnitude of QA's conclusion are
untouched. **2.62 dB is the number of record; 2.86 dB should not be quoted again.**

**There is no structural decoder deficit — and I want that stated plainly, because it is the reading
this table invites and it is wrong.** A flat 12% deficit against jt9 on clean isolated signals would
have been the most decision-relevant finding in this study, and I went looking for it expecting to
find it. It is not there. **Once the out-of-band slot is removed, our decoder is 147/147 — a perfect
match for jt9 across the entire high-SNR plateau.** On isolated, clean, comfortable-SNR signals we
are exactly as good as jt9. Whatever row 4's gap is, it is not a broken demodulator on easy signals,
and this arm is now positive evidence for that rather than silent on it.

**Why the existing stop rule missed it.** The design's stop rule said "R.4's jt9 arm must reproduce
B.1's depth-1 behaviour on a shared buffer." It checked the *reference* decoder against a known
answer and left the *subject* decoder unchecked — so a defect that suppressed only our side passed
cleanly. That is a gap in my design, not in QA's execution.

**New stop rule, fixed now and applying to R.3 and anything else using these buffers:** every
planted signal must lie **wholly inside the intersection of both decoders' search bands**, asserted
at generation time (an FT8 signal occupies ~50 Hz above its base frequency, so the usable ceiling is
~2950 Hz, not 3000). Any arm comparing two decoders must state the band each one searched, and
**a flat SNR-independent offset between two decode curves is to be treated as a suspected harness
defect until excluded, never as curve shape.**

## 3. Why the 6.3% / 6.2% conversion is rejected

QA flagged the threshold definition as its own operational choice and asked me to rule on it
directly rather than accept it by default. **Ruling: it does not support the number built on it.**

The construction is:

- **threshold** := 5th percentile of the *hit* population's SNR — "the weakest signal we are
  empirically already handling."
- **recovered(x)** := count of misses whose SNR falls in `[threshold − x, threshold)`.

That second line is a **step model**: below the threshold we always fail, above it we always succeed,
so buying `x` dB sweeps up exactly the band `x` wide underneath it. But the finding reported in the
very next paragraph is that **80.4% of the misses sit at or above the threshold.** Under a step model
those messages cannot exist. The companion statistic falsifies the model used to compute the headline.

The threshold is a **minimum over successes** — the luckiest 5% tail of what we occasionally get
through — and comparing any population against a minimum-over-successes will nearly always return
"most of it is above." The claim is close to structurally guaranteed rather than measured. Decoding
is probabilistic: R.4's own `ours` curve falls 100% → 62.5% → 37.5% → 8.3% over four dB, so there is
a wide band where we succeed *sometimes*. A message sitting where we succeed 30% of the time is
squarely in our sensitivity shadow and is counted by this construction as being outside it.

**What the 6.3% actually is:** the count of missed messages in a narrow band below an arbitrary
reference point, under a model the data contradicts. It is a **floor** on the sensitivity-attributable
recovery — and necessarily a floor, since a soft curve shifted left by 2.62 dB helps everywhere it is
not already saturated, including above the threshold, where 80% of the misses are.

**It must not appear in a Captain-facing summary,** and I am ruling on that directly because QA asked
(§5, second question). Not because the direction is wrong — I think it is right — but because a
number that will be read as "sensitivity buys us 6%" is precise, memorable, load-bearing for a
decision, and unsupported by its own construction.

## 4. R.4b — the real-corpus decode-probability curve

**Per HK-004, I checked whether I could just do this rather than commission it.** The persisted
artefacts (`db_to_messages_corpus*.json`) carry only the derived curve, not the per-message SNR
values, so I cannot. QA has the raw values — the distributions in findings §3 were computed directly
for this arm. **This is arithmetic on data already in hand: no decode wall-time, no capture, no
rebuild, no synthetic generation.**

**Method.** For each corpus, bin every WSJT-X-decoded message by its reported SNR (whole dB — the
native resolution; no half-dB steps, per findings §6) and compute

> **P(we also decoded it | SNR bin) = hits(bin) / (hits(bin) + misses(bin))**

This is our decoder's real-world sensitivity curve measured against WSJT-X as reference, on real
traffic. It needs no synthetic-to-real conversion, which means **it is the one instrument in this
study that does not inherit the CPFSK-vs-GFSK caveat** — the caveat findings §6 correctly identifies
as most exposed exactly here.

**Three deliverables:**

1. **The curve itself**, per corpus, with Wilson intervals and bin counts; never collapsed across
   corpora.
2. **The high-SNR asymptote** — P at the strong end, where sensitivity cannot be the explanation.
   This is the number that partitions the miss population into "sensitivity-shaped" and "structural"
   with no modelling assumption at all, and **as far as I can tell nobody in this study has computed
   it.** I think it is the most decision-relevant single number still outstanding.
3. **A shift-model recovery estimate**: how many current misses would be recovered by shifting the
   measured curve left by **2.62 dB** (§2's corrected value). This is the honest replacement for
   §3's 6.3%, and it should be reported *with* the step-model floor beside it so the two are
   comparable and the difference between them is visible.

**Reading rule, fixed now, before the numbers exist:**

| result | reading |
|---|---|
| P saturates (≥ ~95%) above the threshold region | Misses above threshold are genuinely structural. **QA's conclusion is confirmed and strengthened**, ~6% becomes approximately right for the sensitivity component, and the structural remainder is quantified as the rest. R.3 must attribute it. |
| P stays materially below saturation across a broad SNR band | Our loss is broad-spectrum and probabilistic. The step model **understates** the shift benefit; the shift-model number replaces 6.3% as the sensitivity contribution, and it may be materially larger. |
| P is high in sparse cycles and depressed in dense ones at the same SNR | **Co-channel/collision is the driver.** Row 4's target is co-channel handling — which Arm A structurally cannot see and R.3's isolated geometry cannot see either. This is the branch that would demand an Arm B arm, and it is the branch I would bet on given C.3. |

The third row is worth the split by cycle density even though it costs a little more, because it is
the only cheap route to the co-channel hypothesis that findings §6 names as the likeliest candidate
for "the other 93%" and that no arm in the study currently tests.

**Cost:** well under a session; a group-by on data already collected.

## 5. What survives, and what I am not disturbing

**Survives, robustly:** sensitivity is a minority contributor to row 4's gap. Two independent
instruments now say so — C.3's proximity proxy and R.4's ΔSNR — and QA's §3.1 observation that two
independent routes landing in the same place is stronger than either alone is correct and is the
most valuable line in the notification. **A 2.62 dB pure-sensitivity edge cannot explain
jt9-depth-1's 55.4%/55.8% real-world miss coverage.** That is the finding.

**Untouched:** C.4's +2, B.2's E = 5.69, C.3's SNR split, B.1/B.1b's 437, R.1's withdrawal of
"anti-correlation". **The 437 has still never moved** — QA's §4 is right and I want it on the record
that this is now the fifth consecutive arm to leave it standing.

**Not disturbing:** the ΔSNR method, the grid, the Wilson treatment, the buffer persistence, or the
jt9-depth-1 scope. All correct as designed and executed.

## 6. R.3 — one further amendment

R.3 as amended at 14:44 stands. One addition, arising from §2:

**R.3 must report which planted signals fail, not only how many** — by slot, by frequency, by
message — and its self-check must assert the band constraint from §2 before any classification is
read. The whole of §2's finding was recoverable in about four minutes from persisted artefacts, but
only because the artefacts kept per-signal rows. That property is what made this arm auditable, it
was QA's own good judgement to persist it, and R.3 should preserve it deliberately rather than by
luck.

The `MaxPass0Candidates` cap axis, the SNR axis, the tolerance ladder, and the D-miss / X-loss /
E-cand classes are all unchanged.

## 7. QA's two questions, answered directly

**Q1 — should R.3 be amended to read a dominant D-miss class against a structural-cause prior?**
**No.** Do not install a prior. R.3's value is that it is the one arm with ground truth and no
matcher; loading it with an expectation is how a reading rule goes wrong, which is precisely what
happened to R.1b's row 2 and cost us a ruling. R.3 as amended already distinguishes the mechanisms —
the cap axis separates ranking/capacity from sensitivity, and the SNR axis separates sensitivity
from structure. **What §3's argument correctly implies is not a prior on R.3 but that R.4b should
run first**, because it measures on real traffic what a prior would otherwise be assumed about. §8
sequences it accordingly.

**Q2 — does the "small in absolute terms" framing belong in a Captain-facing summary?**
**The framing yes, the number no.** "A cleanly measured 2.62 dB sensitivity edge cannot account for
jt9's real-world advantage; most of the gap is something else" is exactly right, is the arm's real
contribution, and is more useful than the design's own two-row table anticipated — QA is right that
the table lacked language for it. But it must be carried by the *comparison* (2.62 dB vs 55.4%/55.8%
coverage), which is robust, and not by the 6.3%, which is not. After R.4b, the sentence can be
quantified properly.

**And one correction to the reading QA applied.** The design's row — "row 4 is an indivisible
commitment; price it against row 5 in full" — was written for a curve that stays flat *because
sensitivity is the mechanism and it must be bought whole*. That is not what happened. The curve is
small because sensitivity is **the wrong axis**, which is a different result and does not license the
"indivisible" conclusion. "Not sensitivity" is not "not decomposable" — and §2's 147/147 says our
demodulator is fine on clean signals, which points at something *more* localised than a rewrite, not
less. **This row should not be applied. It is not evidence for row 5 over row 4, and it must not be
carried into the menu as such.**

## 8. Sequencing

**R.1 ✅ → R.1b ✅ → R.4 ✅ → R.4b → R.3 (amended) → R.2 (only if E-cand is populated).**

R.4b goes ahead of R.3 because it is cheaper by an order of magnitude, it is arithmetic rather than
decode wall-time, it measures on real traffic what R.3 measures synthetically, and its co-channel
branch (§4, row 3) may change what R.3 should be looking for. R.3's buffers are persisted and
waiting; nothing is lost by the reordering.

## 9. What the Captain should take from this

- **ΔSNR = 2.62 dB** (corrected). **The 437 is unmoved**, five arms running.
- **Sensitivity is a minority contributor to row 4's gap** — now two independent instruments, and
  this is the durable finding.
- **Our decoder matches jt9 exactly (147/147) on clean isolated signals at comfortable SNR.** Row 4's
  problem is not a broken demodulator.
- **Do not accept "row 4 is indivisible" from this arm** (§7). The evidence points the other way, if
  anything: a specific missing capability rather than a rewrite.
- **The 6.3% figure is withdrawn** before it reached you. R.4b replaces it and costs well under a
  session.
- The row-4 *mechanism* narrative has been revised repeatedly and my characterisations of it have
  earned discounting; the *quantity* the decision rests on has never moved. If you want to call the
  decision before R.4b/R.3 report, the honest summary is the first three bullets.

## 10. What this does not authorise or settle

- **No native or `src/` change** (HK-011). R.4b is offline arithmetic on collected data.
- **No push, no merge** (HK-014). **No `pre_merge_check.py`** (HK-006 — Captain's trigger).
- **Row 5 untouched**; rows 2 and 3 stay sequenced behind row 4.
- **The `libft8.dll` size question and this branch's disposition** remain open and blocking on the
  Captain. My ruling on the size delta is still owed and is still not here — that is now three notes
  running, and I am flagging it as overdue rather than letting it lapse quietly.
- **The `MaxPass0Candidates` guard** remains owed, and remains QA's to author.
- **NFR-021:** R.4b reports aggregates and counts only; it touches real callsigns solely inside
  git-ignored `artefacts/`.
- **Per HK-015 this is a design, not a task.** `dev-tasks/` and `tasks.md` are QA's to author.

## 11. Honest caveats

- **§2's recomputation is mine, from QA's persisted artefacts, not an independent re-run.** It is a
  regrouping of the same 408 measurements and QA should confirm it against the generator before
  2.62 dB is treated as final — in particular whether the 11 buffers with slot 7 *below* 3000 Hz
  should also be excluded, since a signal based at 2990 Hz still occupies spectrum to ~3040 Hz and is
  partially outside the band. I excluded slot 7 wholesale; the alternative is a per-buffer band test,
  which would move the number slightly again.
- **2.62 dB remains jt9 at depth 1** — a floor on its advantage, not a ceiling. Unchanged from
  findings §2, and it is the right scope for comparability with B.1.
- **CPFSK vs GFSK** carries forward for ΔSNR itself. R.4b is the first arm in this study that escapes
  it, which is much of why it is worth running.
- **I designed the stop rule that missed §2's defect**, and I am now writing its replacement. Same
  partial mitigation as every prior note: §4's reading rule is fixed before the numbers exist.
- **Six self-corrections have now been caught mid-flight** — B.1's anchor drift, B.2's clipping,
  C.4's `MaxPass0Candidates` truncation, R.1's tolerance, R.1b's reading rule, and now R.4's planting
  band. Five of the six were mine. The rate is not falling and I do not think it should be assumed to.

## 12. Cross-references

- `2026-07-27-1510-qa-to-architect-r4-notification.md` — the notification this answers; §5's two
  questions are answered in §7.
- `2026-07-27-r4-sensitivity-gap-findings.md` — the result. §2's ΔSNR **corrected to 2.62 dB**; §3's
  dB-to-messages conversion and §4's reading **rejected**, per §2/§3/§7 above. Self-check, method,
  grid, and §5's "does not settle" all stand.
- `2026-07-27-r4-sensitivity-gap-task-spec.md` §2.3 — the threshold definition, ruled on in §3.
- `2026-07-27-1444-architect-r1b-ruling-and-r3-amendment.md` §6, §7 — R.3's amended axis, extended by
  §6 above; sequencing superseded by §8.
- `2026-07-27-1730-architect-row4-scoping-design.md` §4 — R.4's design; its reading table's row is
  **not applied**, per §7.
- `2026-07-26-b1-jt9-ablation-findings.md`, `2026-07-27-b1b-second-corpus-findings.md` — the
  55.4%/55.8% depth-1 coverage that 2.62 dB falls short of.
- `2026-07-26-c3-candidate-generation-gap-findings.md` — the proximity/SIC proxy this corroborates.
- `artefacts/d001_r4_sensitivity_gap/{measurements,manifest,curves}.json` — the per-signal rows §2's
  audit rests on.

---

*Per HK-015 this is Architect → QA material: R.4b and the extended R.3 are a design for QA to scope
and author, not tasks issued by me. Per HK-014 this note is committed locally and goes no further.
Per HK-011 nothing here touches `src/` or native code. The decision the study feeds — row 4 vs.
row 5 — remains the Captain's, on the Captain's clock.*
