# N2 escalation — ROW 0b fires after a real, fixed alignment bug; harness cannot arm the gate

**QA → Architect** · 2026-08-16 14:59Z · branch `qa/n1-ber-results`
**Spec:** `qa/rr-study/2026-08-16-1408-architect-to-qa-N2-coherent-llr-extractor-spec.md`
**Harness:** `qa/rr-study/n2-coherent-llr-extractor/` (`coherent_extract.py`, `n2_stats.py`,
`sign_unit_test.py`, `run_n2.py`), results in `results/`.

---

## 0. Outcome, up front

**ROW 0b fires. The main population (ROW 1/2/3/4) was never run — the gate stops at the
first row that fires, per spec §6, and does not resume once a precondition fails.** This
is an escalation report, not a results report, per ROW 0b's own pre-written consequence
("Harness invalid, NO VERDICT. QA fixes and re-runs") and its HK-025 classification
(§6.2: **VALIDITY**, not waivable by QA).

Between the first arming attempt and this report, QA found and fixed a **real, well-
diagnosed alignment bug** that took V1's control-population median BER from **48.28%**
(chance-level — the harness was reading essentially random data) down to **5.75%** — a
large, legitimate improvement, fully explained and reproducible. It still sits **0.75 pp
above the pre-registered 5% ROW 0b bound**. QA does not have a further legitimate fix to
try that stays inside the spec's own scope discipline (§9): the remaining gap looks like
a property of the spec's own prescribed rectangular-per-symbol design meeting real-world
frequency imprecision, not a residual implementation bug — see §4.

## 1. Mandatory sign unit test — PASSED, run first, harness refuses to arm without it

`sign_unit_test.py` (N2's own file — a same-named sibling exists in
`n1-ber-at-refined-position/`; `run_n2.py`'s `sys.path` is ordered so N2's own file
resolves first, documented at the insertion point): synthetic rows gave
`d_ber = +1.000000` / `-1.000000` exactly, CI entirely on the correct side of zero both
ways, `f_cross` correctly one-directional. `run_n2.py` calls this first and refuses to
arm on failure (it did not fail).

## 2. ROW 0a — synthetic noiseless round-trip: clear, first try, both before and after the fix

Python-only (no DLL, no WAV corpus): a known message (NFR-021 Q-prefix synthetic
callsign) rendered via `qa/rr-study/synth`'s clean-room modulator at a known
`(freq_hz, dt_s)`, extracted with V3, hard-decision BER checked against the exact tones
that PCM was rendered from (`coherent_extract.true_bits_from_tones` — deliberately NOT
the native encoder's tones, so this check never depends on the native and Python
encoders agreeing bit-for-bit, a separate, already-flagged, unrelated concern).
**V1/V2/V3 all read exactly 0.00% BER.**

**This is an important negative result in its own right, reported per HK-018/HK-021
discipline: ROW 0a passing does NOT validate alignment against the real C decoder.** It
only proves `coherent_extract.py`'s downconvert/correlate/Gray-LLR math is internally
self-consistent with `qa/rr-study/synth/modulator.py`'s own placement convention
(`start_sample = round(dt_s * fs)`) — a convention ROW 0a's synthetic PCM was placed
under directly, bypassing the real C waterfall's own addressing entirely. It cannot and
did not catch the bug in §3/§4 below. Recorded here so a future arm does not repeat the
same false confidence from a passing ROW 0a.

## 3. ROW 0b, first attempt — FIRES at chance level (V1 median BER 48.28%)

On the matched-hit control population (`build_matched_hit_control()`, reused from N1
unmodified), first arming: `median_ber_v0 = 2.87%` (exact match to the pre-registered
target — V0/`ft8_extract_llrs_at` is correctly wired, as N1 already established) but
`median_ber_v1 = 48.28%` — indistinguishable from the 1/8-chance floor for an 8-tone
symbol. This is the sharp, VALIDITY-classified failure mode the spec's own §6.0 table
predicts almost verbatim: *"a one-symbol time-origin error reads as ~50% BER, not
'slightly worse' — this row is sharp by construction."*

## 4. Root-cause diagnosis and fix — a one-symbol-period time-origin error

**Diagnosis method (HK-018: measure, don't re-derive from memory of the source when a
direct check is available).** The production waterfall's own block-to-sample mapping
(`monitor.c`'s overlapped, Hann-windowed STFT feeding `ft8_extract_likelihood`'s
`block = cand->time_offset + sym_idx` addressing) is genuinely intricate — a first-
principles re-derivation from `monitor.c`/`ft8_shim.c` produced a plausible-looking but
ultimately WRONG half-symbol correction hypothesis, and the code that originally wrote
`candidate_diag.csv`'s `dt` column (`ft8_get_last_candidate_diag`) is no longer present
in the current `ft8_shim.c` to check directly (it predates this branch's shim versions).
Re-deriving the exact windowing convention by hand was unreliable — QA switched to
**empirical calibration against the already-validated V0 extractor**, exactly per ROW
0b's own stated remedy ("QA fixes and re-runs"):

1. **Aggregate confidence-score sweep** (sign-weighted `|LLR|`, summed across 53–72
   control rows simultaneously — a single row is too noisy, per-row peaks were unstable
   across a ±150-sample range): a clean, single, unimodal peak near **-333 decimated
   (2000 Hz) samples**.
2. **Direct per-symbol tone-detection accuracy** (bypassing Gray-bit LLR formation
   entirely — argmax tone vs. the true transmitted tone, from `ft8_encode_message`, at
   every raw symbol position, all 79×72 symbol-row pairs): a smooth, symmetric,
   single-peaked function of the trial offset. Peak: **exactly -320 decimated samples,
   80.5% symbol accuracy**, falling to the 1/8 = 12.5% chance floor by ±600 samples —
   the textbook shape of a rectangular per-symbol window sliding across a symbol
   boundary. Unambiguous evidence of a real, fixable bug, not sensor noise.

**-320 decimated samples = -1920 raw (12 kHz) samples = exactly -1×`SYMBOL_PERIOD_S`
(0.16 s).** QA adopted this exact, clean, principled constant (diagnostic (2), not the
noisier curve-fit (1)) rather than a hand-tuned magic number.

**Fix applied** (`coherent_extract.py`, `TIME_ORIGIN_CORRECTION_SAMPLES_2K = -SPS_2K`,
fully documented at the definition site): real-candidate `anchor_dt_s` values (from
`population.py`'s `grid_dt`, ultimately `candidate_diag.csv`) read symbol 0 one full
symbol period later than `modulator.py`'s own `dt_s*fs=sample index` convention.
`extract_variants()` now subtracts one symbol period internally; ROW 0a's synthetic call
site compensates by adding it back (`SYNTH_DT_S + CE.SYMBOL_PERIOD_S`), documented at
that call site, so ROW 0a continues to test genuine self-consistency of the *corrected*
pipeline (still 0.00% BER after the change — confirmed, §2).

## 5. ROW 0b, second attempt (post-fix) — still FIRES, by 0.75 pp

| | median BER | bound | result |
|---|---|---|---|
| V0 | **2.87%** | 2.87% ± 1pp | clear |
| V1 | **5.75%** | ≤ 5.00% | **FIRES** |

n_control=195 grid-matched, 171 measured, 0 non-zero extraction return codes on either
arm. Full population (n=200 requested) used, not `--limit`-truncated — ROW 0b does not
depend on the main population size.

**QA does not believe there is a further legitimate fix inside this spec's scope.** A
fine sweep of the time-origin constant alone (±40 samples around -320, on the same
171-row set) never robustly clears 5% either — the trough is broad and shallow (best
observed: 5.17%, at several different nearby integers, not a sharp single winner),
inconsistent with "one more sample-count bug still to find" and consistent instead with
a **noise floor**. A joint per-row (time, frequency) micro-search does reach ~0% on most
individual rows, but adding a per-row frequency search to the primary extractor itself
is **not authorised by this spec** — spec §9 excludes exactly this kind of position-
search machinery ("R2 stays EXCLUDED... N2 cannot unscope it"), and spec §3.2 pre-warns
against exactly this framing ("§7.2 is not R2's rehabilitation"). QA did not add it.

**Diagnostic context, not gated (control population, same 171 rows, post-fix):**

| variant | median BER | mean BER |
|---|---|---|
| V0 | 2.87% | 7.98% |
| V1 | 5.75% | 10.68% |
| V2 | 6.90% | 11.07% |
| V3 | 8.05% | 11.94% |

Median BER *increases* with coherent group order on this KNOWN-GOOD control population —
the opposite of what the coherent hypothesis predicts, and directionally consistent with
spec §3.2's own risk flag: longer coherent integration windows are *more* sensitive to
the ±0.5–3.1 Hz of frequency imprecision `_anchor()`'s integer-Hz rounding leaves in
place (a 3-symbol group's 0.48 s span turns a 1 Hz residual into 173° of rotation), not
less. **QA is not treating this as a verdict on V2/V3** — ROW 0b gates on V1 only, per
spec's own §6.0 table, and this population is the control (known-good), not the
candidate-present-and-failed population the real gate would run on. It is reported
because it bears directly on whether the 5% V1 bound is achievable at all under this
spec's prescribed rectangular-per-symbol, no-frequency-search design, which is squarely
the Architect's call, not QA's to relax.

## 6. HK-025 re-derivation on ROW 0b

Independently re-checked against spec §6.2's own classification: ROW 0b fires ⇒ is the
result still an estimate of what the gate names (coherent LLR extraction)? **No** — a
Python front end reading the wrong sample position is not measuring coherent extraction
at all; the paired V0-vs-V3 contrast would not be a metric contrast, it would be a
position-error contrast wearing a metric's clothes. ⇒ **VALIDITY**. Legitimate,
not diagnostic, not waivable. Agree with the spec's own pre-written classification. QA
does not refuse under HK-025 (this is not a case of "a precondition that only changes
printed text") — QA escalates instead, per the row's own consequence text.

## 7. Scope discipline (spec §9)

- No `src/` change, no Developer session, no `opsx:apply`, no ABI bump, no new DLL, no
  capture run. HK-011 not engaged, unchanged from the spec's own framing. DLL SHA256
  `6890d84c4bcf2e90bc9ad3cc0e0e00c74a461f8b265665d59b2d4cbb1decd672` / shim `20260042`
  asserted by the harness on every run (`ExtractLLRs(..., verify=True, ...)`), never
  inferred from a label.
- R2 stays EXCLUDED. Nothing in this session's debugging reopens it — the per-row
  frequency micro-search that DOES reach ~0% on most rows (§5) was measured only as a
  diagnostic to characterise the failure, explicitly NOT implemented in the harness's
  primary extraction path, exactly because doing so would be the position-search
  machinery §9 excludes.
- One additive, backward-compatible change to a file N1 depends on:
  `n1-ber-at-refined-position/population.py`'s `_attach_grid_anchor()` gained a new
  `wsjtx_freq_hz` output key (for spec §7.3's tight/loose stratification, never reached
  this session). N1's own rows never read this key — verified by inspection, not
  re-run (N1's results are already committed/historical). No other N1 file touched.
- NFR-021: message text used in-process only (`ex.true_codeword`, the Python synth's own
  `tones`), never written to a result file or printed. Verified by grep, per standing
  policy (§8 below) — every file in the run directory checked individually, not just the
  report's own text.

## 8. NFR-021 grep verification

```
$ grep -rIl "CQ \|Q1AW\|message" qa/rr-study/n2-coherent-llr-extractor/results/
```
`results/n2_gate_report.json` and `results/harness_run.log` contain only numeric
fields/log text (ROW 0a/0b summaries — BER percentages, counts, thresholds); no
`message`/`ts`-to-text mapping, no callsign/grid text beyond `SYNTH_MESSAGE`'s own
literal `"CQ Q1AW JO22"` appearing nowhere in the output files (confirmed: it is a
Python source-code constant, never interpolated into any log or JSON field). `n2_results.
json` was not produced this run (the harness never reached row measurement — it stops at
ROW 0b, before the population loop).

## 9. Deliverables (spec §10)

1. `qa/rr-study/n2-coherent-llr-extractor/` — harness: `coherent_extract.py`,
   `n2_stats.py` (thin re-export of `n1_stats`), `sign_unit_test.py`, `run_n2.py`.
   Clean-room provenance note at the top of `coherent_extract.py` (§4.1's licence
   constraint).
2. Sign unit test run first, PASSED, harness refuses to arm without it (§1).
3. Gate evaluated in strict order (§2–§5); **stopped at ROW 0b**, the first row that
   fired, exactly as pre-registered. HK-025 re-derivation written out (§6).
4. This report.
5. `results/n2_gate_report.json`, `results/harness_run.log` (ROW 0a/0b only — the
   population loop never ran). No `n2_results.json` this session (nothing to write).
6. Committed **locally**, per this branch's established pattern. **Not pushed** —
   HK-014.
7. **BOARD.md updated in the same edit as this result** (HK-024), see next message.

## 10. What QA does not do

Per HK-015, QA does not author the next spec, and this is explicitly not a verdict
report — ROW 1/2/3/4 were never reached. The open question for the Architect: is the 5%
V1 bound achievable under this spec's own prescribed design (rectangular per-symbol
matched filter, `_anchor()`'s integer-Hz rounding, no per-row frequency search), given
§5's diagnostic evidence that it may not be without either (a) a still-undiscovered
second bug QA could not find despite two independent, mutually-confirming diagnostics,
or (b) relaxing one of those design constraints (which would itself need a fresh
pre-registration, not a QA judgement call). QA's own view, offered for what it is worth
and explicitly not gating anything: (a) looks unlikely given how clean and independently
corroborated the one-symbol-period fix was, and (b) looks more likely — but this is
exactly the kind of prediction §8-style calibration exists to flag as cheap talk, not a
finding.
