## Context

The R&R study harness (`qa/rr-study/`) plays synthesised FT8 audio into VB-CABLE while WSJT-X and OpenWSFZ decode it. The existing scenarios (S1–S7) are all controlled single-variable experiments: one signal at a time (S1/S2/S3), one density level at a time (S4), or one controlled overlap pair at a time (S7). This is appropriate for statistical measurement but means the study never presents either appraiser with the kind of holistic multi-station scene that characterises real on-air FT8. The audio sounds clinical, individual FT8 signals are perceptually thin and rapid at the 6.25 Hz tone-change rate, and the session gives no holistic sense of comparative decoder performance in realistic conditions.

The `channel.mix_to_shared_floor()` primitive and the S7 compound renderer already implement everything needed. S8 is primarily a scenario definition, a dispatch branch, and an analyser section — not new synthesis capability.

## Goals / Non-Goals

**Goals:**

- Add scenario S8 with a fixed 12-station band profile spanning 450–2550 Hz at realistic SNR spread (−15 to +3 dB), covering diverse message types (CQ, exchange, acknowledgement).
- The rendered audio SHALL sound perceptibly like a real busy FT8 band when played through VB-CABLE.
- Run S8 first in the study sequence so the Captain hears a realistic scene before the controlled experiments begin.
- Report holistic decode rate per appraiser (messages decoded / messages injected) with between-appraiser delta. No PASS/FAIL gate.
- Truth logging follows the S7 pattern: one truth row per signal so the matcher scores each independently.

**Non-Goals:**

- S8 does not replace S7 (co-channel overlap) or any other controlled scenario.
- S8 does not introduce a new PASS/FAIL threshold — it is an informational benchmark only.
- S8 does not add new synthesis primitives; `mix_to_shared_floor()` and `modulate()` are used as-is.
- Frequency drift, Doppler, or phase noise modelling are explicitly out of scope for this change (separate concern, possibly a future change).
- S8 does not target the D-001 co-channel defect directly; that remains tracked under GitHub issue #3 and will require PCM-domain SIC work.

## Decisions

### D1 — Fixed, human-readable band profile (not procedural)

**Decision:** The 12-station band profile is fully specified in `s8-band-scene.json` as an explicit `signals` array (message text, audio frequency, SNR, dt_s), not generated algorithmically at run time.

**Rationale:** A fixed profile makes every study run comparable across software versions. The Captain can inspect, adjust, and reason about the scene without reading code. Procedural generation would produce a different scene each run (or require a fixed seed and complex re-documentation), obscuring which signal was or was not decoded.

**Alternative considered:** A parameterised generator (similar to S4's `n_signals` + `snr_db_set`) — rejected because S4 already covers density testing. S8's value is in a *specific, auditable, inspectable* scene that reflects real-world band activity, not a parametric sweep.

### D2 — 12 stations, 5 trials, no PASS/FAIL gate

**Decision:** 12 simultaneous stations; 5 trials per study (varying only AWGN seed); no gate criterion.

**Rationale:** 12 stations gives a rich, perceptibly realistic band sound without making the scene so dense that neither app decodes anything meaningful. Five trials yields a stable mean decode rate. No gate is appropriate because S8 is a holistic benchmark — there is no established reference decode rate to gate against. Adding a gate would require calibrating it against historical study data that does not yet exist for this scenario.

### D3 — S8 is optional; offered before the study starts

**Decision:** `run_study.py` prompts interactively at startup — `"Run S8 realistic band scene first? [Y/n]"` — and includes S8 only if the operator confirms. Passing `--skip-s8` on the command line suppresses the prompt and skips S8 unconditionally (for automated / unattended runs).

**Rationale:** S8 is a qualitative listening check, not a measurement. Forcing it into every run adds ~3 minutes of overhead on days when the Captain simply wants to re-run the controlled metrics. Making it opt-in at the prompt respects that — the default answer is Y (so a careless Enter includes it), but it is easy to skip. The `--skip-s8` flag ensures CI or scripted runs are not blocked waiting for input.

### D4 — Reuse S7 truth/matcher pattern

**Decision:** S8 writes one truth row per signal (same as S7) so the existing matcher scores each of the 12 messages independently.

**Rationale:** The matcher already handles per-signal truth rows correctly via the `text+freq` branch. Reusing this pattern avoids changes to the matcher and ensures S8 decode rate is computed on the same basis as S7.

### D5 — Band profile design

The 12-station profile is designed to satisfy three constraints simultaneously:

1. **Perceptual realism** — stations spread across most of the 300–3000 Hz SSB passband with realistic clustering (denser in the 650–1650 Hz sub-window).
2. **Scenario diversity** — includes at least one near-collision pair (≤ 12 Hz separation), one capture pair (≥ 6 dB SNR difference, co-frequency), and a spread of message types.
3. **Fit within the SNR operating range** — all stations between −15 dB and +3 dB; no station so weak it is theoretically undecodable, none so strong it dominates the noise floor estimate.

```
Station  Freq (Hz)  SNR (dB)  dt_s  Message
──────── ─────────  ────────  ────  ──────────────────────
A         450        −8       0.0   CQ Q1ABC FN42
B         650        −3       0.0   Q1ABC Q9XYZ −10
C         850       −12       0.0   Q9XYZ Q1ABC R−08
D        1050         0       0.0   CQ Q1AW FN31
E        1150        −5       0.0   Q1AW Q1ABC +05
F        1162        −8       0.0   ← near-collision with E (12 Hz apart)
G        1500         0       0.0   CQ Q9XYZ EN37
H        1500        −6       0.0   ← capture pair with G (same freq, −6 dB)
I        1650        −3       0.5   Q9XYZ Q1AW 73  (0.5 s late start)
J        1900       −15       0.0   Q1AW Q9XYZ RR73
K        2150        −8       0.0   CQ Q1ABC FN42
L        2550        +3       0.0   Q9XYZ Q1ABC R−08
──────── ─────────  ────────  ────  ──────────────────────
12 stations · 5 trials · 1 scenario part = 60 scored messages per study
```

This profile exercises: SNR spread, near-collision suppression, capture effect, time offset, and full-passband frequency coverage — all simultaneously, as they occur on a real band.

## Risks / Trade-offs

**[Risk] S8 adds ~2–3 minutes to each full study run** (5 cycles × 15 s + boundary-alignment overhead per cycle).
→ Mitigation: Acceptable at the current study duration. S8 runs first so the Captain can abort after it if only the holistic check is needed.

**[Risk] The fixed profile may become stale** — if the Captain adjusts station parameters between studies, results are no longer comparable to prior runs.
→ Mitigation: Treat the profile as a versioned document; increment `_format_version` in the JSON when parameters change, and note the change in the study report.

**[Risk] 12-station decode rate is not directly comparable to S7 metrics** — S7 tests specific overlap families; S8 tests a holistic scene. They measure different things.
→ Mitigation: S8 is reported in a separate section of the study report with its own framing. No attempt is made to normalise across scenario types.

**[Risk] Near-collision pair (E/F at 12 Hz) and capture pair (G/H co-freq) are already tested in S7** — S8 does not add new coverage for those families.
→ Mitigation: S8's value is the *combination* of all these conditions simultaneously in a realistic-sounding scene, not the individual conditions. S7 remains the controlled per-family measurement.

## Open Questions

*(none — all decisions are resolved above)*
