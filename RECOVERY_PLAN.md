# FT8 Decoder Recovery Plan

**Author:** Architect
**Date:** 2026-05-29
**Status:** Proposed — awaiting Product Owner approval
**Affects:** `OpenWSFZ.Ft8` decode pipeline, `p9-all-txt-decode-logging`, CI

---

## 1. Problem statement

The FT8 decoder has been stuck in a non-converging defect loop. Across **18 defects
(D1 → D18)** and **36 developer/QA rounds**, the symptom has never changed:

> The decoder produces **zero real FT8 decodes** from live air while WSJT-X, on the
> identical signal, decodes 40+ stations. Our output is a handful of CRC-14 false
> positives per cycle (invalid callsigns such as `1TJK`, impossible reports such as
> `+4011`).

Each round QA inspects a few log lines from one live cycle, declares a "confirmed root
cause" (Gray code → CRC width → Costas softmax → …), the developer applies a one-line
DSP change, all unit tests stay green, and the next live test fails exactly as before.

This is motion without progress. It must stop.

---

## 2. Root cause of the *deadlock* (not the DSP)

The deadlock is a **validation failure**, not (primarily) a DSP failure.

### 2.1 The only end-to-end test is circular

`tests/OpenWSFZ.Ft8.Tests/Ft8DecoderFixtureTests.cs` is the sole "integration" test. It
builds its input with `TestFt8Encoder`, which encodes a frame using the **same constants
and conventions the decoder uses to decode it**:

```
TestFt8Encoder:  PackType1 → AppendCrc14 → LdpcEncode → BitsToSymbols → SymbolsToPcm
                      (same Gray map, same "CRC over 82 bits", same LDPC generator,
                       clean sine waves, amplitude 0.5, perfect alignment, ~no noise)
                                              │
                                              ▼
Ft8Decoder.DecodeAsync(float[] pcm)  ──►  decodes it back
```

A self-consistent encoder/decoder pair **always** round-trips. The test proves the
decoder agrees with *itself* — not with the FT8 protocol, and not with a real
transmitter. The full green suite (190 tests) therefore gives **false confidence**: it
cannot fail for the failure mode that actually matters.

### 2.2 The only external oracle is unusable for iteration

The sole check against reality is the Captain's **live hardware smoke test**, which is:

- **non-reproducible** — different air signals every run;
- **slow** — one noisy data point per round;
- **fragmentary** — delivered as a few pasted log lines.

So QA debugs by speculation on irreproducible data, every fix is constrained only to keep
the *circular* tests green, and there is no test anywhere that can distinguish "our DSP is
wrong" from "we fed it different audio." That ambiguity is what let 18 plausible-but-wrong
root causes survive.

**Conclusion:** No decoder strategy — patch *or* rewrite — can converge until there is a
deterministic, reproducible test driven by *real* signals with a *known* answer key.
Building that oracle is the unconditional first step.

---

## 3. Strategy: measure first, then decide

The recovery is **oracle-first**. We install a real-signal ground-truth oracle, use it to
measure how far off the current decoder actually is, and let that measurement — not
speculation — choose between patching and porting.

```
Phase 0  Freeze the D-loop
Phase 1  Build the ground-truth oracle  ◄── the missing piece for 36 rounds
            │
            ▼
   ┌─── DECISION GATE (data-driven) ───┐
   │  0 real decodes  → Phase 2A Port  │
   │  some-but-fewer  → Phase 2B Patch │
   └───────────────────────────────────┘
            │
            ▼
Phase 3  Wire the oracle into CI + fix the QA process
```

The oracle (Phase 1) is required **regardless** of which branch the gate selects — even a
flawless ft8_lib port must be validated against real WSJT-X-decoded WAVs before it can be
trusted. Nothing in Phase 1 is wasted work.

---

## 4. Phase 0 — Freeze the defect loop

**Goal:** stop spending effort on speculative single-line DSP fixes.

- Halt the D18 / D19… sequence on `p9`. No further DSP changes until the oracle exists.
- `p9-all-txt-decode-logging` is conflating two unrelated concerns: the **ALL.TXT writer**
  (D16/D17 — complete and correct) and the **decoder correctness** (D18 — a deep, separate
  problem). Separate them:
  - The ALL.TXT logging feature (FR-026/027/028) is functionally done. It can be merged on
    its own merits once the decoder produces real output to log.
  - Decoder correctness moves to its own change (see Phase 1).
- Record this plan as the agreed path so QA stops issuing live-data root-cause briefings.

**Exit criteria:** no open "fix the DSP" task; decoder-correctness work tracked separately.

---

## 5. Phase 1 — Ground-truth oracle (the unblock)

**Goal:** a deterministic test, runnable in seconds with no radio, that fails when the
decoder cannot decode *real* FT8 and passes when it can.

### 5.1 Capture a matched corpus from the connected radio

Use the radio already tuned to 7.074 MHz and let WSJT-X produce the answer key for us:

1. In WSJT-X set **File → Save → Save All**. WSJT-X writes every 15 s cycle to
   `<DataDir>/save/YYMMDD_HHMMSS.wav` as **12 kHz mono** — exactly the decoder's input
   format — and logs its decodes to `ALL.TXT` with a timestamp that **matches the WAV
   filename**.
2. Capture **~10 minutes** on a busy band → ~40 WAV files, each paired with the list of
   real callsigns WSJT-X decoded from it.

This is sourced from our *own* signal chain, so it tests our exact audio path, and there
is no licensing question (decoded callsigns are facts, not copyrightable). The canonical
`kgoba/ft8_lib` `test/wav/` recordings (MIT) are a fallback if a clean capture is hard to
obtain.

### 5.2 Build a WAV→PCM shim (the one new piece of production-adjacent code)

The decoder takes `float[]` PCM; we have no WAV reader today. Add a minimal reader that
converts a 12 kHz mono int16 WAV into the `float[]` `DecodeAsync` expects. Small and
mechanical; WSJT-X's format maps directly. (Confirm exact sample count per file on first
capture and align the decoder's expected window length if needed.)

### 5.3 Replay harness + first measurement

Write a diagnostic test/tool that, for each captured WAV:

- decodes it with `Ft8Decoder.DecodeAsync`,
- compares our decoded messages against WSJT-X's `ALL.TXT` for the same timestamp,
- reports: **real signals matched**, **WSJT-X signals missed**, **our false positives**.

Run it once across the corpus. This single number — *how many of WSJT-X's signals we
recover* — is the data the last 36 rounds never had.

### 5.4 Commit permanent CI fixtures

Select **2–3 representative WAVs** (varied SNR / band congestion), commit them as embedded
fixtures with their expected callsign answer keys, and write an xUnit integration test
asserting the known messages decode. This **replaces the circular `TestFt8Encoder` test**
as our integration coverage. (Keep the encoder test as a fast internal-consistency check,
but it no longer counts as proof of correctness.)

**Exit criteria:**
- Matched WAV/answer-key corpus captured.
- Replay harness reports a concrete recovery rate against WSJT-X.
- ≥2 real-signal WAV fixtures committed with a red/green integration test.

---

## 6. Decision gate (data-driven)

Read the Phase 1 recovery rate:

| Measurement | Interpretation | Branch |
|---|---|---|
| **0 of N** real signals recovered | Homegrown DSP is fundamentally wrong; 18 failed rounds confirm it is not close | **Phase 2A — Port** |
| **Some but materially fewer** than WSJT-X | Pipeline is largely correct; a sensitivity/threshold/timing gap remains | **Phase 2B — Patch** |
| **≈ parity with WSJT-X** | Decoder was effectively fine; the bug was elsewhere (audio path / packaging) — fix that, no decoder rework | Close out |

**Architect's honest expectation:** given 18 consecutive failed root-causes, the most
likely outcome is **0 of N → Phase 2A**. But we now *decide on data*, not a guess — and
the porting effort is only undertaken once the oracle can verify it.

---

## 7. Phase 2A — Port ft8_lib (if the gate selects it)

**Goal:** replace the homegrown decode algorithms with a faithful translation of the
proven MIT-licensed `kgoba/ft8_lib` decode path.

- **Scope:** translate the decode pipeline — candidate sync, symbol/log-likelihood
  extraction, LDPC belief-propagation, CRC, message unpack — to managed C#. The codebase
  already cribs ft8_lib's *constants* (Gray map, LDPC generator, CRC) piecemeal; this
  replaces the *algorithms* around them with the reference logic instead of reinvented
  logic.
- **Why port, not P/Invoke:** preserves the project's pure-managed / Native-AOT /
  single-binary posture and avoids a per-platform native dependency. Porting known-correct
  code is a *finite, convergent* task — unlike inventing the algorithm, which has failed.
- **License:** MIT — compatible; add attribution to the dependency/licence inventory so the
  `LicenseInventoryCheck` gate stays green.
- **Validation:** the Phase 1 oracle is the acceptance test. The port is "done" when it
  recovers ≈ WSJT-X's decodes on the committed fixtures.
- **Reuse:** keep `CycleFramer`, the audio plumbing, `AllTxtWriter`, and the spectrum path;
  swap only the DSP core behind the existing `Ft8Decoder` interface so the rest of the
  system is unaffected.

**Exit criteria:** real-signal fixtures decode at parity with WSJT-X; full suite green.

---

## 8. Phase 2B — Patch against the oracle (if the gate selects it)

**Goal:** close a sensitivity/timing gap in an otherwise-correct pipeline.

- Iterate **only** against the Phase 1 oracle: each change must move the recovery-rate
  number on real WAVs. No change is accepted on the strength of the circular encoder test
  alone.
- Likely suspects to investigate with the real corpus (now reproducibly): time-sweep
  granularity vs. real DT spread, `MaxCandidatesPerSweep` dropping real signals on a
  crowded band, Costas threshold calibration, LLR scaling/sign under real SNR.
- Hard stop: if recovery does not reach parity within a bounded effort (e.g. 2–3 focused
  iterations), escalate to Phase 2A. No open-ended patch loop.

**Exit criteria:** same as 2A — parity on real fixtures; full suite green.

---

## 9. Phase 3 — CI integration & process fix

**Goal:** make the deadlock structurally impossible to re-enter.

- **CI gate:** the real-signal fixture test runs in CI on every push. A decoder change that
  regresses real-signal recovery fails the build — the protection that never existed.
- **Process rule (the QA fix):** "root cause" claims for decoder defects must be
  demonstrated by a **failing reproducible test on a committed WAV**, not inferred from a
  single live session's log lines. Live smoke tests become *acceptance/confirmation*, not
  the primary debugging instrument.
- **Corpus growth:** when a future real-world miss is found, capture that WAV, add it to the
  corpus as a new red test, then fix. The corpus only grows.

**Exit criteria:** real-signal test gating CI; QA process rule documented; D-loop cannot
recur because every claim needs a reproducible failing test.

---

## 10. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Clean live capture is hard (QRM, no signals) | Fall back to MIT `kgoba/ft8_lib` `test/wav/` recordings as fixtures |
| WSJT-X WAV length/format differs from decoder's 180 000-sample assumption | Confirm on first capture; adjust decoder window length — cheap, mechanical |
| Port is larger than estimated | Scoped to the decode path only; existing framing/audio/logging reused; oracle bounds "done" precisely |
| Team reverts to log-scraping habits | Phase 3 process rule + CI gate make reproducible tests the only accepted evidence |
| ALL.TXT feature stalls behind decoder work | Phase 0 separates them; logging merges on its own once real output exists |

---

## 11. Immediate next tasks

1. **Approve this plan** (Product Owner) and confirm the Phase 2 default expectation (Port).
2. **Open a new OpenSpec change** — `p10-decoder-ground-truth` — covering Phase 1 (oracle)
   and Phase 3 (CI/process); split decoder-correctness off `p9`.
3. **Capture the corpus:** enable WSJT-X *Save All* on 7.074 MHz, record ~10 min, collect
   the `save/*.wav` files + matching `ALL.TXT`.
4. **Build the WAV→PCM shim** and the **replay harness**; produce the first recovery-rate
   measurement.
5. **Convene the decision gate** on that measurement; proceed to Phase 2A or 2B.

---

## 12. One-paragraph summary

The decoder loop is stuck because the only end-to-end test is circular (a self-consistent
encoder feeding the decoder) and the only real check is a slow, non-reproducible live smoke
test — so 18 root-causes were guessed, never verified. The fix is to capture real WAVs from
the connected radio with WSJT-X's decodes as the answer key, replay them through our decoder
offline as a deterministic test, and let the measured recovery rate decide whether to port
the proven MIT `ft8_lib` decoder (expected) or patch ours. The oracle is required either
way, costs about a day, and is the piece that has been missing the entire time.
