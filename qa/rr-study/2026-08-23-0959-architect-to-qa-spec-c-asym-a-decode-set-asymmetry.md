# Architect → QA — C-ASYM-A: is D-001 a decoder deficit, or one arm of a two-sided disagreement?

**Author:** Architect, 2026-08-23 09:59Z (`date -u`, HK-017).
**Status:** pre-registration. Nothing here has been run except what §0 and §7 disclose.
**Ownership:** re-analysis of corpora already on disk, plus one short synthetic run.
No `src/` change, no capture run, no Developer session. Parts A/B/D are pure re-analysis;
Part C needs a new scenario file and one registry line (`qa/` only — QA-ownable, HK-011
does not bite).

---

## 0. 🔴 MANDATORY DISCLOSURE — the Architect's first proposal was wrong, and the data that killed it was already on disk (HK-018)

Yesterday's S1–S8 sweep showed OpenWSFZ at **45/45** across nine S8 stations spanning −15 to
+3 dB, and **10/10** on the 1500 Hz capture pair where WSJT-X scored 5/10. Against a live
off-air deficit of 43.8 pp, that is a contradiction.

My first proposal to the Captain was to **walk S8's stimulus envelope outward** — lower the SNR
floor, raise the density — until our curve broke away from WSJT-X's. **That proposal was largely
redundant and I retract it.** Both axes are already instrumented and have already run:

| axis | existing instrument | what it already says |
|---|---|---|
| SNR below S8's −15 dB floor | **S1b** (−24/−21/−18/−15 dB) | 2026-08-22: WSJT-X 58.3%, OpenWSFZ 50.0%, N=12 per appraiser. Per-part: −24 dB **0/3 both**; −21 dB 2/3 vs 0/3; −18 dB 2/3 vs **3/3**; −15 dB 3/3 both. No deficit resolvable at this N. |
| density above S8's 12 signals | **S4** (1/5/10/20/**30** signals, SNR ladder −24…+3) | 2026-08-22: recovery vs injected truth WSJT-X **62.04%**, OpenWSFZ **64.81%**. Decodable-restricted (floor −12 dB): **70.37% vs 76.54%.** We do not merely match at 30 simultaneous signals — we win. |

I proposed measuring what had been measured every sweep for months. QA is entitled to weigh the
rest of this document knowing that.

**What survives, and why it is worth a spec:** the contradiction is now *sharper*, not softer.
Across every synthetic axis we instrument — SNR to −24 dB, density to 30 signals, co-channel
capture, near-collision, time offset — OpenWSFZ matches or beats WSJT-X on the same audio path,
same binaries, same sweep. On live audio it is 43.8 pp behind. **Both cannot be a statement about
the same decoder unless something other than decoding differs**, and this arm is built to find out
which of four candidates it is.

The bars in §5 were set knowing every number in this section and in §7.

---

## 1. The question

> **D-001 counts, of the decodes WSJT-X made, the fraction we did not make. It never counts the
> reverse. If the two decoders have partly disjoint competence, that statistic reports a large
> "gap" whether or not either decoder is worse.**

This is not a hypothetical. It was measured 18 days ago and never followed up (§7).

Four candidate explanations for the synthetic-vs-live contradiction, and this arm separates them:

| # | explanation | tested by | cost |
|---|---|---|---|
| **E1** | **Metric asymmetry.** The gap is one arm of a two-sided disagreement. | Part A | re-analysis |
| **E2** | **Our exclusive decodes are false.** The reciprocal figure is inflated by junk, so the disagreement only *looks* two-sided. | Part B | re-analysis |
| **E3** | **Scope/configuration difference.** The two legs are not searching the same frequency/time space, so "misses" are partly signals we never looked for. | Part D | re-analysis |
| **E4** | **Real-signal impairments absent from the synth** — fading, Doppler spread, transmitter drift, timing spread. | **NOT tested here** — see §8 | generator work |

E4 is the expensive one and it is deliberately last. **It is only worth funding if E1–E3 fail to
account for the contradiction**, and three of the four are answerable this week from data already
on disk. That ordering is the whole point of the spec.

---

## 2. Population — reused, not re-derived (HK-018)

**Live corpus: `artefacts/20260803_live_run_1713/`.** Confirmed present and current in
`qa/ARTEFACT_INVENTORY.md:38` (`--check` clean at drafting time, 2026-08-23 09:59Z):
`owsfz` 4,614 cycles / `wsjt-x` 4,531 cycles; both WAV sets; the inventory flags it
**"D-001 replication corpus — DO NOT PROPOSE A CAPTURE RUN FOR D-001."**

- **Epoch:** the decisive epoch `ts >= 260803_185914`, exactly as used by the 2026-08-05 scouting
  pass. Reuse it verbatim; do not re-derive the boundary.
- **Audio-path identity is already established FOR THIS CORPUS** — 8 shared-filename WAV pairs,
  FFT cross-correlation, median `|r| = 0.9870` (0.9768–0.9947), best-lag ≤ 34.1 ms, RMS ratio
  0.902–1.036, both legs 12 kHz mono 16-bit 15.00 s. ⚠️ This corpus is the single-instance run
  where both decoders sat on one capture device; **cite the recorded verification, do not inherit
  it from any other corpus, and do not re-run it.**
- **Unit of independence is the cycle (`ts`), not the decode** (HK-021(i)). Every CI in this spec
  is a cluster bootstrap over `ts`, 2,000 draws, seed `20260823`. Report **cluster counts alongside
  row counts, never row counts alone.**
- **Matching convention:** distinct `(ts, message)` with bracketed callsign tokens — resolved or
  not — collapsed to a canonical `<HASH>` marker before the equality test, exactly as Task 4 and
  the PASS report §8 did. State the convention in the report; do not invent a new one.

**Synthetic population (Part C only):** a new high-N run, §4.3.

### 🔴 Privacy — NFR-021, read before writing a line of code

Parts A, B and D read live `ALL.TXT` containing **real off-air callsigns**. A live NFR-021 exposure
was found and closed on this repo yesterday. Therefore:

- **No message text, and no callsign, may be printed, logged, or written to any file** — including
  intermediate JSON and including anything under `results/`.
- Every extracted identity is **SHA-256 hashed (truncated) at first use**, exactly as
  `callsign_recurrence_proxy.py` already does. Copy that file's discipline; do not re-derive it.
- Outputs are **counts, fractions and CIs only.**
- Before committing anything, `git check-ignore -v` every output path — **confirm, do not assume** —
  and grep each file individually for callsign-shaped tokens.
- ⚠️ Harnesses on this repo have twice chosen output filenames the guards did not anticipate.
  **Write outputs to paths that already match an ignore rule, or add the rule first.**

---

## 3. ROW 0 — preconditions (all mechanical; evaluate in order, stop at the first VOID)

Per HK-021, each fires an assertion, not a description. Per HK-021(k)/HK-025, each can change the
verdict — if any row here cannot, QA should refuse it rather than run it.

| row | check | bar | consequence |
|---|---|---|---|
| **0a** | Internal join consistency, both legs: `both + ours_only == total_ours` and `both + theirs_only == total_theirs` | **exact equality** | any mismatch ⇒ **VOID**, do not evaluate any row |
| **0b** | Duplicate emission: `distinct (ts,message) == rows` on each leg | **exact equality** | duplicates corrupt every union/intersection count ⇒ **VOID**. (Scouting recorded exact equality on both legs — unlike `jt9`, these counts are honest.) |
| **0c** | 🔴 **Two-sided join sanity:** `both / union` | **must lie in `[0.10, 0.90]`** | outside ⇒ **VOID**. A broken hash-normalisation drives it toward 0; an over-permissive match drives it toward 1. **Both directions are detectable and both are checked** (HK-021(n)). Scouting value: **0.299**. |
| **0d** | Cluster floor in the analysis epoch | **≥ 500 distinct `ts`** | below ⇒ **VOID**. (Epoch carries ~4,600.) |
| **0e** | Bootstrap determinism | two independent full runs **mechanically diffed, byte-identical** | differ ⇒ **VOID**. 🔴 Diff them; never assert it. Sort every set at construction — hash-randomised set iteration has silently broken seeded determinism on this project before. |

**0c is the row that matters.** Ask of every other row: *if my instrument were broken, which way
would this number move, and does any row fire when it does?* (HK-021(n)). For `A` itself the answer
is that a one-sided parse failure drives it to 0 or 1 — which 0a and 0c both catch.

---

## 4. The three measurements

### 4.1 Part A — the asymmetry (PRIMARY, gated)

For the epoch population, on distinct normalised `(ts, message)`:

```
M_ours   = decodes WSJT-X made and OpenWSFZ did not      ("we missed")
M_theirs = decodes OpenWSFZ made and WSJT-X did not      ("they missed")

A = M_ours / (M_ours + M_theirs)
```

`A = 0.5` is symmetric disagreement — neither decoder dominates. `A → 1` is a genuine one-sided
deficit, which is what D-001 has been assumed to be. `A < 0.5` means the reciprocal loss is the
larger of the two.

Report `A` with a cluster-bootstrap CI95 over `ts`, plus `M_ours`, `M_theirs`, cluster counts, and
the achieved CI half-width.

**Stratified view — DESCRIPTIVE ONLY, never gated.** Report `A` within reference-SNR bins, each
half binned **on its own finder's SNR scale** (a WSJT-X-only decode has only WSJT-X's SNR; an
OpenWSFZ-only decode has only ours). This borrows R.D's correct construction and inherits its
limitation: the two halves are then not strictly comparable strata, so per HK-021(g) **the gate is
on pooled `A` and the stratified table is context.** Do not gate a row on it, and do not re-derive
bin edges inside strata.

### 4.2 Part B — is the reciprocal figure inflated by our own false positives? (gated)

E2 is Part A's one serious rival: if our exclusive decodes are largely junk, `A < 0.5` is
manufactured. There is **no oracle for a live band**, so this is a proxy — but a proxy with a
control that has never been built.

Task 4 (2026-08-04) measured singleton fraction — the share of distinct hashed identities seen in
exactly one cycle — for two populations: **ours-only 53.32%** vs **matched-in-both 16.64%**, a
+36.7 pp gap. It then correctly refused to draw a verdict, because *"weak DX heard once"* produces
the identical signature.

🔴 **The control that resolves that confound was never built: the WSJT-X-only set.** Build all
three arms:

```
S_both   = singleton fraction, matched-in-both
S_ours   = singleton fraction, OpenWSFZ-only
S_theirs = singleton fraction, WSJT-X-only        <-- the missing control

Delta_S = S_ours - S_theirs        (SIGNED, per HK-021(l) -- never |Delta_S|)
```

If an elevated singleton rate is a property of *being an exclusive decode* — marginal signals heard
once, by either decoder — then `S_ours ≈ S_theirs`, both well above `S_both`. If instead our
exclusives are junk, `S_ours` stands materially above `S_theirs`.

Reuse `callsign_recurrence_proxy.py`'s extractor and its hashing discipline verbatim; do not write
a second extractor. Cluster-bootstrap `Delta_S` over `ts`.

⚠️ **What Part B cannot do, stated in advance:** ROW B1 does **not** establish that our exclusive
decodes are real. It removes *FP asymmetry* as a **sufficient** explanation of Part A. Both
populations share the same best-effort extractor, so parsing noise inflates both — that is the
point of a difference statistic, and it is also its ceiling. Nothing here may be cited as an FP-rate
measurement.

### 4.3 Part C — does the metric manufacture a gap where an oracle says there is none? (gated)

Parts A and B have no oracle. Synthetic scenarios do: injected truth is known.

Compute, on the synthetic population, both statistics side by side:

```
recovery_ours   = injected messages recovered by OpenWSFZ / injected
recovery_theirs = injected messages recovered by WSJT-X   / injected
M_syn           = of the injected messages WSJT-X recovered, fraction OpenWSFZ did not
                  (the D-001 statistic, computed where truth is known)
```

🔴 **Part C requires a dedicated high-N run — the standing sweep cannot resolve its bar.** At the
sweep's own N (S4: 67 WSJT-X true positives; S8: 55 decodes) the 95% half-width on `M_syn` is
≈ 0.07, against a 0.10 bar. Per HK-021(m) **a cut the instrument cannot resolve is not a gate, it is
a coin flip with a threshold painted on it** — so do not attempt Part C on the existing sweep data.

Instead:

- Add `scenarios/s8hn-band-scene-highn.json`: **a copy of `s8-band-scene.json` with `id: "S8HN"`
  and `trials: 25`**, and one line in `run_study.py`'s `_SCENARIO_REGISTRY`. 🔴 **Do not modify
  `s8-band-scene.json` or S8's registry entry** — the ratified study must be left exactly as it is,
  and S8HN must not enter `_CONTROLLED_SCENARIO_IDS`.
- 12 stations × 25 trials = **300 injected messages per appraiser**; 95% half-width on `M_syn`
  ≈ 0.034 at `M_syn = 0.10`, which resolves the bar with room to spare.
- Cost is roughly one 15 s slot per trial: **on the order of 10–15 minutes**, not a sweep.
- ⚠️ `run_study.py --device` still defaults to `"CABLE Input"`, which is unreliable on this machine.
  **Pass `--device "Voicemeeter AUX Input"` explicitly.** Confirm `captureActive:true` and a live
  tone-injection RMS before arming — a WSL-built daemon silently ran `NullAudioSource` on this
  machine as recently as yesterday. Pin the DLL by **SHA256**, not `shimVersion`.
- Report the station-F result (1162 Hz) separately and **exclude it from `M_syn`'s primary
  denominator**, reporting `M_syn` both with and without it. Station F is a known, reproducible,
  seed-independent 0/5 across four sweeps; leaving it in silently would let one known defect carry
  the gate.

---

## 5. The gates

Rows within each part are **mutually exclusive and evaluated in strict order.** Each states an
assertion. Where a bar is a judgement rather than a derivation, this document says so.

### Gate A — pooled `A` (PRIMARY)

| row | condition | consequence (assertion) |
|---|---|---|
| **A1** | `CI_hi < 0.50` | The disagreement runs **in our favour**: WSJT-X misses more of our decodes than we miss of theirs. ⇒ **D-001's headline figure may not be quoted as a decoder-deficit magnitude in any subsequent proposal, report or board entry unless the reciprocal figure is quoted beside it.** The defect is not thereby closed — it is **re-scoped from "we are 43.8 pp worse" to "the two decoders agree on ~30% of a union neither dominates."** |
| **A2** | `CI_lo <= 0.50 <= CI_hi` | Symmetric disagreement; neither decoder dominates. Same citation restriction as A1, on weaker grounds. |
| **A3** | `CI_lo > 0.50` and `CI_lo <= 0.65` | A real but modest one-sided deficit. D-001 stands, at reduced magnitude; the reciprocal must still be quoted. |
| **A4** | `CI_lo > 0.65` | A genuine, large one-sided deficit. **D-001 stands exactly as framed** and the metric-artefact explanation is dead. |

**The 0.65 boundary is a judgement, not a derivation, and is declared as one.** At `A = 0.65` the
exclusive sets differ by ≈1.86×, the point below which both directions are of the same order and
"disagreement" is the honest word, and above which "dominance" is.

**Resolution (HK-021(m)), computed while drafting.** Naive binomial SE on `A` at the scouting counts
is 0.0021. With ~11 decodes per cycle and moderate intra-cluster correlation, expect a cycle design
effect of 3–4 ⇒ **SE ≈ 0.004–0.008, half-width ≈ 0.008–0.016.** The scouting point estimate (0.311)
sits **0.189 from the 0.50 bar — 12 to 24 half-widths.** This gate is decidable. 🔴 **If the achieved
half-width exceeds 0.05, say so and flag that the 0.65 boundary specifically was not resolvable**,
even though the 0.50 bar will still be.

**Predicted outcome, on the record: ROW A1, ~75%; A2 ~15%; A3 ~7%; A4 ~3%.**

### Gate B — `Delta_S` (governs how Gate A may be read)

| row | condition | consequence (assertion) |
|---|---|---|
| **B1** | `CI_hi < 0.10` | Our exclusive set's singleton signature is not materially worse than WSJT-X's own exclusive set. ⇒ **FP asymmetry is not a sufficient explanation for Gate A's result; Gate A may be read at face value.** |
| **B2** | `CI_lo <= 0.10 <= CI_hi` | Inconclusive. ⇒ **Gate A's row must be reported with this caveat stated in the same paragraph**, every time it is cited. |
| **B3** | `CI_lo >= 0.10` | Our exclusive set is materially more singleton-heavy than WSJT-X's. ⇒ **ROW A1/A2 may NOT be cited as evidence that D-001 is not a deficit.** The reciprocal figure is then suspect and the FP surge becomes the blocking question. |

**The 0.10 bar is a judgement, declared as one:** it is under 30% of Task 4's measured
ours-only-vs-matched contrast (+36.7 pp). Below it, the two exclusive sets are behaving alike
relative to the only calibration this proxy has.

### Gate C — `M_syn` on S8HN (oracle-backed)

| row | condition | consequence (assertion) |
|---|---|---|
| **C1** | `M_syn >= 0.10` **and** `recovery_ours >= recovery_theirs` | 🔴 **Demonstrated with an oracle: the D-001 statistic reports a substantial gap on data where absolute truth says we are not worse.** This is the strongest evidence available to this arm, because unlike A and B it does not depend on a proxy. ⇒ **The one-directional statistic is established as capable of manufacturing a gap, and no D-001 figure may be presented without its reciprocal.** |
| **C2** | `M_syn >= 0.10` **and** `recovery_ours < recovery_theirs` | The gap reproduces on synthetic audio **and** we are genuinely worse there. ⇒ **A bench-reproducible instance of D-001 exists** — which is a large prize in its own right, and supersedes this arm's framing. Report immediately; the programme should pivot to it. |
| **C3** | `M_syn < 0.10` | The metric does not manufacture a material gap at this N. ⇒ the artefact explanation weakens and **E4 (real-signal impairments) becomes the leading candidate.** |

Report `M_syn` both including and excluding station F, but **evaluate the gate on the F-excluded
figure** (§4.3).

### Reading order

Evaluate **B first, then A, then C.** B governs how A may be cited; C is independent of both. If
0a–0e VOID, evaluate nothing and report the VOID.

---

## 6. Part D — the scope check (gated, cheap, and 18 days overdue)

On 2026-08-05 the Architect wrote of the 29.9% agreement figure:

> *"May be a configuration difference on one leg (decode depth / passband / threshold) rather than
> genuine divergence. **If it is a config artefact, months of 'shortfall against WSJT-X' figures are
> measuring the wrong thing. Cheap to check. Not started.**"*

It is still not started. It is still cheap. Do it in this arm.

From `ALL.TXT` on each leg — 🔴 **field `[4]` is SNR, `[5]` is DT, `[6]` is frequency in Hz;
confusing 5 and 6 inverts the result** — compute:

```
band_ours = [P1, P99] of the frequencies of ALL OpenWSFZ decodes in the epoch
F_out     = fraction of WSJT-X-only decodes whose frequency falls OUTSIDE band_ours
```

and the same statistic on the DT axis (`T_out`, against `[P1, P99]` of our own decode DTs).

| row | condition | consequence (assertion) |
|---|---|---|
| **D1** | `F_out >= 0.10` **or** `T_out >= 0.10` | 🔴 **A material share of D-001 is a search-scope difference, not a decoding failure.** ⇒ The programme has a **configuration** lead, not a DSP one, and it is the cheapest fix available anywhere on this defect. Report which axis and the size. |
| **D2** | both `< 0.10` | Scope difference is not material; the misses sit inside the space we already search. ⇒ E3 is eliminated and D-001 is not a passband artefact. |

**Quantum (HK-021(o)):** WSJT-X reports frequency as **integer Hz** and our lattice is 3.125 Hz.
Both are negligible against a `[P1, P99]` span of hundreds of Hz — **state the quantum in the report
and state that it is negligible here**; do not silently rely on it.

**Resolution:** at `M_ours` ≈ 15,671 the binomial half-width on `F_out` is well under 0.01 even with
a design effect of 4. Decidable.

⚠️ **D1 and D2 are exhaustive and mutually exclusive.** D1's "or" is deliberate: either axis alone
is a finding.

---

## 7. 🔴 What was already measured, in full — the disclosure of §0

The bars above were set knowing all of this. It is Architect **scouting** work — whole-corpus,
unstratified, un-SNR-matched, outside any pre-registered rule — and **may not be cited as a verdict
by this arm or any other.** It is disclosed so QA can judge the bars, exactly as C-GAP-D disclosed
its own drafting-time numbers.

**Live reciprocal, `20260803_live_run_1713`, decisive epoch (2026-08-05):**

| quantity | value |
|---|---:|
| OpenWSFZ decodes | 56,202 |
| WSJT-X decodes | 37,158 |
| Both | 21,487 |
| OpenWSFZ only | 34,715 |
| WSJT-X only | 15,671 |
| of WSJT-X's, we missed | **42.2%** |
| of ours, WSJT-X missed | **61.8%** |
| agreement (both / union) | **29.9%** |
| ⇒ implied `A` | **0.311** |

**Task 4 recurrence proxy (2026-08-04), full corpus:** ours-only singleton fraction **53.32%**
(7,357 identities) vs matched-in-both **16.64%** (3,335 identities); median cycles/identity 1 vs 4.
**No WSJT-X-only arm was built** — that is Part B's contribution.

**Synthetic, 2026-08-22 sweep:** S8 55/60 both appraisers; nine clean stations **45/45** for
OpenWSFZ spanning −15…+3 dB; 1500 Hz capture pair ours **10/10** vs theirs 5/10; station F
(1162 Hz, 12 Hz from E) **0/5 for the fourth consecutive sweep** while WSJT-X takes it 5/5. S4
recovery 62.04% vs **64.81%**; decodable-restricted 70.37% vs **76.54%**. S1b as tabulated in §0.

**C-GAP-D (2026-08-22):** `G(3)_pp` = 6.995, CI95 `[6.897, 7.172]`, ROW 1 — extraction quality can
reach at most ~16% of the gap. **This arm does not reopen that and does not depend on it**; it asks
about the other ~84%, which C-GAP-D explicitly left unnamed.

---

## 8. What this arm does NOT do

- **It does not test E4** (fading, Doppler spread, transmitter drift, timing spread). That needs
  generator work and is deliberately sequenced after E1–E3. **ROW C3 is the row that authorises
  opening it**, and nothing else here does.
- **It does not claim our exclusive decodes are real.** No oracle exists for a live band; Part B is
  a proxy with a control, not a measurement (§4.2).
- **It does not measure absolute decoder quality**, on either audio. `A` is a statement about the
  *shape* of the disagreement, not about who is better.
- **It does not reopen C-GAP-D, ROW 0g, or Route B2**, and nothing in it may be read as reviving the
  coherent-LLR line as a D-001 treatment.
- **It does not subsume arm R.D**
  (`qa/cycleframer-alignment-replay/2026-08-05-1459-architect-to-qa-spec-reciprocal-density-asymmetry.md`,
  specced `07cbd1b`, never run, never authorised). R.D asks whether the *density penalty* is ours or
  dense-20m's — a different question. R.D remains available and unrun.
- **It does not investigate station F.** That is a separate, cheap, deterministic lead and deserves
  its own pre-registration rather than a passenger seat here.

---

## 9. Handover

Report to `qa/rr-study/2026-08-23-XXXX-qa-to-architect-c-asym-a-results.md` (timestamp from
`date -u`, HK-017). Report cluster counts beside every row count; report slope/CI/p rather than any
bare correlation; report the achieved CI half-width for every gated statistic.

**QA stops at the gate.** No push, no merge, no `pre_merge_check.py` — that runs on the Captain's
initiative only.

🔴 **QA may refuse any ROW 0 in §3 on HK-021(k)/HK-025 grounds without Architect agreement.**
Classify each as validity or precision, evaluate both branches, and if the verdict is the same
either way the row is diagnostic-only — name it, stop, and do not run a partial arm. Several recent
Architect-authored specs have carried a gate defect that QA's arithmetic caught after the fact;
catching this one before the run is worth more than the run.
