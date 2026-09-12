# `NHARD40-DEFAULT` Amendment 1 — a co-channel oracle leg (`CC`) is added as gate G4, before the dev-task

**Architect, 2026-09-12 10:00Z** (`date -u`, HK-017). Branch `arch/osd-nhard40-default`.
Docs-only; `git diff --stat origin/main -- src/ native/` empty.

Amends `2026-09-12-0912-architect-to-qa-spec-nhard40-default-preregistration.md` (the "base").
Written **after** `NT`'s result (`S1`, accepted `2026-09-12-0956-…-nt-acceptance.md`) and **before
any `CC` datum exists**.

---

## §0. Why, and why this is not a re-read of `NT`

`NT` settled the isolated-station case structurally: `C_B = 0`, so OSD never rescues an isolated
weak AWGN station, and `nhard` cannot cost one. **Any genuine cost of 40 must therefore live where
BP fails on a real signal and OSD rescues it:** co-channel overlap, near-collision, time overlap, a
weak station next to a strong one. The base §6 disclosed that no leg could see these. The only
evidence on file, the 2026-06-20 R6 diagnostic (90/92 S7 "genuine" OSD accepts in `nhard` (40, 60]),
was never payload-labelled (NT ruling §3).

**The PO decided (2026-09-12, "Co-channel check first (Recommended)") that this is measured before
the dev-task.**

- **`NT`'s row is not touched and G2 stays passed.** This amendment **adds a new gate, G4**, to a
  consequence that has not been exercised. It moves no bar of an existing gate and re-reads no
  existing gate.
- 🛑 Base §2 item 3 now requires **`NT-S1` and `CC-S1`**. It is struck and restated below.

## §1. Consequence table, restated (strict order, first match wins)

1. **`NT-S2` or `CC-S2`** ⇒ **Option B is contraindicated as a default.** CLOSE it as a default
   change. The operator setting stays available.
2. **`NT-S3` or `CC-S3`** ⇒ unresolved. Nothing changes.
3. **`NT-S1` and `CC-S1`** ⇒ the Architect asks QA to author the dev-task per base §1, with M2.

## §2. `CC`: the co-channel oracle leg

### 2.1 Scene: S7 geometry, verbatim (HK-018)

- **All 21 parts of `qa/rr-study/scenarios/s7-compounding.json`**, every station's `(msg_id,
  freq_hz, dt_s, snr_db)` exactly as the file gives it. Message texts come from
  `study-messages.json` (MSG-01/02/03, Q-prefix).
- **The five families, as the file labels them:**
  - `co_channel`: parts 0–2
  - `near_collision`: 3–7
  - `time_freq`: 8–10
  - `capture`: 11–14
  - `co_channel_sweep`: 15–20
- **Renderer:** `scene_render.render_scene(signals, seed)` at 12 kHz. It uses the same mixing model
  as `run_scenario._render_compound` (`channel.mix_to_shared_floor`: each station clean, scaled by
  relative `snr_db`, one shared seeded floor); QA states the equivalence with a code citation.
- **Input contract:** `normalise_rms(pcm, 0.20)`, as in `NT`.
- **Trials:** **100 per part ⇒ 2,100 cycles.** Seed `compute_seed('NHARD40-CC', part_index,
  trial_index)`. Fresh noise per cycle.

### 2.2 Legs

These are identical to `NT`: the same PCM decoded at `nhard` **60** (control), **40**
(treatment) and **0** (ceiling / positive control), with `k = 10` and `corr = 0.10` fixed. **State
the setting scheme and persist per-cycle arrays.**

### 2.3 Unit and labels: payload-only, per station

- **Unit = station-cycle:** one injected station in one cycle. There are 2–3 per cycle.
- **`present_L(s)`** = leg `L` has **any** decode whose payload equals station `s`'s payload
  (`true_codeword` compare, `part_a.is_true` semantics). **There is no frequency condition.** In
  co-channel scenes the reported frequency can drift more than 4 Hz from the injected one, and a
  frequency condition would silently re-label a genuine loss as "junk removed". That error runs
  toward S1, the unsafe direction. A random false decode matching one specific 77-bit payload is
  negligible.
- `G` = station-cycles with `present_60`.
- `K` = those with `¬present_40` (**killed by the change**).
- `C` = those with `¬present_0` (**OSD-rescued: the ceiling**).
- `L = K / G`. Per family: `G_f`, `K_f`, `C_f`, `L_f`.

### 2.4 Confidence intervals: mechanical, with clustering and zero counts handled (HK-021(r))

Station-cycles within a cycle are correlated.

- **Pooled and per-family CI** = cycle-clustered bootstrap (2,000 resamples, seed
  `compute_seed('NHARD40-CC-BOOT', 0, 0)`).
- **When `K` = 0 in a set,** its upper bound is replaced by the Clopper–Pearson 95% upper bound on
  **0 of N_cycles**, where N_cycles is the number of cycles in that set with ≥ 1 genuine decode at
  60. 🛑 Never cite a zero-width interval (the A/B ruling).

### 2.5 ROW 0: strict order

| row | check | on failure |
|---|---|---|
| **0a** | DLL SHA-256 = `6b2e16a6…4f85c` (shim `20260050`), asserted in code | VOID |
| **0b** | the rendered signal list equals `s7-compounding.json` for all 21 parts (asserted in code, field by field) | VOID |
| **0c** | determinism: an independent process re-decodes a seeded 300-cycle sample on all 3 legs; per-station-cycle arrays **element-wise identical** | VOID |
| **0d** (power, routes) | `G ≥ 1,000` | S3 |

**Report only, evaluated both ways (HK-021(k)):**

- station-cycles killed at 40 but **present** at 0 (expected 0);
- station-cycles **present at 40 but not at 60** (gained). Removing a decode can change what the
  decoder subtracts, so co-channel gains are possible. **Report `K`, the gains, and net `K − gains`**,
  but gate on `K`: a station lost is lost to the operator even if another is gained elsewhere.

### 2.6 Gate rows (first match wins)

| row | predicate | reading |
|---|---|---|
| **CC-S2** | `CI_lo(L) ≥ BAR_S` **or, for any family `f`, `CI_lo(L_f) ≥ BAR_S`** | **Measurable genuine loss in co-channel conditions.** ⇒ §1 item 1 |
| **CC-S1** | `CI_hi(L) < BAR_S` | **No genuine co-channel loss detected at this resolution.** ⇒ §1 item 3 (with `NT-S1`) |
| **CC-S3** | otherwise, or 0d short | Unresolved. ⇒ §1 item 2 |

**Why the family clause is in S2 and not in S1:** harm in one family must not be averaged away by
four benign ones. The PO accepted this explicitly ("so a problem in one kind of overlap can't be
averaged away"). Requiring **every** family to resolve below the bar would demand power this size
cannot give, so S1 gates on the pool.

**The ceiling, read with the row:** if `C = 0`, OSD rescues no genuine station even in co-channel
S7. Then S1 holds structurally, **and the 2026-06-20 R6 "genuine" population was false accepts.** If
`C > 0`, `K / C` is the share of OSD rescues that 40 removes. Report it per family.

### 2.7 Descriptive (no row)

- Per family: `G_f`, `C_f`, `K_f`, the gains, `p60` / `p40` / `p0` per station role (strong / weak in
  `capture`), and **false decodes per cycle at each setting** (the busy-band FP benefit).
- **The R6 question answered directly:** for parts 0–2, the OSD accepts at 60 split into genuine
  (`C`) and false (false decodes at 60 minus at 0).

### 2.8 Resolution, computed while drafting (HK-021(m))

S7 decodes most stations at these SNRs (0 to −10 dB relative), so expect `G ≈ 4,000` station-cycles
(2,100 cycles × ~2.05 stations × ~0.9 decoded), and about 400 per family at the smallest
(`time_freq`, 300 cycles).

- **Pool:** at `K = 0`, the upper bound is about 3.7/N_cycles ≈ 0.2%. **S1 needs a true pooled loss of
  about 4% or less.**
- **Family:** at `G_f ≈ 400`, S2 fires at a true family loss of about 8% or more (clustering widens
  this a little).

### 2.9 Bar

✅ **`BAR_S = 0.05` applies to `CC`, family clause included. PO RULING 2026-09-12 ~10:00Z**
("Same 5% (Recommended)"), recorded **before any `CC` datum exists**. **FROZEN for this arm.** If
anyone proposes moving it after `K` is known, refuse: that VOIDs `CC`.

### 2.10 Predictions (blind, before any `CC` datum)

| row | probability | reasoning |
|---|---|---|
| CC-S1 | 0.35 | |
| CC-S3 | 0.30 | |
| CC-S2 | 0.35 | Co-channel interference adds hard errors to a genuine codeword, so a genuine OSD rescue at `nhard` 45–60 is physically plausible. That is exactly what 40 removes. |

I expect `C > 0` (0.7). My NT reasoning was wrong in the other direction; weigh these accordingly.

### 2.11 What `CC` cannot see

- Fading, Doppler, drift or timing spread (E4, still unopened).
- More than 3 stations stacked.
- Weak co-channel stations near the decode threshold. S7's weakest is −10 dB relative, and `NT` and
  `CC` do not overlap in SNR.
- Message types outside MSG-01/02/03.

An S1 here reads *"no genuine loss detected in S7's co-channel geometries on AWGN"*, never "safe".

## §3. Running order

| step | status |
|---|---|
| `CC` | ✅ **cleared to run** (PO decision + bar ratified, §0 / §2.9) |
| Dev-task | only on `NT-S1 ∧ CC-S1` (§1) |

Unchanged: no `src/` or `native/` change, no push, no merge (HK-011 / HK-014 / HK-010). NFR-021:
Q-prefix synthetic only. **HK-025 is available in full.**
