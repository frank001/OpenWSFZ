# Architect → QA — F-NBR-A: why is station F never decoded, and is the pass-1 suppressor ever active?

**Author:** Architect, 2026-08-23 11:24Z (`date -u`, HK-017).
**Status:** pre-registration. Everything already measured is disclosed in §0 and §7.
**Ownership:** offline re-analysis plus deterministic offline re-rendering. **No `src/` change,
no rebuild, no capture run, no audio device, no daemon, no WSJT-X, no Developer session.**
A Python harness driving the already-shipped, SHA-pinned `libft8.dll` via `ctypes`, plus
re-analysis of a live corpus already on disk. HK-011 does not bite.

**Trigger:** Captain's call, 2026-08-23. C-ASYM-A Part C promoted station F from
"0/5 on four consecutive sweeps" to **0/25, fully deterministic, seed-independent**, and the
spec that produced it explicitly deferred station F to its own pre-registration.

---

## 0. 🔴 MANDATORY DISCLOSURE — what the Architect measured before writing this, and what he deliberately did NOT measure

Per HK-018 I opened the artefacts before designing anything. Six things came out. **All of
§0.1–§0.4 are ARCHITECT-EXPLORATORY**: one run, one scene, no clustering, no CI. They are
disclosed here because **the bars in §5 were set knowing them**, and QA must be able to see
whether a bar was drawn around a number I had already seen.

🔴 **What I did NOT run, deliberately:** I did **not** compute Part A's `R_forced`, and I did
**not** compute Part B's `Z` on the live corpus. Both are gated primary statistics. Running
them and then writing their bars would make this pre-registration theatre. My predictions for
both are on the record in §5 instead, before the fact.

### 0.1 Station F's miss is NOT a metric artefact — this is a different failure mode from C-GAP-D's

From the committed `qa/rr-study/results/2026-08-23-73c1288/owsfz-all.txt` and `wsjt-all.txt`,
all decodes reported in 1100–1200 Hz across the 25 S8HN cycles:

| 1100–1200 Hz | OpenWSFZ | WSJT-X |
|---|---:|---:|
| station E @ 1150 | **25** | 25 |
| **station F @ 1162** | **0** | **25** |
| decodes matching no injected signal | 3 (at 1144/1147 Hz) | 0 |

**OpenWSFZ emits nothing at 1162 Hz in any cycle.** Station F is not decoded-then-mislabelled,
not decoded-then-mistuned, not a text mismatch. It is never produced.

🔴 This **rules out the T1/T3 explanation that dominated C-GAP-D** (where 75.2% of misses were
unresolved-hash and 23.1% a callsign character differing). Station F is a *genuinely different
defect* and must not be folded into that finding.

### 0.2 The matcher cannot be responsible

`qa/rr-study/harness/matcher.py:31` sets `FREQ_TOLERANCE_HZ = 4.0`, and `_match_appraiser`
requires **both** `_text_matches` (case-sensitive, whitespace-normalised, exact) **and**
`_freq_matches`. E and F are 12 Hz apart — three times the tolerance. They cannot be confused,
and a decode of F reported anywhere in [1158, 1166] would still have matched. Instrument
eliminated as an explanation.

### 0.3 It is not weak-signal, and it is not co-channel overlap in general

In the same 25 cycles OpenWSFZ recovers, 25/25 each:

- **station J @ 1900 Hz, −15 dB** — the weakest signal in the scene;
- **both** members of the **co-frequency capture pair**, G and H, at 1500 Hz, 6 dB apart
  (50 decodes at 1500 Hz across 25 cycles).

OpenWSFZ solves *exactly co-frequency* separation and the scene's weakest signal, and fails a
12 Hz separation at a 3 dB disadvantage. **The failure is specific to small-but-nonzero
frequency separation**, which is a much narrower and more tractable claim than "co-channel
weakness".

### 0.4 🔴 The pass-1 suppression stage is very nearly inert at this scene's SNRs

`ft8_shim.c:743 suppress_candidate_tiles` attenuates a decoded signal's tiles by a factor
ramped on the decode's own SNR (`ft8_shim.c:537-538`):

```
factor = 1 - clamp( (snr_db - (-5)) / (15 - (-5)), 0, 1 )
   factor = 1.0  -> tile completely unchanged (NO suppression)   at snr <= -5 dB
   factor = 0.0  -> tile fully replaced by noise_raw             at snr >= +15 dB
```

I confirmed the SNR it receives is **the same variable written to `ALL.TXT`**:
`ft8_shim.c:1549` stores `all_supp_snrs[n_all_supp] = snr` and `ft8_shim.c:1537` writes
`r->snr = (int)roundf(snr)` from that same `snr`. So the ramp can be scored directly against
the reported SNRs of this run's 283 pass-0 decodes:

| statistic (S8HN scene, 283 decodes, no CI) | value |
|---|---:|
| mean suppression factor (1.000 = no suppression at all) | **0.875** |
| mean attenuation | **12.5%** |
| decodes receiving **exactly zero** suppression | **140 / 283 = 49.5%** |
| station E's own factor (reported −4/−5 dB) | **0.95 – 1.00** |

Pass 1 exists to suppress decoded signals so weaker neighbours emerge. It is the mechanism
that *should* rescue station F. Before pass 1 goes looking for F, it removes **at most 5%** of
station E.

⚠️ **This is not a proposal to move the ramp.** The board records `diag-d001-h5-suppression-
tuning` (shim 20260011) as **REJECTED** for shifting this exact window 10 dB down —
over-suppression confirmed. Re-proposing that would be re-reading a closed gate. The claim
here is narrower and, as far as I can find, never made: **we have never measured how often the
suppressor does anything at all.** §4.2 measures that, on the population D-001 is scored on.

### 0.5 ⚠️ REASONING, NOT MEASUREMENT — a candidate mechanism I am explicitly NOT gating

FT8 tone spacing is 6.25 Hz. E at 1150 Hz sits on bin **184.000**; F at 1162 Hz on bin
**185.92**. Their 8-FSK tone combs are offset by **almost exactly 2 tone bins**, and — both
being `dt_s = 0.0` — their Costas sync symbols are time-aligned.

`ft8_sync_score` (`native/ft8_lib_build/patched/ft8/decode.c:180-190`) is **differential
against ±1 frequency bin**:

```c
score += WF_ELEM_MAG_INT(p8[sm]) - WF_ELEM_MAG_INT(p8[sm - 1]);  // one bin lower
score += WF_ELEM_MAG_INT(p8[sm]) - WF_ELEM_MAG_INT(p8[sm + 1]);  // one bin higher
```

At F's candidate position the *lower* probe bin sits one bin above E's tone — inside E's
spectral-leakage skirt. If that holds, E's energy is **subtracted from F's sync score**: F
would be both 3 dB weaker *and actively penalised by its neighbour*.

🔴 **I derived this by reading code, not by measuring it, and per the Captain's ruling this
arm does NOT gate on it.** §4.3 measures E's causal role by ablation instead — a stronger and
much cheaper test than reading score internals, and one that does not depend on my story being
right. If §4.3 shows E is causal, this paragraph becomes a candidate explanation worth its own
pre-registration. If it does not, **discard this paragraph rather than rescuing it.**

### 0.6 The decisive instruments already exist — verified present in the pinned binary

All four are exported from the currently-shipped DLL, SHA256
`bc8efcf148046f199c057b62c7987c4b69f2dc62d72509458a671305ab051d7f` — **byte-identical to the
binary the S8HN run itself used**, verified today by hashing
`src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll` and `native/ft8_lib_build/libft8.dll` (both match)
and by extracting the export-name table from the binary:

`ft8_extract_llrs_at` · `ft8_ldpc_decode_llrs` · `ft8_get_last_candidate_counts` ·
`ft8_get_last_pass_counts`

**No rebuild is required or permitted by this arm.**

#### 🔴 A contract hazard I raised, checked, and resolved — QA should not re-litigate it

`ft8_extract_llrs_at` returns **raw, pre-normalisation** LLRs and deliberately does not call
`ftx_normalize_logl` (its own header says N1's harness depends on that). Production
(`ftx_decode_candidate`, `decode.c:628-666`) normalises *before* BP. Feeding raw LLRs to a
decoder that expected normalised ones would measure **LLR scale, not LLR quality** — and a
station-F null would then be an artefact of my own harness design.

It is already handled **inside the instrument**: `ftx_ldpc_decode_llrs`
(`decode.c:907-985`) performs, in order, a zero-variance guard (rc `-2`), then **Step 3:
`ftx_normalize_logl` — MANDATORY**, then saves the normalised vector for OSD, then `bp_decode`,
then the *same* OSD fallback and the *same* two-feature accept/reject gate as production.

⇒ `ft8_extract_llrs_at` → `ft8_ldpc_decode_llrs` reproduces the production path **from
extraction onward**, with no normalisation work required in Python. **Do not add your own
normalisation step** — you would apply it twice.

**Production-equivalent arguments, read from source, to be asserted in ROW 0f:**

| argument | value | source |
|---|---:|---|
| `max_iters` | `50` | `ft8_shim.c:509` `K_LDPC_ITERATIONS` |
| `osd_depth` | `2` | `decode.c:666` — production hardcodes `osd_decode(llr_for_osd, 2, plain174)` |

---

## 1. The question

**Part A (PRIMARY).** Station F is never decoded. Is that because the decoder **never looks at
F's position** (candidate selection), or because **the numbers it reads at F's position do not
support a decode** (extraction)? These are the only two loci, they are mutually exclusive, and
one call to an existing export separates them: *hand the decoder F's exact position and see
whether it decodes.*

**Part B.** Independently: in live production, how often does the pass-1 suppression stage
attenuate anything at all?

**Part C (descriptive, not gated).** Is station E *causally* responsible for F's loss, and how
wide is the exclusion zone in Hz and in dB?

Parts A, B and C are on independent gates and independent populations. **No result from one may
be used to read another** — in particular a B1 result does not explain station F, and an A1
result does not indict pass 1.

---

## 2. Population

### 2.1 Parts A and C — regenerated offline, not re-captured

`qa/rr-study/harness/run_scenario.py:371 _render_band_scene` renders the whole 12-station scene
deterministically from `compute_seed('S8HN', 0, trial_index)`: each station encoded clean via
`synth.encoder.encode_message`, scaled by `snr_db`, summed, then given one shared seeded AWGN
floor by `synth.channel.mix_to_shared_floor`. **Given the seed the PCM is reproducible exactly.**

⇒ **Trials 0–24 regenerate the audio the committed S8HN run actually decoded**, which ROW 0b
exploits as a free end-to-end reproduction check. Trials 25–99 are new draws from the same
generator.

⚠️ The modulator's positive-DT clamp defect does not bite here: stations E and F are both
`dt_s = 0.0`, and no station in this scene exceeds the 2.36 s cap.

### 2.2 Part B — a live corpus already on disk (HK-018)

Use the **OpenWSFZ leg of `20260803_live_run_1713`** — the D-001 replication corpus:
20m/14.074, one contiguous 18.96 h decisive epoch, drift screen ROW 5 PASS (+0.0 ppm), 4,614
OpenWSFZ cycles, per `qa/ARTEFACT_INVENTORY.md`.

**Rationale:** this is the population D-001's headline deficit is scored on. Part B's question
is "does the suppressor act in production", and the only honest population for that is
production. **Do not substitute a synthetic scene** — S8HN's SNR distribution is a property of
the scenario file, not of the world, and `Z` computed on it would not be identifiable as a
decoder property (HK-021, metric identifiability). §0.4's synthetic figures are context only
and are **not** the gated statistic.

🔴 Regenerate `qa/ARTEFACT_INVENTORY.md` (`python qa/artefact_inventory.py --check`) before
relying on the row above. If it is stale, fix that first.

### 🔴 Privacy — NFR-021, read before writing a line of code

Part B reads a **live off-air `ALL.TXT` containing real callsigns**. Parts A and C are
synthetic Q-prefix only and are unaffected.

1. Part B needs **one column: the reported SNR**. Never read, store, hash or emit
   `message_text`.
2. All Part B output is **counts and ratios only**. No decode text in any JSON, CSV, log or
   report — including intermediate files.
3. Run `git check-ignore -v` on every artefact produced before committing anything, and grep
   each file individually for callsign-shaped tokens. The board records 203,920 contaminated
   rows in a single `S1_matched.csv` from exactly this shortcut.
4. ⚠️ C-ASYM-A's QA caught itself about to commit a draft quoting five real callsigns. Assume
   you will make the same mistake and check for it explicitly.

---

## 3. ROW 0 — preconditions (mechanical; evaluate in order, STOP at the first VOID)

| row | check | VOID if |
|---|---|---|
| **0a** | SHA256 of the `libft8.dll` **actually loaded by the harness process** equals `bc8efcf148046f199c057b62c7987c4b69f2dc62d72509458a671305ab051d7f` | any mismatch |
| **0b** | Regenerate trials 0–24; run production `ft8_decode_all` offline on each; compare the recovered `(reported_freq_hz, message_text)` multiset per cycle against the committed `owsfz-all.txt` | fewer than **24 of 25** cycles reproduce the 11 recovered stations exactly |
| **0c** | Positive control: run the **Part A pipeline unchanged** at **station A (450 Hz, dt 0.0)** and at **station E (1150 Hz, dt 0.0)** — both recovered 25/25 in production — over trials 0–24 | either station recovers on fewer than **24 of 25** trials |
| **0d** | Determinism: run Parts A/B/C end to end **twice**; **mechanically diff** the output JSON | the two runs are not byte-identical |
| **0e** | Part B's `ALL.TXT` is the archived corpus copy inside the run folder, and its mtime predates this session | it resolves to a shared/production path, or was modified today |
| **0f** | Assert `max_iters == 50` and `osd_depth == 2` are the values read from `ft8_shim.c:509` and `decode.c:666` respectively | either differs from source |

🔴 **ROW 0c is the row that stops us reading an instrument failure as a finding.** Station F's
whole result is a *null* (0 decodes). A null is exactly what a broken offline chain produces.
0c proves the chain — regeneration, `ctypes` marshalling, `ft8_extract_llrs_at`,
`ft8_ldpc_decode_llrs`, payload comparison — recovers signals it *should* recover, using
station F's own near neighbour as one of the two controls. **Without 0c, Part A is
uninterpretable.**

🔴 **HK-025 applies.** Evaluate every row against both branches before running. If a row lands
the same consequence whichever way it goes, it is diagnostic, not a precondition — name it,
stop, and refuse. No partial run.

⚠️ 0b at 24/25 rather than 25/25: the tolerance covers float non-determinism in the offline
audio path, not a systematic difference. **If 0b fails at 23/25 or worse, do not loosen it** —
report and stop; the offline path is not reproducing the live run and everything downstream is
void.

---

## 4. The three measurements

### 4.1 Part A — the locus split (PRIMARY, gated)

`N = 100` trials, `trial_index = 0..99`, seeds `compute_seed('S8HN', 0, trial_index)`.

For each trial:

1. Regenerate the full 12-station mixed PCM (all stations present, unmodified scene).
2. `rc = ft8_extract_llrs_at(pcm, 180000, freq_hz=1162.0, time_offset_s=0.0, out_llr174)`.
   **Require `rc == 0`.** Any `-1`/`-2`/`-3` is a harness fault, not a datum — fix it, do not
   count it as a station-F failure.
3. `ft8_ldpc_decode_llrs(out_llr174, max_iters=50, osd_depth=2, out_a91, out_ldpc_errors,
   out_path, out_crc_ok)`.
4. **Success** ⇔ `out_crc_ok == 1` **and** the recovered payload equals the payload of
   `"Q1ABC Q1AW RR73"` obtained from `ft8_encode_message`. 🔴 Compare **payloads, not text** —
   a text comparison would re-introduce exactly the hash/text failure mode §0.1 just excluded.

`R_forced` = successes / 100.

**Independence:** trials differ only in AWGN seed and are independent draws by construction —
no clustering. Use an **exact Clopper–Pearson** binomial CI, not a bootstrap. (HK-021(o):
resolve against the readout quantum, which here is 1/100.)

Also record, per trial, `out_ldpc_errors` and `out_path` (BP vs OSD vs neither). Descriptive,
no gate — but it distinguishes "BP converged easily" from "only OSD rescued it", which shapes
the follow-up.

### 4.2 Part B — is the suppressor ever active in production? (gated)

Over every OpenWSFZ decode in the live leg of §2.2:

```
factor_i = 1 - clamp( (snr_i - (-5)) / (15 - (-5)), 0, 1 )
Z        = fraction of decodes with factor_i >= 0.99      # effectively zero suppression
Abar     = mean(1 - factor_i)                             # mean attenuation
```

🔴 **`ALL.TXT` field order: `[4]` SNR, `[5]` DT, `[6]` frequency Hz.** The architecture note
records that confusing 5 and 6 inverts a result. **Assert your parse** against a hand-checked
known row before computing anything.

**Clustering — HK-021(i).** Decodes within one cycle are **not** independent. Cluster-bootstrap
by cycle timestamp `ts`, `N_BOOT = 2000`, `seed = 20260823`. 🔴 **Report CLUSTER counts
alongside row counts, never row counts alone** — the board records a ≈3.8× CI error from
exactly this omission.

⚠️ **Do not reuse a population helper without reading it first.** The standing note records
`compute_matched_hit_control(..., limit=N)` truncating in file order rather than sampling, and
three arms consuming ~12 of 68 clusters as a result. Check what any `limit=` argument does.

Report `Z` and `Abar` with CIs, and the SNR histogram the ramp is being scored against
(**counts per SNR bin only — no message text**).

### 4.3 Part C — is E causal, and how wide is the exclusion zone? (DESCRIPTIVE, NOT GATED)

Per the Captain's ruling, this measures the mechanism without gating it. All three use the
**unmodified production decoder** (`ft8_decode_all`) on regenerated audio — no forced positions.

**C1 — neighbour ablation.** For each of 100 trials, render the scene **with station E removed
from `signals`** and everything else byte-identical (same seed, same remaining stations).
Report `R_ablate` = fraction of trials in which **F is recovered with E absent**, with a
Clopper–Pearson CI, beside the with-E baseline.

This is a **direct causal test of E's role using only production code**, and it is strictly
stronger than reading `ft8_sync_score` internals. If `R_ablate` is high while the baseline is
0, E causes F's loss and §0.5's story becomes worth pursuing. If `R_ablate` is also ~0, **E is
not the cause, §0.5 is wrong, and F's loss is a property of F's own position** — a completely
different and much more interesting result.

**C2 — separation sweep.** Hold E at 1150 Hz / −5 dB. Move F to `1150 + Δ` for
`Δ ∈ {6.25, 12, 18.75, 25, 31.25, 50, 100}` Hz (12 = baseline), all else fixed, 100 trials
each. Report `R(Δ)` with CIs. This maps the exclusion zone's **width in Hz and in tone bins**.

**C3 — level sweep.** Hold `Δ = 12` Hz and E at −5 dB. Vary F's SNR over
`{−2, −5, −8, −11}` dB (−8 = baseline), 100 trials each. Report `R(snr_F)` with CIs.
Separates a **level-ratio** effect from a **pure-position** effect.

🔴 **Scope boundary, binding.** C1–C3 characterise **OpenWSFZ's own** exclusion zone against
**injected truth** — an oracle independent of the decoder, so HK-026 is satisfied. They say
**nothing** about whether WSJT-X has a comparable zone, because establishing that needs a
reference decoder and **`jt9 -d 3` offline is not one** (+93.8%, VOIDed Angle 1; the only valid
replacement is fresh WSJT-X on identically replayed audio, i.e. a live leg this arm does not
fund). **No cross-decoder comparison may be drawn from Part C.**

---

## 5. The gates

Rows within a gate are **mutually exclusive** and evaluated in **strict order**. Each states its
consequence as an assertion, per HK-021.

### Gate A — `R_forced` (PRIMARY)

| row | condition | consequence |
|---|---|---|
| **A1** | `CI_lo(R_forced) > 0.80` | **CANDIDATE-SELECTION LOCUS.** Extraction and LDPC recover station F reliably when handed its position; production never hands them the position. Station F's loss is a candidate-selection defect. 🔴 **No extraction-quality, LLR-quality or coherent-combining work may be described as a station-F treatment** in any subsequent proposal. |
| **A2** | `CI_hi(R_forced) < 0.20` | **EXTRACTION LOCUS.** Even at the exact position the LLRs do not support a decode ⇒ E's energy corrupts F's extraction. Candidate selection is **exonerated** for station F. Part C's ablation becomes the priority follow-up. |
| **A3** | otherwise | **UNRESOLVED.** Report `R_forced` with CI. **No locus claim, no mechanism claim, no consequence.** Stop. |

**HK-021(m) — resolution computed while drafting, stated as the exact decision boundary.**
Because `R_forced` is a count out of 100, the gate reduces to a hard count. Computed with
Clopper–Pearson at α=0.05:

| outcome | `CI_lo` / `CI_hi` | row |
|---|---|---|
| **k ≥ 89** successes | `CI_lo = 0.8117` | **A1** |
| k = 88 | `CI_lo = 0.7998` | A3 — misses the bar by 0.0002 |
| k = 85 | `CI_lo = 0.7647` | A3 |
| **k ≤ 11** | `CI_hi = 0.1883` | **A2** |
| 12 ≤ k ≤ 88 | — | A3 |

⇒ **A1 requires ≥ 89 of 100; A2 requires ≤ 11 of 100.** Report the raw count so the row is
verifiable by inspection. At `k = 100` the half-width is 0.0181 and `CI_lo = 0.9638` sits
**9.0 half-widths** above the 0.80 bar — decisively decidable, not marginal.

⚠️ **k = 88 is a knife-edge (0.0002 from the bar).** If the run lands there, it is **A3** and
must be reported as A3. 🔴 **Do not round, re-derive with a different CI method, or re-run with
a different N to move it** — that is exactly the "re-read a closed gate with a better metric"
failure the standing prohibitions name. Report the knife-edge as a knife-edge.

⚠️ **Why `N = 100` and not S8HN's 25.** At `N = 25`, `R = 24/25` gives `CI_lo = 0.7965` — it
would **fail to clear the 0.80 bar despite 24 successes**, forcing A3 on a near-perfect result;
only a clean 25/25 (`CI_lo = 0.8628`) could fire A1. HK-021(m) forbids gating a cut the
instrument cannot resolve. The trials are free (offline, deterministic), so the cheap fix is
more of them.

🔴 **Architect's prediction, on the record, before the run: A1, with `R_forced` ≥ 0.95.**
Reasoning: F's own tone bins are largely uncontaminated — the combs are offset by ~2 bins, so
E's tones fall on F's ±1 *differential probe* bins rather than on F's *signal* bins. **If A2
fires instead, §0.5's mechanism is wrong and must be discarded, not rescued.**

### Gate B — `Z` (independent of Gate A)

| row | condition | consequence |
|---|---|---|
| **B1** | `CI_lo(Z) > 0.50` | **THE SUPPRESSION STAGE IS INERT FOR A MAJORITY OF PRODUCTION DECODES.** Pass 1 may not be cited as the mechanism that recovers weak near-neighbours in live operation. Any future proposal relying on it must **first** establish ramp activity in its own target SNR regime. |
| **B2** | `CI_hi(Z) < 0.20` | Suppression is broadly active in production. **The Architect's §0.4 inertness reading is wrong and is withdrawn.** |
| **B3** | otherwise | Intermediate. Report `Z` and `Abar` with CIs. No consequence. |

**HK-021(m).** At ~4,600 cycles the cluster-bootstrap half-width on a proportion is ≪0.05, so
both bars resolve by a wide margin. The live risk is not resolution but a landing near 0.5
firing B3 — an informative outcome, not a failure.

🔴 **Architect's prediction: B1, with `Z ≥ 0.80`** (live off-air SNRs run well below the
synthetic scene's, so the ramp should be inert more often, not less). **I am stating plainly
that I expect B1 and that its value is the binding consequence, not surprise.** If that reads as
a decorative gate, say so and refuse it under HK-025 — but note what B1 forecloses: a whole
class of "pass 1 will catch it" arguments that have never been tested.

🛑 **What Gate B does NOT authorise, whichever row fires.** It does **not** authorise changing
`K_SOFT_SUPP_SNR_MIN_DB`/`MAX_DB` — that is `diag-d001-h5-suppression-tuning`'s closed ground
(shim 20260011, REJECTED, over-suppression confirmed), and re-reading a closed gate with a
better metric earns a **new** pre-registration, not this one. B1 is a statement about **how
often the stage acts**, not about where the window should sit.

### Reading order

**Read Gate A first, then Gate B, then Part C descriptively.** They are independent; neither
governs how the other may be cited. Part C is read **only** as context for whichever Gate A row
fired, and never as a gate.

---

## 6. 🛑 What this arm does NOT do, and what no result from it authorises

- **Does not touch `src/`.** No rebuild, no new export, no shim version. If you find yourself
  wanting one, stop and escalate — that is a different arm and a Developer session.
- 🛑 **Does not authorise any candidate-budget change.** "**Candidate-budget family closed
  twice — no caps, no passes**" is a standing prohibition. If **A1** fires, the treatment space
  is candidate **selection policy** (e.g. spatial fairness in the heap), explicitly **not**
  raising `K_MAX_CANDIDATES`/`K_MAX_CANDIDATES_PASS2` and **not** adding a pass. A1 identifies a
  **locus**; it authorises **no specific treatment**.
- 🛑 **Does not authorise an OSR change.** `K_FREQ_OSR`/`K_TIME_OSR` 2→4 is prohibited on P3's
  evidence and earns its own pre-registration with FP primary.
- 🛑 **Does not re-open subtract-and-resynthesise** (dead: three builds, three reverts) or
  **spectral locality** (retired permanently, four attempts, zero readings — do not re-propose
  under any name).
- **Does not move the suppression ramp** — see Gate B's closing note.
- **Does not investigate the S5 false-positive regression**, the station-F/S5 relationship, or
  the 8-vs-0 S8HN false positives. Related-looking; separately open; not funded here.
- **Does not perform the NFR-021 `livecopy-preclear` deletion or the 151-file historical
  audit.** Still open, still the Captain's call, still recommended first by the Architect.
- **Does not open E4** (fading/Doppler/drift/timing spread). Only ROW C3 of C-ASYM-A authorises
  that, and this arm does not touch it.
- **Does not bear on E2** (our exclusive decodes are junk-heavy). Station F is a *miss*, E2 is
  about *false positives*. Do not let one read the other.
- **Does not claim anything about WSJT-X's behaviour** — see §4.3's scope boundary.

---

## 7. Everything the Architect measured today, in full (the disclosure of §0)

Sources, so QA can re-derive every number independently:

| finding | derived from |
|---|---|
| 1100–1200 Hz decode table (§0.1) | `qa/rr-study/results/2026-08-23-73c1288/{owsfz,wsjt}-all.txt`, field `[6]` filtered to 1100–1200 |
| matcher tolerance (§0.2) | `qa/rr-study/harness/matcher.py:31,120-126,168-174` |
| J and G/H recovery (§0.3) | frequency histogram of `owsfz-all.txt` field `[6]`: `1900 → 25`, `1500 → 50` |
| suppression ramp arithmetic (§0.4) | `ft8_shim.c:537-538,743-790`; SNR provenance `ft8_shim.c:1537,1549` |
| ramp duty-cycle figures (§0.4) | `factor` evaluated over all 283 rows of `owsfz-all.txt` field `[4]` |
| tone-comb offset (§0.5) | 1150/6.25 = 184.000; 1162/6.25 = 185.92 |
| differential sync score (§0.5) | `native/ft8_lib_build/patched/ft8/decode.c:180-190` |
| production decode order (§0.6) | `decode.c:628-666`; probe equivalence `decode.c:907-985` |
| production LDPC/OSD args (§0.6) | `ft8_shim.c:509`; `decode.c:666` |
| DLL SHA + export table (§0.6) | `sha256sum` on both copies; export-name extraction from the binary |

**Not measured, deliberately:** `R_forced` (Part A) and live `Z` (Part B). See §0.

---

## 8. Handover

- Harness location: `qa/rr-study/f-nbr-a/`. Results under `qa/rr-study/f-nbr-a/results/`.
- ⚠️ **Guard your results paths.** N14's `results_guard.py` (`guard_paths()`) exists precisely
  because harnesses in these directories silently clobber git-tracked baselines on re-run. Wire
  it in, or justify not doing so.
- Report to `qa/rr-study/<UTC>-qa-to-architect-f-nbr-a-results.md`, sections per HK-001,
  timestamps per HK-017 (`date -u`, filename and byline must agree).
- **QA stops at the gate.** Commit locally; **no push, no merge, no `pre_merge_check.py`**
  (HK-014, HK-006, HK-010).
- 🔴 **HK-025 stands: QA may refuse to run this spec** on HK-021(k) grounds without Architect
  agreement. Name the row and the evaluation, stop, and do not run it partially.
- 🔴 If a ROW 0 check needs correcting to be runnable, **correct it and disclose the correction
  in full**, as C-ASYM-A's QA did with the bootstrap-construction defect. A disclosed correction
  is a result; a silent one voids the arm.
