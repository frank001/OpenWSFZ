**User-facing:** yes (a new configuration key, `decoder.coherentFallbackAudio`, whose absent value changes what the daemon decodes)

## Why

The coherent fallback decodes candidates the first passes missed, and it has so far read the **original** cycle audio. The probe (COH-FB-RESIDUAL) and its B2
measurement ran it on three audio choices on the same 400 cycles of night `20260925_2010` (PC, build `9ef703d0`, descriptive only): the original audio,
the audio left after the earlier passes subtracted what they decoded (the step-down residual buffer), and **both**, merged by payload.

| Replay, 400 cycles | NET (pp) |
|---|---|
| Residual − Original | +3.60 [3.07, 4.13] |
| Both − Residual | +0.98 [0.74, 1.25] |
| Both − Original | +4.59 [4.26, 4.92] (the offline union is +4.56) |

The Captain picked **`Both`** as the default on 2026-10-28 (*"Go with both"*) after those figures and QA's `FBAUDIO` R&R sweep on `sol` (all validity rows PASS,
0 false positives, 0 abandoned runs; Section 6 decodes per WAV, OpenWSFZ minus WSJT-X, −4.06 [−4.84, −3.31], descriptive, a new era row). Architect spec:
`qa/rr-study/2026-10-27-1818-architect-to-qa-coh-fallback-residual-replay-spec.md`, Amendments 2 and 4 (`arch/coh-fallback-residual`, `bde72dc8`; read with
`git show bde72dc8:<path>`).

One fact shapes the safeguards. `Both` runs the fallback twice on **one shared time budget**. On `sol` (FX-8350) the fallback ended as late as **12,276 ms**
into the cycle, **724 ms** before the 13 s limit (the Captain's PC: 8,238 ms). The guard that turns a slow-machine overrun into a lost second run instead of a
late cycle already exists in `9ef703d0`; this change requires a test of it (N-1) before merge.

## What Changes

- `src/OpenWSFZ.Abstractions/DecoderConfig.cs`: `CoherentFallbackAudio` enum (`Original | Residual | Both`), key `decoder.coherentFallbackAudio`, **an absent key reads `Both`**, an explicit value is kept, JSON as the enum name, case-insensitive on read.
- `src/OpenWSFZ.Ft8/Ft8Decoder.cs`, `CohFallbackAudioSelector`, `CohFallbackParallelRunner`: the three modes (already in `9ef703d0`); `Both` runs the residual first, then the original audio on what is left of the one budget, merges by payload (the residual row wins), and logs `audio=both(<level>)` with `fromOriginal`, `fromResidual`, `inBoth`.
- `src/OpenWSFZ.Daemon`: the key is read once per window, effective on the next window; config file and API only, **no Settings-page control**.
- Tests: the key's default and round trip, the merge as a pure function, the selector's step-down cases, and **N-1** (the budget guard).
- `VERSION`: one minor bump (0.66) for the arm, with every place the gates check. `REQUIREMENTS.md`: FR-099.

## Out of scope

A Settings-page control; any change to the fallback's candidate selection, its F1b gate or its multi-set walk; a re-measurement (B2 already ran `Both`
explicitly, so changing the default adds no decode path that was not measured); the live era row (stamped by the daemon's start time after the deploy).

## Era

Deploying starts the live era **"FB-AUDIO"** (`Both` is the default). Live figures are never pooled across it, nor with the "MS ON" era.

## Capabilities

### Modified Capabilities

- `ft8-coherent-fallback`: ADDED requirements for the audio key, its default and the shared budget.
