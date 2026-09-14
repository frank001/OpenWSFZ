# `PASSBAND-140` (the G2(b) `140 Hz` rung, re-armed) — pre-registration: does opening the candidate passband at both edges (`f_min` 200 → 140 Hz, `f_max` 3000 → 3075 Hz) raise reference-matched 20m recovery, on today's binary, without costing in-band recovery?

**Architect, 2026-09-14 15:42Z** (`date -u`, HK-017). Branch `arch/g2b-passband-140` (cut from
`origin/main`, now at `b4f67f42`). Docs-only; `git diff --stat origin/main...HEAD -- src/ native/` empty.

**Status: cleared to specify; the Developer session and the run are cleared by the same go.** The
Captain, 2026-09-14 ~15:3xZ, on the recommendation to re-arm the passband widening with a rewritten
plan: *"proceed"*. `BAR_G` and `BAR_H` (§3.4) are Architect-set, not PO-ratified. The Captain may move
either **before the first datum**. After that both are frozen, and anyone proposing to move them (me
included) gets refused.

**Amendment 1, 2026-09-14 15:52Z, before any build or datum.** The top edge is back in the treatment:
`WIDE` also sets `f_max` = 3075 (§0.3 item 4, §2.1). Our real top edge today is **2959 Hz, not 3000 Hz**,
because a candidate needs all 8 tones inside the waterfall. That leaves 179 C2 reference decodes above it,
not 33. Sections touched: title, §0.1, §0.2, §0.3, §2.1, §3.1, §3.2 0a/0f, §3.5 A2/A3, §3.7, §4, §6.

**Supersedes, as the instrument for this question:** revision 6's pre-registration
(`qa/cycleframer-alignment-replay/2026-08-13-1614-qa-to-architect-g2b-revision-6-j1-j6-fixed.md`),
the 08-25 arming directive (`…/2026-08-25-1550-…-g2b-140hz-rung-armed-captains-ruling.md`), and the
08-25 baseline ruling's §5 (`qa/rr-study/2026-08-25-1725-…-140hz-baseline-ruling.md`). §0.3 says what
carries over, what is retired, and why.

---

## §0. What this is, why now, and what it reuses

### 0.1 The one-line reason

`ft8_shim.c` builds its waterfall from `.f_min = 200.0f` (`:1472`, `ft8_decode_all`; `:1872`,
`ft8_extract_llrs_at`). Any signal whose base tone sits below 200 Hz is missed **by construction, 100%
of the time.** WSJT-X FT991A decodes them. **The top edge cuts too, and lower than its constant
suggests:** `f_max` = 3000 gives `max_bin` = 481 (`monitor.c:116`), and a candidate needs all 8 tones in
the waterfall (`decode.c:292`: `freq_offset + num_tones − 1 < num_bins`). So the highest base tone we can
decode is `(481 − 8) × 6.25 + 3.125` = **2959.4 Hz**. Our live logs top out at exactly **2959 Hz** on both
corpora (checked). This is the largest recoverable item on the board that is
not closed or prohibited (ledger bucket A; GAP-CENSUS-A ROW A1, `S_A` = 6.17%). The Captain armed it on
2026-08-25. It then stalled for three weeks because the two binaries it needs were never built. **Nothing
about the question has changed. The instrument has to.**

### 0.2 The ceiling on today's audio, counted while drafting (HK-018)

REF = WSJT-X FT991A `ALL.TXT`, dial `14.074`, FT8 rows, counted by audio frequency. **Counts only. No
replay, no match, no recovery, no leg was run.**

| corpus | REF rows | `low` 138–199 Hz | `hi` 2960–3034 Hz | still out: ≤ 137 / ≥ 3035 | ours (live) outside 200–2959 |
|---|---:|---:|---:|---:|---:|
| **C2** `20260908_live_run_1827-fp-floor-live-2`, from `260908_193645` | 91,076 | **1,733 (1.90%)** | **155 (0.17%)** | 17 / 24 | 0 of 57,969 |
| **C1′** `20260808_live_run_0016-8080`, `[260808_011045, 260808_111500]` | 64,771 | 703 (1.09%) | 56 (0.09%) | 6 / 51 | — |

⇒ **The most this change can add on C2 is ≈ 2.1 pp of `R`** (1.90 low + 0.17 top). It is a ceiling, not
an expectation: those signals pass the radio's filter skirts, and our overall recovery against WSJT-X is
61%. ~~`≥ 3000` Hz: C2 33, C1 73~~ (the first draft counted the top edge from `f_max`, not from the real
2959 Hz edge; C2 actually has 179 REF rows above 2959).

⚠️ **Disclosure (de-blinding check).** Beyond the table above I have seen exactly one outcome-bearing
number, and every reviewer since 08-12 has seen it too: `79ea12af`'s commit message reports a 250-cycle
dev replay (C1's first 250 cycles, `wsjt-x/wav`): 131 emitted gains in `[140,200)`, 109 in-band gains
and 125 in-band losses against 4,842 baseline decodes. Those are **emitted** counts on the raw ABI, not
reference-matched. They are why C1's first 250 cycles are burned (§1), and I state them here so that
no bar below can be read as tuned to them. `BAR_H` equals revision 6's `churn_net` floor, which was set
on 08-12 with the same numbers in view.

### 0.3 What carries over from revision 6, and what is retired

**Carries over, unchanged:** the question (does the rung recover real signals); the rung (`f_min` =
140, i.e. `min_bin` = `(int)(140 × 0.16)` = 22 ⇒ **137.5 Hz**, same 6.25 Hz lattice, so no in-band bin
moves, `monitor.c:115`); the burned-corpus rule (C1 held out from cycle 250); the two-binaries-one-tree
build discipline (08-25 §5.2); the determinism control; pin-the-SHA; the `[100,140)` rung stays unrun.

**Retired before any datum, for reasons 1–3. Item 4 corrects the treatment itself:**

1. **Its primary metric counts emitted decodes, not reference-matched ones** (`g2b_gate.py:394-435`:
   `g_low` = gained `(freq, dt)` tuples in the new band ÷ baseline decodes). It cannot separate recovery
   from a false accept in the thinnest-SNR part of the band. That is exactly the question the 08-25
   directive §5 left open and called the only thing between a measured rung and a shippable one.
   **This arm's primary metric is `R`, reference-matched by construction, so the question closes.**
2. **It drives the raw C ABI** (`g2_verification_replay.py`). That is not the live path: `ALL.TXT` is
   post-`IsPlausibleMessage` and text-deduplicated (`Ft8Decoder.cs:338-354`), and the replay bypasses
   both. That was the defect in my own LIVE-GAP-NOW spec (acceptance ruling §2.1). ≥ 52.8% of that arm's
   replay-only decodes were implausible messages live never writes.
3. **Its baseline pin (`f2f30c89…`/`20260033`) was already retired** on 08-25, and its manifest was never
   populated.
4. ~~**Its `f_max` = 3030 half is dead.** `[3000, 3030)` gained 0 decodes in `79ea12af`'s own run; the raw
   WAV sits at −42.9 dB there (the radio's filter, ledger Table 4); and C2's REF has 33 rows above
   3000 Hz in total. **Changing `f_max` would add a second variable (five more bins in the noise-floor
   median) with nothing to buy. This arm changes `f_min` only.**~~ **Its `f_max` = 3030 was mis-derived,
   and the evidence that the top edge was "dead" was blind by construction (HK-026).** `79ea12af` sized
   the passband so that REF base frequencies up to 3030 Hz were covered, but it set `f_max` = 3030 as if
   the waterfall's top edge were the highest decodable base tone. It isn't. With `f_max` = 3030 the
   highest base tone is `(485 − 8) × 6.25 + 3.125` = 2984 Hz. Our reported `freq_hz` is the base tone,
   so a gain landing in `[3000, 3030)` was impossible: "0 gains in `[3000, 3030)`" could not have read
   anything else. The same holds for ledger Table 4's upper-passband row. **This arm keeps `79ea12af`'s
   stated intent (cover REF base tones to 3030 Hz) and applies the 8-tone arithmetic it left out:
   `f_max` = 3030 + 7 × 6.25 ≈ 3075 ⇒ `max_bin` 493 ⇒ top base tone 3034 Hz.** That covers 155 of C2's
   179 REF rows above 2959 Hz. The top edge adds 12 bins (481 → 493), while the bottom edge adds 10
   (32 → 22).

The family adjudicator, round 7 and K1–K5 are **not reopened.** They served a three-rung family, and
no family is being adjudicated here. Revision 6's four bars are **not applied**. The legacy quantities
are still reported, descriptively (§3.5 A4), so the Captain can see them.

### 0.4 The shipping condition is met on its own terms

The 08-13 and 08-25 rulings said G2(b) *"may not ship until R2 reports"*, so that no baseline moved
under the R0→R2 programme. **R2 reported on 2026-08-22** (`fe98e171`: Phase B wrap-up, §4.3 VOID, QA
stops; change archived at `f00f09f3`). Its successor route (Route B2, the coherent extractor) was parked
by the Captain on 2026-09-14 (THRESH-A route A). No programme is now standing on that baseline.
**Architect reading: the condition is discharged. It is the Captain's ruling, so it is his to confirm (§5
Q2).** Until he does, a ROW G1 recommends a ship and does not open the ship dev-task.

### 0.5 Reused, not rebuilt (HK-018)

| what | where | note |
|---|---|---|
| matcher | `qa/rr-study/live-gap-now/matcher.py` `recovery()`, `load_all()` | H1's `R_wild` path. LIVE-GAP-NOW ROW 0c reproduced `40,003 / 69,222` with it, to the digit. |
| paired bootstrap | `live-gap-now/bootstrap.py` `paired_cluster_bootstrap()`, `delta_summary()` | frequency clusters, per-draw arrays. §3.1 adds a cycle-cluster variant. |
| corpus lists | `live-gap-now/corpus.py` `c1_cycles()`, `c2_cycles()` | C1 needs the held-out cut (§1). |
| decode loop | `live-gap-now/decode_leg.py` `decode_corpus()` | ⚠️ its `main()` runs C1 then C2 **in one process**, so C1's hash-table state leaks into C2. Not acceptable here (§2). |
| seam | `live-gap-now/seam.py` `seam_fidelity()` | as LIVE-GAP-NOW ROW 0d |
| wav/normalise | `qa/cycleframer-alignment-replay/p23_common.py` `read_wav()`, `normalise_rms()` | mirrors `Ft8Decoder.NormalisePcm` |
| legacy terms | `qa/cycleframer-alignment-replay/g2b_gate.py` `per_cycle_terms()`, `rates()` | **imported, not re-implemented**, for A4 only |

🔴 **HK-020 trap, named in advance:** `p23_common.DECODE_PARAMS` is `(10, 0.10, 60)` and is
deliberately pinned to 60 (`p23_common.py:49-55`). `dll_pin.load_leg()` applies it. **Every leg here
sets its params explicitly and asserts them (§2).** The station, and `main`'s code default since PR #168,
run at **40**.

---

## §1. Corpora and reference

| id | role | corpus | cycles | our audio | `REF` |
|---|---|---|---|---|---|
| **C2** | **primary** | `artefacts/20260908_live_run_1827-fp-floor-live-2/` | `cycle_start_utc ≥ 2026-09-08T19:36:45Z`, dial `14.074`, from `cycle-archive.csv`, `*_2.wav` excluded (as LIVE-GAP-NOW §1) | `cycle-audio/` | `wsjtx-1-ft991a/ALL.TXT`, **A only** |
| **C1′** | **sign replication** | `artefacts/20260808_live_run_0016-8080/` | `owsfz/wav/` stems in **`[260808_011045, 260808_111500]`** | `owsfz/wav/` (our own capture) | `wsjt-x/ALL.TXT`, **A only** |

- **C1′'s lower bound is the burned-cycle cut.** The 251st file of sorted `wsjt-x/wav/*.wav` is
  `260808_011045.wav`; files 1–250 (to `260808_011030`) are `79ea12af`'s dev set. Checked while
  drafting. QA re-derives it (ROW 0h).
- **REF is restricted to the decoded cycle set** (`ts` ∈ the cycles every leg decoded), so a cycle with
  no WAV is not a miss for either leg. Report `|REF|` per corpus. It will differ slightly from A1's
  91,046.
- **Why C2 is primary:** it is current-era audio, and its live `openwsfz/ALL.TXT` was written by the
  **same binary `main` ships today**: `6b2e16a6…`, hashed from `origin/main` and from `cf21ac5`
  (identical), with **zero commits to `src/OpenWSFZ.Ft8/` or `native/` since `cf21ac5`** (checked). So the
  replay can be validated against live on the very corpus that carries the gate (ROW 0d). C1 cannot offer
  that.
- **Neither corpus is de-blinded for this contrast.** No `f_min` = 140 binary has ever decoded either.
  LIVE-GAP-NOW's de-blinding covers its own `L08 → NOW` `Δ` only.

## §2. Builds and legs

### 2.1 The Developer session (HK-011): two binaries, one tree, one session

QA authors the dev-task (HK-015). These are its binding constraints; the procedure is QA's to write.

1. **A throwaway branch off `origin/main` (`b4f67f42` or later), never pushed or merged.** `BASE` = that
   tree, rebuilt from source with `native/ft8_lib_build/rebuild_shim.bat` (the authoritative script,
   `BUILD.md:116`). `WIDE` = the identical tree plus **exactly two edited lines**:
   `.f_min = 200.0f, .f_max = 3000.0f,` → `.f_min = 140.0f, .f_max = 3075.0f,` at `ft8_shim.c:1472` and
   `:1872`. Both call sites change so that the diagnostic extractor keeps the production waterfall
   geometry. **`FT8_SHIM_VERSION` is not bumped:** a bump would be a third diff line, and identity is by
   SHA anyway.
2. **`git diff BASE..WIDE` is exactly those two lines**, and it is pasted into the dev-task's completion
   record. Anything else: stop and report, no leg.
3. **Both DLLs are copied to `artefacts/passband-140/bin/` with distinct filenames**
   (`libft8_PB140_BASE.dll`, `libft8_PB140_WIDE.dll`). **The tracked `src/OpenWSFZ.Ft8/Native/*/libft8.*` is
   not modified.** `git status` after the session shows no change under `src/`.
4. **Both SHA-256s go into a new manifest, `qa/rr-study/passband-140/dll_manifest.json`, committed before the
   first leg runs.** Never edit an entry after its leg has run. The old `g2b_dll_manifest.json` stays
   retired with revision 6.
5. **Nothing ships.** No `f_min`/`f_max` edit reaches `main` from this session.

### 2.2 Legs

**One process per (leg, corpus)**, each starting cold, one continuous chronological pass per corpus.
**No partitioning:** the callsign hash table is process-global, and matching cold starts across legs is
simpler than matching partitions. Each leg asserts, **through the loaded handle**, the SHA-256 of the
loaded file, `ft8_lib_version_check()`, and `ft8_set_decode_params` with the params below. Legs may run
concurrently as separate processes. Supervise anything over an hour (HK-013 / HK-023).

| leg | binary | params `(k, corr, nhard)` | corpora | purpose |
|---|---|---|---|---|
| **B40** | `BASE` | `(10, 0.10, 40)` | C2, C1′ | primary baseline |
| **W40** | `WIDE` | `(10, 0.10, 40)` | C2, C1′ | treatment |
| **B60** | `BASE` | `(10, 0.10, 60)` | C2 | seam check against C2's live log, which ran at 60 (ROW 0d) |
| **B40r** | `BASE` | `(10, 0.10, 40)` | C2, first 300 cycles | determinism (ROW 0e) |
| **K60** | committed `6b2e16a6…` (from `git show origin/main:…/win-x64/libft8.dll`) | `(10, 0.10, 60)` | C2, first 500 cycles | only if ROW 0b's SHA test fails |

Pipeline per cycle: `read_wav()` → `normalise_rms(…, 0.20)` → `ft8_decode_all` → **the managed chain**
(§3.1). Keep the raw per-cycle output too (`artefacts/`, gitignored). ≈ 5,200 C2 cycles × 3 full legs +
2,418 C1′ × 2, at ≈ 0.55–0.57 s a cycle, is about an hour wall-clock with the legs run in parallel.

**Truncation guard (ROW 0g):** if any cycle returns exactly `MAX_RESULTS`, raise `MAX_RESULTS` to 400
and re-run that leg on that corpus. Report the count. W40 is the leg most likely to hit it.

## §3. `PASSBAND-140` measurement

### 3.1 Definitions (predicates as code, HK-021(r))

- **The managed chain**, applied to every replay leg per cycle, in production order: `TrimEnd()` →
  de-duplicate by message text (first wins, native order) → **production
  `Ft8Decoder.IsPlausibleMessage(msg, grammarStore)`, called from the production assembly by
  reflection** (it is `internal static`, `Ft8Decoder.cs:568`; this is qa-tooling, not a `src/` change),
  with `grammarStore = new CallsignGrammarStore(<path>)` exactly as `Program.cs:115-123` builds it, from
  the station's own `callsign-grammar.json` beside `config.json`. Record that file's SHA-256. 🛑 **No Python
  port.** My partial port in the LIVE-GAP-NOW acceptance ruling missed the D9-R3 grammar rule. This arm
  calls the real code.
- `R(OWS, REF)` = `matcher.recovery()`: `100 × (|REF ∩ OWS| + |wild_gained|) / |REF|`. That is H1's
  `R_wild`, keyed `(ts, message)`. Report `R_base` (exact only) and the wildcard margin `M = R_wild − R_base`
  beside every `R`.
- **Per-REF-row indicator:** `hit_L(r)` = 1 if REF row `r` is in the exact set or in `wild_gained` for leg
  `L`. Then `R = 100 × Σ hit / |REF|`.
- **Bands, by the REF row's own `freq_hz`** (the base tone, as ours is), cut at the two apertures'
  real edges: `sub` ≤ 137 · **`low` 138–199** · `in` 200–2959 · **`hi` 2960–3034** · `beyond` ≥ 3035.
- `D(C)` = `R(W40, C) − R(B40, C)`, in pp. `D_band(C)` = `100 × Σ_{r ∈ band}(hit_W40(r) − hit_B40(r)) / |REF|`.
  **Additive identity, asserted mechanically:** `D = D_sub + D_low + D_in + D_hi + D_beyond` to within
  `1e-9`.
- **Paired CIs, two cluster schemes, and the wider one governs.** N_BOOT = 2000, seed `20260914`, both
  legs recomputed on the same draw, `Δ` taken per draw (never the difference of two independent CIs):
  - **frequency clusters** over REF's distinct `freq_hz` (`paired_cluster_bootstrap()`, as LIVE-GAP-NOW);
  - **cycle clusters** over REF's distinct `ts` (decodes in one cycle share one noise realisation and one
    candidate ordering, HK-021(i), revision 6's unit).

  `CI_lo = min(lo_freq, lo_cyc)`, `CI_hi = max(hi_freq, hi_cyc)`, from the 2.5/97.5 percentiles. The same
  rule applies to `D_in`. `SE` is reported for both schemes.

### 3.2 ROW 0: strict order

| row | check (as code) | on failure |
|---|---|---|
| **0a** build | `git diff BASE..WIDE` = the two `monitor_config_t` lines only (§2.1.1–2); both SHAs in the committed manifest before the first leg; every leg's loaded-file SHA, `ft8_lib_version_check()` and asserted params match §2.2 | **STOP** |
| **0b** BASE is what ships | `SHA(BASE) == 6b2e16a6991ae953…34f85c`, **or** K60 and B60 give identical full tuples `(ts, freq_hz, dt, snr, message)` on C2's first 500 cycles | **STOP, escalate.** A `BASE` that differs from the shipped binary makes `W − B` a contrast on a toolchain nobody runs. |
| **0c** chain fidelity | the chain applied to C2's **live** `openwsfz/ALL.TXT`, grouped per cycle, rejects **≤ 0.1%** of rows (≤ 57 of 57,969) | **STOP.** Live is post-chain, written by the same code, so a correct chain rejects ≈ 0 (my partial port rejected 3). |
| **0d** seam | B60 through the chain vs C2's live `openwsfz/ALL.TXT`, `seam_fidelity()`: **`F_live ≥ 0.97`**. Report `F_rep` (after the chain), `M` for both, and live cycles with no WAV. | **§3.6 rows VOID.** The replay is not the live decoder. |
| **0e** determinism | B40r's full tuples equal B40's on C2's first 300 cycles, mechanically diffed | **VOID.** A paired contrast on a non-deterministic instrument is noise. |
| **0f** the treatment moves (HK-021(q)) | W40's C2 output ≠ B40's; **W40 emits ≥ 1 post-chain decode with `freq_hz` < 200, and ≥ 1 with `freq_hz` > 2959, on C2**; **B40 emits 0 outside 200–2959** | **STOP.** The wrong DLL loaded, or an edge never reached the waterfall. Paste one W40 decode per edge, `(ts, freq_hz, snr)`, into the report as the exhibit (no message text). |
| **0g** truncation | no cycle at `MAX_RESULTS` in any leg, after any re-run | re-run at 400, then **STOP** if still hit |
| **0h** C1′ cut | the 251st sorted `wsjt-x/wav/*.wav` is `260808_011045.wav` | **STOP** |

**Why each row changes the verdict (HK-021(k), both branches evaluated):**
- **0b:** without it a positive `D` could belong to QA's build, not to the change. 0b ties `BASE` to the
  binary behind C2's live log, which is also what makes 0d mean anything.
- **0c:** the chain is text-based and frequency-blind, so a wrong rule strikes the new band exactly as
  hard as the old. It would bias `D_low`, `D_hi` and the A3 flag. Checking it on live, where the right answer is
  ≈ 0 rejections, is the only place we know the truth.
- **0d:** a replay reproducing < 97% of live's own decodes has a defect bigger than anything explained.
  LIVE-GAP-NOW measured `F_live` = 0.9832 on this corpus, binary and `nhard`, and the chain cannot raise
  `F_live`. That breaks both legs in unknown ways. **`F_rep` is deliberately NOT gated.** Its known excess
  is implausible messages, which cannot enter `R`: partial R4 moved `R_wild` by −0.03 pp (acceptance §2.2).
  The residual, cold hash state, is common to both legs. Gating it would VOID the arm over something that
  cannot bias `D`, and QA should refuse such a row (HK-025).
- **0e / 0f:** if the two outputs were identical, `D = 0` would read G3, falsely. That is FP-REGRESSION
  E2's blind seam.
- **No power row.** A power gate would change nothing: an underpowered CI straddles a bar and lands in G4
  anyway, while a wide CI that still clears or still misses reads correctly. So it is reported (§3.3), not
  gated.

⚠️ **What ROW 0 cannot detect (HK-022, HK-026).**
- **The live log is blind below 200 Hz and above 2959 Hz.** Our live decoder never looked there, so 0d
  validates the seam in-band only. For `D_low` and `D_hi` the only witness is WSJT-X. An argument covers the gap, not a measurement:
  C2's `cycle-audio` is the audio the live decoder was fed, and nothing in the pipeline is
  frequency-dependent except the waterfall bound under test.
- **`REF` is WSJT-X, not truth.** A `low` REF row WSJT-X missed can't be a gain, and an unmatched decode of
  ours can't be called false.

### 3.3 Resolution, computed while drafting (HK-021(m), (o))

- **Readout quantum:** one REF row in 91,000 = **0.0011 pp**.
- **Expected SE(`D`):** the effect lives in ≈ 62 low-band frequency clusters (plus ≈ 75 thinly
  populated top-band ones) out of ≈ 2,900. Resampling
  moves that count by about ±8, which puts frequency-cluster SE at roughly **0.10–0.20 pp**. Cycle-cluster
  SE should be smaller, ≈ 0.05 pp. The wider governs.
- **Power against `BAR_G` = 0.25**, at the SE bounds (P(ROW G1-or-G2 fires | true `D`)):

  | true `D` | 0.50 | 0.75 | 1.00 |
  |---|---:|---:|---:|
  | SE 0.10 | 0.71 | 1.00 | 1.00 |
  | SE 0.20 | 0.24 | 0.71 | 0.96 |

  **My own central estimate is `D` ≈ 0.8 (§4), where this arm has power 0.78–1.0.** It is not sized to fire
  only on a landslide (proposed HK-021(v)).
- **G3 needs `CI_hi` < 0.25**, i.e. `D̂` ≲ 0.05 at SE 0.10, or ≲ −0.14 at SE 0.20. **G3 is a real
  absence: it fires only if the change does essentially nothing.** Everything between G3 and G1 is G4.

### 3.4 Why `BAR_G` = 0.25 pp and `BAR_H` = 0.25 pp

- **`BAR_G` (net gain worth shipping).** On C2, 0.25 pp of `R` ≈ 0.044 extra WSJT-X-confirmed decodes a
  cycle. That's one more every ≈ 23 cycles (≈ 6 min) on a band averaging ≈ 17 reference decodes a cycle.
  It is set above the ledger's "marginal" D-009 sweep (+0.11 pp) and below AO1's 0.71 pp. The change costs
  decode time: `79ea12af` measured +3% for 14 extra bins (0.555 → 0.571 s), and this `WIDE` adds 22
  (449 → 471), so expect ≈ +5%, against the operator-window budget in the latency defect. It also costs some candidate-budget displacement, so it has to buy something. It does not depend on
  any number this arm will produce.
- **`BAR_H` (tolerated in-band loss).** In-band losses are stations that decoded yesterday and don't
  today. Their likely cause is candidate displacement (`79ea12af`: pass-1 saturation 40.8% → 46.4%).
  That scales with band density, while the gain scales with low-band occupancy. **So a real in-band loss is
  a warning that the net can turn negative on a crowded day, even when this corpus's net is positive.** 0.25
  equals revision 6's `churn_net` floor, carried over for continuity (see the §0.2 disclosure).

### 3.5 Descriptive, no row (report every one)

- **A1:** `R`, `R_base`, `M` and `|REF|` for every leg × corpus, and `F_rep` for B60.
- **A2: where `D` lives.** The five-band `D` table for both corpora, with CIs, plus a **yield per edge**:
  `D_low ÷ (low REF share)` and `D_hi ÷ (hi REF share)`, the fraction of each ceiling actually recovered.
  Also recovery of `low` and `hi` REF rows by **REF SNR** in 2 dB bins for W40 (the C-GAP-D presentation).
- **A3: what the operator would see in the new bands, per edge.** W40's post-chain decodes on C2 with
  `freq_hz` in `[137.5, 200)`, and separately in `(2959, 3034.4]`: count, share REF-matched, share
  unmatched. **Unmatched density** (unmatched decodes per 6.25 Hz bin per 100 cycles) in each new band,
  against B40's in-band unmatched density. 🚩 **If either ratio exceeds 3, flag it to the Architect the
  same day, naming the edge, before any ship dev-task is written.** Unmatched is not
  false (HK-026), and FP is off the menu (Captain, 09-12), so this is a flag and not a gate. Still, nobody
  ships an edge that sprays text without the Captain seeing it first.
- **A4: legacy readout, continuity with revision 6.** `g2b_gate.per_cycle_terms()` + `rates()`,
  imported, on post-chain B40 vs W40 over C2: `g_low`, `churn_net`, `churn_gross`. **No bar is applied and
  no row is read.** Revision 6's bars are retired (§0.3).
- **A5: cost.** Per-cycle wall time p50 / p99 / max for B40 and W40 on C2. Candidate counts per pass if the
  binding exposes `ft8_get_last_candidate_counts`, as pass saturation.
- **A6: the 08-25 question, closed in words.** State that `R`'s gains are reference-matched by
  construction.

### 3.6 Gate rows (C2 primary, C1′ sign; first match wins)

| row | predicate | reading |
|---|---|---|
| **G1** | `CI_lo(D(C2)) ≥ +BAR_G` **and** `CI_lo(D_in(C2)) ≥ −BAR_H` **and** `D(C1′) > 0` (point) | **Ship-eligible.** Real net recovery, no material in-band cost, replicates in sign. |
| **G2** | `CI_lo(D(C2)) ≥ +BAR_G` **and** `CI_lo(D_in(C2)) < −BAR_H` **and** `D(C1′) > 0` (point) | **Net gain, with an in-band cost.** A trade for the Captain. |
| **G3** | `CI_hi(D(C2)) < +BAR_G` | **No material gain.** The aperture holds real signals that we still don't decode. |
| **G4** | otherwise (straddles `BAR_G`, or C1′ disagrees in sign) | **Unresolved.** |

Mutually exclusive by construction. G1 and G2 split on `D_in`. G3 cannot hold alongside either
(`CI_lo ≥ 0.25` against `CI_hi < 0.25`, with `lo ≤ hi`). G4 is the remainder.

### 3.7 Consequences

- **G1** ⇒ **ship recommended.** Once the Captain confirms §0.4, QA authors the ship dev-task:
  - `f_min` 140 and `f_max` 3075 at both call sites (or one edge only, if A3 flagged that edge and the
    Captain rules so);
  - `FT8_SHIM_VERSION` bump and all-platform rebuild (macOS by CI, as standing);
  - `BUILD.md`'s "Monitor Configuration" block updated;
  - **the false comment at `Ft8LibInterop.cs:231`** fixed.

  Merge needs the Captain (HK-010). From then on A1 = 61.09% is a **pre-G2(b)** figure and must say so. If
  A3 flagged, the Captain sees the density numbers before the dev-task is written.
- **G2** ⇒ the Captain decides with `D`, `D_low`, `D_hi`, `D_in` and A3 in front of him. One `WIDE`
  cannot say which edge caused an in-band cost. If that matters to the decision, the follow-up is a
  split-edge build pair, not a re-read. Architect recommendation goes in the acceptance ruling, not now.
- **G3** ⇒ **the passband route closes.** The ledger records bucket A as *"aperture real, signals real (WSJT-X
  decodes them), not recovered by widening on this binary"*. G2(b) is struck from the running order. The
  `[100,140)` rung is not run.
- **G4** ⇒ report every figure. Nothing ships. The Architect decides between a second current-era corpus and
  stopping. `D` may not be cited as a gain or as the absence of one.

**All rows, regardless:** the `Ft8LibInterop.cs:231` comment (`20260038` "(b) the decode candidate
passband widens from [200, 3000) Hz to [140, 3030) Hz") **is false on `main` today** (`ft8_shim.c:1472`
reads 200). If this arm does not ship, the comment is corrected in the next Developer task that touches
`src/OpenWSFZ.Ft8/`. It is recorded here so it isn't lost.

---

## §4. Architect predictions: blind, on the record, before any datum

| row | probability | reasoning |
|---|---|---|
| **G1** | 0.45 | 1,888 real, WSJT-X-decodable signals (1,733 low, 155 top) sit behind walls we built. Even at half our in-band yield that clears 0.25 pp by a wide margin. |
| **G2** | 0.25 | Displacement is real (pass-1 saturation rose in `79ea12af`), and C2 is crowded. `D_in` near −0.1 to −0.2 is plausible, so the harm bar could be crossed. |
| **G4** | 0.20 | Low-band occupancy is lumpy (few stations, long dwell), so frequency-cluster SE may be at the top of my range. C1′'s ceiling is only 1.15 pp. |
| **G3** | 0.10 | Only if skirt-attenuated signals sit below our threshold almost uniformly. |

**Point predictions:** `D(C2)` ∈ **[+0.55, +1.4] pp**; low yield (`D_low` ÷ 1.90) ∈ [0.35, 0.65]; top
yield (`D_hi` ÷ 0.17) ∈ [0.25, 0.65], lower than the low edge's because the radio's upper skirt is
steeper (−42.9 dB in the raw WAV at `[3000, 3030)`); `D_in(C2)` ∈ [−0.25, 0.00] pp; A3 flag fires: 0.6. **ROW 0b** by SHA equality 0.4, by output identity 0.9. **ROW 0d**
PASS 0.85. Calibration: my last three categorical calls in this programme missed (LIVE-GAP-NOW ROW 0d,
THRESH-A T2 at 25% prior, `Δ50`). Weight these accordingly.

---

## §5. PO questions (before the first datum only)

- **Q1: `BAR_G` = 0.25 pp and `BAR_H` = 0.25 pp?** Architect-set per §3.4. Movable **before QA produces any
  `D`**; frozen after. A move proposed once `D` is known is refused and VOIDs the arm.
- **Q2: is the "may not ship until R2 reports" condition discharged?** Architect reading: yes (§0.4). It
  does not block the measurement either way. It only decides whether a G1 opens the ship dev-task directly.
- **Q3: retiring revision 6's bars** (§0.3) replaces the instrument the Captain armed on 08-25. The reasons
  are in §0.3. If he would rather keep them as a co-gate, say so now. Revision 6's rows would then run
  alongside §3.6 on the same post-chain legs, read in the same invocation (K1), and a disagreement between
  the two goes to him.

---

## §6. What this arm does NOT do

- 🛑 **No `src/` or `native/` change reaches `main`; no push, no merge** (HK-011, HK-014, HK-010). The two
  builds are measurement artefacts on a throwaway branch (§2.1).
- 🛑 **No capture run.** Both corpora are on disk.
- 🛑 **Does not re-read** GAP-CENSUS-A, LIVE-GAP-NOW's VOID `Δ`, X1/X2, C-GAP-D, or any closed gate. It
  does not reopen revision 6's family adjudicator, round 7 or K1–K5.
- 🛑 **Does not touch the `[100,140)` rung, `f_max` beyond 3075, the candidate caps** (`K_MAX_CANDIDATES*`; the
  candidate-budget family is closed twice) **or suppression.** If A5 shows saturation rising, that is a
  finding, not a licence.
- 🛑 **Spectral locality stays barred.** Nothing here stratifies by distance to a neighbouring decode.
- **Cannot see:** any band but 20m; WSJT-X's own misses; true false-positive rates; nhard 60 behaviour of
  `WIDE`.

**NFR-021.** Both corpora's `ALL.TXT` files and WAVs carry real third-party callsigns. Message text stays
in memory and in `artefacts/` (gitignored), never `qa/`. The report carries counts, rates, frequencies and
SNRs only. ROW 0f's exhibit carries no message text. **Scan the report prose** with `scan()`/`classify()`
before committing (the scanner skips uncommitted directories).

## §7. Running order and authorisation

| step | who | status |
|---|---|---|
| This spec | Architect | ✅ Captain: *"proceed"* (2026-09-14) |
| Q1–Q3 | Captain | open until the first `D` exists (Q2, Q3: until the report) |
| Dev-task for §2.1 | QA (HK-015) | cleared |
| `BASE` + `WIDE` builds, manifest committed | Developer (HK-011) | cleared by the same go |
| Chain tool (§3.1) + ROW 0c | QA | can run before the builds land (needs live `ALL.TXT` only) |
| ROW 0a/0b/0h → legs → 0d–0g → §3.6 → §3.5 | QA, in that order | supervise if > 1 h |
| Report, committed locally | QA | push/PR needs the Captain's go (HK-033) |

🔴 **HK-025 is available in full.** If any row here is a diagnostic dressed as a gate, name it, evaluate
both branches, and refuse it.
