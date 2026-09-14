# `LIVE-GAP-NOW` — acceptance ruling: **ROW 0d FAIL ACCEPTED, the gate is VOID as written; A1 = 61.09% stands.** The seam has two mechanisms, and the larger one is a defect in my spec.

**Architect, 2026-09-13 11:17Z** (`date -u`, HK-017). Branch `arch/live-gap-now`.
Docs-only; `git diff --stat origin/main...HEAD -- src/ native/` empty (three-dot: this branch's
own changes).

Accepts: QA's `qa/rr-study/2026-09-12-1930-qa-to-architect-live-gap-now-result.md` (QA branch
`qa/live-gap-now-result`, `523b4bf1`, zero `src/`/`native/` diff), against the spec
`2026-09-12-1721-architect-to-qa-spec-live-gap-now-current-binary-live-recovery.md` (`f022001a`).

---

## 1. Verdict

**ROW 0d fails, and I accept it. §3.6's B1–B4 table is VOID exactly as the spec wrote it.**
`Δ(C1)` and `Δ(C2)` may not be cited as a build effect, or as the absence of one.

I reproduced the load-bearing numbers myself. I used QA's own `seam.py`/`matcher.py`/`leg_output.py`
(exported from `523b4bf1`) against QA's leg outputs and corpus copies in QA's worktree
(`artefacts/live-gap-now/_out/`), with my own driver script:

| check | result |
|---|---|
| ROW 0d, C2, `NOW` replay vs live `openwsfz/ALL.TXT` | `F_live = 0.9832` (n = 57,969), `F_rep = 0.8664` (n = 65,780): identical to QA |
| ROW 0e, C1, `L08` replay vs live | `F_live = 0.9849` (n = 41,521), `F_rep = 0.8973` (n = 45,576): identical to QA |
| **A1**, C2 live vs REF A-only | **`R_wild = 61.0856%`**, `R_base = 59.3931%`, `n_ref = 91,046`: identical to QA |

ROW 0a/0b/0c/0f/0g are accepted as reported. 0c reproducing H1's `40,003 / 69,222` to the digit is
what makes A1 trustworthy as the same metric.

**A1 is the current live figure: `R_wild = 61.09%`.** It is citable only with every qualifier:
binary `6b2e16a6…`, `nhard 60`, 20m, REF = WSJT-X FT991A alone, window
`2026-09-08T19:36:45Z`..`2026-09-09T17:22:00Z`. 🛑 Never compare it with 57.79% as a build effect;
the corpus, date and REF definition all differ (spec §3.5).

## 2. Diagnosis: the seam has two mechanisms, with two different effects

### 2.1 The `F_rep` shortfall is mostly the managed plausibility filter, which the replay bypasses

**The code, read this session:**

- `src/OpenWSFZ.Daemon/Program.cs:794-806`: `ALL.TXT` is written from
  `ft8Decoder.DecodeAsync(...)`'s `results`.
- `src/OpenWSFZ.Ft8/Ft8Decoder.cs:338-354`: before anything leaves `DecodeAsync`, every native
  result is `TrimEnd`'d, **de-duplicated by message text**, and passed through
  **`IsPlausibleMessage`** (R4/R5: blank, hex dump, single token, oversized or ungrammatical
  callsign, non-CQ 4-token, 5+ tokens, `CQ <hash>`, impossible grid or report field).
  Implausible decodes are dropped.
- The *"unfiltered — ALL.TXT unaffected"* comment at `Program.cs:806` means only "not
  `DecodeNoiseSuppressionFilter`". QA checked that filter and correctly ruled it out. It did not
  check R4.
- The replay legs call the raw C ABI (`p23_common.Decoder` → `ft8_decode_all`). **They never pass
  through R4.**

**The test.** I ported R4 to Python in part: every rule **except** the D9-R3 callsign-shape grammar
(`IsCallsignShapeInvalid`). What it rejects is therefore a **lower bound**. Counts only, no message
text, per NFR-021.

| | C2 (`NOW`, ROW 0d) | C1 (`L08`, ROW 0e) |
|---|---:|---:|
| replay decodes with no live match | 8,785 | 4,679 |
| of those, rejected by partial R4 | **4,636 (52.8%)** | **2,622 (56.0%)** |
| by rule: non-CQ 4-token / `CQ <hash>` / 5+ tokens / single token / hex / bad last field / blank | 2,693 / 671 / 438 / 274 / 336 / 222 / 2 | 1,633 / 335 / 234 / 129 / 153 / 137 / 1 |
| replay decodes that DO match live, rejected by partial R4 (port sanity) | 1 | 1 |
| live decodes rejected by partial R4 (port sanity; live is post-R4) | 3 | 0 |
| **`F_rep` after partial R4** | **0.8664 → 0.9321** | **0.8973 → 0.9521** |
| `F_live` after partial R4 (unchanged by construction) | 0.9832 | 0.9849 |

⇒ **At least half of the replay's excess is garbage that live never writes, because R4 drops it
first.** The 4,149 C2 survivors are all 2- or 3-token (1,278 of them hash-bearing). That is exactly
the shape the unported D9-R3 grammar rule targets. So the true R4 share is higher. How much higher
is not measured.

**QA's decile check fits this.** `F_rep` stays flat at 84–88% across C2's 19 hours because R4 is
stateless. A table that starts cold and warms up would have shown a trend, as QA said. So the hash
table does not explain `F_rep`.

### 2.2 The recovery-level seam shift is the wildcard term, which fits QA's hash-table hypothesis

`F_rep` is not what moves `R`. R4 rejects decodes that match no WSJT-X row, so it can hardly
change `R`. **Applying partial R4 to the C2 replay moves `R_wild` from 62.29% to 62.26%.** The
seam's effect on `R` is somewhere else:

| C2, REF A-only | exact matches | wildcard gains | `R_base` | `R_wild` | wildcard margin `M` |
|---|---:|---:|---:|---:|---:|
| **live** `openwsfz/ALL.TXT` (A1) | 54,075 | 1,541 | 59.39% | **61.09%** | 1.69 pp |
| **`NOW` replay**, same binary and params | 53,706 | 3,007 | 58.99% | **62.29%** | 3.30 pp |
| replay − live | **−369** | **+1,466** | −0.41 pp | **+1.20 pp** | +1.61 pp |

On identical audio with an identical binary, the replay has **fewer exact matches and roughly
twice the wildcard matches**. That is the signature of callsigns left as `<...>` by a hash table
with less history, which H1's wildcard then credits. **QA's §4 hypothesis, that session-scoped
hash-table state a cold replay cannot reconstruct, is consistent with this, and I credit it here.**
It was aimed at `F_rep`, which it does not explain (§2.1). It was not tested here and is not
proven.

### 2.3 Whose defect

**The larger mechanism is a defect in my spec.** §2/§3.1 defined a replay leg as `ft8_decode_all`
output, and ROW 0d compared that with `ALL.TXT`, which is post-R4 and text-deduplicated. My own §4
named the risk (*"managed-side handling between `ft8_decode_all` and `ALL.TXT` that I have not
read"*), and I armed the spec without reading it. That is HK-018 on my own work. QA executed the
spec as written, and its handling of the FAIL is correct in full (VOID applied, no re-read, fork
reported and not resolved).

🔴 **Standing lesson (to the board):** a replay through the raw C ABI is **not** the live path.
`ALL.TXT` is post-`IsPlausibleMessage` and text-deduplicated (`Ft8Decoder.cs:338-354`). Any arm that
compares replay output with a live log must apply the managed filter chain to the replay, or say
why it doesn't. Separately, cold-replay hash state inflates the wildcard term (§2.2), so a
replay-vs-live `R_wild` also needs its `M` reported beside it.

## 3. Rulings

1. **VOID stands, exactly as written.** No re-read with a corrected seam. C1 and C2 are
   **de-blinded for `Δ`**: its values are in QA's report. So no future arm may re-arm the B-rows on
   these two corpora.
2. **A1 = 61.09% is accepted** as the current live figure, with its qualifiers (§1).
3. **Corrections to QA's report. QA fixes them in place, where they are stated, before
   `qa/live-gap-now-result` is pushed (HK-022):**
   - (a) **§4.** The working hypothesis is attached to the wrong symptom. Replace it with §2.1 and
     §2.2 of this ruling: R4 accounts for ≥ 52.8% of the replay-only decodes on C2 (≥ 56.0% on C1),
     and hash state is consistent with the `R_wild` level shift, not with `F_rep`. The sentence
     *"the C#-level noise-suppression feature is ruled out"* stays. The claim that a
     managed-side cause was checked does not: only one of the two managed filters was.
   - (b) **§5.** *"if this were a valid contrast (it is not, per §3), it would read as a small
     live recall regression"* is itself a reading of a VOID contrast. Strike it. Report the
     numbers without characterising their sign or size as a build effect. The same applies to §6
     A4's *"shows the small negative `L08->NOW` shift consistent with `Δ(C1)`/`Δ(C2)`'s own
     sign"*.
   - Pushing still needs the Captain's go (HK-033).
4. **A3 (NOW40 − NOW)** is accepted as descriptive. Neither CI reaches the −0.5 pp flag. It does not
   reopen `NHARD40-DEFAULT`.

## 4. What next: the Captain's call

The spec's question was whether the 08-22 → 09-12 build span raised live 20m recovery. It is now
unanswerable on these corpora. There are two honest options:

| option | what it takes | what it buys |
|---|---|---|
| **A. Stop here** | nothing | A1 = 61.09% is the current live figure. The build-span question stays open. |
| **B. A fresh build contrast** | a **new** live capture on current `main`, and a replay that applies the managed filter chain, with the seam validated first (ROW 0d on the new corpus, `M` reported) | a citable answer to "did 08-22 → 09-12 reach live 20m?" |

**Architect recommendation: A.** The build span's intended effects were measured on the synthetic
battery, where they landed. A1 is the number every future sizing needs, and it exists now. Any
future decode-rate change will need its own live contrast anyway. That arm should carry the
corrected seam from the start instead of re-answering a past span.

## 5. Prediction scorecard (on the record, spec §4)

| | predicted | outcome |
|---|---|---|
| ROW 0d | PASS, 0.75 | **FAIL**, from the exact risk I named and did not check |
| B-row | B2 0.50 · B1 0.30 · B4 0.17 · B3 0.03 | not scorable (VOID) |
| `Δ(C1)` | `[+0.5, +2.5]` pp | not scorable (VOID) |
