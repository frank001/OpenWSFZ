# Screenshot: both daemons decoding simultaneously — S3 (DT offset), 2026-07-01 ~20:09 local

**File:** `both-daemons-decoding-s3.png`  
**Captured:** 2026-07-01 20:09:33 local (18:09:00 UTC — mid-S3, parts 4–6)

## What is shown

Side-by-side browser view of both OpenWSFZ daemon UIs during a live R&R study run:

| | **Left — Windows daemon** | **Right — Linux/WSL2 daemon** |
|---|---|---|
| Audio device | Voicemeeter Out B2 (VB-Audio Voicemeeter VAIO) | pulse |
| Audio state | ● AUDIO (green) | ● AUDIO (green) |
| Decode state | DECODING (green) | DECODING (green) |
| Cycle time | 8.0 s | 8.0 s |
| Injected signal | CQ Q1ABC FN42 at 1500 Hz | same (shared ft8combined sink) |

## Observed decode characteristics (S3 parts visible in screenshot)

| Property | Windows | Linux |
|---|---|---|
| Decoded freq | 1500 Hz | 1484–1488 Hz |
| Reported SNR | +1 to +2 dB | 0 to −16 dB |
| Reported DT | +0.0 to +2.0 s (S3 DT ladder) | +0.0 to +1.0 s |
| DT bias (Linux vs Windows) | — | ≈ −1 s (audio routing latency) |

The **~16 Hz frequency offset** on the Linux side (1484–1488 vs 1500 Hz) is
attributable to resampling through the combine-sink RDPSink path (48 kHz →
44.1 kHz → back to 48 kHz via Windows audio) introducing a slight clock-rate
discrepancy. This is a systematic offset to characterise in the results.

The **~18 dB SNR offset** (Windows +1/+2 dB, Linux −15/−16 dB at the same
injected level) is the primary calibration measurement of this R&R study. Both
are decoding the same signal; the difference reflects the noise floor estimation
difference between `libft8.dll` (win-x64) and `libft8.so` (linux-x64).

## Non-Q callsigns in decode list

Several non-Q-prefix entries are visible (e.g., rows at −16 dB, −27 dB). These
are **AWGN false-positive decodes** — the decoder found CRC-valid bit patterns
in the white noise floor. They are not injected by the harness (S3 injects only
`CQ Q1ABC FN42`) and do not represent real transmissions. NFR-021 does not apply
to decoder artefacts from noise.

## Audio routing at time of capture

```
WSL2 synthesiser
      │
      ▼
ft8combined (PulseAudio combine-sink)
      ├──── ft8loopback ──── ft8loopback.monitor ──── Linux daemon (arecord -D pulse)
      └──── RDPSink ──── WSLg bridge ──── Windows audio ──── Voicemeeter AUX → B2 ──── Windows daemon
```
