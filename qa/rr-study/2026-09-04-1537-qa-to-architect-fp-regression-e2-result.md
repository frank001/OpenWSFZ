# `FP-REGRESSION` -- QA to Architect: E2 result (ROW 0a)

**QA, 2026-09-04 15:37Z** (`date -u`, HK-017). Pack:
`2026-09-04-1441-architect-to-qa-execution-pack-fp-regression.md`. Spec:
`2026-09-04-1432-architect-to-qa-spec-fp-regression-bisect.md`. This session runs **E2 only**, per
the Captain's explicit instruction ("Start on E2 only") and the Architect's ruling
(`2026-09-04-1507-...`) that E2 proceeds unchanged and is not gated by the inventory flag.

**🛑 HARD STOP 2 fires at the end of this report per the pack ("after E2, on either branch").**
This session stops here regardless of the verdict below. E3 is NOT started.

---

## What was run

Decoded the full frozen 4,000-slot M1 S5 AWGN corpus (`qa/rr-study/awgn-fp-replay/_work/m1m4_s5/`)
through **B1** (`3bd4cd0`, 2026-08-05, pre-regression, last 0/120 in-chain sweep) and through **B8**
(`c3a9ea8`/`f5dec23`, 2026-08-22, post-step, 4/120 in-chain sweep), **paired -- the same 4,000 WAVs
through both binaries.**

**Machinery, and why it differs from Row0rCarryForwardTests.cs's own approach:** that file's own
docstring discloses a structural obstacle -- `Ft8LibInterop.ExpectedShimVersion` is a hard-coded
`20260050` compile-time constant, so `LoadAndVerify()` throws on any older binary before a decode
call is reachable. Both B1 and B8 are older than `20260050`, so **neither** side of this row could
run through the managed C# wrapper. Predicate shipped as code (HK-021(r)):
`qa/rr-study/fp-regression/row0a_instrument_sensitivity.py`, a raw ctypes binding directly to the
exported C ABI (same approach `qa/cycleframer-alignment-replay/p23_common.py` already uses
elsewhere in this repo for a different arm), bypassing the managed version self-test entirely.

- **ABI stability confirmed before relying on it:** `ft8_shim.h` read at both B1 and B8 (git
  history) -- `FT8Result` struct layout (`freq_hz`, `dt`, `snr`, `message[36]`), `ft8_decode_all`
  and `ft8_set_ap_bits` signatures are byte-identical at both endpoints.
- **PCM normalisation matched to the canonical harness, not to a different one in this repo:**
  `tests/OpenWSFZ.Ft8.Tests/WavReader.cs` divides each int16 sample by `32768.0` to get `[-1,1]`
  float32 -- this script does the same. (`p23_common.py`'s own `Decoder` reads raw, unnormalised
  int16 magnitude for a separate live-audio RMS-scaling pipeline; using that convention here would
  have desynchronised this instrument from the already-established 10.875%/435-event-slot offline
  rate this arm's own spec cites as the reference figure.)
- **AP bits disabled**, mirroring `Ft8LibInterop.SetApBits([], [])` exactly (0/0 counts, non-null
  1-byte buffers). **Decode params left at native compiled defaults** (`10, 0.10, 60` -- identical
  across B1..B8 per every shim header's own doc comment) -- nothing in the closed candidate-budget
  family was touched.
- Binary manifest re-asserted independently before either binary decoded anything (both SHA256
  matched exactly; see below) -- consistent with E1's manifest, not re-derived from it.

## Reporting requirement 1 -- recomputed SHA of every binary used

| Label | Commit | Manifest SHA256 | Recomputed SHA256 (this run) | Match |
|---|---|---|---|---|
| B1 | `3bd4cd0` | `f2f30c890b253eb6b69aa1a89c26d2991ee70aa2a202c68361130344bb7d4015` | `f2f30c890b253eb6b69aa1a89c26d2991ee70aa2a202c68361130344bb7d4015` | OK |
| B8 | `c3a9ea8` | `bc8efcf148046f199c057b62c7987c4b69f2dc62d72509458a671305ab051d7f` | `bc8efcf148046f199c057b62c7987c4b69f2dc62d72509458a671305ab051d7f` | OK |

Shim self-test (`ft8_lib_version_check()`, logged not enforced -- this row deliberately decodes
across two different, both legitimately pinned, shim versions): B1 = `20260033`, B8 = `20260046`.

## Reporting requirement 2 -- working tree

```
git diff --stat -- src/ native/
```
**Empty**, confirmed before the run and again at report time. `git status --short` shows only new
files under `qa/rr-study/fp-regression/` (script, redaction script, results). No extracted DLL was
copied into `src/OpenWSFZ.Ft8/Native/`.

## Reporting requirement 3 -- every row, inputs/threshold/verdict

**Predicate (spec sec.4 ROW 0a / pack E2):** FIRES iff the paired difference (B8 − B1) in offline
false-accept rate is **≤ 0**. False-accept rate = event slots (≥1 decode) / total slots, since this
corpus is noise-only by construction (S5, no injected signal).

| Quantity | Value |
|---|---|
| n (paired slots) | 4,000 |
| n11 (both binaries fire) | 435 |
| n10 (B1 fires, B8 does not) | **0** |
| n01 (B8 fires, B1 does not) | **0** |
| n00 (neither fires) | 3,565 |
| rate(B1) | 10.8750% (435/4000) |
| rate(B8) | 10.8750% (435/4000) |

**Signed difference (B8 − B1) = +0.0000 pp. Paired 95% CI (closed-form Wald, HK-021(o), no
bootstrap) = [+0.0000, +0.0000] pp** -- exactly zero-width, because there are **zero discordant
pairs**: B1 and B8 do not merely produce statistically indistinguishable rates, they fire on the
**identical set** of 435 slots, out of 4,000, with no exceptions in either direction.

**ROW 0a VERDICT: FIRES.** `diff = 0 ≤ 0` ⇒ per the pack's stated consequence: **"the bisect is
VOID and must not be run."** The offline seam is blind to whatever moved the in-chain rate between
B1 and B8's eras.

## Reporting requirement 4 -- signed differences, never absolute; n and readout quantum

Done above -- `+0.0000 pp`, signed, `n=4000`, both slot-level (binary event/no-event, the quantum
this predicate reads at) and per-CSV-decode fields quoted at their own native quantum (integer dB
for SNR, three decimal places for `dt_s`, matching the CSV's own written precision).

## Reporting requirement 5 -- citation discipline

`3.333%` was not used anywhere in this session as a baseline. The two rates compared are the
offline replay rates of B1 and B8 themselves (10.8750% each) -- this row does not cite the in-chain
`0.556%`/`2.708%`/`3.333%` figures at all; it only asks whether the offline instrument moves between
two specific historical binaries.

## Reporting requirement 6 -- NFR-021

The corpus is noise-only, so decoder output on all 435 event slots is hallucinated
callsign-shaped text by construction, exactly as the pack warns. Scanner run via its own
`scan()`/`classify()` (HK-022):

- Before redaction: `row0a_B1_decodes.csv` 358 distinct flagged tokens (359 occurrences);
  `row0a_B8_decodes.csv` 358 distinct flagged tokens (361 occurrences). Slot CSVs (no message
  column): 0/0 on both, as expected.
- **Guard passed:** 0 of 358 flagged tokens found inside any injected truth `message_text` (S5's
  truth file carries none -- checked, not assumed) ⇒ every flagged token is decoder output, never
  truth.
- **Redacted** via `qa/rr-study/fp-regression/redact_row0a_decodes.py` (same method as
  `awgn-fp-replay/redact_m1_m4_decodes.py`, imports the shipped scanner rather than reimplementing
  it). Placeholder infix **`<RDCTGnn>`** -- distinct from the three the pack names explicitly
  (`<RDCTnn>`/`<RDCTMnn>`/`<RDCTRnn>`) and from two more already in use elsewhere in the repo that
  the pack's list does not mention (`<RDCTKnn>`/`<RDCTSnn>`). Map committed:
  `qa/rr-study/fp-regression/results/REDACTION-MAP-ROW0A.md`.
- **Re-scanned after redaction: 0 flagged on both decode CSVs.** All new files (scripts, both
  redaction maps, both slot CSVs, both decode CSVs) scanned clean before this commit.

## ⚠️ What ROW 0a cannot detect (HK-022, carried from spec §4/pack E2)

That the offline and in-chain effects share a *mechanism*. This row asks only whether the offline
instrument's aggregate false-accept rate moves between B1 and B8 -- it found that it does not move
**at all**, not even by one slot in either direction. That is a stronger non-result than "not
statistically significant"; it is exact agreement on which 435 of 4,000 slots produce a decode. It
says nothing about whether the *in-chain* mechanism (whatever moved 0.556%→2.708%) is even the kind
of thing this offline replay could see if it existed at a smaller magnitude, nor does the identical
event-slot count rule out a subtler effect this binary pair's discordant-pair count of zero cannot
resolve at n=4,000.

## Supplementary diagnostic (same B1/B8 CSVs already produced for this row -- no new binary, no
new decode; NOT a bisect, NOT an attribution, offered only to characterise what the offline
instrument DID see, per this row's own reporting obligation above)

Per-slot decode **counts** are identical for all 4,000 slots (0 slots differ in `n_decodes`). Among
the 435 event slots, comparing individual decode records field-by-field:

| Field | Slots differing (of 435 single-decode-pair-comparable slots*) |
|---|---|
| `freq_hz` | 0 |
| `dt_s` | 0 |
| `reported_snr_db` | 226 |
| `message` text | 3 |

*15 slots carry 2 decodes each and were compared as a set rather than position-by-position; none of
those 15 differ in message text, all differences there are also `reported_snr_db`-only.

**Reading, stated narrowly:** candidate localisation (`freq_hz`, `dt_s`) is untouched between B1 and
B8 on every single event slot. `reported_snr_db` shifts by a small amount (typically ±1-2 dB) on
about half the event slots -- consistent with, but not attributed to, the disclosed
`c3a9ea8`/"negative `time_offset` SNR collapse fix" landing somewhere in this window (**this
sentence is descriptive, not a bisect finding -- ROW 1 is void per the verdict above and no
attribution to a specific commit is licensed by an in-chain-vs-offline comparison in the first
place, let alone this one**). Three slots' decoded message text differs while `freq_hz`/`dt_s`/SNR
stay identical -- the same *shape* as ROW 0r's fire (hash-placeholder resolution/display), but at
0.69% of event slots rather than ROW 0r's 56.6%, and this offline B1-vs-B8 pair is not the same
comparison ROW 0r ran (`20260049`→`20260050`, a much later and different pair of binaries). 🛑 **This
paragraph must not be read as evidence toward the barred `9500e03` hypothesis or any other single
commit** -- per E1.3, no block in this arm may attribute an in-chain OR offline rate/field
difference to a specific commit; only a (now void) ROW 1 bisect could do that.

## What this session did NOT do (scope discipline)

- Did not run ROW 1, ROW 2/3/4, or the bisect in any form -- ROW 0a's fire makes that explicitly
  barred ("do not respond by widening the corpus, changing the metric, or checking one more
  binary").
- Did not touch `src/` or `native/` (confirmed empty diff).
- Did not push, branch, open a PR, or merge (HK-014/HK-011).
- Did not fold Action B (the inventory generator's second root, from the 15:07Z ruling) into this
  block -- that is explicitly not part of `FP-REGRESSION`.

## Next

Per the pack and per spec ROW 0a's own consequence: **the bisect is void.** Spec §0/§3: "the arm
re-scopes to an in-chain instrument, which is a new pre-registration" -- that re-scoping is the
Architect's to draft, not QA's to improvise. **E3/E4 must not run.** `main` unchanged, still 24
ahead of `origin/main`, unpushed, carrying `ac6150d`'s `src/`+`native/` diff ⇒ HK-029's exception
still does not apply; nothing in this session changes that (this commit is `qa/`-only).

---

**Files this session touches:**
- New: `qa/rr-study/fp-regression/row0a_instrument_sensitivity.py` (predicate + decode harness, HK-021(r))
- New: `qa/rr-study/fp-regression/redact_row0a_decodes.py` (redaction pass, reuses the shipped scanner)
- New: `qa/rr-study/fp-regression/results/row0a_{B1,B8}_{slots,decodes}.csv` (redacted)
- New: `qa/rr-study/fp-regression/results/REDACTION-MAP-ROW0A.md`
- New: this report
- Scratch only, gitignored, not committed: `artefacts/fp-regression-2026-09-04/` (extracted DLLs, run log)
