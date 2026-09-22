# `LIVE-GAP-MAP` — result: **Amendment 3 applied, verdict M1** — `CI_lo(H10) = 18.586 ≥ 10.0`; cut-corpus `R_wild 59.90%`, `H10 19.27 pp`; full-corpus sensitivity lands on the same `M1` row

**2026-09-22T17:3xZ update — supersedes the headline below.** The Captain ruled C3 is not voided (Amendment
3, `arch/live-gap-map` `c1c59c65`): cut the 23:00–00:15Z episode, re-read the gate on the rest. See **§0**
for the full re-run. §1–§9 below are preserved as originally written (the VOID finding that triggered the
ruling) except where §0 marks a correction; the verdict now in force is **M1**, not VOID.

QA, 2026-09-22T17:20:34Z (`date -u`, HK-017). Per spec
`qa/rr-study/2026-09-21-1555-architect-to-qa-spec-live-gap-map-24h-20m.md` (`arch/live-gap-map`,
Amendments 1–2), armed 2026-09-21 16:24Z (Captain: *"openwsfz is yours to setup and start on port
8080… ensure the run continues unattended"*), window closed 2026-09-22 16:28:15Z, harness ran at
teardown, exit 0.

**Headline.** `ROW 0g` (power) **passes** with headroom to spare: `n_ref = 128,171` against a
40,000 floor. `ROW 0e′(iii)` (the WSJT-X-alive check) **fails** in one UTC hour
(`2026-09-21 23:00`, worst-hour share `0.9625` against a `0.99` bar), which per spec §3.2 **VOIDs
every `§3.6` row — no M1–M4 reading may be taken from this corpus.** This is not the power failure
the spec anticipated as the alternate VOID route (`0g`→M4); it is a data-quality gate, and QA
traced its cause before writing this up (§4). `D1`, the descriptive current live figure, needs no
row and is reported in full (§5) — **`R_wild = 59.90%`** (`R_base = 58.67%`), **`H10 = 19.21 pp`**
CI95 `[18.51, 19.90]`, `n_ref = 128,171` — citable only with its full qualifiers (§1), and **never
compared with `A1` (61.09%, 2026-09-08/09) as a build effect**: 13 days apart, different
propagation, density and band conditions, per the spec's own standing guard (§3.3).

---

## 0. Amendment 3 result (2026-09-22T17:39:04Z, `date -u`) — cut applied, gate re-read, verdict **M1**

**Ruling, verbatim reference:** `qa/rr-study/2026-09-21-1555-architect-to-qa-spec-live-gap-map-24h-20m.md`
§3.9, committed `arch/live-gap-map` `c1c59c65`. Cut window `2026-09-21T23:00:00Z ≤ cycle start <
2026-09-22T00:15:00Z` (the whole failing hour plus the episode's tail), removed cycles count on neither
side. Put in the harness as code (`AMD3_EXCLUDE`, `lgm_harness.py`), not hand-filtered; new
`harness_sha256 = bc07e6c0…00c626`. Run order per spec: (1) 0e′(i)–(iii) on included cycles, bars
unchanged; (2) §3.6 M-row on included cycles; (3) sensitivity — full-corpus `CI(H10)` beside the cut
figure, not a row; (4) D1–D7 on included cycles, full-corpus D1 requoted, removed `n_ref` stated.

**(1) ROW 0e′ on the cut cycles — all three pass:**

| check | cut result |
|---|---|
| **(i)** archive share | **PASS.** `0.99982` (numerator and denominator both drop the 300 cut cycles, same convention as the 19:05:00Z swap) |
| **(ii)** OWS decoded | **PASS.** `1.0000` (4,575 rich cycles, 0 misses) |
| **(iii)** WSJT-X alive | **PASS.** Worst checked-hour share now `1.0000` (the 23:00Z hour — the only failing hour — is removed in full: 240 of its 300 cut cycles were that hour, so it no longer exists to check; 20 hours qualify for the check post-cut, down from 21) |

**(2) §3.6 M-row on the cut cycles: `M1`.** `CI_lo(H10) = 18.586 ≥ 10.0` bar. `n_ref = 127,482` (**ROW
0g** still passes by over 3×, bar 40,000). `R_wild = 59.9026%`, `H10 = 19.2686` pp, CI95 `[18.586,
19.967]` (bootstrap N=2000, seed 20260921, 2,803 distinct frequencies, 5,459 included cycles).

**(3) Sensitivity (reported, not a row):** the full (uncut) corpus, same code path and seed, run fresh in
the same invocation: `H10` CI95 `[18.509, 19.902]`, which is also `≥ 10.0` → **also `M1`.** **The cut does
not decide the verdict** — both the cut and the full corpus land on `M1`, confirming the disclosure in
Amendment 3 ("very unlikely to change the M-row... if it does, the report must say so first"). It did not.

**(4) D1–D7 on the cut cycles**, qualifiers unchanged from §5's original D1:

| figure | cut (included cycles) | full corpus (requoted from §5 below) |
|---|---|---|
| `R_wild` | 59.9026% CI95 `[58.792, 61.022]` | 59.8997% CI95 `[58.838, 61.020]` |
| `H10` | 19.2686 pp CI95 `[18.586, 19.967]` | 19.2095 pp CI95 `[18.509, 19.902]` |
| `n_ref` | 127,482 | 128,171 |
| `R_base` | 58.6695% | 58.6708% |
| misses | 51,117 | 51,397 |
| strong misses | 24,564 | 24,621 |
| included cycles | 5,459 | 5,759 |

**Removed by the cut:** 300 cycles, **689 REF rows** (0.54% of the full-corpus `n_ref`) — small enough that
neither figure above moves meaningfully, consistent with the sensitivity result in (3).

**D2 (eight-band SNR), D3 (frequency bands), D4 (cycle-load quintiles), D6 (uncorroborated), D7 (exposure
split)** on the cut cycles are in `results/lgm_result_amendment3.json` in full; headline moves are all
sub-percentage-point versus the full-corpus figures in §5 (e.g. D7: `H10` splits `7.544` pp EXPOSED /
`11.725` pp not-EXPOSED, cut, vs `7.51`/`11.70` full corpus) and change no reading.

**Two corrections to §4 below, per the Captain's ruling** (§4's episode-identification finding is not
disturbed — only these two claims are struck):
- The ~2800–3000 Hz edge described as "the receiver's own anti-alias filter" is **wrong**: at 12 kHz
  sampling, Nyquist is 6 kHz. It is the radio's IF filter. Struck at §4, second bullet.
- The full-run scan's 189-cycle (13.1% of night-window) signature is **not the same population** as the 9
  `0e′(iii)`-failing cycles, and must not be presented as *the cause* of the failure — it is a related
  spectral signature, not a demonstrated match. Struck at §4, third and fourth bullets ("this does not
  rescue the VOID" sentence stands; the 13.1% figure itself is not retracted, only its causal framing).

**§6 prediction inputs, updated** (verdict is no longer VOID): `L3` (M1 fires) now reads **HIT** on its own
terms — no longer "does not apply". `L4` (M2 fires) reads **MISS** — M1 fired, not M2. `L1`/`L5` unchanged
(both HIT). Scoring remains the Architect's, not mine (§6's own convention).

**§9 superseded:** the fork reported there is resolved by Amendment 3 for C3 — no re-arm is needed, and
decision (1) (re-arm) does not apply. Decision (2) (amend `0e′(iii)` for **future** runs, not C3) still
stands exactly as the spec states it (score only cycles where OWS itself decoded ≥1 within ±1); still
flagged, not built — that remains the Architect's or Captain's call, per HK-025.

---

## 1. HK-020 — critical config, and what `REPORT_MUST_SAY.md` requires disclosed here

**C3's OpenWSFZ leg is a separately published binary with a config copy, not the Captain's station
daemon.** `D1` is "what the operator sees" for the **decode path only** — decoding parameters,
audio device, noise suppression are identical to the station's saved config; nine non-decode-
affecting keys differ (network exposure, PTT method receive-only, log/archive paths and retention).
Full nine-key table: `artefacts/20260921_1624_live_run-live-gap-map/REPORT_MUST_SAY.md`. The
station's own usual build is unknown — its daemon was not running at arm time, so this could only
be checked against the run binary.

| config | value |
|---|---|
| Corpus | `artefacts/20260921_1624_live_run-live-gap-map/` (gitignored, NFR-021; `openwsfz/ALL.TXT`, `wsjtx-1-ft991a/ALL.TXT`, `cycle-audio/`, `row0.json`, `results/lgm_result.json`) |
| Window | `2026-09-21T16:28:15Z → 2026-09-22T16:28:15Z`, 24 h wall clock, one radio (Yaesu FT-991A) feeding both decoders on `Voicemeeter Out B1` |
| Build | `decoding_improvement` `84cac119` (contains `fa8a56ae`), `libft8.dll` SHA-256 `38a21f840b00af146348c166786cb54e178cd2201c5ed4dba3016a4c589a1cba`, shim `20260054`, product version `0.50+84cac119`, `nhard` 40, suppression triple default `(−5,+15,1)` |
| REF | WSJT-X 2.7.0 (`b4f9a4`), profile `- FT991A`, `NDepth=3`, no AP bit, `A`-only |
| Harness | `qa/rr-study/live-gap-map/lgm_harness.py`, committed `1ff42da9` (`qa/live-gap-map`) before any C3 datum; installed byte-identical into `<corpus>/tools/` (sha256 `afa2b597…`), which is the copy the supervisor actually ran |
| Supervisor incident | one swap at `19:05:13Z` (a flashing-console bug in the supervisor's own health-loop subprocess calls, fixed same session, `3e1701f3`); cost exactly one 15-second cycle (`19:05:00Z`), dropped from both sides' counts, not scored as a miss. No other restarts. Teardown clean, zero orphan daemon processes |

## 2. ROW 0 (strict order, per spec §3.2)

| row | check | result |
|---|---|---|
| **0a** identity | loaded-DLL SHA-256 == pin, shim == `20260054` | **PASS.** `38a21f84…1cba`, shim `20260054`, product `0.50+84cac119…` |
| **0b** params | `osd_nhard_max == 40`, suppression triple == default `(−5,+15,1)` | **PASS**, both equal to the read-out's own default |
| **0c** one audio stream | daemon and WSJT-X name the **same** endpoint, `captureActive` true | **PASS.** Both `Voicemeeter Out B1 (VB-Audio Voicemeeter VAIO)`; device ID `{0.0.1.00000000}.{8dbb88e8…}` on our side (WSJT-X's `.ini` stores no device ID, name only); `SoundInChan` absent (WSJT-X default) |
| **0d** reference depth | `NDepth=3`, no AP bit, dial `14074000` | **PASS** |
| **0e′(i)** archive coverage | archived WAV / wall-clock cycles ≥ 0.99, plus `captureActive` at arm | **PASS.** `0.9998` |
| **0e′(ii)** OWS decoded | of cycles with ≥5 REF rows, share with ≥1 OWS decode ≥ 0.99 | **PASS.** `1.0000` (4,614 rich cycles, 0 misses) |
| **0e′(iii)** WSJT-X alive | per UTC hour with ≥240 OWS decodes, share of cycles with a REF row within ±1 ≥ 0.99 | **FAIL.** Worst hour `2026-09-21 23:00`, share `0.9625` (9 of 240 cycles miss). 21 of 24 hours qualified for the check (3 excluded, <240 OWS decodes/hour); 457 of 128,171 REF rows (0.36%) sit in the 3 unchecked hours |
| **0f** matcher | pointed at C2, reproduces `n_ref` 91,046 / `R_wild` 61.09 / `H10` 17.96 exactly | **PASS, exact.** `91046` / `61.0856%` (61.09) / `17.9634` (17.96); 35,430 misses, 16,355 strong, all 8 band-row counts match |
| **0g** power | `n_ref(C3) ≥ 40,000` | **PASS**, by over 3×. `n_ref = 128,171` |

**All 0a–0d and 0f–0g pass; 0e′ fails on (iii) alone.** Per the spec's own table: "any of (i)–(iii)
fails ⇒ all §3.6 rows VOID; report the gaps."

## 3. Consequence of 0e′(iii)'s failure (spec §3.2, applied exactly as written)

`§3.6`'s M1/M2/M3/M4 gate does not run. No `CI_lo(H10)`/`CI_hi(H10)` reading may be cited as "the
strong-miss pool is still large" or "has closed" — that routing decision is undetermined on this
corpus. `D1`–`D7` are `§3.4` descriptive figures, a separate section that the spec says to report
"every one" regardless of VOID (§5 below), and `D1` still replaces nothing about `A1` — it is read
from live logs and needs no row, but it is not compared to `A1` as a build effect either (§3.3).

## 4. Diagnosis: an interference episode, not a closing band alone

Traced the nine `0e′(iii)`-failing cycles to the sample, then scanned the full 24 h for the same
signature. Full detail, spectrograms and an interactive timeline: published artifact
`https://claude.ai/artifact/T7pRfvXhmvpb3qK3KPgzvo` (private, share on request) and
`qa/endurance/2026-09-21-84cac119/session_log.md` §3. Summary:

- **Five of the nine cycles are genuine propagation silence** — RMS 9–42, matching the
  fully-established `01:00–02:00Z` dead-hour baseline exactly.
- **Four are not.** RMS 750–950, indistinguishable from a normal busy cycle, yet zero decodes on
  both sides. Welch PSD + STFT show a flat, structureless floor filling the entire 0–2800 Hz FT8
  passband edge-to-edge, cut sharply at ~~the receiver's own anti-alias filter~~ **[CORRECTED per
  Amendment 3, §0 above: this is the radio's IF filter, not anti-alias — at 12 kHz sampling Nyquist is
  6 kHz, nowhere near 2800–3000 Hz]** — not a discrete tone, not a legible carrier. `clipped_samples` is
  zero across every one of the 5,778 archived cycles in the full 24 h, so whatever raised the floor
  stayed inside the receiver's linear range throughout.
- **Full-run scan** (floor > 20 dB and peak−floor contrast < 10 dB, calibrated from the four traced
  cycles, all 5,778 archived cycles): zero hits in 4,338 day/evening cycles; **189 of 1,440
  night-window cycles (13.1%)**, concentrated — dense `23:20–00:05Z`, tapering out by
  `00:10–00:15Z`, then **genuinely clean `00:15–03:30Z`** (over 3 hours, floor back to −30 to
  −45 dB, the true-silence signature), with a few small blips `03:45–04:00Z` as the band reopens.
  **[FLAGGED per Amendment 3, §0 above: this 189-cycle population is a related spectral signature over
  the full run, not a demonstrated match to the 9 `0e′(iii)`-failing cycles specifically — the 13.1%
  figure itself stands, but do not present it as the cause of the 9-cycle failure.]**
- ~~**Reading**: the bounded shape — abrupt onset, a ~70-minute episode, a clean stop — is offered as
  a hypothesis, not asserted as mechanism (same discipline as `LIVE-GAP-NOW`'s §4 correction):
  consistent with something local having a start and an end (a transmission, a device on a
  schedule), and not consistent with grey-line enhancement (which strengthens discrete signals
  gradually over tens of minutes, not this). Physical cause not identified from audio alone.~~
  **[STRUCK per Amendment 3, §0 above: this reading leaned on the 189-cycle scan as if it explained the
  9 failing cycles, which the ruling rejects as a population match. The four traced cycles' own spectral
  description (previous bullet, as corrected) stands; no causal reading beyond that is asserted.]**

**This does not rescue the VOID.** `0e′(iii)` does not distinguish a closed band from a masked
one — either way REF produced nothing usable in that stretch, and VOID is the correct,
pre-registered response regardless of which one caused it.

## 5. Descriptive, no row (spec §3.4, reported in full per the VOID instruction)

**D1 — the new live figure**, qualifiers: binary `38a21f84…1cba` / shim `20260054` /
`decoding_improvement` `fa8a56ae` or its docs-only descendant `84cac119`, `nhard` 40, 20 m
(14.074 MHz), REF = WSJT-X FT991A alone, one radio and one audio stream, window
`2026-09-21T16:28:15Z → 2026-09-22T16:28:15Z`, 5,759 included cycles.

`R_wild = 59.8997%` CI95 `[58.838, 61.020]`, `R_base = 58.6708%`, `n_ref = 128,171`, misses
51,397, strong misses (`H10` pool) 24,621, `H10 = 19.2095` pp CI95 `[18.509, 19.902]` (bootstrap
N=2000, 2,803 distinct frequencies, seed 20260921). **Never compared with `A1` as a build effect.**

**D2 — eight-band SNR table** (E4 §0.2's columns, same format as C2's for side-by-side reading):

| band | ref rows | `R_wild` | misses | % of all misses |
|---|---:|---:|---:|---:|
| ≤ −21 | 7,995 | 22.71% | 6,179 | 12.02% |
| −20..−16 | 13,423 | 30.75% | 9,295 | 18.08% |
| −15..−11 | 19,484 | 41.99% | 11,302 | 21.99% |
| −10..−6 | 21,578 | 53.33% | 10,071 | 19.59% |
| −5..−1 | 19,850 | 64.81% | 6,986 | 13.59% |
| 0..+4 | 16,436 | 75.40% | 4,044 | 7.87% |
| +5..+9 | 12,164 | 83.73% | 1,979 | 3.85% |
| ≥ +10 | 17,241 | 91.06% | 1,541 | 3.00% |

**D3 — frequency bands (Hz):**

| band | ref rows | `R_wild` | misses |
|---|---:|---:|---:|
| < 200 | 774 | 65.89% | 264 |
| 200–3000 | 127,385 | 59.86% | 51,126 |
| > 3000 | 12 | 41.67% | 7 |

**D4 — recovery by cycle load** (quintiles fixed on C3's own REF-rows-per-cycle, over cycles with
≥1 REF row; edges 19/25/30/35 rows/cycle — a cycle-count axis, not spectral locality):

| quintile | ref rows | `R_wild` | strong misses, pp of `n_ref` |
|---|---:|---:|---:|
| 1 (quietest) | 8,961 | 67.77% | 0.828 |
| 2 | 19,644 | 66.16% | 2.323 |
| 3 | 27,209 | 63.05% | 3.856 |
| 4 | 33,007 | 58.57% | 5.337 |
| 5 (busiest) | 39,350 | 53.92% | 6.865 |

**D5 — recovery by UTC hour**: full table in `results/lgm_result.json`. The two lowest-`n_ref`
hours (`2026-09-22 01`, 2 rows; `2026-09-22 03`, 229 rows) sit either side of the §4 interference
episode and the genuine dead patch — read alongside §4, not independently.

**D6 — uncorroborated, not false**: OpenWSFZ's own live decodes in-window: 77,630. Uncorroborated
by REF: 866 (1.1%) — counts only, not a false-positive rate (FP citation guards §0).

**D7 — strong misses by nearby-signal exposure** (Captain's Q1 = YES, this arm only, descriptive,
gates nothing, licenses no further live stratification; `DENSITY-LIVE` classifier unchanged, TEST =
this corpus's own live log): of 87,269 rows at REF SNR ≥ −10, 10,197 (11.7%) are `EXPOSED`. `H10`
splits `7.51` pp `EXPOSED` / `11.70` pp not-`EXPOSED` (total `19.21` pp). Miss rate within each
population: `EXPOSED` 94.34%, not-`EXPOSED` 19.46%.

## 6. Architect's blind predictions (spec §4) — inputs handed over, scoring is yours

| # | prediction | input |
|---|---|---|
| L1 | ROW 0f reproduces C2 exactly | **HIT.** §2 above, exact to the figures pre-registered |
| L2 | ROW 0 (0a–0f) passes at arm time without a Captain routing change | 0a–0d passed at arm time without incident; 0e′(iii) and 0g are necessarily read only after the window closes, so this is yours to score against what "at arm time" was meant to cover |
| L3 | M1 fires | **Does not apply as literally predicted** — the verdict is VOID, not M1, so this reads as a miss on its own terms regardless of what the raw `H10` CI (`[18.509, 19.902]`, entirely above the 10 pp bar) would have shown had 0e′ passed. Reported as `prediction_inputs_Architect` in `lgm_result.json`, not self-scored here |
| L4 | M2 fires | Same basis — does not apply, verdict is VOID |
| L5 | D1's `R_wild` lies in `[57.0, 65.0]` % | **HIT.** `59.90%` |

## 7. Endurance-session ANOVA (comparability, per your standing 2026-07-27 instruction)

Full package: `qa/endurance/2026-09-21-84cac119/` (`anova_report_20m.md`/`.html` + charts,
`session_log.md`) — not duplicated here. Headline: grid-alignment gate **passed clean** on both
sides (`G=1.0000`), no cycle-clock drift on this build, so a straight pooled table (unlike the
2026-08-02 run's `8080` leg, which needed grid-snapping). 76,961 matched pairs; SNR means −2.575 dB
(ours) vs 0.088 dB (WSJT-X); DT 0.938 s vs 0.284 s — notably wider apart than the 2026-08-02
comparator's 0.322 s/0.213 s, flagged, not interpreted; frequency offset negligible as in every
prior session.

## 8. NFR-021

`openwsfz/ALL.TXT`, `wsjtx-1-ft991a/ALL.TXT` and `cycle-audio/` carry real third-party callsigns
and stay in the gitignored corpus directory. This report, both `lgm_result*.json` files,
`session_log.md` and `anova_report_20m.md`/`.html` carry counts, rates, frequencies, SNRs and
audio-derived power measures only — no message text or callsign appears anywhere in any of them
(this includes the Amendment 3 §0 additions and the §4 correction markers). `scan()`/`classify()`
(imported directly, not via `main()`'s git-diff-against-main path, since this file is/was
uncommitted — HK-018/MEMORY guard) run clean against this file, both harness output JSONs, and the
endurance-directory files.

## 9. Where this leaves the arm (spec §3.7) — **SUPERSEDED, see §0**

As originally written, before Amendment 3. VOID's consequence, per spec: every figure is reported (§5, done), nothing is re-based, and no
localisation arm or sensitivity-route decision is triggered — that's what M1/M2 would have opened,
and neither ran. `D1` stands as the current live figure, with its qualifiers, needing no row of its
own but licensing no comparison against `A1` either. Two decisions are yours, not mine:

1. **Re-arm a fresh 24 h capture** for a clean (non-VOID) M1–M4 reading — the supervisor's
   flashing-console bug is fixed and no other defect is outstanding, so a re-run would not need the
   same excuses.
2. **Amend `0e′(iii)`** before any such re-run: it currently can't tell "REF silent while OWS
   active" apart from "both silent" within its hourly window, which is how a genuine interference
   episode and a genuine propagation gap both trip the same check. A candidate refinement (score
   only cycles where OWS *itself* decoded something in the ±1 window) is flagged, not built.

I am not proposing which of these to do — reporting the fork, not resolving it (HK-025's own
"I report the fork, I do not resolve it" convention, `LIVE-GAP-NOW` §8).

## 10. Artefacts

Corpus: `artefacts/20260921_1624_live_run-live-gap-map/` (gitignored, ~real callsigns, `HANDOFF.md`
+ `results/lgm_result.json` [original, uncut] + `results/lgm_result_amendment3.json` [Amendment 3 cut
run, includes the full-corpus sensitivity block] + `results/lgm_stdout.txt` are the harness's own
record). Harness: `qa/rr-study/live-gap-map/lgm_harness.py`, Amendment 3 cut added this session
(`harness_sha256 bc07e6c0…00c626`), committed separately from this report (docs+tooling, no `src/` or
`native/` diff). Committed to this report: this file, `qa/endurance/2026-09-21-84cac119/*`. Branch:
`qa/live-gap-map` (`1ff42da9`, `3e1701f3`, plus the harness Amendment 3 commit, this report and the
endurance directory). **Not pushed** (HK-033) — Captain's go needed for push/PR; nothing merged.
