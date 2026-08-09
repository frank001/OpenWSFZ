# Architect → QA: spec P2 + P3 — the input-conditioning arm, and the sub-lattice shift-union arm

**Author:** Architect, 2026-08-09 (01:29 UTC, from `date -u`, per HK-017). Repo `main` at `130f8a5`.
**Status:** offline in-process replay of WAVs already on disk. **No `src/` change, no rebuild, no
capture, no Developer session, no WSJT-X reconfiguration.** Both arms drive the **production**
`libft8.dll` through ctypes exactly as `w1_sec5_calibration.py` does.
NFR-021: **counts and rates only** in every committed artefact — message text lives in a scratch
directory outside the repo and is never copied in.
**Run order: P1a → P2 → P3.** All three are independent; this order is cheapest-first.

---

## 0. Provenance — where these two arms came from, and one correction I owe the record

The Captain proposed, in one breath: *softmax + temperature before the decoder; normalise; equalise;
filter; synthesise what we receive and feed that to the decoder.* I ruled three of the four dead from
code, and I was **partly wrong on one of them.**

**What I said:** the pipeline is provably gain-invariant, because `ft8_extract_symbol`
(`decode.c:1017-1030`) takes differences of dB values and `ftx_normalize_logl` (`decode.c:380-399`)
rescales the 174 LLRs to a fixed variance of 24.

**What is actually true:** that argument holds **only inside the waterfall's encoding range.**
`WATERFALL_USE_PHASE` is undefined, so `WF_ELEM_T = uint8_t` with `mag = x*0.5 − 120.0`
(`decode.h:25-31`) — a **127.5 dB window from −120.0 to +7.5 dB, quantised at 0.5 dB.** Outside it
every bin clips to the same value, the differences vanish, and the invariance argument collapses.
Measured on five real WAVs through the production DLL: **raw int16 → 3 decodes; the same audio
scaled by 1/32768 → 115 decodes.** A 38× swing from gain alone.

🔴 **This does not by itself mean production is mis-scaled** — `Ft8Decoder.cs:258` already forces
every buffer to `PcmNormalisationTargetRms = 0.20f` (≈ −14 dBFS), and live figures put signals near
−40 dB and the noise floor near −67 dB, comfortably inside the window. **But that constant was
introduced as the D-002 *SNR-bias* fix — a purpose the shim's own history records it FAILING at**
(the fix ended up being the −26.5 dB bandwidth constant) — **and it has never been validated
against recall.** A shipped constant, chosen for the wrong reason, sitting on a mechanism with a
demonstrated cliff, is worth exactly one arm. **P2 is that arm.**

**P3** is the surviving form of the Captain's last idea. Subtract-and-resynthesise is dead — built
three times (`20260007`, H3 `20260008`, H3b `20260009`) and reverted three times, H3b losing 17 pp
after fixing both diagnosed model errors. My hypothesis for why, offered as hypothesis: **you cannot
subtract a signal you cannot locate**, and we locate on a 3.125 Hz / 0.08 s lattice. But *"give the
decoder modified data"* has a version nobody has tried: **move the signal to where the grid already
is, and union the results.** That buys the missing sync refinement from outside the decoder.

## 0.1 Shared prohibitions

🛑 **P2 is NOT a parameter sweep against the architectural gap.** The architecture note's "do not
propose parameter sweeps" (D-009: 45 points, +0.109 pp) governs *downstream tuning knobs*. This is an
**input-conditioning term with a measured 38× cliff** and a ROW 2 that closes it permanently. One
arm, seven points, mechanism-derived. **If ROW 2 fires, it never gets proposed again.**
🛑 **Do not re-read T1, T2, H1, H1a or P1.** None of `G`, `D_int`, `U`, `M`, `A` appear here.
🛑 **No capture run.** Everything is on disk and `--check` clean.
🛑 **No `src/` edit.** P2 varies the scale **inside the harness**, before the ctypes call. A ROW 1
result is a *recommendation* about `Ft8Decoder.cs:52`, never an edit (HK-011).

---

## 1. Shared method

**Corpus.** 20m clean window `260808_004000`..`260808_111500`, **WSJT-X FT991A's own WAVs**,
`artefacts/20260808_live_run_0016-8080/wsjt-x/wav/` — **2 529 in-window files** of 2 748 in the
directory. Same window and same `REF` as P1, via `t1_frequency_quantisation.load`, `WINDOW_20M`,
`LEG_20M`. `REF` = intersection of the two WSJT-X instances on `(ts, message)` = **69 222**; verify
this reproduces exactly and abort if not.

⚠️ **We decode WSJT-X's audio, not our own capture.** That removes the capture-path variable (P1's
argument) but means the baseline is **not** the live 8080 number. Do not compare to 55.5%/57.8% as if
like-for-like; the ROW 0 band below is deliberately loose for this reason.

**Decoder.** `native/ft8_lib_build/libft8.dll`, **SHA256 `39aa1031ad63fd7c882ae9093a3d6c4d681f1c45e2a4f3b4336ff6c3f45e0aba`**,
`ft8_lib_version_check()` = **20260035**. 🔴 **Assert both at startup and record them in the report** —
five unmerged branches carry rebuilt DLLs and `FT8_SHIM_VERSION` collides twice, so version alone
does not identify a binary. Call `ft8_set_decode_params(10, 0.10, 60)` — the frozen production
triple. Buffers are 180 000 float samples (15 s @ 12 kHz); WAVs are mono 16-bit 12 kHz, confirmed.

**PCM convention.** Read int16, convert to float, **then normalise RMS to the arm's target** —
mirroring `Ft8Decoder.NormalisePcm`, including its `SilenceRmsThreshold = 1e-6` guard (return
unchanged, do not divide). P2's baseline point and **all** of P3 use **RMS = 0.20**, production's value.

### 1.1 🔴 Process isolation and the hash table

The shim's 256-slot callsign hash table is **process-global and never re-initialised**
(`ft8_shim.c:599-632`), and TLS diagnostics are per-thread. Therefore:

- **Parallelise with PROCESSES, never threads.** Threads share the table and race.
- **Within a process, decode a contiguous file partition in chronological order**, and for a given
  file run **all variants of that file consecutively** before moving to the next. This guarantees
  baseline and treatment see **identical** hash state, so `<...>` text effects are common-mode.
- ⚠️ **Disclose in the report:** partitioning across N processes gives each a private table, so
  `<...>` rates differ from a single-process production run. This is common-mode within every
  contrast here, but it is a real difference from production and must be stated, not buried.

### 1.2 Clustered error bars

Both headline metrics are counts over decodes, and **decodes cluster by frequency** (design effect
**2.52×** measured on this corpus in P1, **3.5–4.2×** in T2a). **Report a frequency-clustered
bootstrap CI**, ≥1 000 draws, seed **20260809**, resampling distinct `REF` frequencies with
replacement. Where a metric is a *difference* between legs run on the same files, the bootstrap must
be **PAIRED** — resample clusters once per draw, recompute both legs on those clusters, difference
inside the draw. 🛑 **No binomial interval may appear anywhere.**

---

## 2. P2 — does the shipped PCM scale cost decodes?

### 2.1 Sweep points, derived from the mechanism (not from any outcome)

Production sits at RMS 0.20 = −14.0 dBFS. Sweep **±18 dB in 6 dB steps**, symmetric about it:

```
RMS   :  0.025   0.05    0.1     0.20    0.4     0.8     1.6
dBFS  : -32.0   -26.0   -20.0   -14.0    -8.0    -1.9    +4.1
vs prod:  -18     -12      -6      0       +6     +12     +18
```

Seven legs × 2 529 files. **The points were fixed from the waterfall's dB window before any recovery
number was computed** — this keeps P2 blind and must be stated in the report.

### 2.2 Metrics

```
R(s) = 100 * |D(s) ∩ REF| / |REF|          recovery at scale s
P    = max_s R(s) − R(0.20)                 <- HEADLINE: recall left on the table by the
                                               shipped constant.  Same axis as G, D_int, M.
s*   = argmax_s R(s)
```

### 2.3 Pre-registered gate (HK-021)

```python
def p2_row0(n_cycles, ref_n, r_prod, r_by_scale, argmax_is_endpoint, p_val):
    if n_cycles < 800:
        return "ROW 0a"          # too few cycles
    if ref_n != 69222:
        return "ROW 0b"          # population is not the standing one; nothing comparable
    if not (45.0 <= r_prod <= 70.0):
        return "ROW 0c"          # our decoder on WSJT-X audio at production scale must land
                                 # near the believed 55-64% band (HK-021(e)); outside it the
                                 # harness is wrong, not the decoder
    if max(r_by_scale.values()) - min(r_by_scale.values()) < 1.0:
        return "ROW 0d"          # an 18 dB swing either way moved nothing: the scale is not
                                 # reaching the decoder -- instrument failure, not a null
    if argmax_is_endpoint and p_val >= 0.5:
        return "ROW 0e"          # optimum is outside the swept range: range too narrow.
                                 # Instrument limitation -- re-register wider, do NOT read P.
    return None

def p2_gate(p_val):
    if p_val >= 2.0:  return "ROW 1"
    if p_val <= 0.5:  return "ROW 2"
    return "ROW 3"
```

| row | consequence — as an assertion |
|---|---|
| **ROW 0a–0e** | **Instrument failure, not a null.** Report the failing check and its value. ROW 0e specifically means the range was too narrow — it is *not* evidence the constant is optimal. Do not repair-and-rerun in-session. |
| **ROW 1** (`P ≥ 2.0`) | 🔴 **`PcmNormalisationTargetRms = 0.20f` is mispriced and is a cheap D-001 treatment candidate.** Report `P`, `s*`, the full `R(s)` curve and the clustered CI. **Recommend to the Captain, with the number, a one-constant change at `Ft8Decoder.cs:52` — a recommendation, NOT approved work (HK-011).** 🛑 Do not edit `src/`. |
| **ROW 2** (`P ≤ 0.5`) | 🔴 **CLOSE input scaling permanently.** Assert into the board: PCM scale is not a recall lever within ±18 dB of production; the waterfall's 127.5 dB window is not binding at operating levels. **Neither normalisation, AGC, nor equalisation may be proposed again without new evidence** — this arm is the answer. |
| **ROW 3** (`0.5 < P < 2.0`) | Report `P`, `s*` and the curve. Real but small; fold into framing. No `src/` recommendation. |

### 2.4 Predictions

| # | prediction | tested by |
|---|---|---|
| 1 | `R(0.20)` = **52–64%** | ROW 0c |
| 2 | `P` = **0–1.5 pp** | the gate |
| 3 | **ROW 2 or ROW 3** — production is already on the plateau | the gate |
| 4 | The curve is **flat within ±6 dB** and falls off only at ±18 dB, with the **high** side falling harder (saturation is a harder wall than quantisation) | §2.2 curve |

---

## 3. P3 — does sub-lattice placement cost decodes?

### 3.1 The five legs

The lattice is **3.125 Hz / 0.08 s** (`K_FREQ_OSR = K_TIME_OSR = 2`, `ft8_shim.c:469-470`). Three
positions per axis, evenly spaced, reduce worst-case residual from 1.5625 Hz to 0.52 Hz:

| leg | transform applied to the PCM |
|---|---|
| `base` | none (production behaviour) |
| `F+` | frequency shift **+1.0417 Hz** (= 3.125/3) |
| `F−` | frequency shift **−1.0417 Hz** |
| `T+` | time shift **+0.0267 s** (= 0.08/3, i.e. +320 samples) |
| `T−` | time shift **−0.0267 s** (−320 samples) |

**Frequency shift** = analytic signal via `scipy.signal.hilbert`, multiply by `exp(2πi·δ·t)`, take the
real part. **Time shift** = integer sample roll with zero fill, **not** wraparound. All five legs on
the identical file, consecutively, in one process (§1.1).

### 3.2 Metrics

```
U       = base ∪ F+ ∪ F− ∪ T+ ∪ T−
S_all   = 100 * |REF ∩ (U \ base)| / |REF|        <- HEADLINE: reference decodes recovered
                                                     only by shifting.  Same axis as G, M, A.
S_freq  = 100 * |REF ∩ ((F+ ∪ F−) \ base)| / |REF|
S_time  = 100 * |REF ∩ ((T+ ∪ T−) \ base)| / |REF|   <- the axis NOTHING has ever measured
X       = |U \ base \ REF| / |U \ base|           <- GUARD: share of shift-added decodes that
                                                     are not in REF (false-positive pressure)
```

🔴 **`S_time` is the point of this arm.** T1 already bounded the frequency axis (`G` = 3.16 pp, a
floor). The **time axis is not identifiable from `ALL.TXT` at all** — reference DT resolution is
0.1 s, coarser than our own 0.08 s step. A shift experiment needs no reference DT, so it reaches
what the measurement instrument cannot. **Report `S_freq` and `S_time` separately, always.**

### 3.3 Pre-registered gate (HK-021)

```python
def p3_row0(n_cycles, ref_n, r_base, synth_freq_err_hz, u_equals_base, se_s_all):
    if n_cycles < 800:
        return "ROW 0a"
    if ref_n != 69222:
        return "ROW 0b"
    if not (45.0 <= r_base <= 70.0):
        return "ROW 0c"          # same believed-bound check as P2
    if synth_freq_err_hz > 0.25:
        return "ROW 0d"          # the SHIFT CONTROL failed: a synthetic signal shifted by a
                                 # known delta must move the decoder's reported frequency by
                                 # that delta. If it does not, the mixer is broken and every
                                 # number here is meaningless.
    if u_equals_base:
        return "ROW 0e"          # the union added literally nothing: shifts not applied
    if se_s_all > 1.0:
        return "ROW 0f"          # the 1.0 pp ROW 2 bar is not separable from noise --
                                 # UNDERPOWERED, an instrument failure, NOT a null
    return None

def p3_gate(s_all, x_guard):
    if s_all >= 3.0 and x_guard <= 0.50:  return "ROW 1"
    if s_all <= 1.0:                      return "ROW 2"
    return "ROW 3"
```

🔴 **ROW 0d, the shift control, is mandatory and must run FIRST.** Synthesise an FT8 signal at a
known frequency with the existing `qa/rr-study/synth` GFSK encoder, decode it unshifted and shifted
by +1.0417 Hz, and assert the reported `freq_hz` moves by that amount within 0.25 Hz. **This is the
check P1's ROW 0d should have been** — a large expected effect where absence is genuinely diagnostic
(HK-021(j)). Without it a silently broken Hilbert mixer produces a confident null.

| row | consequence — as an assertion |
|---|---|
| **ROW 0a–0f** | **Instrument failure, not a null.** Report the failing check and its value. ROW 0f means underpowered — *not* evidence that shifting does nothing. Do not repair-and-rerun in-session. |
| **ROW 1** (`S_all ≥ 3.0` and `X ≤ 0.50`) | 🔴 **Sub-lattice placement costs real decodes, and sync refinement becomes the leading D-001 treatment candidate.** Report `S_all`, `S_freq`, `S_time`, `X` and the clustered CI. **Recommend to the Captain: raise `K_FREQ_OSR`/`K_TIME_OSR` 2→4 at `ft8_shim.c:469-470` as the cheap production form** — a one-line native change, therefore a **recommendation only**, requiring a Developer session (HK-011) and a rebuild. Note the memory cost (4× waterfall) and that a union of five runs is *not* the proposed production design. |
| **ROW 2** (`S_all ≤ 1.0`) | 🔴 **A major negative result — assert it plainly.** The coarse lattice does **not** cash out in recall at this granularity, and the "no sync refinement" reading of D-001, while architecturally true, **does not explain the gap.** The programme should redirect: the remaining demodulation suspect is **non-coherent single-symbol extraction** (`ft8_extract_symbol`, max-log over 8 magnitude bins, with `ft8_decode_multi_symbols()` dead code). Update the board's framing — edit, do not annotate. |
| **ROW 3** (`1.0 < S_all < 3.0`, or `S_all ≥ 3.0` with `X > 0.50`) | Report all four metrics and the CI. If the `X` guard is what blocked ROW 1, **say so explicitly** — that is "the union buys decodes but also manufactures them," a different finding from "shifting does nothing," and it argues for refinement *inside* the decoder rather than a union outside it. |

### 3.4 Predictions

| # | prediction | tested by |
|---|---|---|
| 1 | `S_all` = **1.5–5.0 pp** | the gate |
| 2 | **ROW 3** | the gate |
| 3 | `S_freq` > `S_time` | §3.2 |
| 4 | `X` = **0.35–0.65** — the union adds roughly as many non-`REF` as `REF` decodes | the guard |
| 5 | the shift control passes with error < 0.05 Hz | ROW 0d |

⚠️ **Calibration, quoted because these gates turn on my predictions (HK-021):** categorical ROW calls
**2 of 4**; ranges **3 of 5**, and **both range misses were too pessimistic about how cleanly an
effect separates** — read my ranges as asymmetric, skewed toward *larger* effects than I state.

---

## 4. Unattended execution (HK-023, HK-013, HK-019)

The Captain is AFK ~8 h with **no shell interaction available.** Therefore:

1. **Smoke-test every harness on ~20 files before arming.** An unattended launch of never-executed
   code is the failure mode these rules exist to prevent (HK-020).
2. **Detached, not `Monitor`-owned.** A `Monitor`-owned process dies at session end and `TaskStop`
   can report success while it lives. Launch with `nohup … & disown`, **verify the PID via
   `Win32_Process`**, and use any tail purely for notification.
3. **Checkpoint per arm and per partition** to JSONL in a scratch dir outside the repo, so a crash
   loses one partition, not eight hours. The runner must be **resumable** and must skip completed
   partitions on restart.
4. **Supervisor** per HK-013: restart on death, cooldown, **cap 5 retries**, log every event. Port
   the UTC-midnight log-rotation guard from the HK-013 addendum — **this run crosses 00:00 UTC.**
5. **Teardown** (HK-019): the runner exits cleanly when all arms finish; the supervisor must exit
   too, not linger. Check for orphan processes before arming.
6. **Order P1a → P2 → P3.** If an arm hits ROW 0, **record it and continue to the next arm** — do not
   repair in-session, and do not let one arm's instrument failure block the others.

## 5. Deliverables

One report per arm, filename and byline from real `date -u` and in agreement (HK-017), each with:
the DLL SHA256 and version assertion; the ordered gate trace; the headline metric with its
**clustered** CI; predictions scored; the §1.1 hash-table disclosure; citation limits. Plus a single
`RUN_SUMMARY.md` giving each arm's row and where its report is. **No push, no merge, no `src/`
change.** Committing is the Captain's call (HK-010/HK-014) — but **commit locally** so nothing is
lost, exactly as P1's artefacts were.

## 6. Citation limits set in advance

**May be cited:** `P`, `s*`, `R(s)`; `S_all`, `S_freq`, `S_time`, `X` — each **with its clustered CI
and its gate row**; the shift-control result; the DLL identity.

🛑 **May not be cited:** any of these as a statement about **live** OpenWSFZ recovery (we decode
WSJT-X's audio, not our capture path); `R(0.20)` as a revision of 55.5% or 57.8%; any binomial
interval; `S_all` as a promise of production gain (the production form is an OSR change, not a
union, and has not been measured); any restatement of `G`, `D_int`, `U`, `M`, `A`, or the recovery
headline; any `src/` change presented as approved.
