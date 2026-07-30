# D-001: Architect → QA — ruling on the cross-band corpus + capture-chain findings
# Two measurements authorised by the Captain. One new defect raised as a separate item.

**Author:** Architect, 2026-07-30 (22:53 UTC, `date -u`, per HK-017).
**REVISED 2026-07-30 23:15 UTC — see §R below. One ruling of mine is withdrawn.**
**For:** QA (§5, §6, §6b, §7 are actionable), and the Captain (§0, §4, §8).
**Answers:** `2026-07-30-2221-qa-to-architect-capture-chain-and-cross-band-findings.md`.
**Additive to:** `2026-07-27-2012-architect-to-qa-d001-closing-handoff.md`, which remains the
standing reference for programme state and stop rules. **Supersedes nothing.**
**Authorisation:** the closing handoff §0 reserves re-opening the diagnostic programme to the
Captain. The two measurements in §5 and §6 were **put to the Captain and explicitly authorised**
in this session, with cost estimates, before being written down as tasks. They are not
Architect-initiated arms. §7 is raised as a **separate item outside D-001**, on the Captain's
direction.

> **A note on the date.** This document is timestamped 2026-07-30 UTC, not 2026-07-31. Local
> time was 00:53 CEST on the 31st; `date -u` is 22:53 on the 30th, and `git log` for the QA
> note this answers reads `2026-07-31T00:24:32+02:00` = 22:24 UTC on the 30th. HK-017 requires
> UTC, mechanically derived. Filename and byline agree.

---

## R. Revision record — 2026-07-30 23:15 UTC

The Captain asked whether cross-decoding the two recorders' WAVs (jt9 on ours, our decoder on
WSJT-X's) would add insight. Validating that the two sets were comparable **found a critical
capture defect**, now raised separately as
[`DEFECT-capture-clock-drift-silent-decode-loss.md`](../../DEFECT-capture-clock-drift-silent-decode-loss.md).

**In short:** OpenWSFZ's capture window drifts ~45–49 ppm against UTC on the physical-radio
device (not on the virtual-audio device), and once accumulated drift passes ~2.4 s — about 13
hours in — decoding collapses to ~2% of the reference, silently, with the heartbeat still
reporting `dataFlowing=true` and zero `WRN`/`ERR`/`FTL` in the log.

| section | change |
|---|---|
| **§3.2** | **WITHDRAWN — my ruling, and it was wrong.** I attributed the 40m corpus's shortfall to reference method. The real cause is that half that session was broken |
| **§3.1** | Density law **reduced from four points to three.** The cross-instance claim is withdrawn — the fourth corpus is on the drifting device |
| **§4** | QA's capture-chain sample is **confounded** — it sits at 2.34 s of drift, at the cliff edge |
| **§6** | Measurement B **redesigned** around drift stratification; it was invalid as written |
| **§6b** | **NEW** — the re-alignment experiment, which settles the drift question offline |
| **§8, §9** | Updated; the 49.9% figure is struck entirely |

§1, §2, §5 and §7 stand unchanged.

**How this was caught matters procedurally.** It was not caught by a test, a gate, or a
supervisor — all of which reported healthy. It was caught by checking whether two files were
actually comparable before comparing them, which is HK-018's rule doing exactly its job. The
same check also caught two errors of my own in the same hour (a wrong log-timestamp timezone
assumption, and a lag-convention I validated against a synthetic control before trusting).

## 0. Summary — the one thing to read if you read nothing else

QA's numbers all reproduce exactly. **Re-cutting the same data changes three conclusions.**

0. **A critical capture defect was found while validating this ruling** (§R). It invalidates one
   of the corpora outright, confounds QA's §3, and reverses one of my own conclusions below.
   Read `DEFECT-capture-clock-drift-silent-decode-loss.md` first — it matters more than anything
   else in this document.
1. **§1's cross-band finding is real and stronger than QA presented**, on the three corpora that
   survive §R. Holding the *reference method* constant, they obey
   `parity ≈ 112 − 37.6·log₁₀(decode density)` — monotone across a full decade of density
   (3.4 → 36.4 decodes/cycle) and three bands. The fourth point sat on that line too, but it
   comes from the drifting device and must be recomputed before it can be counted (§3.1).
2. **§3's capture-chain effect is not established** — it is ~1.5σ (p ≈ 0.12), and the argument
   offered for the two effects being non-confounding is **circular algebra** that would come out
   "exactly" for any four numbers. QA's conclusion may well be right; the evidence given does not
   support it yet.
3. **A previously undocumented defect:** OpenWSFZ's reported SNR carries a **gain error**, not an
   offset — `ours ≈ 0.58 × reference − 4.3 dB`, confirmed at per-decode level. D-002 "fixed" SNR
   bias in June with a *constant*; a constant cannot correct a slope. Raised separately per §7.

**The consequence that matters for the menu** is not diagnostic. If parity is a near-deterministic
function of band occupancy, **NFR-018's shape is wrong** — a single global "≥ 80% parity"
threshold is partly a statement about operating conditions, not about the decoder (§8).

---

## 1. What I actually checked, and how

Per HK-018 — and because the closing handoff §10 records two withdrawn Architect rulings that a
five-minute measurement would have caught, with the explicit note that *"this rule is not aimed at
QA"* — I opened the underlying data rather than reasoning from QA's summary.

| check | method | result |
|---|---|---|
| QA's parity figures | recomputed from the four committed `anova_report_*.md` decode counts | **all four reproduce exactly** |
| QA's DT deltas (§2) | recomputed from published appraiser means | **all four reproduce to 3 dp** |
| QA's §3 2×2 | re-derived interaction and significance | **conclusions do not follow from the stated evidence** (§4) |
| decode density | derived from `WAV cycles fed to jt9` per report | monotone with parity; see §3 |
| SNR agreement | corpus-mean regression, then the committed per-decode scatter PNG | **gain error confirmed visually** (§7) |
| Is the SNR→suppression hypothesis new? | read `ft8_shim.c` change history | **No — already tested and rejected as H5.** See §7.3 |
| Can the measurements be run cheaply? | counted matched WAVs; timed `jt9` directly | **yes** — §5 needs no decoding; §6 measured at 2.66 s/WAV |

The last two rows are the point of the exercise. One killed a hypothesis of mine before it reached
this document; the other turned two cost estimates into measurements.

## 2. Rulings on QA's five recommendations

| QA rec | ruling | why |
|---|---|---|
| **1** — fold the capture-chain effect into the row 4 decomposition as "small, real, measured" | **Not accepted as written.** Defer pending §6 | ~1.5σ is not "real". Embedding it now is how the closing handoff §6 acquires a tenth withdrawn number |
| **2** — re-weigh the withdrawn co-channel/density mechanism | **Accepted, with a caution QA did not raise** (§3.3) | the withdrawal did rest on a low-power test. But density ≠ co-channel; there is an equally good rival explanation, and §5 separates them |
| **3** — present 64.1%/789 as one sample from a 49.9%–91.6% distribution | **Accepted in substance; my correction to it was itself wrong** (§3.2, withdrawn at §R) | the range is **53.2%–91.6% on three clean corpora**. 49.9% is struck — not a reference-method artefact as I claimed, but a broken session (§R) |
| **4** — dev-task correcting the D6 comment | **Accepted, with an addition** (§7.4) | don't just delete it — record the measurement and its date, or the next engineer re-assumes it |
| **5** — do not chase the resample question | **Accepted, and reinforced** | §6 must establish the effect *exists* before anything is spent on why. QA had these backwards — rec 1 folds in a number that rec 5 forbids validating |

## 3. The density law — §1 restated properly

### 3.1 The finding QA under-sold

QA reported a 49.9%–91.6% spread "tracking density," and set the two 40m corpora aside as not
apples-to-apples. That framing hides the result. Holding the **reference method** constant
(jt9 re-decode), all four jt9-referenced corpora fall on one line:

| corpus | band | capture instance | ref decodes/cycle | parity | status |
|---|---|---|---:|---:|---|
| `2026-07-29-5016363` 80m | 80m | SDR Uno / Voicemeeter | 3.38 | 91.6% | **clean** — no drift |
| `2026-07-29-5016363` 10m | 10m | SDR Uno / Voicemeeter | 8.52 | 77.7% | **clean** — no drift |
| `2026-07-29-5016363` 20m | 20m | SDR Uno / Voicemeeter | 36.36 | 53.2% | **clean** — no drift |
| ~~`2026-07-29-489135a` 40m~~ | 40m | **USB Audio CODEC** | 19.81 | ~~62.4%~~ | **SUSPENDED** — drifting device (§R) |

```
parity(%) ≈ 111.9 − 37.63 · log₁₀(reference decodes per cycle)
```

The three surviving points are **monotone across a full decade of density** and span four-fold
in parity. That relationship is the finding, and it is unaffected by the defect: all three come
from the Voicemeeter instance, which §R's evidence shows does not drift at all.

**What §R took away, stated plainly:**

- **The cross-instance claim is withdrawn.** I wrote that two different capture chains obey the
  same law, and treated that as the study's first quantitative bound on the closing handoff
  §2.3 capture-chain candidate. The fourth corpus is on the **drifting** device and its 62.4%
  is depressed by an unknown amount over its final hours. It fell on the line, but that may be
  coincidence. **It must be recomputed on its drift-free window before it counts** — QA task in §6b.
- **Three points, two fitted parameters, one degree of freedom.** I am not quoting R² for a
  three-point fit; it would be meaningless. Monotone across a decade is the honest claim, and it
  is enough to motivate Measurement A — which is where the mechanism actually gets decided.

### 3.2 ~~The 49.9% outlier is a reference-method artefact~~ — **WITHDRAWN**

> **This section was wrong and is withdrawn in full.** I argued that the 40m corpus's 49.9%
> parity sat 13.7 points below trend because it used a live-WSJT-X reference rather than a jt9
> re-decode, and I proposed a citation rule on that basis. **That explanation is false.**
>
> The actual cause is the capture clock drift (§R). That corpus ran 25 hours: roughly 13 hours
> at ~65% parity, then a collapse to ~2% for the remaining 12. **49.9% is the average of a
> working application and a broken one.** It is not a parity measurement, not a reference-method
> artefact, and not a data point of any kind.
>
> **What I should have done:** the hourly breakdown that revealed this is a five-line
> computation over two `ALL.TXT` files that were already on disk. I reasoned about a
> between-corpus difference instead of opening the within-corpus time series. That is precisely
> the failure HK-018 exists to prevent, and the closing handoff §10 singles out as *"not aimed
> at QA."* Third such ruling in this thread; this one at least was caught before it propagated
> into the row 4 decomposition.

**What replaces it.** The 49.9% figure is struck entirely (§9). QA's rec 3 — *"present 64.1% as
one sample from a wide distribution"* — still stands, but the distribution is
**53.2%–91.6% on three clean corpora**, not 49.9%–91.6% on five.

The reference-method question I raised is **not resolved either way** — it is simply unevidenced,
because the only corpus that could have tested it is invalid. Whether a live-WSJT-X reference and
a jt9 re-decode give materially different parity on the *same* audio remains open, and
Measurement C (§6b) would answer it as a free by-product.

**Citation rule that does survive, and is worth keeping:** state the reference method with every
parity number. It was good practice for a bad reason.

### 3.3 Why this does *not* yet revive the co-channel mechanism — the caution QA missed

QA is right that the withdrawal rested on a low-power test (in-corpus density proxy, p90/p10 ≈
1.6–1.8, under 0.3 decades) and that this is ~1.03 decades at R² = 0.9985. That is a genuine power
difference and QA was right to flag it rather than let the withdrawal stand unexamined.

**But "parity falls with density" does not imply co-channel collision.** There is an equally good
rival explanation already on record:

> **Pure sensitivity acting through the SNR mix.** Denser bands carry proportionally more marginal
> signals. A decoder with a fixed 2.62 dB sensitivity deficit (R.4, measured) will miss a larger
> *fraction* of a population whose SNR distribution sits lower — with no signal-on-signal
> interaction anywhere in the mechanism.

The marginal correlation in §3.1 cannot distinguish these. They make **different predictions under
stratification**, which is what §5 measures. Until §5 runs, the honest position is: *the withdrawal
was under-powered and is no longer safe to rely on, and the replacement mechanism is not yet
identified.*

## 4. §3's capture-chain effect — three problems

> **Added at revision (§R): the sample is confounded, which subsumes both problems below.**
> QA's 30 cycles run `260730_064015` → `260730_064730`. Cross-correlation measures the drift at
> that instant as **−2.342 s** — hour 12 of the session, immediately before the cliff at
> −2.48 s. The two WAVs QA compared are **not recordings of the same instant**; they are offset
> by 2.34 s and overlap by only ~84%.
>
> So §3's headline — *"WSJT-X's own recording of a given instant is measurably easier to decode
> than OpenWSFZ's recording of the identical instant"* — is not describing audio quality. The
> most likely reading is that our window was truncating signals WSJT-X captured whole. **The
> +12.5% is a plausible measurement of the drift, not of the capture chain.**
>
> This also retires QA's §5 framing: the resample algorithm was never the remaining candidate,
> because the effect it was invoked to explain has a much simpler available cause. §4.1 and §4.2
> below still stand on their own terms and are retained — the reasoning errors are real
> independent of the confound.

### 4.1 The "multiplicative combination" argument is circular

QA writes:

> *"The two effects combine close to multiplicatively, not confounding one another: 1.125 × 1.478
> ≈ 1.663, against the observed combined ratio 544/327 = 1.663 exactly."*

With the 2×2 labelled `a` = ours/our-WAV = 327, `b` = ours/WSJT-X-WAV = 368, `c` = jt9/our-WAV =
495, `d` = jt9/WSJT-X-WAV = 544, QA has computed `(b/a) × (d/b)` and compared it to `d/a`. Those
are **algebraically identical for any four numbers whatsoever.** The "exactly" is guaranteed by
arithmetic and carries no information about the data.

The real test is the interaction term:

```
interaction = ad/bc = (327 × 544)/(368 × 495) = 0.9765    → −2.3% departure from multiplicativity
SE(log interaction), independent-Poisson              = ±9.8%
```

So: **no detectable interaction, but the data cannot distinguish multiplicative from additive** —
the measurement is nowhere near precise enough to make that call. QA's conclusion is not
contradicted; it is simply unevidenced. Per the closing handoff §6 discipline, the stated
demonstration should not be cited again (§9).

### 4.2 The effect itself is ~1.5σ

| comparison | ratio | SE(log) | z | p (nominal) |
|---|---:|---:|---:|---:|
| WSJT-X WAV vs our WAV, **our decoder** (368 v 327) | 1.125 (+12.5%) | 0.076 | **1.55** | ≈ 0.12 |
| WSJT-X WAV vs our WAV, **jt9** (544 v 495) | 1.099 (+9.9%) | 0.062 | **1.52** | ≈ 0.13 |

Two further points make this **weaker** than the table suggests, not stronger:

- **The two rows are not independent confirmation.** They run on the same 30 cycles of audio. Two
  correlated 1.5σ results in the same direction are close to one 1.5σ result.
- **The SEs are anti-conservative.** Decodes within a cycle are not independent draws; the true
  standard errors are wider than independent-Poisson.

QA's caveat — *"not enough to pin the percentages down precisely"* — undersells this. The correct
statement is that **the effect is not yet distinguishable from zero.** Direction has replicated
weakly; magnitude has not been established at all.

This is why rec 1 is deferred rather than rejected: the point estimate may be perfectly correct.
It just has not been measured yet, and §6 measures it cheaply.

## 5. MEASUREMENT A — SNR-stratified recall ⟨authorised by the Captain⟩

**Purpose:** separate the two rival explanations of §3's density law. This is the decisive
discriminator, and it needs **no new data collection and no decoding.**

### 5.1 Why it is nearly free

Every input is already committed to `artefacts/`, with SNR present in every row:

| file | rows | role |
|---|---:|---|
| `20260729_live_run_1831-8081/owsfz/{10m,20m,80m}/jt9_ALL.TXT` | 12 701 / 49 527 / 9 845 | reference decodes, 3 bands |
| `20260729_live_run_1831-8081/owsfz/{10m,20m,80m}/ALL.TXT` | — | our decodes, same 3 bands |
| `20260729_live_run_1831-8080/wsjt-x/ALL.TXT` | 110 232 | reference decodes, 40m |
| `20260729_live_run_1831-8080/owsfz/ALL.TXT` | 55 027 | our decodes, 40m |

Line counts match the published ANOVA reports exactly. **Measured parse time: 0.06 s for the
49 527-row file.** Total compute for all four corpora is under a second.

> **Note:** the 40m/489135a corpus (the point that lands dead on the trend at 19.81/cyc) did
> **not** retain its `jt9_ALL.TXT` and cannot be included without re-decoding 3 575 cycles
> (≈ 2.6 h at measured throughput). **Do not re-decode it for this measurement.** Three
> jt9-referenced bands spanning 3.4 → 36.4 decodes/cycle is a full decade and is sufficient.

### 5.2 Design

For each corpus, using **`anova_common.py`'s existing normalisation and matching logic — reused,
not reimplemented**:

1. Take the reference decoder's full decode list.
2. Bin by **reference-reported SNR**, 2 dB bins.
3. Per bin, compute **recall** = fraction of reference decodes that OpenWSFZ also found
   (same cycle + normalised message), with Wilson intervals.
4. Overlay the three jt9-referenced bands (3.4 / 8.5 / 36.4 decodes per cycle) on one axis.
   Plot the 40m live-WSJT-X corpus as a **separate series**, never pooled with the jt9 ones (§3.2).

**Mandatory self-check before any reading is taken:** total matched count per corpus must
reproduce the published ANOVA figure exactly (20m = 24 201, 10m = 9 177, 80m = 8 290,
40m = 52 736). If it does not, the matching logic has drifted and the run is void.

### 5.3 Reading rule — **pre-registered, fixed before the run**

Let `R_b(s)` be recall for band `b` at reference SNR `s`. Compare the three jt9-referenced bands
over their region of common SNR support.

| outcome | reading | consequence |
|---|---|---|
| **Curves overlay** (band separation < 5 pts across the common region) | Density is a *marginal artefact* of differing SNR mixes. Recall is a function of SNR alone. | **Pure sensitivity. The co-channel withdrawal STANDS.** §3.1's law is real but explained; row 4's target is sensitivity/front-end, unchanged. |
| **Dense bands sit materially below sparse at matched SNR** (≥ 10 pts, monotone in density) | At the *same* signal strength we miss more when the band is busier. That is competition, not sensitivity. | **The co-channel withdrawal REVERSES.** This becomes a named, measured mechanism and materially re-scopes row 4. Escalate to the Captain before any further work. |
| **Separation 5–10 pts, or non-monotone in density** | Partial/ambiguous. | Report as ambiguous. **Do not interpret further.** Escalation, not interpretation. |
| **Curves cross** (sparse below dense at some SNRs) | Not anticipated by any current model. | Escalation. Do not rationalise it in the findings document. |

No other reading is authorised. Per the closing handoff §4.3's template, this rule is fixed **now,
in advance**, and must be quoted verbatim in the task spec before the run.

### 5.4 Cost

| item | estimate | basis |
|---|---|---|
| compute | **< 5 seconds** | measured (0.06 s per 50k rows) |
| script + plots + report | **1–2 h** of QA session time | ~100 lines reusing `anova_common.py`, four overlay plots, findings doc |
| **total** | **half a QA session** | dominated entirely by writing, not running |

## 6. MEASUREMENT B — capture-chain replication at n = 300 ⟨authorised by the Captain⟩

**Purpose:** establish or refute §3's ~10–13% capture-chain effect, which is currently ~1.5σ.

### 6.1 The material exists

I counted the matched pairs directly in `artefacts/20260729_live_run_1831-8080`:

```
OpenWSFZ WAV stems : 5 795
WSJT-X   WAV stems : 5 783
MATCHED (both recorders captured the same instant) : 5 782
span : 260729_183130 → 260730_183945   (~24 h continuous)
```

**QA used 30 of 5 782 — 0.52%** — in one contiguous 7.5-minute window starting at matched-cycle
index 2 908. The remaining 99.5% is sitting on disk, already matched, already git-ignored.

> The single-window design is arguably a bigger weakness than n itself: 7.5 minutes is **one**
> propagation condition, one noise environment, one point in the diurnal cycle. Stratifying
> across the full 24 h fixes both problems at once.

### 6.2 Design — **REVISED at §R. The original design was invalid.**

> **What changed and why.** The original design sampled every 19th cycle across the full 24 h,
> to spread across propagation conditions. **That is now the worst possible sampling**: it would
> have drawn roughly half its cycles from the post-collapse window where we decode ~2%, and
> pooled them with healthy ones. It would have produced a large, confident, and entirely
> spurious "capture-chain effect" — a far worse outcome than QA's underpowered n=30.
>
> Stratify by **measured drift**, not by time.

- **Measure drift per sampled cycle first**, by cross-correlating the two WAVs (the procedure in
  the defect report §2.1; validate the lag convention against a synthetic control before
  trusting it).
- **Primary arm — the clean estimate.** Sample **n = 300** from cycles with
  **|drift| < 0.5 s** only. On this session that is roughly the first 2 hours, so a wider
  sample may need a second session or the 489135a corpus's early hours. **This is the only arm
  that measures the capture chain**, because it is the only one where the two recordings are of
  substantially the same audio.
- **Secondary arm — the dose–response, and the more valuable output.** Sample ~50 cycles at each
  of ~8 drift levels spanning 0 → 4.4 s. This yields the decoder's **DT tolerance curve** as a
  measured constant. §2.3 of the defect report brackets the cliff at 2.34–2.48 s from decode
  counts alone; this would resolve it properly, for both decoders, and the project needs that
  number regardless of D-001.
- **Sampling within a stratum:** fixed stride, not random — reproducible.
- **Arms:** unchanged from QA's — the same 2×2 (our WAV / WSJT-X WAV) × (our decoder / jt9),
  `jt9 -8 -d 3`, our decoder at baseline grid point `k10_c0.10_n60` via
  `qa/rr-study/d001-param-sweep-2026-07-22/`. Confirm again that `src/` is unchanged versus the
  live run's build before trusting decoder-identity.
- **Analysis — this is a change from QA's method.** Report the pooled 2×2 for comparability, but
  the **primary test must be paired per-cycle** (Wilcoxon signed-rank on per-cycle decode counts,
  or McNemar on per-message concordance). Pooled ratios ignore intra-cycle correlation and
  overstate significance; the paired test both handles it correctly and has more power.
- Report the interaction term `ad/bc` with its CI. **Do not repeat the `(b/a)×(d/b)` identity** (§4.1).

### 6.3 Reading rule — **pre-registered, fixed before the run**

**Applies to the primary (|drift| < 0.5 s) arm only.** Any capture-chain conclusion drawn from
pooled or drifted cycles is void, however tight its confidence interval looks. The secondary arm
is descriptive — it reports the tolerance curve and is not subject to this rule.

| outcome | reading | consequence |
|---|---|---|
| **Effect confirmed**, paired test p < 0.01, direction as in §3 | The capture chain really does cost us decodes. | Folds into the row 4 decomposition **with its measured magnitude and CI** — this is what rec 1 wanted and could not yet have. Only *then* does the resample question become worth pricing. |
| **Effect refuted**, CI comfortably spans zero | n=30 was noise. | **Drop it.** Strike §3's percentages from the record per §9. The resample question dies with it. |
| **Ambiguous** (0.01 ≤ p < 0.05, or CI includes zero but point estimate holds) | Underpowered even at n=300 → the effect is smaller than 10–13%. | Report as bounded-small. **Do not escalate n further** — an effect needing n > 300 to see is not row-4-relevant. |

### 6.4 Cost — **measured, not estimated**

I timed `jt9 -8 -d 3` directly on this machine's WAVs: **2.66 s per WAV** in steady state
(13.31 s for 5 files, after FFTW warm-up).

| n | jt9 decodes (2 sources) | jt9 wall-clock | nominal z if effect is +12.5% | verdict |
|---:|---:|---:|---:|---|
| 30 *(QA's run)* | 60 | 3 min | **1.55** | inconclusive |
| 100 | 200 | **9 min** | 2.84 | marginal — would likely not survive the paired correction |
| 200 | 400 | **18 min** | 4.01 | decisive |
| **300 (recommended)** | **600** | **27 min** | **4.92** | **decisive, with margin** |
| 500 | 1 000 | 44 min | 6.35 | past diminishing returns |

**n = 300 is the recommendation.** It leaves comfortable margin for the paired correction (which
will lower the effective z below these nominal figures), and the marginal cost over n = 200 is
nine minutes.

| item | estimate | basis |
|---|---|---|
| jt9 arms (600 decodes) | **27 min** | **measured** at 2.66 s/WAV |
| our-decoder arms (600 cycles) | **10–20 min** | *estimated* — in-process, no per-file process spawn, so materially faster than jt9; includes one harness build |
| harness changes (stride sampling, paired test) | 1–1.5 h | QA session time |
| **total wall-clock compute** | **~45 min** | |
| **total session** | **~2–3 h** | |

**QA: record actual timings for the our-decoder arms** — that figure is the one estimate in this
document that is not a measurement, and it should not stay one.

## 6b. MEASUREMENT C — the re-alignment experiment ⟨NEW at §R⟩

**This is now the highest-value measurement available, and it is not a D-001 measurement.** It
settles the capture defect, and it is the answer to the Captain's original question about
cross-decoding — a stronger version of it.

### 6b.1 The idea

The per-cycle drift is directly measurable by cross-correlation. So our archived WAVs can be
**shifted back into alignment with WSJT-X's and re-decoded.** Three previous
`fix-cycle-boundary-clock-drift` rounds were defeated by slow, non-reproducible live testing.
This settles the same question **offline and deterministically, on 5 782 matched pairs already
on disk.**

### 6b.2 Design

1. For each sampled cycle, measure the lag by cross-correlation.
2. Shift our WAV by the measured lag (sample-domain roll, zero-padding the vacated tail — no
   resampling, no interpolation, so nothing new is introduced into the audio).
3. Re-decode the shifted WAV with **our own decoder**, and with **jt9** as a control.
4. Compare parity before and after realignment, **within the collapsed window** (drift > 2.5 s,
   where baseline parity is ~2%) and within the healthy window as a null control.

### 6b.3 Reading rule — **pre-registered, fixed before the run**

| outcome | reading | consequence |
|---|---|---|
| **Collapsed-window parity recovers toward ~65%** | The collapse is window misalignment and nothing else. **Proven, not inferred.** | The defect's mechanism is confirmed; the fix targets cycle-boundary synchronisation. **The affected corpora become recoverable by realignment** rather than being written off |
| **Parity recovers only partially** (say to 20–45%) | Misalignment is the main cause but something else co-varies with session age — thermal, buffer growth, memory | Report the residual. Do **not** speculate on the co-factor without measuring it |
| **No recovery** | The drift is a *symptom*, not the cause. Something else in the capture path degrades with session length | Escalate. The defect report's §7 hypothesis is wrong and the diagnosis must widen |
| **Healthy-window control moves materially** | The realignment procedure itself is doing something | Harness defect. Void the run and fix the shift logic before re-reading anything |

### 6b.4 Cost

| item | estimate | basis |
|---|---|---|
| cross-correlation, 300 cycles | **~2 min** | measured — each pair is two 180 000-sample FFTs |
| decode, 300 cycles × 2 decoders × (shifted + unshifted) | **~1 h** | jt9 measured at 2.66 s/WAV; our decoder estimated |
| harness + report | 2–3 h | shift logic is ~20 lines; the reading is the work |

**Free by-products**, which is why this is the best-value run on the table:

- The **DT tolerance constant** (§6.2 secondary arm), needed independently of D-001.
- **The 489135a 40m corpus recomputed on its drift-free window** — which restores or refutes the
  fourth point of the density law and the withdrawn cross-instance claim (§3.1).
- **The reference-method question** left open by §3.2's withdrawal: the same cycles decoded by
  jt9 and present in live WSJT-X's `ALL.TXT` give a direct like-for-like comparison of the two
  reference methods on identical audio, at no extra cost.

## 7. SEPARATE ITEM — OpenWSFZ's reported SNR has a gain error ⟨raised outside D-001⟩

On the Captain's direction this is raised as its own item, **not folded into D-001**, where it
would be lost.

### 7.1 The measurement

From the same four committed ANOVA reports, on **matched** decodes — the identical message in the
identical cycle, found by both decoders:

| corpus | our mean SNR | reference mean SNR | we read **low** by |
|---|---:|---:|---:|
| 80m (jt9) | +1.417 dB | +9.454 dB | **8.04 dB** |
| 10m (jt9) | −4.950 dB | −1.755 dB | **3.20 dB** |
| 20m (jt9) | −3.704 dB | +1.898 dB | **5.60 dB** |
| ~~40m (live WSJT-X)~~ | ~~−13.061 dB~~ | ~~−0.563 dB~~ | ~~12.50 dB~~ **— suspect (§R), excluded** |

Regressing ours on the reference across the three jt9-referenced corpora — **all three on the
non-drifting device, so the fit below is unaffected by §R; the 40m row above is listed for
completeness only and is excluded from the fit:**

```
ours ≈ 0.585 × reference − 4.28 dB          residuals ±0.53 dB on 3 points
```

A pure offset would give slope 1.00. **This is a gain error.** I did not leave it at a
three-point corpus-mean regression — the committed per-decode scatter
(`anova_report_20m_snr_scatter.png`, n = 24 201 pairs) confirms it visually: the cloud crosses
`y = x` near −20 dB and falls progressively further below it as signal strength rises, reading
roughly +15 to +20 where the reference reads +40.

### 7.2 Why this matters, and why it is not a D-001 finding

- **Certain, and product-facing.** Reported SNR is wrong in QSO records and in outbound spots, by
  up to ~12 dB on strong signals. Given the recent external-reporting work, that error propagates
  off this machine into the wider reporting network. **This is the part that should be actioned.**
- **D-002 did not fix this.** June's D-002 corrected an SNR bias with a *constant* (the shim
  bandwidth term, −26.0 → −26.5 dB, `SNR = signal_db − noise_floor_db − 26.5`). A constant cannot
  correct a slope. That is the likely reason SNR bias keeps re-appearing.
- **The mechanism is consistent with a signal-contaminated noise-floor estimate.** In an additive
  formula, slope < 1 arises when the noise-floor term rises with the signal itself. Both
  estimators are histogram medians over waterfall bins (`compute_noise_floor` globally;
  `compute_local_noise_floor_db` over a K=32-bin sideband window per signal, introduced by
  `fix-d004-local-noise-floor`). **This is a hypothesis, not a finding** — it has not been
  measured and must not be cited as one.
- **It is NOT density-driven.** I checked, because the alternative would have tied it to §3: the
  sparsest band (80m) shows the *largest* offset. The gain model explains all three corpora to
  ±0.53 dB with no density term. The two findings are independent.

### 7.3 A hypothesis I formed and then killed — recorded so nobody re-forms it

`snr_db` is not merely reported metadata: it feeds the soft-suppression ramp
(`K_SOFT_SUPP_SNR_MIN_DB` = −5.0, `K_SOFT_SUPP_SNR_MAX_DB` = +15.0) that attenuates decoded
signals before the pass-1 candidate search. Under-reported SNR therefore means strong signals are
**under-suppressed** — which would plausibly damage exactly the weak-under-strong decodes row 4
targets. That is an attractive mechanism linking §7 to D-001's core.

**It is already tested and rejected.** `ft8_shim.c`'s own history records
`diag-d001-h5-suppression-tuning` (`FT8_SHIM_VERSION 20260011`), which shifted that ramp 10 dB and
was **REJECTED at −10.75 pp** (S7 46.24% vs H4 56.99%): *"Over-suppression confirmed."*

I am recording the one narrow reason this may not fully close the question, and then leaving it
alone: **H5 translated the window** (both endpoints −10 dB), whereas a gain error of 0.58 requires
a **slope** correction. A translation over-suppresses weak signals while still under-suppressing
strong ones — which is precisely what H5's own rejection note describes. So H5 tested a different
correction shape.

**That is also exactly the "the failed test doesn't really refute me" reasoning that produced two
withdrawn Architect rulings on 2026-07-27.** It is written down as a caveat, not a claim, and
**no work is proposed on it.** If §5 or §7 later make it live again, it comes back with a
measurement attached.

### 7.4 What I recommend QA does with this

Per HK-015 the dev-tasks are QA's to author; per HK-011 anything touching `src/` or native code
routes through a separate Developer session with the Captain's sign-off. My recommendation:

1. **Author a defect write-up for the SNR gain error**, outside the D-001 thread, carrying §7.1's
   measurement. Note explicitly that this supersedes the assumption that D-002 closed SNR bias.
   **Do not propose a fix in it** — the estimator question needs measuring first, and the
   correction shape (gain vs offset vs estimator change) is the whole decision.
2. **Cheap next measurement, if the Captain wants one:** regress our SNR on the reference
   *per-decode* across all four corpora (same near-free re-parse as §5 — the data is already
   loaded) to get a proper slope, intercept, and CI, and to confirm whether the slope is stable
   across bands. This would fold naturally into Measurement A's script for almost no extra cost.
3. **The D6 comment dev-task (QA rec 4): accepted, with an addition.** Do not simply delete the
   `L = −R` assertion in `WasapiAudioSource.cs`. It may have been true of an earlier hardware
   configuration. **Replace it with the measurement, its date, and its method**
   (`corr(L,R) = 1.000000`, `RMS(L−R) = 0.0`, 2026-07-30, via
   `qa/audio-capture-lr-phase-check/`), so the next engineer inherits a checked fact rather than
   re-assuming an unchecked one. Still low priority; still currently harmless.

## 8. What this changes for the menu — for the Captain

This is the part that is not diagnostic, and it is why §1 mattered more than §3.

**The 64.1% anchor is not a mid-range sample.** The original corpus ran ~21 minutes against a live
WSJT-X GUI reference reporting 2 028 decodes — roughly **24 decodes per cycle**, which places it in
the *dense half* of the range now measured (3.4 → 36.4). If the density law holds, the same
decoder on a sparse band would show parity in the high 80s, and on a busy one around half.

**That makes NFR-018's shape questionable, independently of which menu row is chosen.** A single
global "≥ 80% parity" threshold is partly a statement about operating conditions rather than about
the decoder — it is achievable today on a quiet band and unreachable on a busy one, with no code
change in between.

The consequence for the decision:

- **Row 1 (accept and re-baseline) becomes materially more attractive** — *if* the re-baseline is
  expressed as a **density-conditioned curve or a stated reference condition** rather than a
  scalar. That option did not exist when the menu was written, because the data to define the
  curve did not exist.
- **Rows 4 and 5 are not devalued.** The gap is real at every density measured. But a row 4
  business case built on "recover 789 messages" should now state the band conditions it assumes,
  because the prize is condition-dependent in a way the menu did not capture.
- **I am not re-opening the menu**, and this does not change my §4 recommendation from the B.3
  memo. The decision remains row 1 vs row 4 vs row 5, and it remains the Captain's.

**One addition at §R.** The density law now rests on three corpora rather than four, so §8's
argument is *motivating* rather than *established* until Measurement A runs. It should be put to
the Captain as a live possibility that changes NFR-018's shape, not as a finding. And a practical
consequence: **the capture defect should be fixed, or sessions capped below ~12 hours on the
affected device, before any further long-session corpus is gathered for this purpose** —
otherwise every new corpus needs the same forensic salvage the 40m ones now need.

**The row 4 decomposition I owe** (closing handoff §8) should wait for Measurement A. If §5
reverses the co-channel withdrawal, the decomposition's shape changes materially — competition
handling is a different engineering target from sync/candidate quality. Delivering it before §5
runs would risk exactly the wrong-sized commitment the menu's own caveat warns about.

## 9. Numbers and readings that must NOT be cited

Additions to the closing handoff §6 list. If any of these appears in a future findings doc, task
spec, or Captain-facing summary, that is a defect.

| withdrawn / corrected | replacement |
|---|---|
| *"the two effects combine close to multiplicatively … 1.125 × 1.478 ≈ 1.663 against 544/327 = 1.663 exactly"* | **Circular** — true for any four numbers. Cite the interaction term instead: `ad/bc = 0.977 ± 9.8%`, i.e. **no detectable interaction, and insufficient precision to claim multiplicativity** |
| *"a real, but secondary, capture-chain effect exists"* / *"small, real, measured"* (§0.2, rec 1) | **Not established.** ~1.5σ, p ≈ 0.12, two correlated arms, anti-conservative SEs. **Pending Measurement B** |
| *"parity ranges 49.9% to 91.6%"* as a single distribution | **53.2%–91.6%**, three clean corpora. **49.9% is struck entirely** — that corpus averages ~13 h at ~65% with ~12 h of a broken application at ~2% (§R). Not a parity measurement |
| **My own §3.2**: *"the 49.9% shortfall is a reference-method artefact (jt9 re-decode vs live WSJT-X)"* ⟨mine, withdrawn same day⟩ | **False.** The cause is the capture clock drift (§R). The reference-method question is now **unevidenced either way** — Measurement C would settle it |
| **My own §3.1**: *"two different capture chains obey the same parity law … bounds inter-chain variation under one parity point"* ⟨mine, withdrawn same day⟩ | **Withdrawn.** The second chain is the drifting device; its 62.4% is depressed by an unknown amount. Recompute on its drift-free window before citing |
| *"WSJT-X's own recording of a given instant …"* (QA §3's framing) | The two recordings were **2.34 s apart**, not of the same instant. The comparison is confounded (§4) |
| `2026-07-29-5016363/anova_report_40m.md` as a parity source | **Do not cite for parity at all.** Its DT and SNR appraiser means are likewise session-averaged across a ramp and a collapse |
| *"the 64.1% figure came from one band, one 21-minute corpus"* — correct, but incomplete | Add: that corpus sat at **~24 decodes/cycle**, the **dense half** of the measured range. It is not a mid-range sample (§8) |
| D6 comment's *"differential signal (L = −R)"* in `WasapiAudioSource.cs` | **Measured false on current hardware**: `corr(L,R) = 1.000000`, `RMS(L−R) = 0.0` (2026-07-30). Harmless in practice; must not be relied on as documentation |
| *"D-002 closed the SNR bias question"* | **Superseded.** D-002 corrected a constant; the residual is a **gain error** (slope ≈ 0.58), which a constant cannot fix (§7) |

## 10. What this document does NOT do

- **Does not re-open the diagnostic programme** under the closing handoff §0 as a standing effort.
  §5 and §6 are two bounded measurements, each with a stop rule, **put to the Captain and
  authorised in this session** before being written down.
- **Does not authorise any new arm beyond §5 and §6.** In particular: the resample-algorithm
  question stays closed (QA rec 5, accepted); the H5/suppression thread stays closed (§7.3); the
  40m/489135a jt9 re-decode is explicitly **not** authorised (§5.1).
- **Does not change the menu decision.** Row 1 vs row 4 vs row 5 remains the Captain's.
- **Does not invalidate any corpus.** Every finding here is additive re-interpretation of data
  that stands.
- **Does not touch `src/` or native code** (HK-011). §7.4's items are recommendations for QA to
  author and route to a Developer session, not applied.
- **No push, no merge** (HK-014 / HK-010) — committed locally, stops there. **No
  `pre_merge_check.py`** (HK-006) — the Captain's trigger only.
- **NFR-021:** aggregates only. All raw material referenced stays under git-ignored `artefacts/`.

## 11. Cross-references

- **`DEFECT-capture-clock-drift-silent-decode-loss.md`** (repo root) — the capture defect found
  while validating this ruling. **Read first**; it invalidates one corpus, confounds QA's §3, and
  forced §R's revisions.
- `2026-07-30-2221-qa-to-architect-capture-chain-and-cross-band-findings.md` — the note this answers.
- `2026-07-27-2012-architect-to-qa-d001-closing-handoff.md` — standing programme reference; §0 stop
  rule, §2.2 the withdrawn co-channel bet, §2.3 the three unmeasured candidates, §6 the citation
  blacklist this document extends, §8 the row 4 decomposition owed.
- `2026-07-26-2359-architect-b3-costed-menu.md` — the five-row menu; §6's "one corpus" caveat is
  the one §3 and §8 now answer.
- `2026-07-27-1730-architect-row4-scoping-design.md` — row 4 scoping, now gated on Measurement A (§8).
- `qa/endurance/2026-07-29-5016363/anova_report_{10m,20m,40m,80m}.md` + `CONTAMINATION-NOTE.md`,
  `qa/endurance/2026-07-29-489135a/anova_report_40m.md` — §3's source data.
- `qa/endurance/anova_common.py` — the matching/normalisation logic Measurement A must reuse.
- `artefacts/20260729_live_run_1831-8080/` (5 782 matched WAV pairs), `…-8081/owsfz/{10m,20m,80m}/`
  (cached `jt9_ALL.TXT`) — §5 and §6's material, git-ignored.
- `src/OpenWSFZ.Ft8/Native/ft8_shim.c` — SNR formula, `compute_local_noise_floor_db`,
  `K_SOFT_SUPP_*`, and the H5 rejection record (§7).
- `src/OpenWSFZ.Audio/WasapiAudioSource.cs` — the D6 comment (§7.4).

---

*Revised 2026-07-30 23:15 UTC per §R: §3.2 withdrawn in full, §3.1 reduced to three corpora,
§6 redesigned, §6b added, §8/§9 updated. Two of the withdrawn items in §9 are my own, both
caught and struck the same day rather than propagating into the row 4 decomposition.*

*Per HK-015 this is Architect → QA material; the task specs and the §7.4 dev-tasks are QA's to
author and own. Per HK-014 this note is committed locally and goes no further — no push, no merge.
Per HK-011 nothing here touches `src/` or native code. Per HK-006 no `pre_merge_check.py` run is
implied. Per HK-017 the filename and byline both carry `date -u` UTC (2026-07-30 22:53Z), which is
the previous calendar day from local CEST. The row 1 vs row 4 vs row 5 decision remains the
Captain's.*
