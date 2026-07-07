# D-001 Option B — Co-Channel Attribution Pass: Results Report

| Field | Value |
|---|---|
| Defect ID | D-001 (open, issue #3) |
| Type | Offline log-analysis decision gate (no product/decoder/shim code touched) |
| Governing spec | `dev-tasks/2026-07-07-d001-b-cochannel-attribution-spec.md` |
| Work order | `dev-tasks/2026-07-07-d001-b-cochannel-attribution-HANDOFF.md` |
| Analysis date | 2026-07-07 |
| Repo HEAD at analysis time | `b4bdf88` |
| Sessions analysed | 07-07 (`20260706_live_run_2308`, shim 20260033) · 07-06 (`20260706_live_run`, shim 20260031) · 06-22 (`20260622_live run`, shim 20260029) — all three ALL.TXT pairs survived; no corroboration gap |
| Classification script | `classify_cochannel.py` (this directory); numeric results in `cochannel_classification_results.json` |
| Status | **COMPLETE — verdict delivered below** |

---

## Section 1 — Study Hypothesis

### 1.1 What this pass answers

QA's H7-scoping caveat (`dev-tasks/2026-07-07-d001-h7-mmse-scoping-arch.md`) left the headline
D-001 SNR-stratified recall gap undecomposed: we knew OpenWSFZ under-recalls WSJT-X in the
low-SNR bands, but not what fraction of that gap is **co-channel** (the failure mode MMSE joint
demodulation targets) versus **isolated-weak** (a sensitivity problem MMSE cannot fix). This
pass — **Option B** — resolves that caveat using only already-retained `ALL.TXT` decode logs
from three live sessions. No WAV re-decode, no live session, no product code change.

**The question, precisely:** of the low-SNR decodes WSJT-X recovered and OpenWSFZ missed, what
fraction had a same-slot neighbour close enough in frequency to plausibly be a co-channel
interferer? That fraction, **F**, is the ceiling on what H7 can buy.

### 1.2 Method summary (full detail in the governing spec)

1. Reuse the existing endurance recall matcher (slot + 50 Hz-binned frequency + text) to build
   the WSJT-X-only miss set, excluding hashed (`<...>`) messages, restricted to WSJT-X SNR bands
   `< −15 dB` and `−15…−10 dB` (the bands the gap concentrates in).
2. For every miss, find its nearest same-slot neighbour in the **union** of both apps' raw
   decode lists (a co-channel interferer may have been decoded by only one app).
3. Classify by Δf to that neighbour: **Tight** (≤ 15 Hz, primary cutoff) / **Partial**
   (15–50 Hz) / **Isolated** (no neighbour ≤ 50 Hz).
4. **F = Tight / total classified misses.** F′ = (Tight + Partial) / total is reported as an
   optimistic secondary bound, not the decision metric.
5. Rigour controls per spec §5: a 5-point window sweep of the tight cutoff (10/12/15/20/25 Hz),
   an explicit downward-bias statement, a classification rule that never conditions on the
   miss's own SNR, and a capture-effect sub-check within the Tight class.

### 1.3 Pre-committed decision thresholds (Captain-locked, not reopened here)

| F | Verdict |
|---|---|
| ≥ 0.60 | Gap predominantly co-channel → recommend H7 scoping (contingent on s7 K=10 restore, spec §6) |
| ≤ 0.30 | Gap predominantly isolated-weak → do not scope H7 |
| 0.30 < F < 0.60 | Mixed → Captain decides, weighing recoverable-recall estimate against 3–6 month cost |

### 1.4 Null hypothesis

**H₀:** The co-channel-attributable fraction F of the low-SNR WSJT-X-only miss set is high
enough (≥ 0.60) that a perfect MMSE joint demodulator would close the majority of the D-001 gap,
independently confirmed across three sessions and stable under reasonable Δf-cutoff choices.

---

## Section 2 — Data Summary

### 2.1 Inputs

All three sessions' `OpenWSFZ ALL.TXT` / `WSJT-X ALL.TXT` pairs were present on disk (Gate 0
passed with no corroboration gap — better than the spec's worst case, which only guaranteed the
07-07 primary session).

| Session | Shim | OpenWSFZ lines | WSJT-X lines |
|---|---|---|---|
| 2026-07-07 | 20260033 | 48,028 | 76,920 |
| 2026-07-06 | 20260031 | 47,013 | 75,193 |
| 2026-06-22 | 20260029 | 33,123 | 50,450 |

### 2.2 Matcher cross-validation

The miss-set construction (slot + 50 Hz freq bin + text, non-hashed) was cross-checked against
the independently-produced `qa/endurance/2026-07-07-bb0a1c4/report.md` SNR-band recall table for
the 07-07 session. The `< −15 dB` band total (3,295 + 7,332 = 10,627) and the `−15…−10 dB` band
total (11,406) match this script's output **exactly**, and the derived miss counts (7,518 and
6,344 respectively) are consistent with that report's published recall percentages. The
classification layer is built on a matcher already proven correct by an independent report.

### 2.3 Miss-set sizes (low-SNR bands, non-hashed)

| Session | `< −15 dB` miss / total | `−15…−10 dB` miss / total | Pooled miss / total |
|---|---|---|---|
| 07-07 | 7,518 / 10,627 | 6,344 / 11,406 | 13,862 / 22,033 |
| 07-06 | 6,263 / 9,083 | 5,448 / 9,574 | 11,711 / 18,657 |
| 06-22 | 4,403 / 6,445 | 3,644 / 7,000 | 8,047 / 13,445 |
| **Combined** | **18,184 / 26,155** | **15,436 / 27,980** | **33,620 / 54,135** |

---

## Section 3 — Results

### 3.1 Classification at the primary cutoff (Tight ≤ 15 Hz)

| Session | Tight | Partial | Isolated | Total | **F** | F′ |
|---|---|---|---|---|---|---|
| 07-07 | 3,879 | 6,295 | 3,688 | 13,862 | **28.0%** | 73.4% |
| 07-06 | 3,747 | 5,373 | 2,591 | 11,711 | **32.0%** | 77.9% |
| 06-22 | 2,330 | 3,760 | 1,957 | 8,047 | **29.0%** | 75.7% |
| **Combined** | **9,956** | **15,428** | **8,236** | **33,620** | **29.6%** | **75.5%** |

The three independent sessions cluster tightly (28.0–32.0%) and straddle the 0.30 "do not
scope" boundary — two sessions fall just below it, one just above. This is the first sign that
the primary-cutoff point estimate alone is not a safe basis for a clean verdict.

### 3.2 Window-sensitivity sweep (combined, all sessions pooled)

| Tight cutoff | Tight | Partial | Isolated | **F** |
|---|---|---|---|---|
| 10 Hz | 7,435 | 17,949 | 8,236 | 22.1% |
| 12 Hz | 8,370 | 17,014 | 8,236 | 24.9% |
| **15 Hz (primary)** | **9,956** | **15,428** | **8,236** | **29.6%** |
| 20 Hz | 12,467 | 12,917 | 8,236 | 37.1% |
| 25 Hz | 15,021 | 10,363 | 8,236 | 44.7% |

**The §3 verdict flips inside the sweep.** At the tighter end (10/12/15 Hz) F sits at or below
0.30 (the "do not scope" branch); at the wider end (20/25 Hz) F lands solidly in the 0.30–0.60
"mixed" band. F never approaches 0.60 at any point in the sweep, so "recommend H7 scoping"
(F ≥ 0.60) is never in play. Per the HANDOFF's pre-committed escalation rule (§3, "Verdict flips
inside the window sweep → report as inconclusive → mixed-case path; do not pick a side to force
a clean answer"), this sweep result — combined with the session-to-session straddle in §3.1 — is
**inconclusive between "do not scope" and "mixed,"** which the rule resolves to the mixed-case
path.

### 3.3 Error direction (spec §5.2)

The classifier can only see neighbours that were *decoded* by one of the two apps. A miss tagged
"isolated" may in fact have had an interferer neither app decoded (too weak, or itself another
casualty of the same demodulation limitation). This biases F **downward** — the true co-channel
fraction is very likely higher than measured. Applied to §3.1's result: the measured 29.6% is a
floor, not a ceiling. This further undermines confidence in a "do not scope" call and reinforces
the mixed-case reading — a result that is *already* on the wrong side of 0.30 before accounting
for the bias would need a materially larger safety margin to survive it.

### 3.4 Capture-effect sub-check (within Tight class, combined)

| Metric | Value |
|---|---|
| Tight-class misses (n) | 9,956 |
| Mean SNR delta (nearest neighbour − miss), 07-07 / 07-06 / 06-22 | 6.28 / 6.24 / 6.89 dB |
| Median SNR delta (all sessions) | 7.0 dB |
| Misses with delta ≥ 10 dB ("captured by a much stronger partner") | 3,626 (36.4%) |

Just over a third of Tight-class misses show the textbook capture-effect signature — the missed
signal sat within 15 Hz of a neighbour reported ≥ 10 dB stronger. This is consistent evidence
that within the Tight subset, a real co-channel/capture mechanism (not noise) is driving misses —
the mechanism MMSE joint estimation is designed to address. It does not, however, change F itself
or move the headline verdict; it corroborates that the Tight bucket is measuring the right thing.

### 3.5 Recoverable recall — upper bound (spec §4.4)

| Session | Tight (recoverable) | WSJT-X total in bands | Upper-bound pp |
|---|---|---|---|
| 07-07 | 3,879 | 22,033 | 17.61 pp |
| 07-06 | 3,747 | 18,657 | 20.08 pp |
| 06-22 | 2,330 | 13,445 | 17.33 pp |
| **Combined** | **9,956** | **54,135** | **18.39 pp** |

This is a **ceiling**, not a forecast: it assumes a hypothetical perfect MMSE implementation
recovers every single Tight-class miss. A real implementation recovers a fraction of these. Set
against the Architect's 3–6 month H7 estimate (`qa/rr-study/results/d009-investigation-2026-06-21/report.md`
§5.2), even the generous ceiling implies roughly **2–4 engineering-weeks per recall percentage
point** in the affected low-SNR bands — and the true cost-per-point is higher than this floor,
since no real implementation reaches the ceiling.

---

## Section 4 — Verdict Table

| Check | Result |
|---|---|
| Gate 0 (data availability) | PASS — all three sessions, no corroboration gap |
| Matcher cross-validation | PASS — exact match to independently-produced endurance report |
| F at primary cutoff (combined) | 29.6% (Tight 9,956 / 33,620) |
| F range across window sweep | 22.1% – 44.7% |
| F per-session at primary cutoff | 28.0% / 32.0% / 29.0% — straddles the 0.30 boundary |
| Verdict stability | **FAILS to stabilise** — flips between "do not scope" and "mixed" across the sweep and across sessions |
| Error-direction bias | Downward (true F likely > measured) — works against "do not scope" |
| F′ (optimistic bound) | 75.5% — substantial "maybe" mass in the Partial bucket |
| Capture-effect corroboration | 36.4% of Tight misses show ≥10 dB delta to nearest neighbour — real mechanism, not noise |
| Recoverable recall (ceiling) | 18.39 pp combined, at ~2–4 eng-weeks/pp under the most generous assumption |

**§3 branch selected: 0.30 < F < 0.60 — "Scope-with-a-price-tag decision."** The pre-committed
escalation rule for an inconclusive sweep resolves ties toward the mixed path rather than a
coin-flip pick, and both the per-session straddle (§3.1) and the known downward bias (§3.3)
independently point the same direction: away from "do not scope" and toward "mixed." **F never
approaches the 0.60 threshold at any point tested**, so "recommend H7 scoping" outright is not
supported by this evidence either.

---

## Section 5 — Recommendations

### 5.1 One-paragraph recommendation to Architect and Captain

The co-channel-attributable fraction of the D-001 low-SNR miss set is **F ≈ 29.6% (combined),
ranging 22–45% across a reasonable Δf-cutoff sweep and 28–32% across three independently
corroborating sessions** — a result that straddles rather than clears the pre-committed 0.30 "do
not scope" threshold, and which the HANDOFF's own inconclusive-sweep rule therefore resolves to
the **mixed-case, scope-with-a-price-tag branch** rather than either clean outcome. Recommend
against outright rejecting H7 (F never reaches even the "do not scope" band with real margin, and
the classifier's inherent downward bias means the true fraction is probably somewhat higher than
measured) and equally against unconditional H7 approval (F comes nowhere near the 0.60
co-channel-dominant threshold at any tested cutoff). The decision the Captain must make is a
cost/benefit one: a perfect H7 implementation would recover **at most ≈18.4 recall percentage
points** in the affected low-SNR bands, against a 3–6 month estimated build — roughly 2–4
engineering-weeks per point at that ceiling, with real recovery certain to be lower. The
capture-effect sub-check (36.4% of Tight misses show a ≥10 dB stronger co-channel partner)
corroborates that the mechanism MMSE targets is genuinely present in the Tight bucket, which
should weigh in favour of scoping if the Captain's cost appetite allows it — but that is a
product-priority call this analysis cannot make.

### 5.2 What this pass does NOT authorise

Per the HANDOFF's explicit boundaries: no H7 OpenSpec proposal, no s7 harness change, no
re-opening of the three endurance conclusions, and — because F lands in the mixed band, not the
≥0.60 band — the spec §6 harness precondition (restore s7 to K=10, make co_channel/near_collision
the primary regression oracle) is **not yet triggered**. It remains noted for whenever a Captain
decision moves this toward Option A.

### 5.3 Suggested next step

Present this report to the Captain for the scope-with-a-price-tag decision. If the Captain elects
not to proceed given the ≤18.4 pp ceiling and 3–6 month cost, the natural redirect (per spec §3's
"do not scope" branch, since the low end of the sweep sits there too) is sensitivity remedies
(matched-filter / soft-decision / additional LDPC-OSD depth) or Option C (disclosed product
limitation) — both cheaper avenues that a mixed-but-borderline F does not rule out.

---

## Appendix A — Reproduction

```
cd qa/rr-study/results/2026-07-07-b4bdf88-d001-cochannel-attribution
python classify_cochannel.py
```

Reads directly from the local, git-ignored `artefacts/` tree (paths hard-coded per session).
Writes `cochannel_classification_results.json` (aggregate counts only) alongside this report.

---

**NFR-021 compliance:** This report and `cochannel_classification_results.json` contain **no
callsigns and no message text** — only aggregate counts, fractions, and SNR-delta statistics
derived from the local `ALL.TXT` logs. The raw `ALL.TXT` files themselves are not committed
(`artefacts/` is git-ignored in its entirety per `.gitignore`, independent of this analysis) and
are not referenced by content anywhere in this directory.
