# `DENSITY-MECH` — 🛑 **VOID** (Architect's §10 ruling, `arch/density` `1a7f9547`) — ~~result: ROW 1 M1, unanimous~~

🛑 **CORRECTED (post-hoc, 2026-09-18T14:36Z, Architect's §10 ruling, `arch/density` `1a7f9547`): this
arm's verdict is VOID. Do not cite "ROW 1 M1" or "the loss is in extraction" from this report — see the
correction notes struck into §4/§7/§9 below and the summary at the bottom of this file. The run itself
was clean (ROW 0, the per-cell numbers, and the position mapping in §2 all stand as fact) — only the
INTERPRETATION drawn from `orc_E` was wrong. Amendment A1 (spec §10.5) is the follow-up, reported
separately.** Original title, struck: ~~`DENSITY-MECH` — result: **ROW 1 M1, unanimous** — offered the
exact true position with production's own LDPC settings, extraction still fails 0/100 in every excluded
cell~~

QA, 2026-09-18 14:33Z (`date -u`, HK-017). Per spec
`2026-09-18-1356-architect-to-qa-spec-density-mechanism-oracle-position.md`, `arch/density` `1b0d7d20`,
dispatched on Captain authority (*"1. go"*). Offline, synthetic, Q-prefix only. No station time, no live
corpus, no `src/`/`native/` change, no Developer.

~~**Headline: ROW 0 is entirely silent and the primary reads ROW 1 M1, with full unanimity — not a
near thing.** In every one of the 7 primary cells where production excludes the victim (`prod ≤ 0.20`),
the oracle offered `F`'s exact true position with production's own extraction and LDPC settings decodes
it **0/100 times**. The paired control (same noise, `E` removed) decodes the same position **100/100
times** in every one of those same cells. **The bits are corrupted at the true position, not merely
unreached.** This is `M1`: the loss is in extraction (D-001 limb 2), not upstream.~~

🛑 **CORRECTED: this headline is VOID.** My own §5 table already contained the falsification and I
missed it while writing: `orc_E` reads **0/100 in cells where `prod` reads 94–100/100 on the same
audio** (primary `Δ=18.75,X=+1`: prod 94/100; strong `Δ=12.0`/`Δ=18.75`: prod 100/100 both). The
oracle's own premise — "production's own extraction + LDPC, at the right spot" — cannot fail 100/100
where production succeeds 100/100. `orc_E=0` is therefore not evidence the bits are corrupted for
production; it's evidence the oracle isn't measuring what it claimed to. Two things production does
that the oracle didn't (Architect's §10.2, checked in `ft8_shim.c` against `main`): production is
**two-pass** (`K_MAX_PASSES=2`) with soft SNR-scaled tile suppression between passes, which the oracle's
single unsuppressed-waterfall extraction omits entirely; and production extracts at **wherever its own
candidate search lands**, not necessarily `F`'s literal true position. ROW 0 proved the oracle can say
YES (E removed) and NO (−30 dB) — it never checked the oracle against production **with E present**,
which is the only condition this arm actually reads. That's a design gap in the spec I ran faithfully,
not a defect in the run itself.

---

## 1. HK-020 — critical config (checked against spec §1, not inherited from a header)

| config | value |
|---|---|
| Scene | `F-NBR-A`'s S8HN scene, verbatim: `qa/rr-study/f-nbr-a/scene_render.py` + `qa/rr-study/scenarios/s8hn-band-scene-highn.json` (12 stations, Q-prefix). `E` at 1150 Hz; `F` moved per cell, level set per cell |
| Binary | `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll`, SHA-256 `91997e38038d9328edcb49cd1e8661706d0092ed2c73e808094c96c3980ad2c6` (shim `20260051`) — hashed from the file actually loaded, matches spec §1.2's pin exactly |
| LDPC settings | `max_iters=50`, `osd_depth=2` — **read from the build this session**, not inherited from a comment: `K_LDPC_ITERATIONS=50` (`ft8_shim.c:509`), wired as pass-0's `max_iterations` via `k_pass_cfg` (`ft8_shim.c:1579`) into `ftx_decode_candidate` (`ft8_shim.c:1625`); `osd_decode(llr_for_osd, 2, plain174)` hardcoded in production's own BP-failure fallback (`decode.c:666`) |
| Entry points | `ft8_decode_all`, `ft8_extract_llrs_at`, `ft8_ldpc_decode_llrs` — all confirmed present on the loaded handle (ROW 0a). `ft8_coherent_llr_at` **not imported, not called anywhere in this arm** (spec §4 item 5) |
| Cells | Primary: `Δ ∈ {6.25, 12.0, 18.75} Hz × X ∈ {+1, +3, +6} dB` (9 cells, `E` fixed −5 dB, `F` at −6/−8/−11 dB). Strong-victim (reporting only): same `Δ`, `F` +5 dB, `E` +8 dB (3 cells) |
| N | 100 trials/cell, **run twice in full** for ROW 0b |
| Wall time | 777 s (13.0 min) per full run, ~26 min total for both determinism passes |

New code: `qa/rr-study/density-mech/density_mech.py`. Reused verbatim (HK-018): `f-nbr-a/{scene_render.py,
part_c.py}` (scene machinery, `_f_recovered`), `f-nbr-a/dll_common.py` (`extraction_time_offset_s`/
`SYMBOL_PERIOD_S` **only** — not its own stale DLL pin), `n1-extract-llrs-at-position/extract_llrs_ctypes.py`,
`r2-coherent-llr-instrument/ldpc_decode_ctypes.py`.

## 2. §1.3 — position mapping (deliverable 1's "write it down" requirement)

**`freq_hz`** passed to `ft8_extract_llrs_at` = `F`'s **tone-0 base frequency** — the exact value
`scene_render.py`'s `F_TRUE_FREQ_HZ`/`move_station_freq()` sets, and the same value passed as
`synth.encoder.encode_message`'s own `base_freq_hz`. `synth/modulator.py:153` documents this explicitly:
*"`base_freq_hz` is the audio frequency of tone 0; tone k sits at base + k × 6.25 Hz."* This is also the
convention `ft8_decode_all` itself reports (confirmed by the `B-pos-A`/`B-orig-A` precedent, both gated
arms: `b_pos_a_lattice_position.py` feeds `round(row["anchor_freq_hz"])` — `ft8_decode_all`'s own reported
frequency — straight into `ft8_extract_llrs_at` with no offset).

⚠️ **Named because it's a trap, not because it's settled:** the shim header's own doc comment
(`ft8_shim.h` ~line 1092) calls this parameter *"requested **centre** frequency, Hz."* Read literally
against an 8-tone span, that would mean `base + 3.5×6.25 = base + 21.875 Hz` — a different point entirely.
Every existing verbatim-reused harness (`B-pos-A`, `B-orig-A`, this one) treats it as tone-0 regardless,
and **ROW 0c is the mechanical proof**: it came back **100/100 in every primary cell**, not merely the
≥90% bar — if the mapping were off by 21.875 Hz or any other fixed offset, an unobstructed victim at its
nominal position would not decode anywhere near that reliably. The header's "centre" is native-side
shorthand for "the signal's reference audio frequency" (FT8/WSJT-X convention), not the tone-span
midpoint.

**`time_offset_s`** = `F`'s true `dt_s` (**0.0** in this scenario) **+ `SYMBOL_PERIOD_S` (0.16 s)** — the
**confirmed** `B-orig-A` finding (`2026-08-21-1412-…-b-orig-a.md`, ROW 1 FIRED): the waterfall index
`ft8_extract_llrs_at` reads runs exactly one FT8 symbol ahead of raw-PCM time. Reused verbatim via
`dll_common.extraction_time_offset_s()` — **not re-derived**. `time_offset_s` used throughout: **0.16 s**.

## 3. ROW 0 (strict order, either fires ⇒ STOP)

| row | predicate | result |
|---|---|---|
| **0a — binary** | SHA-256 = pin, shim = `20260051`, `max_iters`/`osd_depth` recorded, all three entry points present | **PASS.** Exact match; all exports confirmed |
| **0b — determinism** | two full runs ⇒ byte-identical results JSON, mechanically diffed | **PASS.** Diffed in code (`wall_time_s` excluded, the only field allowed to vary) — every other field, including every per-trial-derived rate and BER quartile across all 12 cells + ROW 0d, matched exactly between run 1 and run 2 |
| **0c — oracle can say YES** | `orc_0` ≥ 0.90 in every primary cell | **PASS, and not close: 100/100 in all 9 primary cells.** The position mapping is right |
| **0d — oracle can say NO** | `F` alone at −30 dB, `Δ=12`: `orc_0` ≤ 0.20 | **PASS.** `0/100`. No leakage |
| **0e — bench reproduces** | `prod` ≤ 0.20 in ≥ 6 of 9 primary cells | **PASS.** `7/9` excluded (the two survivors are `Δ=18.75, X=+1` at `94/100` and `Δ=6.25, X=+1` at `35/100` — both near the knife-edge, `Δ=12, X=+1` still excludes at `15/100`) |

**ROW 0 is silent.** ~~The primary reading stands.~~ 🛑 **CORRECTED: ROW 0 silence does NOT mean the
primary reading stands.** The Architect's §10.3 finding: ROW 0 proved the oracle can say YES (0c, E
removed) and NO (0d, −30 dB) — it never checked the oracle against production **with E present**, which
is the only condition the primary reading actually reads. That's the exact gap that voids §4 below.

## 4. ~~Primary — per-cell reads (7 excluded primary cells, only these are read)~~ 🛑 Data stands, "read" column and verdict VOID

The `prod`/`orc_E`/`orc_0`/BER-shift **numbers** below are correct and stand as measured. The **`read`
column and every M1 conclusion drawn from it are VOID** (Architect's §10 ruling, `1a7f9547`) — see the
correction below the table.

| Δ (Hz) | X (dB) | F (dB) | `prod` | `orc_E` | `orc_0` | BER shift median (E−0) | ~~read~~ |
|---:|---:|---:|---:|---:|---:|---:|:---:|
| 6.25 | +3 | −8 | 0/100 | **0/100** | 100/100 | 0.379 (66.0 bits) | ~~M1~~ VOID |
| 6.25 | +6 | −11 | 0/100 | **0/100** | 100/100 | 0.385 (67.0 bits) | ~~M1~~ VOID |
| 12.00 | +1 | −6 | 15/100 | **0/100** | 100/100 | 0.345 (60.0 bits) | ~~M1~~ VOID |
| 12.00 | +3 | −8 | 0/100 | **0/100** | 100/100 | 0.443 (77.0 bits) | ~~M1~~ VOID |
| 12.00 | +6 | −11 | 0/100 | **0/100** | 100/100 | 0.443 (77.0 bits) | ~~M1~~ VOID |
| 18.75 | +3 | −8 | 0/100 | **0/100** | 100/100 | 0.385 (67.0 bits) | ~~M1~~ VOID |
| 18.75 | +6 | −11 | 0/100 | **0/100** | 100/100 | 0.385 (67.0 bits) | ~~M1~~ VOID |

~~**Unanimous M1.** `orc_E` is **exactly 0/100 in all seven** — not merely under the `≤0.20` bar, but at
the floor. `orc_0` is **exactly 100/100 in all seven**, same seeds, same noise, only `E` removed. This is
the cleanest possible separation the design allows: the paired control confirms the extraction path and
LDPC settings are fully capable at this exact position; only `E`'s presence breaks it. Median BER shift
is **60–77 bits out of 174** — three to four times the spec's own 20-bit prediction bar (§8 #5).~~

~~**VERDICT: ROW 1 M1.** Per spec §7: this and D-001 limb 2 are the same work item. The business case is
**≈4.30 pp** (`DENSITY-LIVE`'s citable figure). `coherent_llr.c`'s ROW 0g is still uncleared, so this
result specifies **no remedy** — only that the defect and limb 2 are the same one.~~

🛑 **CORRECTED (post-hoc, Architect's §10 ruling, `1a7f9547`): the "Unanimous M1" reading above is VOID,
and I should have caught it before writing it — the falsifying data was already in my own §5 table.**
`orc_E` reads 0/100 in the 7 cells above, but `orc_E` **also** reads 0/100 in cells where `prod` succeeds
94–100/100 on the same audio (primary `Δ=18.75,X=+1`: `prod=94/100`; strong `Δ=12.0`/`Δ=18.75`:
`prod=100/100` both — see §5 below). The oracle's stated premise, "production's own extraction+LDPC at
the right spot," cannot fail 100/100 where production succeeds 100/100. So `orc_E=0` in the 7 excluded
cells is not proof the bits are corrupted *for production* — it's proof the oracle measured something
production doesn't actually do. Two candidate reasons (Architect §10.2, not yet distinguished):
production's own **two-pass** tile-suppression (`K_MAX_PASSES=2`, unmodelled by the oracle's single-pass
unsuppressed-waterfall extraction), and production extracting at **wherever its own candidate search
lands**, not necessarily `F`'s literal true position. **What DOES stand as fact (Architect §10.4):**
single-pass magnitude extraction at the victim's exact true position, on an unsuppressed waterfall, is
completely corrupted by a ≥1 dB-stronger neighbour within 18.75 Hz — 0/100 in every one of these 7 cells,
against 100/100 with the neighbour removed on the same noise. That is real and measured. **What it does
NOT establish is that this is what happens to F inside production**, which is the whole question this
arm was meant to answer. Amendment A1 (spec §10.5) is the follow-up that distinguishes the two
explanations; reported separately.

## 5. §4 — reporting only (gates nothing, changes no row)

**Strong-victim cells** (`F` +5 dB, `E` +8 dB, reporting only): `Δ=6.25` excludes (`prod=0/100`,
`orc_E=0/100`, `orc_0=100/100`); `Δ=12.00` and `Δ=18.75` do **not** exclude — `prod=100/100` both — yet
`orc_E=0/100` in both of those too. 🛑 **This is the exact contradiction the Architect's §10 ruling
caught, and it was sitting right here, unsurfaced, when I first wrote this section**: I reported
`prod=100/100` prose and left `orc_E` out of the sentence. Production decodes `F` from this audio every
single time at `Δ=12`/`Δ=18.75`; the oracle at `F`'s textbook true position decodes it *never*. That is
not "reads M1 by the same predicate" (my original wording, struck) — it is proof the oracle isn't
measuring production's own path. See the correction in §4 above.

**BER shift, all 12 cells:** every cell — excluded or not, primary or strong — shows a substantial
positive median shift (0.30–0.44, i.e. 53–77 bits) when `E` is present vs the paired removed-`E` control,
including the two primary cells that still decode in production most of the time (`Δ=18.75,X=+1`:
0.305/53 bits, `prod=94/100`; `Δ=6.25,X=+1`: 0.316/55 bits, `prod=35/100`) and the two strong cells that
decode in production **every** time (`Δ=12.00`/`Δ=18.75`, `prod=100/100` both). ~~The corruption is
present even where production still recovers the victim most of the time — consistent with a real but
sometimes-survivable bit-level effect, not a binary switch.~~ 🛑 **CORRECTED: this framing undersold what
the numbers show.** It isn't "sometimes survivable" — `orc_E` is 0/100 in *every* cell including the ones
where production recovers `F` 100% of the time. The BER-shift figures are real facts about single-pass
extraction at the true position (§10.4), but "survivable" implies the oracle and production are on the
same path, which the data now say they are not.

**Codeword-position BER** (payload/CRC/parity split, computed for the 7 M1 cells per spec §4 item 4):

| Δ,X | payload BER (n=77) | CRC BER (n=14) | parity BER (n=83) |
|---|---:|---:|---:|
| 6.25,+3 | 0.360 | 0.170 | 0.432 |
| 6.25,+6 | 0.366 | 0.214 | 0.434 |
| 12.00,+1 | 0.328 | 0.319 | 0.367 |
| 12.00,+3 | 0.437 | 0.428 | 0.442 |
| 12.00,+6 | 0.443 | 0.429 | 0.446 |
| 18.75,+3 | 0.383 | 0.500 | 0.358 |
| 18.75,+6 | 0.390 | 0.500 | 0.361 |

**No consistent regional concentration** — payload and parity BER sit within a few points of each other
in every cell; CRC (only 14 bits) is noisier and ranges wider (0.17–0.50) but shows no systematic
direction. The corruption looks roughly uniform across the codeword, not localised to one region.
Descriptive only, per spec.

## 6. What this can't see (spec §5, checked, not re-litigated)

One scene, one interferer, synthetic AWGN (§5.1) — this is a statement about **this** geometry. An `M2`
would not say *where* upstream the loss occurs (§5.2) — moot here since the read is `M1`. An `M1` does
not mean every extraction change would help (§5.3) — it means the magnitude-only single-symbol metric is
corrupted at the true position, the premise of limb 2, not proof of its remedy. No live data was read
(§5.4) — `DENSITY-LIVE`'s clearance was for one live test and was not reused here.

## 7. Predictions (spec §8) — reported, not self-scored

| # | prediction | called | actual |
|---|---|---:|---|
| — | Mechanism reads M2 (carried, scored elsewhere) | 0.60 | **M1** |
| 1 | ROW 0 silent | 0.75 | **silent** |
| 2 | ROW 1 (M1), given ROW 0 silent | 0.35 | **ROW 1 M1** |
| 3 | ROW 2 (M2), given ROW 0 silent | 0.25 | did not occur |
| 4 | ROW 3 (MIXED), given ROW 0 silent | 0.40 | did not occur |
| 5 | Paired BER shift at `Δ=6.25, X=+3` median ≥ 20 bits | 0.65 | **66.0 bits — clears the bar by >3×** |

~~Flagging plainly: the carried, previously-scored prediction (0.60 on M2) was wrong; the freshly-reasoned
`#2` (0.35 on M1, written the same session after re-examining the physics — spec §8's own note that `E`'s
tones land directly in 6–7 of `F`'s 8 tone bins) was right, at low confidence. Worth a line in the ledger:
this is the HYPOTHESISED-mechanism class the ledger already flags as biased, and here the position moved
in the right direction (toward M1) between the carried figure and the fresh one, even though the fresh
one still called it a minority outcome.~~

🛑 **WITHDRAWN (Architect's §10.6 ruling, `1a7f9547`): "#2 called it right" is retracted along with the
verdict.** Per the ruling: **all `DENSITY-MECH` §8 predictions are UNSCORED, arm void** (the ledger's own
`E4-STAGE2` precedent for a void row). The carried assessment §8 #2 (M2 @ 0.60) **stays open**, not
resolved either way. I should not have scored a prediction against a verdict I hadn't yet cross-checked
against the arm's own falsifying data.

## 8. NFR-021

Scene stations are Q-prefix synthetic throughout (`Q1ABC Q1AW RR73`, etc., per `s8hn-band-scene-highn.json`).
The classifier/harness never prints message text; `oracle_trial()` and `codeword_position_ber()` work
entirely in bit/rate space. `scan()`/`classify()` (`qa/rr-study/nfr021_pre_merge_scan.py`) run clean
against `density_mech.py`, `results/density_mech_result.json`, and this report.

## 9. ~~Where this leaves the arm (spec §7)~~ 🛑 VOID — superseded by §10 below

~~**ROW 1 (M1) → Architect/Captain: whether to reopen D-001 limb 2, with ≈4.30 pp as its business case.**
Per spec, the first question is clearing `coherent_llr.c`'s ROW 0g — **no fix is specced from this arm**,
and none is implied here. `ft8_coherent_llr_at` was not touched anywhere in this run.~~

🛑 **CORRECTED: no route is authorised by this arm.** The verdict this section pointed to is void
(§4/§10). `ft8_coherent_llr_at` genuinely was never touched, and that much stands. Everything else in
this section assumed a verdict that turned out not to survive cross-checking against `prod`.

## 10. 🛑 VOID — Architect's acceptance ruling

**Architect, 2026-09-18T14:36Z, spec §10, `arch/density` `1a7f9547`.** Verdict: **VOID**. `orc_E` reads
0/100 in cells where `prod` reads 94–100/100 on the same audio (primary `Δ=18.75,X=+1`; strong
`Δ=12.0`/`Δ=18.75`) — the oracle's own premise cannot survive that. Design gap (§10.3, logged against the
spec, not the run): ROW 0 proved the oracle can say YES (E removed) and NO (−30 dB) but never checked it
against production **with E present**, the only condition the arm reads. What stands as fact (§10.4):
single-pass magnitude extraction at `F`'s exact true position on an *unsuppressed* waterfall is fully
corrupted by a ≥1 dB-stronger neighbour ≤18.75 Hz away — 0/100 vs 100/100 with the neighbour removed,
same noise. What is **not** established: M1, M2, or which production stage recovers `F` where it is
recovered. `DENSITY-LIVE`'s ≈4.30 pp is unaffected — that arm is about *whether* the loss happens, this
one about *where*, and *where* is now open again.

**Amendment A1** (spec §10.5) is dispatched and reported separately: same harness/seeds/binary, disables
pass 1 via `ft8_set_decode_params`, reads `F`'s production-reported position, and re-runs the oracle
*there* instead of at the textbook true position. Carries no M1/M2 verdict itself — it decides which of
two mechanisms (a displaced candidate vs pass-1 recovery) explains cells where production succeeds.

## 11. Artefacts

Committed by path (HK-014/HK-033 — **not pushed**, Captain's go needed): `qa/rr-study/density-mech/`
(`density_mech.py`, `results/density_mech_result.json`), this report. Branch: `qa/e4-bench`. No `src/`/
`native/` change. No station time, no new capture — pure offline synthetic re-analysis on the existing
`F-NBR-A` scene.
