# D-001: Architect → QA — ruling on Measurements A, B, C, plus the drift root cause in code
# Three rulings requested, three given. One is a partial rejection of a mechanical outcome —
# because my own reading rule was under-specified and QA implemented the half of it I wrote down.
# One item the ruling did not ask for is delivered: the capture defect's §7 mechanism, now
# established by reading the code.

**Author:** Architect, 2026-07-31 (00:29 UTC, `date -u`, per HK-017). Repo at `b3a05c4`.
**For:** QA (all actions below are QA's to route), and the Captain (§1 and §6 need decisions).
**Answers:** `2026-07-31-0018-qa-to-architect-measurements-abc-plus-snr-defect.md` §6 items 1–4.
**Amends:** `2026-07-30-2253-architect-ruling-cross-band-density-law-and-capture-chain.md` —
S5.3's reading rule (drafting defect, §1.1 below), S3/S9 (the Measurement B strike, §3), and §9's
blacklist (three additions, §5).
**Supersedes nothing.** `2026-07-27-2012-architect-to-qa-d001-closing-handoff.md` remains the
standing programme reference.

---

## 0. Summary — the one thing to read if you read nothing else

| item | QA's request | ruling |
|---|---|---|
| **Measurement A** | rule on the reversed co-channel withdrawal; re-shape the row 4 decomposition | **PARTIALLY REJECTED.** The withdrawal cannot be restored — that part is mechanical and stands. But **the reversal is not licensed**: the "monotone in density" half of S5.3's row 2 fails in **10 of 26 bins**, and the curves cross. Rows 3 **and** 4 fire, not row 2. Outcome is *escalate, do not interpret*. **Row 4 decomposition stays gated.** One cheap discriminator recommended to the Captain (§1.4) |
| **Measurement C** | rule on actioning a cycle-boundary fix; rule on recomputing the affected corpora | **ACCEPTED IN FULL, and extended.** I read `CycleFramer.cs` and `WasapiAudioSource.cs`: **the mechanism is now established in code** (§2.1), closing the first bullet of the defect's §7. Fix: **yes, action it** — but the *first* deliverable is the offline oracle, not the diff (§2.3). Corpora: **yes, recompute before any re-citation** (§2.4) |
| **Measurement B** | strike S3/S9's capture-chain percentages | **ACCEPTED.** Struck at §3. And **upgraded**: the refutation is not just a deletion, it converts an unmeasured closing-handoff §2.3 candidate into a **measured upper bound** (§3.2) |
| **SNR gain error** | none needed | Agreed, none needed. Two consequences recorded at §4 |

**The one thing that changed my mind mid-review:** I expected to rule "reversal accepted" and
write the row 4 re-scope. I checked the per-bin table first, per HK-018, and the monotonicity
claim does not hold. It is my drafting that let a two-band check stand in for a three-band one.

## 1. Measurement A — PARTIALLY REJECTED

### 1.1 The drafting defect is mine

S5.3 row 2 reads *"Dense bands sit materially below sparse at matched SNR (≥ 10 pts, **monotone
in density**)"*. I never said what tests "monotone in density". With three bands at 3.38 / 8.52 /
36.36 reference decodes per cycle, the condition can only mean:

```
recall(80m) ≥ recall(10m) ≥ recall(20m)      in each common-support bin
```

`measurement_a_snr_recall.py` tested only `recall(80m) ≥ recall(20m)` — the outer pair — found it
26/26, and printed **"monotone"**. That is a defensible reading of an under-specified rule, and
QA's own §4 flagged the very pattern that breaks it. The gap is my drafting, not QA's execution.
QA's write-up is also internally inconsistent on this point (§3 bullet 3 says the curves cross
"a few times"; §3's closing paragraph says "not crossing, not non-monotone") — worth noting only
because the auto-generated outcome line overrode the human observation, which is the failure mode
to watch for when a script prints a verdict.

### 1.2 What the full three-band test actually gives

Recomputed directly from `measurement_a_snr_recall_report.md`'s own committed table:

| check | result |
|---|---|
| `recall(80m) ≥ recall(20m)` | 26 / 26 bins ✔ |
| `recall(10m) ≥ recall(20m)` | 25 / 26 — **fails at [−22, −20) dB** (10m 14.7%, 20m 21.2%) |
| `recall(80m) ≥ recall(10m)` | **16 / 26 — fails in 10 bins** |
| … of which at SNR ≥ 0 dB | **9 of 14 bins fail** (10m beats 80m by up to 8.3 pts) |

The sparsest band is beaten by a band **2.5× denser** across most of the upper half of the SNR
range. Density does not order the curves. What the data shows is not a gradient across three
bands — it is **20m sitting 10–35 points below both other bands** (median gap to the *better* of
the other two: 17.7 pts), with 10m and 80m interleaving.

### 1.3 The ruling, applied mechanically

Against S5.3 as written, on the full three-band data:

- **Row 1 is excluded.** Separation is 36.0 pts, not < 5. **The co-channel withdrawal cannot be
  restored.** The pure-sensitivity explanation of §3.3 — a fixed 2.62 dB deficit acting through
  the SNR mix — predicts a horizontal shift and is **refuted** by a vertical gap holding from
  −24 dB to +28 dB. This much is mechanical and I accept it without reservation.
- **Row 2 is not satisfied.** Its second condition fails, in 10 of 26 bins.
- **Row 3 fires** (*"non-monotone in density → Partial/ambiguous. **Do not interpret further.**
  Escalation, not interpretation."*)
- **Row 4 also fires** (*"Curves cross (sparse below dense at some SNRs) → Not anticipated by any
  current model. Escalation. **Do not rationalise it in the findings document.**"*)

**Consequence.** The withdrawal is dead; competition is **not** established in its place. The
honest position is now narrower than either side of the menu wanted: *we have one band-specific
deficit of large magnitude and no identified mechanism.* Per rows 3 and 4, that escalates to the
Captain and is **not** interpreted further — which means:

> **The row 4 decomposition stays gated**, exactly as ruling §8 left it. It is still owed. I am
> **not** re-shaping it toward competition handling, because a 20m-specific deficit and a
> density-driven competition effect are different engineering targets, and committing to the
> wrong one is precisely the wrong-sized commitment the B.3 menu's own caveat warns about.

### 1.4 Two candidate mechanisms — one killed from data already on record, one live

Per HK-018, before proposing anything I checked what was already measured.

**KILLED — `K_MAX_CANDIDATES = 140` saturation.** QA flagged this at its §4 as worth a look. It
has already been measured. `2026-07-26-c1-candidate-cap-sweep-findings.md`: raising the cap
140 → 300 → 600 on a matched corpus yields **+12 decodes (+0.93%)**, identical at 300 and 600,
with the real candidate population plateauing at ~220–295 and `meanAbsLLR` flat — the extra
candidates are the same low-confidence population, not a better set being denied. A ~1% effect
cannot account for a 17–35 point gap. **Do not spend a session on this.** The one caveat worth
recording: that sweep ran at ~19 decodes/cycle, not 20m's 36.4, and pass-0 candidates sat pinned
at exactly 140 (median) — so the cap *is* binding there and would bind harder on 20m. The
measured marginal yield, not the binding, is what kills it.

**LIVE, and decisive — within-band density stratification.** The whole ambiguity is that band
identity and band density are confounded: three bands, three densities, three antennas, three
propagation environments, three spectral characters. **20m's own cycles vary in density**, and
that comparison holds every band-specific factor constant. I checked whether it has the power
the original withdrawn test lacked:

```
20m, 1 330 cycles, 49 527 reference decodes (jt9)
per-cycle density:  p10 = 22   median = 37   p90 = 49   max = 98
p90/p10 = 2.23  (the withdrawn test's in-corpus proxy was 1.6–1.8)
```

0.35 decades between the p10 and p90 strata. The between-band fit
(`parity ≈ 111.9 − 37.63·log₁₀ density`) predicts a **~13-point** separation over that range —
large, and with ~8 000 matched decodes per stratum it is measurable many times over. **This is
the test that separates "competition" from "20m specifically", and it needs no decoding, no new
data, and no new script beyond a stratify-and-rerun of `measurement_a_snr_recall.py`.**

**I am not authorising it** (closing handoff §0 stop rule; every arm in this thread went to the
Captain first). I am recommending it to the Captain as the single highest-value hour available,
and it is the one thing that would ungate the row 4 decomposition.

**Pre-registered reading rule — fixed now, before any run, and this time stated as a test:**

| outcome | reading | consequence |
|---|---|---|
| Dense-cycle recall sits **≥ 8 pts below** sparse-cycle recall at matched reference SNR, in **≥ 80% of common-support bins** | Density suppresses recall with band identity held constant. | **Competition confirmed as a named, measured mechanism.** Row 4 re-scopes toward it. Escalate before engineering |
| Separation **< 3 pts**, or fails the 80% bin criterion | Density does not act within a band. The cross-band effect is **20m-specific** and not a density law. | The density law is withdrawn entirely. Row 4's target reverts to sensitivity/front-end; the 20m deficit becomes its own bounded question |
| Separation **3–8 pts**, or direction inconsistent across bins | Partial. | Report as ambiguous. **Do not interpret.** Escalate |
| Sparse-cycle recall sits **below** dense | Not anticipated. | Escalate. Do not rationalise |

Repeat the identical test on 10m and 80m as replication — free, same script — but the reading is
taken on 20m, which is the only band with the density range to carry it.

### 1.5 One confound, and its direction

jt9's reported SNR is referenced to its own noise-floor estimate, which on a crowded band is
inflated by other signals' energy. A decode reported at "0 dB" on 20m is therefore, if anything,
**physically stronger** than one reported at 0 dB on 80m. That biases the comparison **against**
the observed 20m deficit — i.e. the real gap is likely larger, not smaller. This is reasoning,
not a measurement, and it is recorded as a reason not to worry about the confound rather than as
a finding.

## 2. Measurement C — ACCEPTED IN FULL, and extended

The measurement is clean and I accept it without qualification. It is the best-executed run in
this thread: sign convention derived from first principles, validated against a synthetic control
*and* against the design's own null control, smoke-tested before full scale, n=300, both
pre-registered traps checked and neither triggered. **4.0% → 63.1%, landing inside the healthy
baseline's own CI, against a null control that moved 0.3 points, is proof.** S6b.3 row 1 fires
exactly as QA read it.

### 2.1 The mechanism, now established in code — closing the defect's §7 first bullet

The defect report states: *"'Capture free-runs on the device sample clock without UTC resync'
fits all four sessions but has **not** been verified by reading `WasapiAudioSource.cs` or
`CycleFramer.cs`."* I read both. **It is verified, and it is the framer.**

`CycleFramer.RunAsync` synchronises to UTC **exactly once**, at startup:

```csharp
int leadingSilence = ComputeLeadingSamples(startUtc);   // ← the only wall-clock read
DateTime cycleStart = AlignToCycleStart(startUtc);
...
if (filled == SamplesPerCycle)                          // 180 000 samples
{
    output.TryWrite((window, cycleStart, windowDialFreq));
    filled     = 0;
    cycleStart = cycleStart.AddSeconds(CycleDurationSecs);   // ← arithmetic, never re-checked
}
```

After that first alignment the framer's entire timebase is **"180 000 samples *is* 15.000
seconds"**. `_clock.UtcNow` is never consulted again. Upstream, `WasapiAudioSource` builds
`new WdlResamplingSampleProvider(samples, 12_000)` from the device's **declared** rate — the
resampler converts by the ratio of nominal rates and cannot know the crystal's true rate, so any
hardware rate error passes through the resampler unchanged into the 12 kHz stream.

The arithmetic closes exactly:

```
measured drift      −0.1744 s/hour  (measure_drift_8080_session.py regression)
                  = 48.4 ppm
missing samples     0.1744 s × 12 000 = 2 093 samples per hour
                    2 093 / 43 200 000 = 48.4 ppm      ✔ identical
→ the USB CODEC clocks ≈ 11 999.42 Hz where the framer assumes exactly 12 000.000 Hz
```

And it explains the control case with no extra assumption: **Voicemeeter is a virtual device
slaved to the system timebase — zero crystal error, therefore zero drift**, which is precisely
what the three 8081 corpora show. The defect's §7 bullet can be closed.

**A second, independent path to the same failure, found while confirming the first.** Both
`WasapiAudioSource`'s buffer-overrun branch (>4 s buffered) and its channel-write failure branch
are **warn-only** — they log and continue. Any sample dropped anywhere upstream permanently
shifts every subsequent window, and the framer **cannot detect it**, because its only notion of
time is the sample count it is itself being lied to about. The 48 ppm crystal is simply the most
reliable way to hit this; a single stalled consumer would do it too, instantly and invisibly.
**This is a framer design defect, not only a hardware-clock defect** — which matters, because a
fix aimed only at rate compensation would leave the drop path wide open.

### 2.2 Ruling on QA's question (a): action the fix — yes

**Yes, action it.** The severity is already established as Critical in the defect report and the
mechanism is no longer a hypothesis. But the ordering matters more than the speed, because
**three previous `fix-cycle-boundary-clock-drift` rounds were each defeated by slow,
non-reproducible live testing** — 9.5 alone burned an 11h51m round to fail. Shipping a fourth
attempt into the same verification vacuum would be the fourth instance of one mistake.

### 2.3 The first deliverable is the oracle, not the diff

Measurement C's real contribution is that **this defect is now testable offline and
deterministically**, which it has never been. Two things fall out, and the first must land first:

1. **A deterministic unit-level regression test.** Drive `CycleFramer` from a synthetic sample
   source clocked at 11 999.42 Hz against a fake `_clock`, simulate 24 h, and assert emitted
   window boundaries stay within a stated tolerance of UTC. Runs in milliseconds; needs no audio,
   no radio, no live session. **Every one of the three failed rounds would have been caught by
   this before it was ever armed.** A second case — inject a dropped chunk mid-stream — covers
   §2.1's second path.
2. **An acceptance constant, derived not guessed.** The decoder's DT cliff is bracketed at
   **2.34–2.48 s** (defect §2.3, corroborated by Measurement C's collapsed stratum). Holding
   boundary error under ~0.2 s — an order of magnitude inside the cliff — permits ~1.1 hours
   between resyncs at 48 ppm. **Resynchronising every cycle is therefore trivially sufficient**,
   with three orders of magnitude of margin, and needs no rate estimation, no resampling, and no
   PLL. The cheap fix is the correct one here; I would treat any proposal involving rate
   estimation or adaptive resampling as over-engineering unless the simple resync is measured to
   fail.

**Fix shape, for scoping only — not a diff, and not binding on the Developer session:** re-derive
each window's boundary from the wall clock rather than from accumulated sample counts, absorbing
the residual per cycle. Per HK-011 this is `src/` work: QA authors the dev-task, a separate
Developer session applies it, the Captain signs off the diff before push. Per HK-015 the task
spec is QA's to write, not mine. **I propose no code.**

Sequencing I recommend to QA: task 1 = the oracle (test-only, no `src/` behaviour change, low
risk); task 2 = the fix, gated on task 1 going red first against current `main`. A regression
test that does not fail before the fix proves nothing.

### 2.4 Ruling on QA's question (b): recompute before re-citation — yes, and here is the scope

**Yes — unconditionally.** Both affected corpora's headline parity figures are, as of now,
*known-recoverable but not recovered*. Being recoverable is not a licence to cite the damaged
number, and it is equally not a licence to cite a recovered number that nobody has computed.

| figure | status until recomputed |
|---|---|
| `2026-07-29-5016363/anova_report_40m.md` — 49.9% | **Struck** (ruling §9, unchanged). Not a parity measurement. Recomputation on the realigned window would make it one |
| `2026-07-29-489135a/anova_report_40m.md` — 62.4% | **Suspended** (ruling §3.1, unchanged). This is the fourth density-law point and the withdrawn cross-instance claim; it cannot be restored or refuted without the recompute |

Priority: **489135a first**, because it is the one that carries live consequences — it is the
only route to restoring or killing the cross-instance claim I withdrew at §R. QA is right that
this is a follow-on and was right to flag it rather than let it be assumed done by C.

Two constraints on that recompute, so it is not started on a false footing. First, ruling §5.1
still stands: **489135a did not retain its `jt9_ALL.TXT`**, so this needs ~2.6 h of re-decode and
is not a by-product of anything. Second, the ruling's §8 practical consequence stands and gains
force: **fix the defect, or cap sessions below ~12 h on the affected device, before gathering any
further long-session corpus** — otherwise every new corpus needs this same forensic salvage. Given
HK-020's record on multi-band overnight runs, this belongs in the pre-flight check for the next
one, not in a document nobody re-reads.

### 2.5 What C does *not* settle, restated so it is not assumed

QA correctly declined to claim two by-products S6b.4 advertised. I confirm both: the reference-
method question (jt9 re-decode vs live-WSJT-X `ALL.TXT` on identical audio) is **still
unevidenced**, and 489135a is **still not recomputed**. The DT tolerance constant is delivered
only as a confirmed bracket (2.34–2.48 s), not as a resolved curve — which §2.3 shows is
sufficient for the fix's acceptance criterion, so I am **not** asking for the S6.2 secondary arm.
QA's judgement to skip it is accepted.

## 3. Measurement B — ACCEPTED, and upgraded from a strike to a bound

### 3.1 The strike

S6.3's own consequence column is unambiguous and the outcome is a clean null, not an
underpowered one: n=300 (10× the original), interaction CI [0.9526, 1.0421] around 0.9964, paired
Wilcoxon p=0.44 / 0.84 against a nominal z ≈ 4.9 had the effect been real. **Struck, effective
now:**

| struck | replacement |
|---|---|
| ruling §3, *"+12.5% (our decoder) / +9.9% (jt9) capture-chain effect"* | **Refuted at n=300.** Ratios 1.0034 / 0.9998; interaction 0.9964, 95% CI [0.9526, 1.0421]; paired Wilcoxon p=0.44 / 0.84 |
| ruling §9's *"pending Measurement B"* qualifier on rec 1's *"small, real, measured"* | No longer pending. **Not real.** Rec 1 is now finally **rejected**, not deferred |
| the resample-algorithm question (QA rec 5, ruling §10) | Stays closed, now for a stronger reason: the effect it was invoked to explain does not exist |

The mechanism is settled too, which is why this is a refutation rather than a shrug: the original
sample sat at **2.34 s of drift** (ruling §4/§R), and Measurement C independently proves that
regime is pure window misalignment. The +12.5% was measuring the drift defect. Two measurements
from different directions agreeing on that is worth more than either alone.

### 3.2 The upgrade — this is not merely a deletion

Closing handoff §2.3 lists the capture chain as one of three **unmeasured** candidates for the
D-001 gap. It is no longer unmeasured. The interaction CI bounds it:

> **The capture chain costs us at most ~4–5% of decodes, and the point estimate is zero.** It
> cannot be a material term in the row 4 decomposition, and it cannot account for any part of a
> 17–35 point band gap.

That is exactly what rec 1 wanted — a measured magnitude with a CI for the decomposition — in
negative form. **When the row 4 decomposition is finally written, this belongs in it as a closed,
bounded line item, not as an omission.** One of three candidates is now retired on evidence.

QA's decision to run only the primary arm was correct and I would have ruled against running the
secondary one had it been proposed.

## 4. SNR gain error — noted, two consequences

No ruling needed; correctly routed standalone per the Captain's direction. Two things to record:

- **It does not contaminate Measurement A.** QA binned by *reference* SNR precisely because of
  this. That was the right call and it is why A survives review at all. Any future re-analysis
  that bins by our own SNR inherits a 0.69 slope and is invalid.
- **The slope, not the offset, is the architectural point.** At slope 0.6865 the error is
  condition-dependent, so **any threshold expressed in our SNR units is mis-scaled by an amount
  that varies with signal strength** — a constant correction cannot fix it, which is what retires
  *"D-002 closed the SNR bias question"* (ruling §9). I offer no view on the correction shape;
  that decision is open and it is not mine to pre-empt.

## 5. Additions to the citation blacklist (ruling §9)

| withdrawn / corrected | replacement |
|---|---|
| *"the capture chain costs ~10–13% of decodes"* / any of §3's percentages | **Refuted at n=300** (§3.1). Cite the bound instead: **≤ ~4–5%, point estimate zero** |
| *"Measurement A shows a monotone density law"* / *"the co-channel withdrawal reverses"* / *"competition is a measured mechanism"* ⟨QA's §1, from my under-specified rule — **the drafting defect is mine**⟩ | **Not established.** Monotonicity fails in 10/26 bins and the curves cross. What is measured is **a 20m-specific deficit of 10–35 pts**. The withdrawal is dead; **competition is a candidate, not a finding** (§1) |
| *"`K_MAX_CANDIDATES = 140` may explain 20m's deficit"* ⟨QA's §1/§4, flagged not claimed⟩ | **Measured and killed** — 140→300 yields +0.93% with the population plateauing at ~220–295 (`2026-07-26-c1-candidate-cap-sweep-findings.md`). Cannot account for a 17–35 pt gap |
| *"the capture defect's code mechanism is not established"* (defect §7, first bullet) | **Now established** (§2.1): `CycleFramer` resyncs to UTC once at startup and thereafter counts samples; 48.4 ppm arithmetic closes exactly and explains the Voicemeeter control |

## 6. What this asks of QA, in order

1. **Escalate Measurement A to the Captain as §1.3 states it** — withdrawal dead, competition not
   established, row 4 still gated — and put §1.4's within-band stratification to the Captain as a
   recommendation with its reading rule attached. **Do not run it unauthorised.** Correct the
   auto-generated "monotone" verdict line in `measurement_a_snr_recall_report.md` and its script,
   noting the rule defect was mine.
2. **Author two dev-tasks for the drift fix, in this order** (HK-000/HK-015): the offline oracle
   first (test-only), the fix second, gated on the oracle failing against current `main` first.
   Per HK-011 both route to a separate Developer session with the Captain's sign-off; neither
   checklist carries `pre_merge_check.py`.
3. **Add the 489135a recompute to the queue** as its own task, priced at ~2.6 h of re-decode
   (§2.4), and hold both 40m parity figures struck/suspended until it lands.
4. **Carry §3.2's bound into the row 4 decomposition** when I deliver it — it is a closed line
   item now, not a gap.
5. Nothing here needs a push, a merge, or a gate run.

## 7. What this document does NOT do

- **Does not re-open the diagnostic programme** (closing handoff §0). §1.4 is a recommendation to
  the Captain, not an authorisation, and it carries its own stop rule.
- **Does not deliver the row 4 decomposition.** Still owed; still gated, now on §1.4 rather than
  on Measurement A. I will not write it against a 20m-specific effect of unknown mechanism.
- **Does not change the menu.** Row 1 vs row 4 vs row 5 remains the Captain's, and ruling §8's
  argument that NFR-018's single global 80% threshold is the wrong *shape* is unaffected by
  anything here — it rests on the parity range across corpora, not on the density law's
  monotonicity.
- **Does not touch `src/` or native code** (HK-011). §2.1 quotes `CycleFramer.cs` read-only;
  §2.3 is scoping, not a diff. No fix is proposed as code.
- **Does not propose configuring the WSJT-X instances** — Captain's to manage.
- **No push, no merge** (HK-014/HK-010) — committed locally, stops there. **No
  `pre_merge_check.py`** (HK-006) — the Captain's trigger only.
- **NFR-021:** aggregates only; every raw input referenced stays under git-ignored
  `artefacts/`/`_work/`.

## 8. Cross-references

- `2026-07-31-0018-qa-to-architect-measurements-abc-plus-snr-defect.md` — the note this answers,
  and the three measurement write-ups it links.
- `2026-07-30-2253-architect-ruling-cross-band-density-law-and-capture-chain.md` — amended here
  at S5.3 (§1.1), S3/S9 (§3.1), §9 (§5).
- `DEFECT-capture-clock-drift-silent-decode-loss.md` — §7's first bullet closed by §2.1; severity
  and evidence unchanged.
- `DEFECT-snr-reported-gain-error.md` — §4's subject; no ruling.
- `2026-07-26-c1-candidate-cap-sweep-findings.md` — the measurement that kills the
  `K_MAX_CANDIDATES` hypothesis (§1.4).
- `measurement_a_snr_recall_report.md` — the committed per-bin table §1.2 recomputes from.
- `src/OpenWSFZ.Ft8/CycleFramer.cs` (RunAsync, `ComputeLeadingSamples`),
  `src/OpenWSFZ.Audio/WasapiAudioSource.cs` (`WdlResamplingSampleProvider`, the warn-only
  overrun/drop branches) — §2.1's evidence.
- `2026-07-27-2012-architect-to-qa-d001-closing-handoff.md` — standing reference; §2.3's
  candidate list, one entry of which is retired at §3.2; §8's owed decomposition.

---

*Per HK-015 this is Architect → QA material; every action above is QA's to route, and the
dev-tasks are QA's to author. Per HK-014/HK-010 committed locally, no push, no merge. Per HK-011
nothing here touches `src/`. Per HK-017 filename and byline both carry `date -u` UTC. Per HK-018
the monotonicity recomputation, the candidate-cap check, the within-20m density spread, and the
`CycleFramer` read were all done before this document was written — two of them changed its
conclusions. The Measurement A escalation and §1.4's authorisation are the Captain's.*
