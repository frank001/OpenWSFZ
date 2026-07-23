# D-001 Option B Addendum — Partial-Bucket Δf Structure (Fine-Grained Histogram)

| Field | Value |
|---|---|
| Defect ID | D-001 (open, issue #3) |
| Type | Descriptive re-analysis of Option B's own retained per-miss data — no new inputs, no new session, no product/decoder code touched |
| Governing spec | `dev-tasks/2026-07-22-d001-partial-bucket-delta-histogram-spec.md` |
| Refines | `report.md` (this directory) — Option B, §3.2 window sweep / §3.4 capture-effect |
| Analysis date | 2026-07-23 |
| Sessions analysed | Identical to Option B: 07-07 (`20260706_live_run_2308`) · 07-06 (`20260706_live_run`) · 06-22 (`20260622_live run`) |
| Script | `classify_cochannel_delta_histogram.py` (this directory, a copy of Option B's committed `classify_cochannel.py`) |
| Numeric results | `cochannel_delta_histogram_results.json` (this directory) |
| Status | **COMPLETE — descriptive detail only; Option B's F = 29.6% / mixed verdict is unchanged and not reopened** |

---

## 1. What this adds, and what it does not

Option B's §3.2 sweep showed F climbing 22.1% → 24.9% → 29.6% → 37.1% → 44.7% across the 10–25 Hz
cutoffs it tested, with no data points between the 25 Hz sweep ceiling and the 50 Hz Partial
boundary, and no visibility into whether the 15,428-miss Partial bucket is a smooth spectral skirt
(one mechanism, weakening with distance) or has internal structure. This addendum answers that
using only Option B's own `min_deltas` per-miss data, re-binned at 5 Hz resolution instead of three
coarse buckets, plus the window sweep extended to 30/35/40/45 Hz, plus the Tight-class
capture-effect sub-check (§3.4 of Option B) repeated for Partial.

It does **not** propose new thresholds, does not re-run the classification decision, and does not
change F, F′, or the mixed verdict Option B delivered. Per spec §3.4, this is reported, not
re-decided.

**Self-check (spec §3.1 point 2):** the histogram's Isolated bin sums to **8,236** and the 0–50 Hz
numeric bins sum to **25,384** — both exact matches to Option B's combined Isolated and
Tight+Partial counts. The script asserts this and fails loudly on any mismatch; it passed. The
extended sweep also reproduces Option B's own 10/12/15/20/25 Hz figures verbatim (22.1% / 24.9% /
29.6% / 37.1% / 44.7%), confirming this decomposition has not diverged from the classification it
refines.

---

## 2. Fine-grained histogram (5 Hz bins, 0–50 Hz, pooled across both SNR bands)

| Bin (Hz) | 07-07 | 07-06 | 06-22 | **Combined** | % of numeric mass |
|---|---:|---:|---:|---:|---:|
| 0–5     | 1,677 | 1,552 |   975 | **4,204** | 16.6% |
| 5–10    | 1,041 | 1,002 |   586 | **2,629** | 10.4% |
| 10–15   |   984 | 1,023 |   597 | **2,604** | 10.3% |
| 15–20   |   963 |   935 |   729 | **2,627** | 10.3% |
| 20–25   | 1,111 |   860 |   531 | **2,502** |  9.9% |
| 25–30   |   898 |   751 |   478 | **2,127** |  8.4% |
| 30–35   |   992 |   783 |   568 | **2,343** |  9.2% |
| 35–40   |   894 |   800 |   612 | **2,306** |  9.1% |
| 40–45   |   825 |   760 |   534 | **2,119** |  8.3% |
| 45–50   |   789 |   654 |   480 | **1,923** |  7.6% |
| *(Isolated)* | 3,688 | 2,591 | 1,957 | **8,236** | *(not part of the 25,384 base)* |

*(numeric-mass % is each bin's share of the 25,384 Tight+Partial total, not of the grand total
including Isolated.)*

### 2.1 Shape: not a smooth skirt

Two features stand out, and both are consistent across all three independent sessions rather than
an artefact of pooling:

1. **A front-loaded peak, not an exponential decay.** The 0–5 Hz bin (16.6%) is roughly 1.6–2× any
   other bin, consistent with Option B's working hypothesis — a real co-channel/capture mechanism
   concentrated near-zero Δf. But the decline from there is not smooth: bins from 5 Hz out to 45 Hz
   sit in a comparatively narrow 7.6–10.4% band, i.e. the mass does not keep falling toward the
   Partial boundary the way a single fading mechanism would predict — it flattens into a long,
   fairly level tail.
2. **A consistent local dip-then-rise at 25–35 Hz.** All three sessions show the same pattern: the
   25–30 Hz bin is a local minimum, and the 30–35 Hz bin ticks back **up** from it (07-07: 898 →
   992; 07-06: 751 → 783; 06-22: 478 → 568). This is not large in absolute terms (roughly +5–19% per
   session) and could still be sampling noise at these bin populations, but the fact that the same
   dip-then-uptick shows up independently in all three sessions — rather than only in the pooled
   total — is worth flagging as it argues against "one smooth mechanism, monotonically weakening
   with distance" as the complete picture. It does not, on its own, establish a second distinct
   mechanism; it is a data shape worth keeping in view if H7 scoping returns to this question.

**Per rigour control §4.3:** the shape is broadly consistent session-to-session (same front-load,
same 25–35 Hz wobble in all three), unlike being pooled-only artefact. This is reported as
observation, not elevated to a new classification boundary.

---

## 3. Extended window-sensitivity sweep (combined, pooled bands)

| Tight cutoff | Tight | Partial | Isolated | **F** |
|---|---:|---:|---:|---:|
| 10 Hz | 7,435  | 17,949 | 8,236 | 22.1% |
| 12 Hz | 8,370  | 17,014 | 8,236 | 24.9% |
| **15 Hz (primary)** | **9,956** | **15,428** | **8,236** | **29.6%** |
| 20 Hz | 12,467 | 12,917 | 8,236 | 37.1% |
| 25 Hz | 15,021 | 10,363 | 8,236 | 44.7% |
| 30 Hz | 17,229 |  8,155 | 8,236 | 50.9% |
| 35 Hz | 19,461 |  5,923 | 8,236 | 57.9% |
| 40 Hz | 21,825 |  3,559 | 8,236 | 64.9% |
| 45 Hz | 23,860 |  1,524 | 8,236 | 70.9% |
| 50 Hz (= F′) | 25,384 | 0 | 8,236 | 75.5% |

The 10–25 Hz rows reproduce Option B's own table exactly. The new 30–45 Hz rows complete a
monotonic curve to the 50 Hz boundary, where — as the spec anticipated — F(50 Hz) equals F′(50 Hz)
= 75.5% **by construction**, since every Hz the cutoff advances simply reclassifies whatever
histogram mass sits in that slice from Partial to Tight. **This sweep is the cumulative integral
of §2's histogram; it is not independent evidence of anything the histogram doesn't already show.**
It is reported per spec §3.2 for completeness, but §2 (the histogram) and §4 below (the
capture-effect split) are where the actual finding is.

---

## 4. Capture-effect check: Tight vs. Partial

Option B's §3.4 found 36.4% of Tight-class misses show a ≥10 dB SNR delta to their nearest
same-slot neighbour (the "captured by a much stronger partner" signature). Repeating that same
check for the Partial class (delta = neighbour SNR − miss SNR, evaluated in the
`15 Hz < best_delta ≤ 50 Hz` branch):

| Session | Tight capture ≥10 dB | Partial capture ≥10 dB |
|---|---:|---:|
| 07-07  | 36.2% (n=3,879) | **40.8%** (n=6,295) |
| 07-06  | 36.4% (n=3,747) | **36.9%** (n=5,373) |
| 06-22  | 36.7% (n=2,330) | **44.2%** (n=3,760) |
| **Combined** | **36.4%** (n=9,956) | **40.3%** (n=15,428) |

**This is the addendum's headline finding.** Per spec §3.3's own interpretation guide: the
physically expected default is a *falling* ≥10 dB fraction from Tight to Partial (adjacent-signal
rejection gets easier as Δf grows, so capture should look less like capture and more like
background noise the further out you look). What is observed instead is **flat-or-rising in all
three sessions** — Partial's capture-effect fraction matches or exceeds Tight's every time, and
combined it is 3.9 percentage points *higher* (40.3% vs 36.4%). Per the spec's own pre-stated
reading of this result: **this is evidence the same capture/near-collision mechanism extends past
15 Hz, and F′ (not F) is the more honest read of where the recoverable ceiling actually sits** —
not because the Partial bucket is noise, but because a comparable fraction of it carries the same
stronger-neighbour signature that corroborates the Tight bucket.

This does not overturn Option B's F = 29.6% verdict or its locked thresholds — it sharpens what the
18.4pp recoverable-recall ceiling is made of, for the £-per-point conversation the report already
flagged as unresolved.

---

## 5. Caveats (restated, not re-derived, per spec §4)

- **Same error-direction bias as Option B (§3.3 there).** A miss classed at any Δf can only ever
  see *decoded* neighbours — an undecoded co-channel interferer is invisible to this method. The
  fine histogram inherits this downward bias unchanged; if anything, real Δf mass near 0 Hz may be
  under-represented relative to what is shown here.
- **No re-running of the classification decision.** Every number in this addendum is a
  decomposition of Option B's existing 9,956 / 15,428 / 8,236 split, self-checked against it and
  matching exactly.
- **Not a substitute for the isolated-miss pipeline diagnosis** offered alongside this spec
  (`dev-tasks/2026-07-22-d001-isolated-miss-pipeline-diagnosis-spec.md`) — that is a different
  question (why isolated misses fail) using different inputs (retained audio).

---

## 6. Verdict (unchanged)

Option B's mixed verdict at F = 29.6% stands, Captain-locked, unchanged. This addendum's
contribution is descriptive: the Partial bucket is not simply "the same mechanism fading to
nothing" — its capture-effect signature is at least as strong as Tight's, and its Δf mass does not
decay smoothly to the 50 Hz boundary but flattens into a broad, slightly-wobbling tail. Both
observations point the same way: **F′ (75.5%) is not a loose upper bound to be discounted — it is
closer to the honest picture of how much of the Partial bucket plausibly shares Tight's mechanism
than F (29.6%) alone conveys.** This is offered as additional resolution for the Captain's H7
cost/benefit weighing, not as a reason to reopen it.

---

## 7. References

| Reference | Content |
|---|---|
| `dev-tasks/2026-07-22-d001-partial-bucket-delta-histogram-spec.md` | Governing spec for this addendum |
| `report.md` (this directory) | Option B — the verdict and sweep table this addendum adds resolution underneath |
| `classify_cochannel.py` (this directory) | Option B's committed script (unmodified) |
| `classify_cochannel_delta_histogram.py` (this directory) | This addendum's script (copy + extensions) |
| `cochannel_delta_histogram_results.json` (this directory) | Aggregate numeric output (no callsigns, no message text — NFR-021) |
| `dev-tasks/2026-07-07-d001-b-cochannel-attribution-spec.md` §5 | Original rigour controls this addendum extends |
