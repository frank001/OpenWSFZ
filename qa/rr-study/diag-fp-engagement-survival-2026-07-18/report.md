# FP-vs-Engagement-Validator Survival Diagnostic — 2026-07-18

| Field | Value |
|---|---|
| Trigger | Captain question: does `engagement-target-validation` (region-anchored callsign grammar gate, PR #81) justify revisiting D-009's trust-first OSD posture (`K_MIN_SCORE_PASS2=10`, corr/nhard gates ON)? |
| Diagnostic tool | `Program.cs` in this directory — `dotnet run -c Release` |
| Reuse | Real production `EngagementTargetValidator`, `CallsignRegionStore`, `CallsignGrammarStore` (`OpenWSFZ.Daemon`) via `ProjectReference` — no reimplementation of the grammar-check algorithm |
| Data | Live, operator-refreshed `%APPDATA%\OpenWSFZ\callsign-regions.json` (29,013 entries, `IsSeedData=false` — confirmed by the tool's own startup assertion, which aborts otherwise) and `callsign-grammar.json` (`DigitRunMax=3`, `SuffixLengthMax=6`, `TotalLengthMax=11`) |
| Status | Complete — advisory diagnostic, no PASS/FAIL gate |

---

## 1. Study Hypothesis

D-009 (`results/d009-investigation-2026-06-21/report.md`) found OSD manufactures
structurally valid, CRC-14-passing FT8 messages from pure AWGN noise, and shipped a
**trust-first** decoder configuration (K=10, corr/nhard gates ON) explicitly to protect
against a false OSD decode becoming a **false logged QSO** — at a measured cost of ~14 pp
`co_channel` and ~5 pp `co_channel_sweep` recovery versus the pre-gating OSD launch.

`engagement-target-validation` (PR #81, archived 2026-07-18) subsequently added an
independent, downstream gate: a decoded callsign token must pass a region-anchored
grammar check before it may be armed as a live TX-engagement target (manual engage,
CQ auto-answer arming, or responder matching). A token this validator rejects is still
decoded and displayed, but **cannot** reach automated QSO completion or ADIF logging via
`QsoAnswererService`/`QsoCallerService`, and is soft-blocked with an operator prompt on
the manual path.

**Question:** does this second gate substantially reduce the log-integrity risk that
justified D-009's trust-first posture — i.e., would a meaningful fraction of OSD's
noise-manufactured false positives be caught by the grammar check before they could ever
reach TX engagement? If so, the co-channel-sensitivity cost D-009 paid may now be worth
revisiting (e.g. trialling a more sensitivity-leaning `KMinScorePass2`/`OsdCorrThreshold`
configuration via the already-shipped `decoder-settings-page` runtime controls).

**Null hypothesis:** the engagement-target-validator's survival rate for D-009-class
noise-manufactured false positives is high (≳ 75%) — i.e., the validator does **not**
meaningfully change the log-integrity risk calculus, because FT8's own callsign-packing
grammar already constrains a 77-bit payload's unpacked callsign field to a shape-plausible
string almost independent of whether the bits were forced from real signal or from noise.

## 2. Data Summary

**Corpus.** Every false-positive message on record in this repo's committed `S5_matched.csv`
files that yields an evaluable callsign-shaped token, drawn from three prior R&R-study runs:

| Source | Run | Decoder config | FP messages | Evaluable tokens |
|---|---|---|---|---|
| A | `results/2026-06-20-8eea3c4` | Pre-D-009 gating (shim 20260025, K=1, no corr/nhard gates) | 9 | 20 |
| B | `results/2026-07-04-a3738fc-f002-s5-n300` | **Current shipped** (K=10, gates ON), N=300 slots | 8 | 12 |
| C | `results/d011-fp-recheck-2026-07-04` | **Current shipped** (K=10, gates ON), N=120 slots | 7 | 11 |
| **Total** | | | **24** | **43** |

Excluded from token extraction: report/control words (`R`, `RR73`, `RRR`, `73`, signal
reports), Maidenhead grid-square tokens, and the `<...>` unresolved-hash placeholder
(not a callsign token). One additional candidate run (`2026-06-22-f11f438`) was inspected
and discarded — its "false_positive=True" rows are genuine synthetic Q-prefix signals
(`Q1ABC`, `Q9XYZ`, `Q1AW`) mislabelled by a VB-CABLE audio-mixer contamination artefact
of that specific run (the same class of contamination D-009 §2.1 documents elsewhere),
not noise-manufactured false positives — including it would have corrupted the sample
with genuine signals.

**OpenWSFZ git SHA at runtime:** not pinned for this diagnostic (informational, ad hoc
tool — not a `run_study.py` scenario). Validator code is current `main` as of 2026-07-18
(post `0459f36`).

**Each token was evaluated exactly once** through `EngagementTargetValidator.Validate()`
against the live table.

## 3. Results

Full per-token output (verdict + rejection reason where applicable) is captured in this
run's console transcript; the tool is re-runnable (`dotnet run -c Release` in this
directory) and deterministic against the current live region/grammar files.

### 3.1 Per-source survival rate

| Source | Total | Allowed (survives) | Rejected (caught) | Survival rate |
|---|---|---|---|---|
| A — pre-gating baseline | 20 | 19 | 1 | 95.0% |
| B — current shipped, N=300 | 12 | 10 | 2 | 83.3% |
| C — current shipped, N=120 | 11 | 10 | 1 | 90.9% |
| **B+C combined (current shipped config only)** | **23** | **20** | **3** | **87.0%** |
| **Overall (A+B+C)** | **43** | **39** | **4** | **90.7%** |

### 3.2 What got caught, and why

Only 4 of 43 tokens were rejected — all for the same reason (`FitsDigitRunThenSuffix`/
`RemainderFitsGrammar` failure: a matched region prefix whose remainder does not reduce to
a ≤3-digit run followed by a ≤6-letter suffix within `TotalLengthMax=11`):

| Token | Matched prefix | Remainder | Why it fails |
|---|---|---|---|
| `MR1I` | `M` (England) | `R1I` | Digit-run must lead the remainder; `R1I` starts with a letter, not a digit. |
| `KOWQ8MGEQVT` | `K` (United States) | `OWQ8MGEQVT` | No digit until position 4; even if it did, the letter-run either side overflows `SuffixLengthMax=6`. |
| `RHLI8VWMXMG` | `R` (European Russia) | `HLI8VWMXMG` | Same overflow shape as above. |
| `NZP10KAK/9J` | `N` (United States) | `ZP10KAK` | Digit doesn't lead; base callsign (portable suffix `/9J` already stripped) is 7 chars of letters before any digit. |

All four are cases where the OSD-forced payload happened to unpack into an unusually long
or digit-position-scrambled string — the tail of the distribution, not the bulk of it.

### 3.3 Why survival is high, not low (correcting the pre-study hypothesis)

The working hypothesis going into this diagnostic (see §1) was that a large share of
OSD-manufactured noise callsigns would be shape-anomalous — hex-dump-like or otherwise
implausible — and would therefore be caught by the same class of check the validator's own
design precedent (`6KER05BPPBQ`) illustrates. The measured 90.7% survival rate refutes
that. The reason is structural, not a validator weakness: the FT8 standard-message
**packer** (both the real one and this repo's own clean-room QA synth, per `synth/packing.py`)
encodes a callsign into the 77-bit payload using a constrained base-38-style alphabet that
already assumes callsign-like structure (letters/digits in specific position ranges,
optional portable-suffix bits) before OSD ever sees it. When OSD force-corrects a noise
codeword to a nearby valid LDPC codeword, the **unpacking** step decodes those bits back
through the same structural assumption — so the manufactured "callsign" is shape-plausible
almost by construction, independent of whether the underlying bits came from a real
transmission or from AWGN. The region-anchored grammar check operates on exactly that same
shape space, so it has very little independent discriminating power against this
particular failure mode. This is the same conclusion D-009's own R6 diagnostic reached
about `nhard`/sync-score separability (§3.2 of that report) — a different feature, same
underlying reason: OSD's false positives are not distinguishable from genuine decodes by
any cheap post-hoc feature, because the forcing process itself preserves message structure.

## 4. Summary Verdict Table

| Metric | Measured value | Informational threshold | Verdict |
|---|---|---|---|
| Survival rate, current shipped config (B+C) | 87.0% (20/23) | N/A — advisory diagnostic, no gate | **INFO** |
| Survival rate, overall (A+B+C) | 90.7% (39/43) | N/A | **INFO** |
| Null hypothesis (§1): survival ≳ 75% | Confirmed (87.0–95.0% across all three sources) | — | **NOT REFUTED** |

**Overall finding: the engagement-target-validator does *not* meaningfully reduce the
log-integrity risk D-009's trust-first posture was chosen to guard against.** Roughly
9 in 10 of the noise-manufactured false positives on record would sail through the
grammar gate unchanged and remain fully eligible for automated TX engagement and ADIF
logging.

## 5. Recommendations

1. **Do not revisit D-009's trust-first posture on the basis of the engagement-target-validator.**
   The premise raised in the triggering conversation — that the new validator substantially
   offsets the co-channel-sensitivity cost of K=10/gates-ON — is not supported by this data.
   The two defences are largely non-overlapping: the validator catches shape-anomalous
   outliers (digit-position-scrambled or overlong strings), while D-009's OSD false
   positives are, by the mechanism in §3.3, shape-plausible in the overwhelming majority
   of cases. No action recommended on decoder settings from this finding alone.

2. **N is small (43 tokens, 4 rejections) — informational, not a statistically powered
   estimate.** A Wilson 95% CI on the combined 87.0% (20/23) figure is roughly
   [67%, 96%] — wide, but the point estimate is far enough from any threshold that would
   flip the recommendation (even the low end of the interval is well above a rate that
   would justify calling the validator a meaningful mitigant). If a tighter estimate is
   wanted, a dedicated S5 run at the current shipped config (N≥120, matching R&R-004's
   sizing precedent) piped directly through this same tool would sharpen it — not
   currently judged necessary given the direction of the finding.

3. **No defect raised.** The engagement-target-validator is working exactly as designed
   (design.md's own stated scope is narrower than "catch all OSD noise" — it targets
   grammar-implausible tokens specifically, e.g. its own `6KER05BPPBQ` precedent). This
   diagnostic simply establishes that its overlap with D-009's failure mode is small; that
   is new information, not a bug in either capability.

4. **If the co-channel-sensitivity trade is to be revisited, it needs its own basis** —
   e.g. a fresh D-009-style ablation re-run to see whether anything has changed in the
   underlying OSD behaviour, or a Captain policy call that the ~14 pp/~5 pp sensitivity
   cost is no longer acceptable regardless of the FP-consequence question. This diagnostic
   answers the specific downstream-mitigation question asked; it does not reopen D-009 on
   its own terms.

**NFR-021 compliance:** all tokens in this report are OSD-manufactured noise artefacts
from synthetic AWGN test signals (not real amateur-radio traffic) or, in the pre-gating
source, values already committed to this repository in prior R&R-study reports. No real
callsigns appear in this diagnostic.
