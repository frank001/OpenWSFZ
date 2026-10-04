**User-facing:** yes

## Why

Decodes reach the operator only after the whole 15 s slot has closed, then a further ≈ 0.5 s of decoding. #122 asked how much
of that can be brought forward. Gate 4a (`qa/rr-study/results/2026-10-03-122-gate4a-truncation-replay/report.md`, ruled
`qa/rr-study/2026-10-03-1435-architect-122-gate4a-report-ruling.md`) replayed four archived corpora and decoded a **zero-filled
copy** of the first part of each window. At a cut of **x = 2.0 s** (13.0 s of audio) the early decode already held about **98 %**
of what the full window gives (`C(2.0)`: P 0.984, R 0.983, X17 0.988, X80 0.987), and it took about as long as the full decode
(`t(2.0)` ≈ 527 ms against `t(0)` ≈ 534 ms), so those decodes would appear **about 2 s earlier**.

Two things the same gate also showed are why this is not just "decode earlier":

- the early decode also finds a few rows the final decode does not confirm (`S_unc` 0.17 to 0.47 per 100, `S_corr` 0.26 to 1.29
  per 100), so the panel needs to **mark** early rows and say which were **confirmed**;
- on corpus P one final decode in 20 175 was lost when early decodes ran first in the same process (V2: 1 074 of 1 075 cycles
  identical; the Engineer's re-run D1 showed the flag-OFF decode itself reproduces 1 075 of 1 075, so the loss is attributed, not
  proven, to **shared state from the early decodes**). A build must therefore protect the final decode **by construction**.

The Captain authorised the build on 2026-10-03 (about 14:31Z, the Architect's window: *"1. agreed"*) with these defaults: the
automation ignores early decodes the final decode does not confirm, the panel shows them marked, the cut point is 2.0 s, and the
first phase is **panel only** (the automation follows after step 2, progressive batches). The Architect's spec is
`qa/rr-study/2026-10-03-1440-architect-to-qa-spec-122-step4-early-decode.md` (`arch/122-latency` `c41a0c30`, with D1's ruling
`c1a75d10`).

## What Changes

When a cycle's window holds `earlyDecodeCutSeconds` before its end (default 2.0 s, so 13.0 s of audio, 156 000 of 180 000
samples), the daemon decodes a **copy** of that partial window, zero-filled to full length, **pass 0 only**, and publishes the result
to the **decode panel only** as an *early* batch with each row marked *early*. At the slot end the ordinary decode runs as today and
publishes to every consumer as today. On the panel a final row that matches an early row (same text, |Δf| ≤ 10 Hz, one-to-one)
**confirms** it: one row, mark removed. An early row no final row confirms stays, marked *unconfirmed*. ALL.TXT, external reporting
(UDP), the QSO answerer and caller and the cycle-audio archive see nothing of the early batch.

- New capability **`early-decode`** (trigger, never-in-the-way rule, panel-only delivery, confirm and mark, config, log line,
  flag-OFF identity, the pass-0-only entry, the dial-frequency guard).
- New requirement on **`ft8lib-interop`**: the process-global callsign-hash state the native decode mutates can be **saved and
  restored** around the early decode (new exports, new `FT8_SHIM_VERSION`), so the final decode is unaffected **whatever the
  mechanism of the V2 loss turns out to be**.
- Config: `decoder.earlyDecodeEnabled` (default **true**: the Captain decided "default on" on 2026-10-04, after the build and the A3 live run; it was specified and built default false), `decoder.earlyDecodeCutSeconds` (default 2.0, range 0.5 to 3.0).
- Web: new panel messages and marks (visual and accessible), no change to the existing `decode` message.
- `FT8_SHIM_VERSION` bump, `libft8.dll` and `libft8.so` rebuilt (macOS by CI), `VERSION` and `REQUIREMENTS.md` (FR-083).

## Impact

- **Code:** `src/OpenWSFZ.Ft8/CycleFramer.cs` (early window emission), `src/OpenWSFZ.Ft8/Ft8Decoder.cs` (a pass-0-only early entry),
  `src/OpenWSFZ.Ft8/Native/ft8_shim.c` and `ft8_shim.h` (hash-state save/restore), `src/OpenWSFZ.Ft8/Ft8LibInterop.cs`,
  `src/OpenWSFZ.Daemon/` (a decode gate, an early-decode service, `Program.cs` wiring), `src/OpenWSFZ.Abstractions/DecoderConfig.cs`,
  `src/OpenWSFZ.Web/` (event bus, WebSocket messages, config overlay), `web/js/main.js` and the panel markup.
- **CPU:** one extra ordinary pass-0 decode (≈ 0.5 s of one core) per cycle, inside the capture window, while a residual pass of the
  previous cycle may still be running. The never-in-the-way rule skips the early decode when the decoder is busy; A3 measures it live.
- **Not changed:** the final decode, batch 2, the answerer and caller, ALL.TXT, UDP, the archive, the decode-filter admission, and
  every default EXCEPT this flag's own default, which the Captain set to ON on 2026-10-04 (it was OFF when built and measured).

## Out of scope (stated, not forgotten)

- **Phase 4b**, the QSO automation acting on early decodes. Per the Captain's default an early decode the final does not confirm
  is dropped from the automation's state when the final batch arrives; its own spec comes after step 2 (progressive batches).
- Any **decode-rate claim**. Early-only decodes corroborated by WSJT-X are shown on the panel but reach no log; whether they should
  reach ALL.TXT is the Captain's separate decision, after A3.
- Running the **residual pass** on the partial window (a decode-rate question, not part of this).
- Whether WSJT-X itself publishes early (step 1, the Engineer's, queued).

## Open decisions recorded for the review (QA's proposals, the Architect confirms)

1. R4 mechanism: **snapshot and restore** of the process-global hash state (recommended) over **suppressed writes**, see design D4.
2. The early rows pass through the **same visibility filter** (`DecodeNoiseSuppressionFilter`) as batch 1, so a row hidden at the end is not shown early (design D6).
3. Three requirements and two acceptance rows QA adds to the Architect's list (design D10): R9 pass-0-only entry, R10 dial-frequency
   guard, R11 same visibility filter, **A1b** (flag ON, nothing early reaches ALL.TXT, UDP, the QSO channels or the archive) and an
   **A2 positive control** on the known failing cycle.
