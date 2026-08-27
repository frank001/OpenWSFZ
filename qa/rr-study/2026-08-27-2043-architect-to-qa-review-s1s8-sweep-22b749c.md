# Architect → QA — Review of the S1–S8 full sweep, 2026-08-27 (`22b749c`)

**Author:** Architect, 2026-08-27 20:43Z (`date -u`, HK-017).
**Subject:** `qa/rr-study/results/2026-08-27-22b749c/report.md` (commit `f869782`, local, unpushed).
**Status:** Review COMPLETE. Overall verdict **PASS is upheld**. Four corrections requested
(R1–R4), one of which requires withdrawing a stated finding. A fifth section (R5) answers a
question raised by the PO on reading the sweep, and in my judgement is the most important
thing in this document.

---

## 0. Method — what I re-derived, and what I took on trust

Per HK-022, I did not review this report by re-reading its own claims. I rebuilt its principal
numbers from the matched CSVs with an independent script and compared:

| Quantity | Report | My re-derivation | Agrees |
|---|---|---|---|
| S5 FP events, this run (both appraisers) | 0 / 60 | 0 / 60 | ✅ |
| S5 FP events, 08-22 OpenWSFZ | 4 / 120 | 4 / 120 | ✅ |
| 08-22 FP events falling in S5 parts 0+1 | "all 4" | 4 (3 in P0, 1 in P1) | ✅ |
| κ OpenWSFZ-vs-truth, this run | 0.588 | 0.588 | ✅ |
| κ OpenWSFZ-vs-truth, 08-22 / 08-21 | 0.625 / 0.687 | 0.625 / 0.687 | ✅ |
| S7 OpenWSFZ "all" recovery | 78.60% | 169/215 = 78.60% | ✅ |
| `src/` identical `2ae939c` vs `22b749c` | asserted | `git diff --stat` empty; only `RUNBOOK.md` differs | ✅ |
| matched CSVs / ALL.TXT gitignored | asserted | `git check-ignore -v` confirms (`.gitignore:162,164`) | ✅ |

Reproducing κ to three decimals is what licenses R1 below: the same script that matches the
analyser's output is the one that shows the finding is confounded.

**Not independently checked:** the live capture itself, the WSJT-X profile, the `libft8.dll`
SHA256, and the NativeAOT/WASAPI crash. These are taken as reported.

---

## 1. What the report gets right, and should be credited with

**The headline is sound, and it is sound for the right reason.** The S5 gate recovering
from a ratified FAIL in the same sweep that R&R-009 halved N from 120 to 60 is exactly the
shape of result that is usually an artefact. QA anticipated that and pre-empted it with the
correct check: were last sweep's 4 events inside the 60 slots the new battery still covers?
I verified this independently — all 4 were (3 in part 0, 1 in part 1). So the comparison is
**4/60 → 0/60 on identical ground**, not 4/120 → 0/60. That is the difference between a
finding and an artefact, and QA got it right unprompted.

**One piece of calibration to add, not a correction.** 4/60 → 0/60 is Fisher exact
p = 0.119 two-sided (0.059 one-sided). The improvement is real but not statistically strong
on its own. The report's chosen posture — "resolved for now rather than closed" — is
therefore correct and should not be upgraded on this evidence.

**The mid-run process incident is handled to the standard I want.** Root cause correctly
localised (`run_scenario.py` deriving its run directory from live `HEAD` per invocation
rather than being handed one by `run_study.py`), the fix correctly identified, disclosed in
the report's own Section 1 rather than a footnote, and the data-integrity argument
(schema-identical, zero scenario-ID overlap) is the right argument. Catching the NativeAOT
WASAPI crash *before* arming rather than after is also good discipline.

---

## 2. R1 — WITHDRAW the S4/S5 pooled-κ decline finding (H₀-D)

**Severity: material. This is a stated finding that does not survive its own confound.**

The report rejects H₀-D on a "third consecutive decline" in OpenWSFZ-vs-truth κ:
0.687 → 0.625 → **0.588**, and calls it "a real pattern, not obviously noise."

The pooled κ population is *S4 positives + S5 negatives*. R&R-009 cut the S5 negatives from
120 to 60 **in this run**. Those negatives are all correctly classified (specificity 100%),
and easy true-negatives inflate κ. Removing 60 of them lowers κ mechanically, with no change
in decoder behaviour whatsoever. The report caveats this N change carefully for the S5 gate,
and then does not carry the caveat into a finding computed over the same slots.

Recomputed with all three sweeps on the same 60-negative basis:

| Sweep | κ as reported | κ like-for-like (60 neg) | 95% CI (like-for-like) |
|---|---|---|---|
| 08-21 | 0.687 | 0.596 | [0.49, 0.71] |
| 08-22 | 0.625 | 0.516 | [0.40, 0.64] |
| 08-27 (this) | 0.588 | **0.588** | [0.48, 0.70] |

Not a monotonic decline — a dip at 08-22, driven by that sweep's 4 FP events, and a
**recovery to the 08-21 level**. WSJT-X behaves the same way like-for-like (0.558 → 0.539 →
0.568, flat).

**Robustness (the obvious objection, pre-empted).** If I had happened to drop the two
"hard" parts, the drop would be about part identity, not N. Restricting to parts **2+3**
instead of 0+1 gives the same effect: 08-21 0.687 → 0.609, 08-22 0.625 → 0.568. The drop
tracks the sample size, not which parts were kept.

**Second, independent reason the finding fails.** Even taking the reported figures at face
value with no correction at all, their CIs overlap heavily — the report prints
[0.48, 0.69] for this run and compares point estimates across sweeps without ever testing
whether the differences clear their own intervals. They do not. There was no detectable
trend to reject H₀-D on, before the confound is even considered.

**Requested change.** Withdraw the finding; restate H₀-D as **not evaluable across the
R&R-009 N change**. Recommend to the Captain that pooled κ be computed on a **fixed
negative count** going forward, or it will remain non-comparable to all eleven prior sweeps.

**What should NOT be lost in the withdrawal.** κ was obscuring the real number in both
directions. OpenWSFZ's *recovery* on S4 is 66.67% (72 TP / 36 FN). That is the figure worth
attention, and it is unaffected by any of the above.

---

## 3. R2 — S8 per-station table silently merges two stations (harness defect)

**Severity: material. Presentation only — the overall S8 rate is unaffected — but it hides
the single most interesting result in S8.**

`harness/analyse.py:1201` builds the station map as `dict[float, str]` keyed on frequency,
and `:1218` groups the breakdown by *unique frequency*. Stations **G and H are both at
1500 Hz** — that is the entire point of them; they are the capture pair
(`scenarios/s8-band-scene.json`, signals[6] and [7], 0 dB and −6 dB).

Consequences, all three confirmed by reading the code and the data:

1. `station_map[1500.0]` is overwritten — G is invisible, the row is labelled **H**.
2. `snr_db` comes from `.iloc[0]` — the row prints **0.00 dB, which is G's level**, not H's.
3. The counts are **pooled across both stations** (hence "8/10" and "10/10" in a table where
   every other row is out of 5).

So the printed row `| H | 1500 | 0.00 | 8/10 | 10/10 |` carries H's label, G's SNR, and both
stations' data. The report also states "12 simultaneous stations" above a table with 11 rows.

Resolving by `(freq, snr)` recovers what the table destroyed:

| Station | Freq | SNR | WSJT-X | OpenWSFZ |
|---|---|---|---|---|
| G | 1500 Hz | 0 dB | 5/5 | 5/5 |
| H | 1500 Hz | −6 dB | **3/5** | **5/5** |

**WSJT-X's only two S8 misses are both on the weak member of the capture pair, and OpenWSFZ
beats it there 5/5.** That is the one place in S8 where OpenWSFZ outperforms the reference,
and the table cannot show it. It also stands in apparent tension with S7's capture result
(OpenWSFZ 25% on weak capture signals) — see R5, where that tension turns out to be the
most informative thing in the sweep.

**Requested change.** Group per-station on `(freq_hz, snr_db)` or on the scenario's signal
index rather than frequency alone; same for the PNG, which inherits the same 11 bars. This
is `qa/` harness tooling — no Developer session required (HK-011), and it can ride along
with the run-dir pin fix already recommended.

---

## 4. R3 — the Station F recommendation is stale (HK-018)

**Severity: moderate. The report asks for work that was already done four days ago.**

Section 5 states Station F has been "queued for a targeted look twice already and still not
actioned," and Recommendation 2 asks that it "actually get the targeted look."

It got one. `qa/rr-study/2026-08-23-1214-qa-to-architect-f-nbr-a-results.md` (F-NBR-A,
2026-08-23) ran it and largely answered it:

- **C1 — cause established, not merely correlated.** Removing station E, nothing else
  changed, flips F from **0/100 to 100/100**. E is necessary and sufficient in this scene.
- **C2 — footprint measured.** Complete exclusion holds through 3 tone bins (18.75 Hz),
  sharp transition at 4 bins (25 Hz, 27%), resolved by 5 bins (31.25 Hz, 98%).
- **C3 — level dependence measured.** A ~3 dB knife-edge: F recovers 100/100 the instant it
  is 3 dB stronger than E, 0/100 when merely equal.
- **Gate A fired A2** — the locus is **extraction**, not candidate selection.

The report contains zero mentions of F-NBR-A. The mitigating explanation is structural: this
sweep is a separate Captain-directed thread, and F-NBR-A belongs to the D-001 line. That is
precisely the situation HK-018 exists for, and it is why the rule says to open the existing
findings before writing a recommendation.

**Requested change.** Re-point the recommendation. The open question is no longer "why does
F fail" — it is C2's residual: whether the 3–5 bin footprint is a tile boundary or a
comb/leakage effect, and then a fix. Asking for a fourth "look" wastes the three that
happened.

---

## 5. R4 — %Tolerance rows print a verdict belonging to a different number

**Severity: minor, but it is a trap for future readers.**

`harness/analyse.py:1880` renders the %Tolerance value beside
`_verdict_grr(metrics["pct_contribution_grr"])` — that is, the verdict is computed from
**%Contribution** and printed next to **%Tolerance**. This is why S3 reads
`| %Tolerance (GR&R) | 89.79% | PASS |`. The gate itself is correct — %Contribution is the
§10-ratified metric — but under AIAG conventions an 89.79% %Tolerance next to the word PASS
will be read as a passing tolerance figure by anyone who was not in this conversation.

**Requested change.** Either render the verdict against the number it belongs to, or label
the column so the pairing is explicit (e.g. `Verdict (on %Contribution)`).

---

## 6. R5 — On "little to no progress in application performance" (PO-raised)

The PO's remark on reading this sweep was that there has been little to no visible progress
in the application's performance despite what has been promised. **I checked it against the
trend rather than answering from impression, and the PO is substantively correct.** I also
think the data says something more useful than "we are stuck," so both halves follow.

### 6.1 The remark is correct

From the report's own Section 6 trend table, OpenWSFZ's decode figures since the D-009 fix
(2026-06-20):

| Sweep | 06-20 | 06-22 | 07-04 | 08-05 | 08-15 | 08-21 | 08-22 | 08-27 |
|---|---|---|---|---|---|---|---|---|
| S7 recovery | 70.2 | 74.4 | 73.0 | 70.2 | 74.4 | 68.4 | 79.5 | 78.6 |
| S8 decode rate | 86.7 | 86.7 | 86.7 | 83.3 | 86.7 | 83.3 | 91.7 | 91.7 |

Over ten weeks and eight full sweeps, S7 has oscillated in a 68–80% band with no trend that
clears its own scatter, and S8 has moved by three messages out of sixty. The gap to the
reference decoder remains **19.1 pp on S7** and **5.0 pp on S8**. The large early gain
(47% → 70% on S7) is D-009, in June. Nothing since has moved the needle on yield.

This is not for want of effort: 128 commits have touched `src/` or `native/` since 06-20.
But almost all of the decode-path work in that window — the M, N, P, B-phase, gap-census and
G2(a) arms — produced **diagnostic exports and instruments**, not shipped decode changes.
Several arms were VOIDed or withdrawn outright. The F-001 line, including the slice merged
immediately before this sweep, is QSO/callsign parsing and does not touch decode yield at
all. So a sweep run right after that merge was never going to show a performance change, and
the report is right that it is a status check rather than a regression test — but that also
means **this sweep is not evidence that the performance work is progressing, and it should
not be read as such.**

### 6.2 What the data says that is more useful than "stuck"

I attributed every one of OpenWSFZ's 46 S7 misses to its part, and the result is striking:

| Miss family | Misses | ΔF |
|---|---|---|
| Near-neighbour with level deficit (P12, P13, P14) | 15 | 7–11 Hz |
| Near-neighbour at equal level (P4, P15) | 11 | 5–6 Hz |
| 3-stack co-channel (P2 — structural, Captain-waived 06-22) | 15 | 19 Hz |
| Co-channel 2-stack (P0, P1) | 5 | 7–13 Hz |
| **Everything else** | **0** | — |

**All 46 misses occur at frequency separations between 5 and 19 Hz.** Every part at
ΔF ≥ 25 Hz decodes 10/10. And on S8, all 5 of OpenWSFZ's misses are station F — 12 Hz from
its neighbour. The deficit is not diffuse across the decoder; it is concentrated in one
narrow band of frequency separation.

That band is *the same one F-NBR-A independently measured* on a different harness: complete
exclusion through 18.75 Hz, resolved by 31.25 Hz. Two instruments, two scenarios, same zone.

Separation alone is not sufficient to cause failure — several parts inside that band decode
10/10 — which matches F-NBR-A's C3 finding that within the zone, **level ratio** decides.
And this sweep contributes a genuinely new data point that F-NBR-A's sweep could not, because
it started at 6.25 Hz: the S8 G/H pair at **ΔF = 0 Hz, −6 dB down, recovers 5/5** (R2 above),
while S7's P12 at **ΔF = 9 Hz, −6 dB down, recovers 0/5**. Same level deficit, opposite
outcome, distinguished only by whether the signals share a tone bin exactly or overlap it
partially. That is a mechanism clue, and it is the tension R2's collapsed table was hiding.

### 6.3 What I conclude, and what I am not claiming

**Conclusion.** The performance plateau is real, and the PO is right to call it out. But the
reason is not that the defect is elusive. We have a reproducible, causally-established,
level-and-separation-characterised decode defect with its locus already narrowed to
extraction — and it plausibly accounts for **all 5 S8 misses and 26–41 of the 46 S7 misses**.
The bottleneck has not been diagnosis for some weeks now. It has been that the diagnosis has
not been converted into a fix, while the investigation opened further arms and the sweep
reports kept re-queuing the same "targeted look."

**What I am not claiming.** I have not shown that one fix closes the gap; P2's 3-stack case
is structural and separately waived, and the equal-level failures (P4, P15) may be a
different mechanism from the level-deficit ones. Per-part N is 10–15 messages, so the
attribution table is a concentration argument, not a per-part significance claim. And
F-NBR-A's C2 explicitly left the mechanism question open.

**Recommendation to the PO and Captain.** Treat the near-neighbour exclusion zone as the
named performance work item, and scope it as a *fix* rather than another measurement arm.
If the Captain wants one more arm first, the highest-value one is cheap and now well-posed
by 6.2: sweep ΔF from 0 Hz upward at fixed −6 dB, which the existing F-NBR-A harness
(`qa/rr-study/f-nbr-a/`) can do nearly as-is, and which would establish whether the Δ = 0
survival is the general rule and where the zone actually opens.

---

## 7. Actions

### For QA (this report, `f869782`, local and unpushed — cheap to correct now)

1. **R1 — withdraw the κ decline finding**, restate H₀-D as not evaluable across the
   R&R-009 N change, and add the like-for-like table from §2. *(Required — a stated finding
   is confounded.)*
2. **R2 — fix the S8 per-station grouping** in `analyse.py` (`:1201`, `:1218`) and
   regenerate the S8 section and PNG. Ride it along with the already-recommended run-dir pin.
3. **R3 — re-point the Station F recommendation** at F-NBR-A's residual question, and
   cross-reference `2026-08-23-1214-qa-to-architect-f-nbr-a-results.md`.
4. **R4 — fix the %Tolerance/verdict pairing** at `analyse.py:1880`.
5. Add the Fisher figure from §1 to the S5 finding so its strength is on the record.
6. File the NativeAOT/WASAPI publish crash as a dev-task rather than leaving it in a report
   section — it is a real build defect and will be lost there.

### For the Captain / PO (decisions, not QA's to take)

7. **Ratify or reject a fixed negative count for pooled κ.** Until then the metric is
   non-comparable across the R&R-009 boundary and should not carry findings.
8. **Scope the near-neighbour exclusion fix** (§6.3) — fix, or one final bounded arm.
9. **Station F** — confirm it moves from "queued for a look" to owned work.

### Not requested

The **overall PASS stands.** All three ratified §10 gates clear on numbers I re-derived
myself. None of R1–R4 changes a gate outcome; R1 removes a finding, R2–R4 correct
presentation and tooling.

---

## 8. Standing-rule notes

- **HK-014** — this document is docs-only and committed locally. Nothing pushed, no merge.
- **HK-015** — this is Architect → QA. It authorises no `src/` change; any harness fix is
  QA's to make under HK-011's qa-tooling exception, and any decode fix needs a Developer
  session and Captain sign-off.
- **NFR-021** — this document contains no callsign text; the station identifiers (A–L) are
  synthetic scenario labels, and all quoted figures are counts, frequencies and levels.
