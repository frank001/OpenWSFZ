# D-001 Isolated-Miss Pipeline-Stage Diagnosis — Results Report

| Field | Value |
|---|---|
| Defect ID | D-001 (open, issue #3) |
| Type | Offline log-analysis + live local-replay diagnostic (no product/decoder code touched — instrumentation reuse only) |
| Governing spec | `dev-tasks/2026-07-22-d001-isolated-miss-pipeline-diagnosis-spec.md` |
| Decision context | `qa/rr-study/results/2026-07-07-b4bdf88-d001-cochannel-attribution/report.md` (Option B) — left the 8,236-miss (24.5%) Isolated class entirely undiagnosed at the pipeline-stage level |
| Analysis date | 2026-07-23 |
| Session analysed | 07-07 (`20260706_live_run_2308`) — the only session with retained per-slot WAV audio |
| Scripts | `materialise_isolated_sample.py` (§3.1), `run_isolated_replay.py` (§3.2–§3.4), both this directory |
| Numeric results | `isolated_sample_candidates.json`, `isolated_replay_results.json` (this directory) |
| Status | **COMPLETE — pilot (n=40 reproduced) verdict delivered below** |

---

## Section 1 — Study Hypothesis

### 1.1 What this pass answers

> Of the Isolated-class low-SNR misses (WSJT-X decoded, OpenWSFZ did not, no plausible
> co-channel interferer within 50 Hz), what fraction failed because OpenWSFZ's candidate
> search never proposed the signal — versus failed because a candidate was found but LDPC
> could not converge on it?

Option B (F=29.6%, mixed verdict) answered the co-channel question but left the mirror
question — the 24.5% of misses it classified **Isolated** — undiagnosed. Isolated misses are,
by construction, not something H7 (MMSE joint demodulation) can fix; this pass asks *which*
sensitivity question they actually are, reusing instrumentation and audio that already exist
(the always-on candidate-count/LLR diagnostic, and the 07-07 session's retained per-slot WAV
audio) — no new capture, no product code change.

### 1.2 Method summary (full detail in the governing spec)

1. **§3.1 (offline, safe):** extend `classify_cochannel.py`'s per-band loop (copy, not
   modified) to retain `(ts, freq_hz, wsjt_snr, band)` for every 07-07 miss classified
   Isolated at the primary 15 Hz cutoff, then draw a stratified, seeded, over-drawn sample
   (60/stratum) via `compute_seed`.
2. **§3.2 (live):** launch a throwaway local OpenWSFZ.Daemon instance (isolated
   `--config`/`--port`, never touching the operator's real config), configured via its own
   HTTP API for Debug file logging + ALL.TXT decode logging + VB-CABLE (`CABLE Output`)
   capture. Replay each candidate's retained `save/*.wav` slot, boundary-aligned to the FT8
   15 s cycle grid, preceded by a disposable noise "pre-roll" cycle for AGC settling.
3. **§3.3 (classification):** Gate R first — does the target message reappear on replay? If
   yes, the miss did not reproduce (tallied separately, Tier 0). If no, classify the cycle's
   Debug candidate-count/LDPC-fail-stats lines per the spec's table (candidate-generation
   failure / LDPC-convergence failure / Ambiguous).
4. **§3.4:** report both tiers; this is a **pilot (n=40 reproduced target)**, not a precision
   estimate, and pre-commits no new decision threshold — only Option B's existing F/mixed
   verdict stands as the Captain-locked reference.

### 1.3 Pre-committed decision thresholds

**None.** Per spec §4 rigour control 4, this is exploratory groundwork to determine *whether*
a dominant failure mode exists worth chasing — not a go/no-go gate the way Option B's F was.

### 1.4 Null hypothesis

Isolated misses reproduce reliably on replay (low Decoded-on-replay fraction) and split
cleanly toward one of candidate-generation-failure or LDPC-convergence-failure (low Ambiguous
fraction) — i.e., the existing pass-level diagnostic is sufficient to attribute the failure
mode without further instrumentation. **Rejected on both counts** (Section 3).

---

## Section 2 — Data Summary

### 2.1 Inputs (spec §2 Gate 0 — reconfirmed 2026-07-23)

| Input | Status |
|---|---|
| Isolated-class miss list, 07-07 session | Materialised fresh (not previously computed anywhere) — **3,688** misses, matching Option B's own per-session Isolated count for 07-07 exactly (cross-check) |
| Per-slot WAV audio, 07-07 | **100% coverage** — all 3,688 Isolated misses have an on-disk same-named `save/*.wav` (better than the spec's own caveat anticipated; no capture-gap losses) |
| Candidate-count/LLR diagnostic | Confirmed always-on in `Ft8Decoder.cs`; enabled via `Logging.FileEnabled=true` / `FileLogLevel=Debug`, no code change |
| Local binary used for replay | `src/OpenWSFZ.Daemon/bin/Release/net10.0/win-x64/publish/OpenWSFZ.Daemon.exe` (self-contained, non-AOT) — smoke-tested independently before the full run (banner, `/api/v1/status`, `/api/v1/audio/devices` all confirmed functional) |

### 2.2 Sample composition

| Band | Population | Drawn (over-draw) | Tried | Reproduced (Gate R) | Decoded-on-replay |
|---|---:|---:|---:|---:|---:|
| `< -15 dB` | 2,477 | 60 | 23 | 20 | 3 |
| `-15..-10 dB` | 1,211 | 60 | 36 | 20 | 16 |
| **Combined** | **3,688** | **120** | **59** | **40** | **19** |

Both strata reached their 20-reproduced-miss target well within the 60-try over-draw budget
(23 and 36 tries respectively) — no re-seeding was needed.

---

## Section 3 — Results

### 3.1 Tier 0 — Reproduction (Gate R)

| Band | Decoded-on-replay | Fraction | 95% Wilson CI |
|---|---:|---:|---:|
| `< -15 dB` | 3 / 23 | 13.0% | [4.5%, 32.1%] |
| `-15..-10 dB` | 16 / 36 | **44.4%** | [29.5%, 60.4%] |
| **Combined** | **19 / 59** | **32.2%** | [21.7%, 44.9%] |

**This is the headline finding.** Per spec §3.3's own pre-committed reading: a high
Decoded-on-replay fraction is a first-order finding in its own right, pointing at a
**live-path / timing / gain-staging difference** rather than a raw decoder-sensitivity gap —
and this is not a marginal effect. In the `-15..-10 dB` stratum, **nearly half** (44.4%,
95% CI up to 60.4%) of misses that Option B classified Isolated and that this pass confirmed
have no same-slot neighbour, decoded successfully the moment they were replayed in isolation
through a clean VB-CABLE loopback — with none of whatever was different about the original
live capture (AGC history, cycle-boundary/sample-clock alignment, adjacent-cycle state,
possibly real contemporaneous band conditions the recording cannot fully reproduce). The
`< -15 dB` stratum shows the same direction at a lower rate (13.0%), consistent with a
live-path effect that matters more once a signal is already only weakly capturable — a signal
9 dB further into the noise floor has less margin for a live-path handicap to still allow a
decode, so the reproduction fraction should be expected to fall as SNR drops, which is exactly
what is observed.

### 3.2 Tier 1 — CG vs. LDPC split (within the 40 reproduced misses)

| Verdict | `< -15 dB` (n=20) | `-15..-10 dB` (n=20) | Combined (n=40) | 95% Wilson CI (combined) |
|---|---:|---:|---:|---:|
| Candidate-generation failure (0 candidates) | 0 | 0 | 0 | — |
| LDPC-convergence failure (≤3 candidates, low LLR) | 0 | 0 | 0 | — |
| **Ambiguous** (>3 candidates) | **20** | **20** | **40** | **[91.2%, 100.0%]** |

**Every single reproduced miss landed in Ambiguous.** This is exactly the outcome the spec's
own §3.3 "power caveat" pre-registered as the likely result: the reused diagnostic is
pass-level and passband-wide, and the 07-07 session's real recorded band was consistently busy
enough that a clean CG-vs-LDPC attribution was never possible. Total-candidate counts per
reproduced-miss cycle ranged from 22 to 340 (median 340 in `< -15 dB`, 317 in `-15..-10 dB`) —
**340 is not a natural count, it is the native shim's hard candidate-buffer ceiling**
(`K_MAX_CANDIDATES` (140, pass 0) + `K_MAX_CANDIDATES_PASS2` (200, pass 1) = 340,
`ft8_shim.c`), and it was hit exactly in 12/20 (`< -15 dB`) and 9/20 (`-15..-10 dB`) of the
reproduced-miss cycles. In those cases the true candidate density may be even higher than
reported — the diagnostic saturated, not merely "found many." This reinforces, rather than
merely meets, the ≤3-candidate threshold's opposite conclusion: the passband genuinely was
busy, not borderline.

Because no reproduced miss ever had ≤3 total candidates, the reference meanAbsLLR baseline run
(spec §4 rigour control 1) was correctly skipped by the driver's own conditional logic — there
was nothing to compare against. (For the record, meanAbsLLR across all 40 Ambiguous cycles
clustered tightly at 3.9–4.2 regardless of candidate count, 22 to 340 alike — mentioned only
as an observation; it plays no role in the classification, which turns on candidate *count*.)

### 3.3 Caveats

- **n=40 is a pilot, not a precision estimate** (spec §4 rigour control 4) — the CIs above are
  wide, particularly for the `< -15 dB` Decoded-on-replay fraction (95% CI spans 4.5–32.1%).
- **Single session.** All data is from 07-07 only, the one session with retained WAV audio.
  The finding that the passband is "always busy enough to trigger Ambiguous" is a property of
  this specific real band-opening, not a general claim about every possible isolated miss.
- **Same downward-bias caveat as Option B, restated not re-derived:** this pass cannot see
  candidates OpenWSFZ never proposed at all as distinct from ones it proposed and rejected —
  the pass-level diagnostic cannot attribute any candidate to a specific frequency (§3.3 power
  caveat), which is precisely why Tier 1 saturated to Ambiguous.
- **Replay fidelity is not perfect live-air fidelity.** The 0.5 s cycle-boundary prewarm
  (mirroring `run_h6_probe.py`'s own convention) means playback begins fractionally before the
  daemon's own capture window opens and ends fractionally before the window's nominal close —
  a sub-second effect against a 15 s slot, expected to be negligible for FT8 decode, but noted
  for completeness.

---

## Section 4 — Verdict Table

| Question | Answer |
|---|---|
| Decoded-on-replay fraction (combined) | **32.2%** (95% CI [21.7%, 44.9%]) — high enough to be a first-order finding, not noise |
| Decoded-on-replay fraction, `-15..-10 dB` | **44.4%** (95% CI [29.5%, 60.4%]) |
| Decoded-on-replay fraction, `< -15 dB` | 13.0% (95% CI [4.5%, 32.1%]) |
| CG-vs-LDPC split (of the 40 reproduced misses) | **100% Ambiguous** — current instrumentation cannot resolve this question on this corpus |
| Null hypothesis (clean reproduction + clean CG/LDPC split) | **Rejected on both counts** |

---

## Section 5 — Recommendations

### 5.1 One-paragraph recommendation to Architect and Captain

The dominant, best-supported finding from this pilot is **not** a CG-vs-LDPC signal — the
existing instrumentation cannot deliver one on this corpus, exactly as anticipated — it is the
**32.2% (44.4% in the higher-SNR stratum) Decoded-on-replay rate**. Per the spec's own
pre-committed reading, this redirects the investigation away from both `ftx_find_candidates`
tuning and OSD-depth tuning, toward a **live-path / timing / gain-staging investigation**: some
combination of AGC warm-up state, cycle-boundary/sample-clock alignment, or adjacent-cycle
history present during live capture but absent from an isolated WAV replay is materially
affecting decode success for a meaningful fraction of what Option B labelled Isolated misses.
This is a cheaper, more directly actionable, and — given the effect size — probably
higher-value next step than commissioning the §4.5 per-candidate-frequency shim.

### 5.2 What this pass does NOT authorise

- **Not** a re-run of Option B's classification or its F=29.6%/mixed verdict — unchanged.
- **Not** a conclusion that the Isolated class is "solved" or "explained" — 67.8% of tried
  cases still reproduced as genuine misses, and of those, 100% remain pipeline-stage-unresolved
  (Ambiguous).
- **Not** a decoder or product code change of any kind.
- **Not** a precision measurement — n=40 pilot, single session.

### 5.3 Suggested next steps, in priority order

1. **Live-path/gain-staging investigation** (new, higher priority than originally scoped) —
   instrument or manually compare AGC/soft-limiter state, cycle-boundary timing, and
   adjacent-cycle history between a genuine live capture and an isolated WAV replay of the
   same historical slot, for a handful of the 19 Decoded-on-replay cases identified here (their
   `ts`/`freq_hz` are in `isolated_replay_results.json`... actually excluded from that
   committed file by design — re-derive via a fresh, small, explicitly-scoped follow-up rather
   than reusing this pass's already-discarded per-candidate message data).
2. **§4.5 per-candidate-frequency shim** — still the only route to a decisive CG-vs-LDPC
   answer for whatever fraction of Isolated misses turn out **not** to be a live-path artifact,
   once (1) has been investigated. Bounded, instrumentation-only, no decode-behaviour change,
   as originally scoped.
3. **A larger confirmatory sample** of this same pilot design — only if (1) does not fully
   explain the reproduction gap and a more precise Decoded-on-replay estimate is wanted before
   committing to (2).

---

## Appendix A — Reproduction

- `python materialise_isolated_sample.py` — regenerates the local population (`_work/`,
  git-ignored) and the committed candidate-sample skeleton (`isolated_sample_candidates.json`,
  msg-stripped per NFR-021).
- `python run_isolated_replay.py` — runs the full live pilot (target 20/stratum, over-draw
  60/stratum; pass `--target-per-stratum N --max-tries-per-stratum M` for a smaller smoke
  test). Requires: the self-contained `OpenWSFZ.Daemon.exe` publish output present, VB-Audio
  Virtual Cable installed (`CABLE Input`/`CABLE Output`), and `requests`/`sounddevice`/`numpy`/
  `scipy` importable. Produces `isolated_replay_results.json` (committed, ts/freq/snr/band/
  candidate-count/LLR/verdict only — no callsigns, no message text, per NFR-021).
- Total live session wall time for this run: **2026-07-23 15:05:46Z – 15:50:21Z** (~44.5 min),
  well inside the spec's own "a few hours" effort estimate.
