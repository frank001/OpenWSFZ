# GHOST-HARVEST H0 (desk and smoke): time reversal yields no decode at all in 20 cycles, and it cannot reach the late batches by construction; the corpus is far larger than "40 m only"; an injection route is proposed.

**Written:** 2026-11-13, `date -u` read 11:42:27Z. **To:** Architect, then the Captain. **Authority:** the Captain, "go with option a" (H0). **Basis:** the TA-RES ruling `cf61d84c` §3. A 20-cycle smoke (about 20 s of decoder time; station quiet; no timing compared). Nothing frozen; no spec exists.

## 1. The smoke: 20 cycles of `20261110`, each time-reversed

- **Build and flags:** `bin_v2` (v2 tree `59eb5a8f`), arm B's exact flags, the first 20 of the 500 cycles, each WAV reversed sample by sample (mono, 16-bit, 12 kHz, 180,000 frames, same names), preceded by the night's own warm-up cycle (unreversed) so the hash table holds real calls as in arm B. WSJT-X's `ALL.TXT` passed only to keep the flags valid.
- **Result: 0 decodes in all 20 cycles, in every batch** (b1 to b5 all 0; nc-dump empty). The first fallback run found **0 CRC-valid payloads out of 4,000 candidates** (200 per cycle). So reversal removes every real signal, **and the pipeline's ordinary false-decode rate on this clutter is below what 20 cycles can see** (95 % upper bound for 0 of 20: 0.15 per cycle, no more than that).
- **Speed:** with nothing to decode a cycle takes **0.78 s median** (0.84 max), against ≈ 5 s on the real night: 500 reversed cycles ≈ 7 minutes, so volume is cheap.

## 2. The structural limit (read in the logs, not inferred)

- In all 20 cycles the residual pass **did not run** (`resrun = no-residual` 20 of 20; the late round `skipped-nothing-decoded` 20 of 20; no third pass). The fallback ran once, on the original audio.
- **Reason:** subtraction needs decoded real signals to subtract. With none, there is **no R2, R3 or X3 buffer, no residue, no burial**. A reversed-only harvest can therefore produce ghosts of **batch 1 and of batch 4's original-audio run at most**, never the late-batch ghosts that were refused (LATE-SUB arms C and L, made after subtracting strong real signals), and never ghosts made from the residue R reads.
- Consequence for the question that matters (R's false-present rate on the buffer it came from): **time reversal alone cannot answer it.** I confirmed this before proposing anything.

## 3. A route that keeps the clutter and restores the subtraction path (proposed, not built)

**Reversed real clutter + injected synthetic signals with known truth.**
- Background = a reversed cycle of a real night (the night's noise and spectral clutter, no valid signal). Foreground = N synthetic FT8 signals injected at known frequencies, dts and levels, using the repository's own synthesiser (`qa/rr-study/synth`: encoder, modulator with fading and channel; Q-prefix callsigns only, NFR-021), at the densities and SNR classes of the real night (overlaps included, so strong signals get subtracted and weak ones are buried, as in the real pipeline).
- **Truth is exact:** every published decode not in the injected set is a ghost, in every batch, with the subtraction path active. U′ on O and R on each decode's own buffer can then be scored on real decoder ghosts, by batch, for the first time.
- **Known costs and risks:** (a) the synthesiser has a documented DT clamp and a WSJT-X DT convention offset (memory note `modulator-positive-clamp-and-dt-convention-defects`); (b) the injected signals are clean models, so subtraction on them is better than on real signals, which **lowers** residue ghosts (the safe direction for a "R is circular" finding, the unsafe one for "R is safe"); (c) the false-decode rate is still unknown: 0 per 20 cycles says it is low, so volume matters (below).
- **Alternative (cheaper to build, weaker):** the R&R synthetic corpus on file (`rr-s6-refset-corpus`, 15,680 WAVs with truth) replayed on today's stack: exact truth and the subtraction path, but AWGN instead of real clutter.

## 4. The corpus (listed as the Captain's 2026-10-03 rule requires; E165's "all 40 m" was about the nights with WSJT-X pairing)

**59 artefact folders hold ≥ 100 WAVs (267,114 files in all, with duplicates).** A ghost harvest needs audio only, not WSJT-X's text, so any of them is a candidate. Dial frequency read from each folder's `ALL.TXT` where one exists:

| band (dial) | folders with WAVs (examples; WAV counts) |
|---|---|
| 40 m (7.074) | the endurance nights `20260922` … `20261110_1817` (5,766 to 11,524 each), `20260723`, `20260724_2227`, `_24h_usbcodec…` |
| 20 m (14.074) | `20260731_2004-8080` / `-8081` (20,958 / 20,981), `20260803_1713` (9,934), `20260808_0016` (5,495), `20260921_1624` (11,550), `rr-s6-refset-corpus` (15,680), and the `_rr_*` baselines |
| 80 m (3.573) | `20260726_2106` (5,558), `20260727_2048` (5,941), `20260809_0155` (3,956) |
| 10 m (28.074) | `20260728_1319` (4,628), `20260729_1831-8081` (5,773) |
| 17 m (18.100) | `20260808_1154` (3,714) |
| no `ALL.TXT` found | the older R&R sweeps and `20260613` to `20260706` live runs (several thousand each) |

Duplicates: the `-8080` / `-8081` pairs and the `*_daemon_output` folders are probably the same captures seen twice; I did not de-duplicate. Every WAV I opened is mono 16-bit 12 kHz, 180,000 frames.

## 5. What it would cost (sizing, not a spec)

| item | estimate |
|---|---|
| reversed-only harvest (batch 1 and batch 4 on O only) | ≈ 1 s per cycle: 5,000 cycles ≈ 1.4 h machine; QA ≈ 2 h; yields at most O-sourced ghosts, so it cannot test R |
| reversed + injection (recommended route) | QA ≈ 4–6 h (the injector, truth bookkeeping, a build of the scoring on the ghosts, self-test); machine ≈ 5 s per cycle with signals: 1,000 cycles ≈ 1.4 h, 3,000 ≈ 4 h (PC window each); the number of ghosts to read is the open risk |
| the number of cycles needed | unknown until a first injected smoke gives a rate; 0 of 20 says "low"; to read a late-batch ghost rate of 0.02 per cycle with a half-width of 0.01 needs ≈ 800 cycles per batch-class |

## 6. State

H0 done. Nothing is frozen; the 20 reversed WAVs and the smoke outputs are in `_qa-scratch\ghost-h0\` (no message text: the nc-dump is empty); `_qa-scratch\ta-res\`, `ta-check\` and `ta-mask\` kept. **The Architect specifies or stops; the Captain decides on the cost.**
