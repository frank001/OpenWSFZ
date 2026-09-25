# 2026-09-21/22 session log — LIVE-GAP-MAP 24 h endurance run

**Why this document exists**: the Captain asked for this session's ANOVA report treatment for
comparability with earlier endurance sessions (his 2026-07-27 standing instruction). This is that
document — the narrative account, cross-referenced against the quantitative ANOVA table in this
same directory and against the pre-registered `LIVE-GAP-MAP` harness result, which lives with the
corpus itself (gitignored, real callsigns) rather than here.

**Cross-references**: `anova_report_20m.md`/`.html` (this directory, the matched-decode ANOVA);
`artefacts/20260921_1624_live_run-live-gap-map/` (the corpus — gitignored, NFR-021 — `HANDOFF.md`,
`results/lgm_result.json`, `results/lgm_stdout.txt`); the published spectral-evidence artifact,
`https://claude.ai/artifact/T7pRfvXhmvpb3qK3KPgzvo` (private; share on request); spec
`qa/rr-study/2026-09-21-1555-architect-to-qa-spec-live-gap-map-24h-20m.md` (`arch/live-gap-map`,
Amendments 1–2).

---

## 1. The run

24 h unattended live capture, 20 m (14.074 MHz), one radio (Yaesu FT-991A) feeding both decoders
on the same Windows audio endpoint (`Voicemeeter Out B1`) — OpenWSFZ (`decoding_improvement`
`84cac119`, `libft8.dll` SHA-256 `38a21f84…1cba`, shim `20260054`, `nhard` 40, suppression triple
default `(−5,+15,1)`) against a real, separately running WSJT-X 2.7.0 (`NDepth=3`, no AP bit).
Window `2026-09-21T16:28:15Z → 2026-09-22T16:28:15Z`.

ROW 0a–0d passed at arm time as code (identity, params, one-audio-stream, reference depth). One
supervisor swap at `19:05:13Z` (a flashing-console bug in the supervisor's own health-loop
subprocess calls — fixed same session, `qa/live-gap-map` `3e1701f3`), cost exactly one 15-second
cycle (`19:05:00Z`, dropped from both sides' counts, not scored as a miss). No other restarts;
teardown clean, zero orphan daemon processes.

## 2. The pre-registered result: VOID, not M1–M4

`ROW 0e′(iii)` (the WSJT-X-alive check) failed in one UTC hour (`2026-09-21 23:00`), so per the
spec's own table every `§3.6` gate row is **VOID** — the M1–M4 routing decision cannot be read off
this corpus. This was **not** a power shortfall: `ROW 0g` cleared with `n_ref = 128,171` against a
40,000 floor, over 3× headroom. The descriptive figures (D1–D7) are still valid and reported in
`results/lgm_result.json`: `R_wild` 59.90% [58.84, 61.02] CI95, `H10` (the strong-miss pool) 19.21 pp
[18.51, 19.90] CI95, on 128,171 REF rows — citable only with the run's full qualifiers, never
compared with `A1` (61.09%) as a build effect (13 days apart, different propagation/density/band
conditions).

## 3. Why it voided: an interference episode, not a closing band alone

Traced the nine `0e′(iii)`-failing cycles to the sample. Five are genuine propagation silence
(RMS 9–42, matching the fully-established `01:00–02:00Z` dead-hour baseline exactly). Four are not:
RMS 750–950, indistinguishable from a normal busy cycle, yet **zero decodes on both sides**.
Spectral analysis (Welch PSD + STFT) of those four shows a flat, structureless floor filling the
entire 0–2800 Hz FT8 passband edge-to-edge, cut sharply at the receiver's own anti-alias filter —
not a discrete tone, not a legible carrier, not FT8. No ADC clipping anywhere in the run
(`clipped_samples` is zero across all 5,778 archived cycles), so whatever raised the floor stayed
inside the receiver's linear range throughout.

**Full-run scan** (all 5,778 cycles, floor > 20 dB and peak−floor contrast < 10 dB, calibrated from
the four traced cycles): zero hits in 4,338 day/evening cycles; **189 of 1,440 night-window cycles
(13.1%)**, concentrated — not spread through the night. Dense from about `23:20` to `00:05Z`
(most 5-minute bins 60–95% of cycles affected), tapering out by `00:10–00:15Z`, then **genuinely
clean from `00:15` to `03:30Z`** (over 3 hours, floor back to −30 to −45 dB, the true-silence
signature), with a few small blips `03:45–04:00Z` as the band reopens. The bounded shape — abrupt
onset, ~70-minute episode, clean stop — argues for something with a start and an end (a
transmission, a device on a schedule) over an all-night characteristic of the location or of
grey-line propagation (which strengthens discrete signals gradually, not this). Full spectrograms,
timeline and reading: the published artifact linked above.

**This doesn't rescue the VOID.** `0e′(iii)` doesn't distinguish a closed band from a masked one —
either way REF produced nothing usable in that stretch, and VOID is the correct, pre-registered
response regardless of mechanism.

## 4. The ANOVA (this directory)

`endurance_anova_wsjtx.py` against the corpus's own `openwsfz/ALL.TXT` and
`wsjtx-1-ft991a/ALL.TXT` (both already session-windowed, no filtering needed). **Grid-alignment gate
PASSED clean on both sides (G=1.0000, ROW 1)** — no cycle-clock drift on this build, unlike the
2026-08-02 multi-day run's `8080` leg; the pooled table below needed no grid-snapping.

- OpenWSFZ decoded 77,985 in-window; WSJT-X 128,369. Matched: 76,961 (98.7% of OpenWSFZ's decodes,
  60.0% of WSJT-X's — WSJT-X-only is 40.0% of its total, the same population the harness's `H10`
  strong-miss pool is drawn from).
- SNR: OpenWSFZ mean −2.575 dB vs WSJT-X 0.088 dB (grand mean −1.244 dB).
- DT: OpenWSFZ mean 0.9377 s vs WSJT-X 0.2844 s (grand mean 0.6111 s) — **notably wider apart than
  the 2026-08-02 comparator** (0.322 s vs 0.213 s there); flagged for your read, not interpreted
  here per the tool's own convention.
- Frequency offset: OpenWSFZ 1486.6 Hz vs WSJT-X 1486.5 Hz (grand mean 1486.5 Hz) — statistically
  significant (large n) but practically negligible, as in every prior endurance session.

Every `P` above is 0.0000 at this `n` (tens of thousands of Parts) — expected, and per the tool's
own caveat, the interaction and residual terms are confounded in this unreplicated design; each
table says only whether the two appraisers' *mean* differs, not whether that difference itself
varies signal-to-signal. Cross-run comparison and interpretation is Architect/Captain territory.

## 5. What's left open

- **The formal, spec-routed result report to the Architect** (`§3.7`, VOID + D1–D7 with full
  qualifiers) is not yet written — this document and the ANOVA table are the endurance-comparability
  side of the work; the spec routing is a separate, still-outstanding piece. Say if you want it now
  or after your review here.
- **Supervisor design gap, not yet fixed**: `--resume` always stops and restarts the daemon rather
  than re-attaching to it, because the health loop depends on a `subprocess.Popen` handle only the
  *original* supervisor process holds. A `psutil.Process(pid)`-based re-attach would let a future
  resume happen with zero capture gap. Flagged, not built.
- **Physical cause of the 23:00–00:10Z episode**: not identified from audio alone. Consistent with,
  not proof of, a local source with a roughly hour-long schedule.
- Whether to re-arm a fresh 24 h capture for a clean (non-VOID) M1–M4 reading is your call.
