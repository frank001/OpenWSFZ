# Screenshot: waterfall contrast S4→S5 transition, 2026-07-01 ~20:21 local

**File:** `waterfall-contrast-s4-s5.png`  
**Captured:** 2026-07-01 20:21:04 local (18:21:04 UTC — S5 just completed, S7 starting)

## What is shown

Side-by-side waterfall displays at the S4/S5 boundary.  The waterfall history
(newest at top, older data scrolling down) shows roughly the last 3–4 minutes:
upper portion = tail of S4 (density, multi-signal), lower portion = S5 (pure AWGN
noise, no FT8 signal), with S7's first cycles just appearing at the very top.

| | **Left — Windows daemon** | **Right — Linux/WSL2 daemon** |
|---|---|---|
| Audio device | Voicemeeter Out B2 | pulse (ft8loopback.monitor) |
| S4 signals | Bright, sharp vertical lines | Same signals + rich inter-signal texture |
| S5 noise floor | **Near-black** — invisible | **Bright blue/cyan** — clearly visible |
| Overall character | Clean, low apparent noise | Full dynamic range, complex spectrum |

## Why the waterfalls look so different

Both daemons received the **identical audio signal** from `ft8combined`.  The
difference is entirely in the audio routing path gain:

```
ft8combined → ft8loopback.monitor         Linux daemon   (full 0 dB gain)
ft8combined → RDPSink → WSLg → Voicemeeter AUX → B2   Windows daemon (~−18 dB gain)
```

The Voicemeeter AUX→B2 routing introduces approximately **−18 dB of gain** relative
to the direct ft8loopback path.  This has two visible consequences in the waterfall:

1. **S4 signals (upper portion):** Both waterfalls show the multi-signal density
   injection.  On Linux, the individual FT8 carriers and their GFSK tonal structure
   are clearly resolved, including inter-signal interference patterns and the shared
   AWGN floor.  On Windows, the signals arrive at −18 dB — still decodable, but the
   noise floor and fine spectral structure are compressed below display threshold,
   producing clean sharp lines on a black background.

2. **S5 noise (lower portion):** S5 injects pure AWGN with no FT8 signal at
   −10/−20 dBFS.  On Linux, the noise fills the display with visible spectral
   texture.  On Windows, the same noise, attenuated by 18 dB, is indistinguishable
   from the display's black noise floor — it **disappears entirely**.

## Significance for the R&R study

This screenshot is a direct visual demonstration of the **primary R&R finding**:
the two audio paths are not gain-matched.  The ~18 dB gain difference explains:

- The SNR offset observed in every decode (Linux reports ~18 dB less than Windows
  for the same injected signal)
- The apparent frequency offset (~16 Hz) on Linux (resampling through the
  combine-sink's 48→44.1→48 kHz chain for the RDPSink slave)
- The DT bias (~−1 s on Linux) from the shorter ft8loopback path vs the longer
  WSLg/Voicemeeter chain

**This is not a decoder defect** — both libft8.so and libft8.dll are decoding
correctly given what they receive.  The gain difference is an artefact of the
audio routing setup and must be normalised (or characterised) before comparing
absolute SNR measurements between platforms.

**H₀_SNR is expected to be rejected** in the analysis.  The question for
follow-on work is whether the gain difference is inherent to the Voicemeeter
routing or can be removed by adjusting the Voicemeeter B2 strip gain.

## Audio routing at time of capture

```
WSL2 synthesiser (S5: pure AWGN noise, −10/−20 dBFS)
      │
      ▼
ft8combined
      ├──── ft8loopback.monitor ──── Linux daemon
      │     (full amplitude; noise floor clearly visible in waterfall)
      │
      └──── RDPSink ──── WSLg ──── Voicemeeter AUX ──── B2 ──── Windows daemon
            (~−18 dB path gain; noise floor disappears below display threshold)
```
