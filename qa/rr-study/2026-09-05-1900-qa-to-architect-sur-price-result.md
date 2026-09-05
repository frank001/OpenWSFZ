# `SUR-PRICE` result — ROW 2 does not fire; a distinct-callsign discrepancy investigated, not glossed over

**QA, 2026-09-05 19:00 UTC** (`date -u`, HK-017). Answering
`qa/rr-study/2026-09-05-1854-architect-to-qa-spec-suppress-unknown-region-pricing.md`.

Script: `qa/rr-study/sur_price_analysis.py`. Raw output (aggregate only, NFR-021):
`artefacts/2026-09-05-sur-price/`. `git diff --stat -- src/ native/` **empty**. QA proposes no `src/`
change and draws no verdict on whether `SuppressUnknownRegion`'s default should change (HK-015).

---

## 1. Pins asserted (spec §5)

Region table SHA256 `bcf0bee2…c98e6` (29,013 entries) and the seven-corpus manifest, both asserted
equal to the ROW 0b/FP-MARK-2 pin at run time — hard-fails if either drifted. Both matched. The
inherited **241,858**-decode total is asserted in code (not just quoted in prose, per the spec's own
generalisation of the `==72` lesson) — matched exactly.

## 2. ROW 0a — precondition: PASS

Region table has 29,013 entries (≥ 1) ⇒ the computed default resolves to `true`.
**`SuppressUnknownRegion` is in effect today**, exactly as the spec states.

## 3. 🔴 A real discrepancy, investigated rather than asserted away: "distinct callsigns"

The spec's §1 carries forward **"21,242 distinct callsigns"** from earlier arms. Extracting callsigns
the way `SuppressUnknownRegion`'s own mechanism actually does — `ExtractPrimaryCallsignToken`
(`Ft8Decoder.cs:885-908`, the single token `Region` is looked up against, `Ft8Decoder.cs:364-366`) —
gives **11,000** distinct callsigns, not 21,242. That is a large enough gap to investigate before
using either number.

**Checked three extraction methods against the same 241,858 decodes, not guessed:**

| Method | Distinct count |
|---|---|
| **Single primary token** (`ExtractPrimaryCallsignToken` — what `SuppressUnknownRegion` actually uses) | **11,000** |
| **Both callsign-position tokens** (`FP-MARK-2`'s `callsign_position_tokens()`) | 17,351 |
| **Any non-keyword message token, any position** (excludes `CQ`/`RRR`/`73`/`RR73`/hash-bracket only — no position awareness, no grid exclusion) | **22,713** |

**Conclusion:** the crude, position-blind method lands closest to the previously-cited 21,242 —
strongly suggesting that figure was produced by an informal token census (likely also excluding
grid-shaped tokens, which would pull 22,713 down further toward 21,242) rather than by the project's
own structured callsign-position extraction. **It is not reproducible from any committed script, and
it counts a different, looser population than this arm needs.**

🔴 **Used the single-primary-token count (11,000) for every number below, and did NOT reconcile it to
21,242.** `SuppressUnknownRegion`'s mechanism gates on exactly one token per decode
(`Ft8Decoder.cs:364-366`), never on "any token that looks callsign-shaped" — using the looser figure
here would price a control against the wrong population, the same class of error the R-HASH
instrument citation nearly caused in `FP-MARK-2`.

## 4. ROW 1 — suppression rate

| Unit | k | n | Rate | CP95 |
|---|---|---|---|---|
| Per decode | 938 | 241,849 (9 excluded, no callsign-position token — out of population per spec §5) | **0.3878%** | [0.3635%, 0.4134%] |
| Per distinct callsign | 933 | 11,000 | **8.4818%** | [7.9677%, 9.0181%] |

Roughly **1 in 258 real decodes**, and **roughly 1 in 12 distinct stations**, have a primary-token
prefix this table does not resolve — every one of them removed from the panel and from QSO-automation
eligibility today, under the computed default.

## 5. ROW 2/3 — firm lower bound on false suppression, per session

| Session | Distinct unresolved callsigns seen ≥ 2× |
|---|---|
| `2026023_live run` | **1** |
| `20260613_live run 1h40_items` | 0 |
| `20260614_live_run` | 0 |
| `20260615_live_run` | 0 |
| `20260622_live run` | 0 |
| `20260706_live_run` | 0 |
| `20260706_live_run_2308` | 0 |
| **Mean across 7 sessions** | **0.143** |

**ROW 2 bar (fixed before measurement): fires if the mean ≥ 1. Mean = 0.143 — does NOT fire.**

🛑 **The two caveats the spec requires travel with this number, in the same place, not as an
afterthought (spec §4):**

- **(a) This is a lower bound at today's table, not at capture time.** The pinned table resolves more
  prefixes now than the (older, smaller) tables in effect when these corpora were captured — more
  decodes were suppressed during capture than this arm counts. The bias is known and understates;
  **not corrected for**, per instruction.
- **(b) A small ROW 2 is NOT evidence the control is cheap (HK-021(j)).** It counts only stations
  *proven* genuine by recurring within a session. **46.6% of real callsigns are heard exactly once**
  — every genuinely-heard-once station with an unresolved prefix is invisible to this method by
  construction, and none of ROW 1's 933 distinct unresolved callsigns can be individually cleared or
  convicted by it. The true false-suppression count is higher by an amount this arm cannot measure.

## 6. ROW 4 — prefix concentration signature (descriptive, aggregate only)

| | |
|---|---|
| Distinct unresolved callsigns | 933 |
| Distinct 2-character lead buckets | 280 |
| HHI (0 = fully dispersed, 1 = fully concentrated) | **0.0047** |
| Top-1 bucket share | 1.29% |
| Top-3 buckets share | 3.43% |
| Top-10 buckets share | 8.79% |
| **Signature** | **DISPERSED** |

No small number of prefix buckets accounts for a meaningful share of the unresolved population — this
does **not** look like a stale table with one or two large missing blocks (a "table-gap" signature).
It reads as scattered individual misses, consistent with either real rare-DX prefixes the table
happens to lack, or unlabelled noise, or both — **this row cannot and does not distinguish between
those**, per its own descriptive-only design.

## 7. What this does and does not answer

**Answers:** the control is active today; it removes ~0.39% of decodes and touches ~8.5% of distinct
stations heard; a mechanism-grounded floor finds at least 1 provably-genuine station suppressed, in 1
of 7 sessions, in the sample available — not zero, not large, and **not a ceiling on the true cost**
(§5, caveat b).

**Does not answer:** whether the true false-suppression rate is materially higher (structurally
unmeasurable here); whether the unresolved population is mostly real rare DX or mostly noise (ROW 4
is silent on this by design); whether the default should change (Architect's/PO's to decide).

## 8. NFR-021 / housekeeping

No callsign or prefix printed individually anywhere in this report, the script, or the raw output —
scanned with the project's own `scan()`/`classify()`, prose included, before commit.
`artefacts/2026-09-05-sur-price/` gathered with a `README.md` (HK-016), gitignored, not committed. No
`src/`/`native/` change. Committed locally, **not pushed** (HK-014).

---

**QA, 2026-09-05 19:00 UTC.** ROW 0a/1/2/3/4 reported mechanically. No verdict on
`SuppressUnknownRegion`'s default; no `src/` change proposed.
