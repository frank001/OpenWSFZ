# QA → Architect: Amendment 2 (corrected by Amendment 3) acceptance results — AC-N1 through AC-N5

**2026-08-22 13:49Z.** `r2-coherent-llr-instrument`, `tasks.md` §16.3 (AC-N1, Developer
session) + §17 (AC-N2/N3/N4/N5, this QA session), `feat/r2-coherent-llr-phase-b`.

## 0. Summary

**`signal_db` is where any `true_dt`-dependence must live; `local_noise_db` does not
move.** `local_noise_db` moves +0.23 dB (noise) between the `true_dt == 0` and
`true_dt > 0` strata. `signal_db` moves −6.01 dB pooled — **but see the 2026-08-22
14:11Z correction in §5.2 below: that pooled figure is scenario-confounded and is NOT
the size of the live collapse; within S3 alone, where scenario is held fixed, `true_dt
== 0` shows no deficit.** This localisation (which term carries the effect) is still
the entire reason `ft8_get_last_snr_terms` was built (Amendment 2 §1), and it now has a
direct, index-aligned, per-decode answer rather than an inference from `ALL.TXT`-level
aggregates.

All three gating checks (AC-N2, AC-N3, AC-N4) **PASS**. AC-N1 (Developer session,
`tasks.md` §16.3) **PASS**, independently re-verified by me at code-review time before this
run (see §1). AC-N5 (this session) is reported, not gated, per its own charter.

## 1. Code review of the Developer session's diff (§14-16), before this run

Before running §17 I reviewed the Developer session's own diff against `tasks.md` §14-16
line by line (not merely reading the task file's own claims): the `decode.c:940` guard
widening (11 insertions/2 deletions, exactly the claimed edit), `ft8_shim.c`'s two-line
TLS write at the pre-increment `results[]` index (48 insertions/0 deletions — purely
additive), the `ft8_shim.h`/C# doc comments, the `/EXPORT:` line, and all ten
`IFt8NativeInterop` fake-stub updates individually (not sampled).

Independently re-verified rather than trusted:
- **AC-N1's own "zero decode differences" claim** — diffed the four committed replay
  JSONs myself (pre-Amendment-2 vs post, both platforms, 250 cycles each):
  **0/250 cycle diffs on Windows, 0/250 on Linux.**
- **The re-pinned SHA256** (`coherent_llr_ctypes.py` task 16.4) — hashed the working-tree
  DLL/SO myself; matches the pin exactly on both platforms.
- **`dotnet build`** (Ft8 project, Debug): 0 warnings, 0 errors.
- **`dotnet test`** on `OpenWSFZ.Ft8.Tests`: **317/317 green**, matching the task's own
  claim exactly.
- **No production call site**: grepped `src/` for `GetLastSnrTerms`/`ft8_get_last_snr_terms`
  — only the three interop-seam files and test code; `Ft8Decoder.cs` untouched.

No findings sent back. Approved as a faithful implementation of §14-16.

## 2. AC-N2 — IDENTIFIABILITY (GATES) — PASS

Over 250 contiguous cycles (`WINDOW_20M`, the same corpus/window AC-N1's own replay
uses — no live capture needed, HK-018), 4,842 total decodes:
`abs((signal_db[i] - local_noise_db[i] - 26.5) - snr[i]) <= 0.5 + 1e-3`
for every decode — **0 violations**.

**Max observed `|reconstructed − reported|` = 0.50000 dB**, against the 0.5010 dB bar —
sitting exactly on the int-rounding quantum boundary. This is worth stating plainly: it
independently confirms Amendment 3's own `+1e-3` correction (over Amendment 2's original
strict `<= 0.5`) was load-bearing, not cosmetic. A strict `<= 0.5` bar would have **failed
on this very run**, from float representation alone, on a formula that is otherwise
exactly correct.

## 3. AC-N3 — COUNT CONTRACT (GATES) — PASS

Same 250-cycle run. 0 cycles AV-caught. `ft8_get_last_snr_terms`'s own returned count
matched `ft8_decode_all`'s own returned count on **every single cycle, 0 mismatches.**

## 4. AC-N4 — CAPACITY (GATES) — PASS, all five cases

First `count >= 3` cycle encountered immediately: `ts=260808_004000`, `count=16` (the
very first cycle in the window — no denser-scenario fallback needed).

| Case | Expected | Observed | No-overrun (canary check) |
|---|---|---|---|
| `capacity=0` | n=0, empty | n=0, empty | clear |
| `capacity=1` | n=1 | n=1 | clear |
| `capacity=count-1=15` | n=15 | n=15 | clear |
| `capacity=-5` | n=-1, both arrays untouched | n=-1 | n/a |
| both-NULL, `capacity=26` | n=16 (count it would have written), no crash | n=16 | n/a |

"No-overrun" was checked **independently of the trimmed-return wrapper**: each case was
re-run with a raw ctypes call against a canary buffer pre-filled with a sentinel value
past `capacity` — confirmed untouched every time, not inferred from array length alone.

## 5. AC-N5 — THE MEASUREMENT (reported, not gated)

### 5.1 Methodology, and why it differs from the earlier B-dt-A arm

**This could not reuse `run_study.py`'s live-playback pipeline.** `ft8_get_last_snr_terms`
has no production call site (task 14.4, confirmed by grep in §1 above) — the live
daemon's own `ALL.TXT` can never carry `signal_db`/`local_noise_db` no matter how the
audio reaches it. So this is a direct, offline `ft8_decode_all` + `ft8_get_last_snr_terms`
call over PCM synthesised in-process by `synth.encoder`/`synth.channel` — the SAME
functions `run_scenario.py`'s live-playback path calls — reparameterised from the
playback rate (`DEFAULT_SAMPLE_RATE_HZ=48000`) to the decoder's own native rate
(12,000 Hz, `BUFFER_SAMPLES=180,000`). This is not a novel construction: it is the exact
adaptation `row0g_instrument_gain_check.py`'s own clean-signal trials already established
(HK-018), reused rather than re-derived. First attempt called `run_scenario.py`'s own
`_render_single`/`_render_band_scene` directly and got a 720,000-sample (48 kHz) buffer
`ft8_decode_all` cannot consume — caught immediately, recorded honestly (HK-022), fixed
by calling the lower-level `encoder.encode_message`/`channel.mix_to_shared_floor`
directly at 12,000 Hz instead.

S3 parts 8/9 (`dt_s` 2.4/2.7, the two parts needing the extended-buffer placement
contract) were **skipped** — a separate methodology question this measurement does not
need, since the `dt==0` vs `dt>0` question is already fully posed by parts 0-7
(`dt_s` 0.0 through 2.1). Do not extrapolate this measurement to `dt_s > 2.1` (HK-026).

### 5.2 Result

85/87 rendered rows matched to a truth station by nearest frequency (tolerance 30 Hz,
generous against FT8's own 6.25 Hz tone spacing). 2 unmatched (both `true_dt=0.0`,
excluded rather than force-assigned — see §5.3). 16 S8 decodes flagged **ambiguous**
under the E/F near-collision (12 Hz apart) and G/H co-frequency capture pairs — but
every ambiguous pair shares `true_dt=0.0`, so the stratification itself is unaffected
by the ambiguity (flagged, not silently resolved).

| Term | `true_dt=0` (n=59) mean / median | `true_dt>0` (n=26) mean / median | Δ(mean) |
|---|---|---|---|
| `signal_db` | −14.562 / −15.462 | −8.547 / −7.826 | **−6.014 dB** |
| `local_noise_db` | −35.525 / −35.500 | −35.750 / −36.000 | +0.225 dB |
| reconstructed SNR | −5.536 / −6.057 | +0.703 / +1.411 | −6.239 dB |
| reported SNR | −5.508 / −6.000 | +0.885 / +1.500 | −6.393 dB |

**`local_noise_db`'s Δ (+0.23 dB) is inside the §17.5 3 dB reference band by an order of
magnitude — it does not move.** The two terms' reconstructed SNR and the raw reported
SNR agree closely (−5.536 vs −5.508 at `dt=0`; +0.703 vs +0.885 at `dt>0`) — consistent
with AC-N2's own near-exact identity, an internal cross-check this measurement gets for
free.

**CORRECTION, 2026-08-22 14:11Z (HK-015 — stated by the Architect, this edit is QA's
own, made in place rather than by annotation).** The `−6.01 dB` `signal_db` Δ above
**may not be cited as the size of the live `true_dt == 0` SNR collapse.** Re-grouping
the same 85 matched rows by scenario as well as by `true_dt` shows the stratifier is
very nearly collinear with scenario:

| cell | n | mean `signal_db` |
|---|---|---|
| S3, `true_dt == 0` | 3 | **−7.58** |
| S3, `true_dt > 0` | 21 | **−7.99** |
| S8, `true_dt == 0` | 56 | −14.94 |
| S8, `true_dt > 0` | 5 | −10.90 |

56 of the 59 `dt=0` rows are S8; 21 of the 26 `dt>0` rows are S3. The pooled `−6.01 dB`
is therefore largely an S8-vs-S3 level contrast wearing a `dt` label, not a `dt` effect
in its own right — §5.3's note on asymmetric sample sizes understated this; it is a
confound, and it is load-bearing for the headline number above.

**Within S3 — the one place `fixed.snr_db = 0` holds across every part and only `dt`
varies — `true_dt = 0` (part 0) shows no deficit at all**: reported SNR `+2.0` against
`+0.67 .. +2.0` across parts 1-7. Compare the live B-dt-A arm at that identical cell:
**−15.67 dB** (`2026-08-22-1218-qa-to-architect-b-dt-a-results.md`, §5.1/§5.3). **The
phenomenon did not reproduce offline** in this measurement. That is a finding, not a
harness defect — it is what let the Architect narrow the mechanism to a `time_offset`
sign effect rather than a `true_dt` magnitude effect, and it is TASK 1 (arm B-dt-C1)'s
starting point.

The honest statement of what this section establishes: **`local_noise_db` does not move
between the strata; `signal_db` is where any `dt`-dependence must live, by construction
of the reconstructed-SNR formula; the *size* of the live collapse is not what this
pooled measurement returned, because the pooling confounds `true_dt` with scenario.**
AC-N2/N3/N4 and the getter itself are untouched by this correction — the three gates
stand, and this note revises only the reported, ungated §5.2 reading above.

### 5.3 Honesty notes

- The 2 unmatched rows (S8 trial 4, stations D and F) both decoded with large frequency
  error (31 Hz and 97 Hz respectively) against their nominal truth frequency — plausibly
  a mis-synced or sidelobe decode on that particular noisy trial. Both are `true_dt=0.0`
  stations; excluding them (rather than force-matching) is conservative against the
  `dt=0` stratum, not against the `dt>0` one.
- Sample sizes are asymmetric by construction (S8 contributes 11 of its 12 stations to
  the `dt=0` stratum and only 1 (station I) to `dt>0`; S3 contributes 1 of 8 in-scope
  parts to `dt=0` and 7 to `dt>0`) — not a flaw, just worth naming so the n=59/26 split
  isn't read as itself informative.

## 6. §17.5 — Prediction scoring

| Prediction | Confidence | Result |
|---|---|---|
| AC-N1 zero-diff, first attempt | 95% | **HIT** (0/250 both platforms) |
| AC-N2 passes, first attempt | 85% | **HIT** (0 violations/4,842 decodes) |
| The `true_dt == 0` collapse localises to `signal_db`, not `local_noise_db` | 80% | **HIT on localisation** (−6.01 dB vs +0.23 dB) — **but see §5.2 correction: the −6.01 dB pooled figure is scenario-confounded, not a clean measure of the collapse itself** |
| `local_noise_db` at `true_dt == 0` is within 3 dB of its `true_dt > 0` value | 65% | **HIT** (+0.23 dB) |
| A third mechanism proposal is needed after AC-N5 | 40% | **not mechanically scoreable by this task** — AC-N5 answers WHERE (`signal_db`), not WHY `signal_db`'s own computation depends on `dt`. Left for the Architect's call. |

4/5 mechanically scoreable predictions HIT.

## 7. What this does NOT license (unchanged, restated per `tasks.md` §18)

Does not reopen H5 or license any suppression change; does not change the SNR formula or
choose `DEFECT-snr-reported-gain-error.md`'s fix; does not bear on ROW 0g / task 4.3 /
Route B2 / B3; does not license C2 or C3. AC-N5's own output is not used here to bound
its own blind spot (HK-026) — `dt_s > 2.1` and negative `dt` remain unmeasured by this
instrument, and are not interpolated.

## 8. Artefacts

- `qa/rr-study/r2-coherent-llr-instrument/snr_terms_ctypes.py` — the `ft8_get_last_snr_terms`
  ctypes binding.
- `qa/rr-study/r2-coherent-llr-instrument/ac_n2_n3_n4_identifiability.py` +
  `results/ac_n2_n3_n4_report.json` / `results/ac_n2_n3_n4_run.log`.
- `qa/rr-study/r2-coherent-llr-instrument/ac_n5_dt_stratified_measurement.py` +
  `results/ac_n5_report.json` / `results/ac_n5_run.log`.
- `openspec/changes/r2-coherent-llr-instrument/tasks.md` §17 checked off in place.

## 9. Next

`tasks.md` §19.1 (this report) done. §19.2: stopping here per HK-014/HK-010/HK-006 — no
push, no merge, no `pre_merge_check.py`. The Captain reviews and decides on merge.
Independently, `tasks.md` §11 (Phase B's own ROW 0g re-run) remains open and unscheduled
— this Amendment does not substitute for it.
