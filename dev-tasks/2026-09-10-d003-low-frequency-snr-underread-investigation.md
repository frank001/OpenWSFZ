# D-003 — Low-Frequency (&lt;600 Hz) Live SNR Under-Read: Investigation Scoping

**Date:** 2026-09-10
**Prepared by:** QA
**Audience:** Developer (to execute), Captain (sign-off required before pickup, HK-011)
**Defect ID:** D-003 — `DEFECT-d003-live-audio-low-frequency-snr-underread.md` (repo root). Distinct
from D-002 (`DEFECT-snr-reported-gain-error.md`, a whole-range slope/gain error) — the two are
independent findings.
**Status:** Proposed. **Investigation only. No fix is authorised or proposed by this document.**
Per HK-011, this needs the Captain's explicit sign-off before a Developer session picks it up, and
that session does not run `pre_merge_check.py` or push/merge on its own initiative.
**Branch:** new branch off `main`, name at the Developer's/Captain's discretion — this is a read
+ instrument pass, not a continuation of `qa/2026-09-09-s1-ladder-substrate-proposal`.

---

## 0. Executive summary

`DEFECT-d003-live-audio-low-frequency-snr-underread.md` establishes, from live matched-pair data
already on disk, that below 600 Hz OpenWSFZ reports SNR about 8 dB lower relative to WSJT-X than it
does elsewhere (local median delta −10 dB vs −2 dB overall), one-sided (296 station-hour clusters
under-read-dominant, zero the other way; `k_u=2,062` vs `k_o=6`). That record is a **measurement**,
not a mechanism finding — it does not touch `src/` and does not say *why*. This task scopes the
"why" investigation: read the estimator code for anything specific to low audio offsets, and if
nothing obvious explains it, add **bounded, instrumentation-only** logging to test the leading
hypothesis (June mechanism 1: DC/hum contaminating the waterfall in the low-frequency region) against
the alternative that the sideband-window arithmetic itself is doing something different down there.

**Effort:** a code read plus, if needed, a short local replay with added Debug-level logging. **Not**
a new capture. **Not** a decoder behaviour change — any instrumentation added must not alter what
gets decoded (the same guardrail the D-001 isolated-miss diagnostic task used).

---

## 1. The precise question this answers

> Why does OpenWSFZ's per-signal local noise-floor estimate read ~8 dB high, specifically for
> signals below ~600 Hz audio offset, on live audio? Is it (a) the raw waterfall magnitudes in that
> region being structurally elevated regardless of which signal is being estimated (consistent with
> DC/hum contamination reaching the noise floor before any per-signal window is taken), or (b)
> something in `compute_local_noise_floor_db`'s own window/clamp arithmetic that behaves differently
> near the low edge of the passband?

Both point at different, and differently-sized, remedies:

- **(a) Contamination in the input/waterfall itself** → a DC-block or high-pass stage ahead of the
  FFT, or a floor correction scoped to the affected bins — bounded, but touches the audio front end.
- **(b) An artefact of the estimator's own window math** (see §3.2's clamp note below) → a narrower,
  more mechanical fix confined to `compute_local_noise_floor_db`.
- **Neither, or something else** → the investigation should say so plainly rather than force one of
  the two into an ill-fitting explanation (the same "mixed, no dominant mode" honesty the D-001
  isolated-miss task required).

## 2. What is already known (read, not re-measured — check before adding new instrumentation, HK-018)

- `compute_local_noise_floor_db` (`src/OpenWSFZ.Ft8/Native/ft8_shim.c:1124-1174`) samples
  `K_LOCAL_NOISE_WINDOW = 32` bins each side of the candidate's `freq_offset`: left sideband
  `[max(0, freq_offset − 32), freq_offset)`, right sideband `[freq_offset + 8, freq_offset + 8 + 32)`,
  falling back to the *global* `tls_last_noise_floor_db` only if literally no bins are available.
- **The clamp at bin 0** (`ft8_shim.c:1145-1146`, `if (lo_start < 0) lo_start = 0;`) **only truncates
  the left sideband for `freq_offset < 32` bins** — at 6.25 Hz/bin
  that is audio offsets below ~200 Hz, a narrower range than the ~600 Hz this record's band split
  uses. **This does not, on its own, obviously explain a defect spanning up to 600 Hz** — read this as
  a partial-mechanism candidate, not a confirmed one, and check whether the under-read rate itself
  tapers within the band (the result file's own exploratory 600–1000 Hz vs ≥1000 Hz split found a
  taper past 600 Hz, consistent with *something* fading gradually rather than a hard 200 Hz cutoff).
- `compute_noise_floor` (the *global* estimator, `ft8_shim.c:909-927`) samples the **entire**
  waterfall and is not per-signal — it is not the function this defect implicates directly, but it
  shares the same underlying `mon.wf.mag` values, so any front-end contamination would show up in
  both.
- **No existing instrumentation exposes per-bin waterfall magnitude.** `Ft8Decoder.cs` (~lines
  260-422) surfaces per-pass candidate counts and LDPC/LLR stats (reused by the D-001 isolated-miss
  task, `dev-tasks/2026-07-22-d001-isolated-miss-pipeline-diagnosis-spec.md`) but nothing at
  bin/frequency resolution. Confirm this is still true before writing new code — it was true as of
  this task's own `git grep` pass, 2026-09-10.
- **June mechanism 1** (`qa/endurance/2026-06-14-582bd69/report.md` §3.3) already names "low-frequency
  sideband contamination from DC/hum" as a candidate mechanism, pre-`c3a9ea8`, uncentred, **not a
  baseline** — a lead to test, not a prior finding to confirm by assumption (HK-026: the estimator
  under test cannot be used to define its own ground truth).
- `openspec/specs/ft8-decoder/spec.md:93-97` records that a *different*, already-fixed defect (the
  original global-floor rolloff, up to −22 dB at 2800–3000 Hz) was closed by moving to the per-signal
  local floor. This task's target is the opposite end of the passband and post-dates that fix — do
  not assume the same mechanism or the same fix shape applies.

## 3. Method

### 3.1 Code read first (no run required for this part)

Read the full waterfall-construction path from PCM input to `mon.wf.mag` (FFT windowing, any
existing DC-removal or pre-emphasis stage, block striding) for anything that treats low-frequency
bins differently — deliberately or as an unintended side effect (e.g., a window function's roll-off,
a leaked DC bin, an off-by-one in bin indexing near 0). Report findings even if entirely negative
("no low-frequency-specific code path exists; the effect must be front-end/hardware, not software"
is itself a usable answer that redirects the investigation).

### 3.2 If the code read is inconclusive: bounded instrumentation, reusing the D-001 task's guardrail

Add a Debug-level log line (gated the same way as the existing candidate-count/LLR diagnostic —
`Logging.FileEnabled=true`/`Logging.FileLogLevel=Debug`, no behaviour change) that records, for each
decoded candidate, the **raw per-bin magnitude values** in its `compute_local_noise_floor_db` sideband
window, not just the resulting median. Replay a small, seeded sample of already-identified low-band
under-read decodes (`freq_ow < 600 Hz`, `under` per `d003_live.py`'s own classification — the corpus
and harness already exist, `artefacts/20260908_live_run_1827-fp-floor-live-2`,
`qa/cycleframer-alignment-replay/d003_live.py`) alongside a matched sample of non-under-read decodes
in the same band, and a same-session sample from ≥600 Hz as a control. Compare the raw magnitude
distributions, not just the derived medians, across the three groups.

**This is instrumentation-only, per the D-001 isolated-miss task's own precedent (§4.5/§5 there):**
it changes what is *observed*, not what is *decoded*. It stays within HK-011's read-and-propose
boundary — no shim logic changes, only added logging.

### 3.3 Reproducibility gate

Before drawing any conclusion from replayed audio, confirm each replayed decode still reproduces its
original SNR reading (same `under`/not-`under` classification as the corpus's own `ALL.TXT`). A
decode that reads differently on replay than it did live means the replay harness, not the
estimator, is what's being measured — report that fraction explicitly, the same discipline the
D-001 task's Gate R applied.

## 4. Rigour controls

1. **Do not use the estimator under test to define ground truth** (HK-026) — the comparison is
   always OpenWSFZ's own raw magnitudes across frequency bands, or OpenWSFZ vs the WSJT-X-derived
   `under`/not-`under` labels already computed by `d003_live.py`, never "is this value plausible" by
   eye.
2. **A negative code-read result is a valid, reportable outcome** — do not force a software
   explanation if the read finds none; say so and flag the audio front end (DC coupling, ground loop,
   Voicemeeter routing) as the next place to look, without investigating hardware here.
3. **No decode-behaviour change anywhere in this task.** Any code touched is diagnostic logging only.
4. **State the taper, don't sharpen it.** The result file's exploratory 600–1000 Hz vs ≥1000 Hz split
   is explicitly non-citable (HK-021(y), post-hoc). Use it only as a soft prior for where to draw
   comparison-group boundaries in §3.2, never as a confirmed boundary in the report.
5. **This does not reopen `D003-LIVE` ROW 2** or its acceptance. The rate and the row stand; this
   task is strictly about mechanism.

## 5. Scope guardrails — what this is NOT

- **Not a fix.** No `src/` change beyond diagnostic logging is authorised here. Per HK-011, any
  correction shape this investigation surfaces goes back to QA/Architect/Captain as a separate,
  explicit proposal before a single line of decode-behaviour code changes.
- **Not a new capture.** All audio needed already exists in
  `artefacts/20260908_live_run_1827-fp-floor-live-2`.
- **Not a re-run of the `D003-LIVE` gate.** The rate (`R_u=4.85%`, ROW 2) is accepted and closed;
  this task does not touch it.
- **Not a claim about D-002.** The gain/slope error and this band-specific under-read are recorded as
  independent findings; do not let this investigation's results be read as evidence about the other.

## 6. Deliverables

1. A short report (QA-reviewed before wider circulation, per HK-015's escalation direction) stating:
   the code-read findings (§3.1), and if instrumentation was needed, the raw-magnitude comparison
   across the three groups (§3.2) with the reproducibility fraction (§3.3) reported explicitly.
   Ends with a plain verdict: mechanism (a), (b), neither, or genuinely mixed — and, only if a
   mechanism is identified, a **description** of candidate correction shapes (not a diff, not applied
   code) for QA/Architect/Captain to evaluate separately.
2. Any diagnostic logging added, committed, clearly marked as diagnostic-only (mirroring the existing
   candidate-count/LLR instrumentation's own framing in `Ft8Decoder.cs`).

## 7. References

| Reference | Content |
|---|---|
| `DEFECT-d003-live-audio-low-frequency-snr-underread.md` | The measurement this task investigates the mechanism for |
| `qa/rr-study/2026-09-10-1550-qa-to-architect-d003-live-result.md` | Full `D003-LIVE` result, incl. the corrected frequency split and the exploratory 1000 Hz sub-cut |
| `qa/rr-study/2026-09-10-1556-architect-d003-live-acceptance-ruling.md` | Acceptance ruling and the split correction |
| `qa/cycleframer-alignment-replay/d003_live.py` | Harness — reuse its classification, don't reimplement |
| `qa/endurance/2026-06-14-582bd69/report.md` §3.3 | June mechanism 1 (DC/hum), the leading hypothesis — not a baseline |
| `src/OpenWSFZ.Ft8/Native/ft8_shim.c:909-927,1124-1183` | `compute_noise_floor`, `compute_local_noise_floor_db` — the functions to read first |
| `DEFECT-snr-reported-gain-error.md` | D-002 — a related but independent SNR defect (whole-range slope error) |
| `dev-tasks/2026-07-22-d001-isolated-miss-pipeline-diagnosis-spec.md` | Precedent for this task's shape: instrumentation-only investigation, reproducibility-gated, negative results reportable |
| `openspec/specs/ft8-decoder/spec.md:93-97` | The already-fixed high-frequency rolloff defect — a different mechanism, do not assume it recurs here |

---

*Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>*
*Claude-Session: https://claude.ai/code/session_01NseChs8GHWxH7dJ8L9pwC2*
