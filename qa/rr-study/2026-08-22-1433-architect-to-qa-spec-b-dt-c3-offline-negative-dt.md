# Architect → QA: arm B-dt-C3 — the sign change, offline, over negative `true_dt`

**2026-08-22 14:33Z.** `r2-coherent-llr-instrument`, branch `feat/r2-coherent-llr-phase-b`.
Supersedes **TASK 2 / arm B-dt-C2** of
`qa/rr-study/2026-08-22-1411-architect-to-qa-spec-b-dt-c-reported-dt-sign.md` §5 — see §2
for why. That spec's §1 (mechanism), §3 (collinearity, still dead) and §6 (what is not
licensed) stand unchanged and are not restated here except where a row depends on them.

Captain's call, 2026-08-22 ~14:3xZ: spec the offline arm, do not run the live one yet.

---

## 1. What B-dt-C1 established, and the one number that changes the plan

B-dt-C1 (`qa/rr-study/2026-08-22-1423-qa-to-architect-b-dt-c1-results.md`) fired ROW 1 and
I accept it. At `true_dt == 0`, offline, `reported_dt = +0.160 s` and there is **no SNR
deficit** — the opposite corner from the live corpus's S3 part 0 (`−0.200 s`, `−15.67 dB`).
`true_dt == 0` no longer implies `reported_dt < 0`; the two stratifiers are separated.

The number that changes the plan is in that report's §2.5, column 3:

> `reported_dt − true_dt` is **≈ +0.14 … +0.24 s at every part**, part 0 included.

Nothing was played back, so that is not a playback/capture term — it is the offline path's
own render-to-report offset. Its consequence is structural:

🔴 **The offline path cannot produce `time_offset < 0` from a non-negative `true_dt`.**
Every offline sweep run so far has sat entirely on the positive side of the sign change.
The negative side of this decoder's time response has never been measured by this
instrument at all.

---

## 2. Why this arm replaces B-dt-C2, and why it is the stronger arm

### 2.1 B-dt-C2 was specced on an assumption B-dt-C1 has now undermined

§5.2 of the 14:11Z spec sweeps `true_dt` = 0.00 … 0.30 s, on the reasoning that the live
path's ~0.2 s offset puts the sign change inside that window. B-dt-C1 has now measured an
offset of comparable size and the *unhelpful* sign. If the live offset resembles the
offline one, that sweep sits wholly on the positive side and fires its own ROW 0 ("no part
with `T(p) < 0`") — a ~10-minute live run, a hardware teardown, and two cleared `ALL.TXT`
files spent to learn that the range was wrong.

### 2.2 Offline is not an approximation of the live geometry here — it is the same geometry

Verified in source rather than assumed:

- `Ft8Decoder.cs:50` — `ExpectedSampleCount = 180_000`; `Ft8LibInterop.cs:625/919/984`
  reject anything else. A live decode is **exactly one 15 s slot, boundary-aligned.**
- `synth/modulator.py` `extended=True` (Route B contracts C1/C2) returns
  `(buffer, buffer_start_s)` with genuinely early audio and `buffer_start_s <= 0`; G3
  confirmed all ten S3b negative-DT parts decode clean.

So taking the **last 180,000 samples** of the extended buffer reproduces the live case
exactly: a signal that arrives early loses its leading `|dt|` to the previous slot. This is
not a simulation of the live path's truncation — it is the same truncation.

### 2.3 The discriminator against the rival hypothesis is ~50× wider offline

The rival to my `ft8_shim.c:1491-1498` clamp mechanism is "the signal falls partly outside
the decode window". Offline, that rival is *quantitative*, and it is small. Transmission
length is 79 × 0.160 s = **12.64 s**:

| part | `true_dt` | signal truncated | symbols lost | rival predicts |
|---|---|---|---|---|
| p0 | +0.08 s | 0.00 % | 0.0 | **0.000 dB** |
| p1 | 0.00 s | 0.00 % | 0.0 | **0.000 dB** |
| p2 | −0.08 s | 0.63 % | 0.5 | **−0.028 dB** |
| p3 | −0.16 s | 1.27 % | 1.0 | **−0.055 dB** |
| p4 | −0.24 s | 1.90 % | 1.5 | **−0.083 dB** |
| p5 | −0.32 s | 2.53 % | 2.0 | **−0.111 dB** |
| p6 | −0.48 s | 3.80 % | 3.0 | **−0.168 dB** |
| p7 | −0.72 s | 5.70 % | 4.5 | **−0.255 dB** |
| p8 | −0.96 s | 7.59 % | 6.0 | **−0.343 dB** |
| p9 | −1.20 s | 9.49 % | 7.5 | **−0.433 dB** |

**To reach the live `−15.67 dB` by truncation alone you must lose 97.3 % of the
transmission — 12.30 s of 12.64 s.** Across this entire sweep the rival predicts a smooth
ramp of **under half a dB**, i.e. **under one readout quantum**, while the clamp predicts a
**step of order 15 dB at the sign change, flat thereafter**. The live arm's 8 dB bar had
the rival's signature undefined; here it is computed in advance and printed above, so the
report can put predicted and measured side by side.

⚠️ **The caveat, stated rather than buried:** truncation and clamping switch on at the same
`|dt|`. The gate below is therefore on **shape and co-location**, never on the mere
existence of a deficit. A deficit alone proves nothing; a *step* at the sign change,
flat after, with a sub-quantum rival prediction, is the finding.

### 2.4 Cost and other advantages

Minutes, not a live run. No capture hardware, no `ALL.TXT` clearing, no NFR-021 grep pass,
and — relevant right now — **no dependency on tearing down the orphaned `rr_study_daemon`
(PID 37432, `RMS 0.000E+000`, cycles skipped) that B-dt-C1 flagged under HK-019.** Seeded
and exactly repeatable. B-dt-C2 remains available afterwards as live confirmation if ROW 2
fires and the Captain wants the real capture path exercised; it is not a prerequisite for
anything below.

---

## 3. What runs

A new offline harness, QA's to author, modelled on `b_dt_c1_offline_dt_check.py` (reuse its
`run_s3` structure — HK-018, do not reimplement the decode/match/extract path). No scenario
JSON is needed; the parts list is pre-registered here and lives in the harness, exactly as
B-dt-C1's did.

### 3.1 Grid

**Ten parts, ordered by DESCENDING `true_dt` so that `p` increasing means the signal
arrives earlier**, on the decoder's own 0.08 s sub-block lattice:

`p0 = +0.08, p1 = 0.00, p2 = −0.08, p3 = −0.16, p4 = −0.24, p5 = −0.32, p6 = −0.48,
p7 = −0.72, p8 = −0.96, p9 = −1.20` (seconds).

`fixed` = `{snr_db: 0, base_freq_hz: 1500}`, `message_ids: ["MSG-01"]` — S3's own values, so
every number here is comparable to S3, AC-N5 and B-dt-C1 without re-derivation.
**5 trials per part**, 50 cycles total.

**Trial-count justification (HK-021(o)).** This is a continuous dB response read against a
**1 dB** readout quantum, with an expected contrast of ~15 dB and a rival prediction under
0.5 dB. It is not an attribute rate: S3b's own 100-trials-per-part sizing note is about
decode *rate* and **must not be copied across**. 5 trials resolves a 15 dB step trivially;
they are there to catch a flaky part, not to buy precision.

### 3.2 Rendering — the three details that must be exact

1. **Extended render, then truncate to the slot.** Call
   `encoder.encode_message(text, base_freq_hz=1500, dt_s=true_dt, snr_db=None,
   sample_rate_hz=12_000, extended=True)`, which returns `(buffer, buffer_start_s)`.
   Take `clean = buffer[-180_000:]` and `assert len(clean) == 180_000`. That discards
   exactly the pre-slot audio a boundary-aligned decoder never sees. Do **not** pad, roll,
   or re-centre.

2. 🔴 **Fix the noise sigma once, from the `dt = 0` render — do not let `add_noise`
   re-derive it per part.** `channel.noise_sigma_for_snr` sets sigma from
   `np.mean(signal**2)` over the buffer it is handed
   (`synth/channel.py:65-77`). Handing it a *truncated* buffer would quietly scale the
   noise down with the lost energy and **null out the rival hypothesis by construction** —
   the in-slot SNR would be pinned at exactly 0 dB at every part and the ramp in §2.3 could
   never appear. That would make the arm easier to pass and less honest.
   So: compute `sigma = channel.noise_sigma_for_snr(clean_dt0, 0.0, sample_rate_hz=12_000)`
   **once**, from the p1 (`dt = 0`) untruncated 180,000-sample render, and for every part
   call `channel.add_awgn(clean, sigma, seed, sample_rate_hz=12_000)` directly. Record the
   sigma in the report. In S3/B-dt-C1 this changes nothing (the whole signal is always in
   the slot, so `p_sig` is already constant across parts) — it is exactly the existing
   behaviour, extended to the truncated parts instead of silently diverging there.
   **This is not a new pattern:** `add_awgn` exists for precisely this purpose and its own
   docstring says so — *"a multi-signal sum must NOT have its noise rescaled to the summed
   power — the floor is fixed once, for the slot"* (`synth/channel.py:123-140`). S4/S7/S8's
   shared-floor mixer already does it. A truncated signal is the same situation: the noise
   floor is a property of the slot, not of how much signal happens to be inside it.

3. **Seeds.** For p1 only, use `compute_seed("S3", 0, trial)` for `trial` in 0..2 — the
   *identical* seeds B-dt-C1's part 0 used — so those three rows are a byte-identical
   re-render and must reproduce B-dt-C1's numbers exactly (ROW 0(b) below). p1 trials 3-4
   and all other parts use `compute_seed("B-dt-C3", part_index, trial)`.

---

## 4. Definitions, fixed before the run

- `E(p)` = mean(`reported_snr` − 0) over matched OpenWSFZ decodes at part `p` (true SNR is
  0 dB by `fixed`, so `E(p)` is the signed error in dB).
- `T(p)` = mean `reported_dt` at part `p` (the `dt` field of the ctypes `FT8Result`, as
  B-dt-C1 recorded it — an exact proxy for `time_offset`'s sign per §1 of the 14:11Z spec;
  `dt` cannot land in `(−0.08, 0)`, so the sign survives the print quantum).
- **Analysis set** = `p0 … p_max`, where `p_max` is the largest index such that **every**
  part `p0 … p_max` produced `>= 3` matched decodes. Mechanical; parts beyond `p_max` are
  reported but excluded from every statistic below. This exists because the deep parts lose
  whole symbols of the first Costas array (p9 loses 7.5 of the 7-symbol array) and may
  legitimately stop decoding — an expected outcome that must not be able to void the arm.
- `Δ(p)` = `E(p−1) − E(p)` for `p >= 1` in the analysis set — **signed**, positive means the
  error got worse as the signal moved earlier (HK-021(l)).
- `p_step` = the part index `p >= 1` in the analysis set maximising `Δ(p)`.
- `p_sign` = the **lowest** part index in the analysis set with `T(p) < 0`.
- Matching: nearest decode by frequency, `|freq_err| <= 30 Hz`, identical to B-dt-C1.
- Cluster = `(part_index, true_freq_hz)`. Report clusters and per-part n, never bare rows.

---

## 5. Preconditions — assert, do not assume

1. **Binary identity.** SHA256 must equal
   `f0c081b968b04515f3fe76b853b423c77be1495d8e645115ceb3434f9e81fe58` (win-x64
   `libft8.dll`) / `1ba510b8358029c36e3ad9b8927bf80c140784655211f5e7bffddfb7eb7c046b`
   (linux-x64 `libft8.so`) — **re-verified by the Architect against the working tree at
   14:33Z, unchanged since the 14:11Z pin.** Hash it yourself; never infer the build from
   `FT8_SHIM_VERSION`. These files are still **uncommitted**; if the Captain commits or
   rebuilds before you run, re-pin and record the new hash rather than reusing this one.
2. `synth/modulator.py` still raises rather than clamps at both ends, and
   `test_negative_dt_shifts_signal_earlier` is present and passing. The whole arm rests on
   `extended=True` placing audio where the label says; the 2026-06-05 clamp went undetected
   for two and a half months precisely because nothing asserted that.
3. No `src/` or `native/` change, no rebuild, no live capture. If any of those look
   necessary, **stop and escalate** — HK-011.

---

## 6. Pre-registered rows — mechanical, strict order, mutually exclusive

### ROW 0 — VALIDITY. Fires if **any** limb below holds.

- **(a) Decode floor.** Any part in `p0 … p5` with fewer than 3 matched decodes.
  (`p6 … p9` are exempt by the analysis-set definition in §4.)
- **(b) Exact reproduction.** At p1, over the three trials seeded identically to B-dt-C1's
  part 0, the means do **not** reproduce that run: `reported_snr` mean ≠ `+2.000`, or
  `reported_dt` mean ≠ `+0.160`, or `|signal_db mean − (−7.576)| > 0.001`. Same binary,
  same seeds, same render path ⇒ these must match to the printed digit. This is the limb
  that can actually detect harness drift (HK-022's drafting question: a ROW 0 that shares
  its blind spot with the thing it checks is decorative — an exact re-render against a
  prior run's committed numbers does not).
- **(c) Placement.** For each part, the cross-correlation lag between that part's `clean`
  and p1's `clean` differs from `round(true_dt × 12000)` samples, clipped at the slot edge,
  by more than 1 sample. *(The general lesson from the `modulator.py` clamp defect, written
  down at the time and still absent from every downstream check: nothing ever asserted the
  audio went where the label said. It is two lines here.)*
- **(d) Straddle.** No part in the analysis set with `T(p) >= 0`, **or** no part in the
  analysis set with `T(p) < 0`.

⇒ **STOP, escalate.** Each limb implies a different repair — (a)/(b) a harness or binary
problem, (c) a synthesis problem, (d) a sweep placed off the boundary needing a re-render at
a shifted range. None of them is "run the next row anyway". Name which limb fired.

### ROW 1 — `max_p Δ(p) < 8.0 dB`. ⇒ **NO STEP.**

The collapse did not reproduce offline even with `reported_dt` driven negative. That makes
it live-path-specific and the clamp mechanism is **not** its explanation, whatever else is.
⇒ **STOP, escalate.** Do not read `p_step`; it is undefined without a step. Do not open a
Developer session. This is a real and informative outcome, not a failure of the arm.

### ROW 2 — a step of `>= 8.0 dB` exists **and** `p_step == p_sign`. ⇒ **CO-LOCATED, MECHANISM CONFIRMED** as far as an observational arm can take it.

The SNR step and the `time_offset` sign change are the same event, on the same rows of the
same run. ⇒ Recommend the §1.1 fix of the 14:11Z spec to the **Captain** as a Developer
session, carrying the regression check in §8 below. 🛑 **QA does not open it** (HK-011).

### ROW 3 — a step of `>= 8.0 dB` exists **and** `p_step != p_sign`. ⇒ **SEPARATED, MECHANISM REFUTED.**

The two are distinguishable and the clamp is not what drives the collapse. ⇒ **STOP,
escalate.** Do not open a Developer session. Report `p_step`, `p_sign` and the full table;
that separation is the next arm's starting point.

### Threshold justification (HK-021(m))

`8.0 dB` sits **7.7 quanta below** the expected step (15.67 dB, the live S3 part-0 error
against a ~0 dB positive-side baseline) and **7.6 quanta above** the rival's largest
predicted ramp across the whole sweep (0.433 dB at p9, §2.3). Readout quantum is 1 dB.
Both candidate outcomes are far clear of the line, in both directions. Signed throughout
(HK-021(l)); no `|x|` anywhere in §4 or §6.

### Why co-location, and not "the step is at `true_dt = −0.16`"

`p_step` and `p_sign` are both read from the decoder, on the same rows, in the same run, so
the ≈ +0.16 s offline offset — whatever causes it — shifts both and cancels. The gate is on
whether the two **agree**, never on where either lands in absolute `true_dt`. That is also
why this does not violate HK-026: it is not using the instrument's output to bound the
instrument's own blind spot.

---

## 7. Reported, NOT gated

1. The full per-part table: `n` matched, `E(p)`, `T(p)`, `T(p) − true_dt`, `signal_db`,
   `local_noise_db`, and `Δ(p)`.
2. **Measured vs the §2.3 rival prediction, side by side, one column each.** The rival is
   computed in advance; let the report show it failing or fitting.
3. **Flatness on the negative side:** `max E(p) − min E(p)` over analysis-set parts with
   `T(p) < 0`. The clamp predicts flat within a few dB (a 1-symbol and a 3-symbol shift are
   equally wrong); a monotone ramp tracking `|dt|` is the rival's signature. Not gated —
   with few parts on that side a threshold could not be carried honestly.
4. **`local_noise_db` across all parts.** `compute_local_noise_floor_db`
   (`ft8_shim.c:1023`) takes no time argument and is structurally incapable of responding
   to a symbol-index shift. It should be flat. If it steps, the mechanism as stated is
   wrong regardless of which row fired — say so loudly.
5. **`T(p) − true_dt` on the negative side.** Does the ≈ +0.16 s offset stay constant once
   `time_offset` goes negative, or does `reported_dt` saturate near 0? ⚠️ The old
   `STUDY-SPEC` §R&R-003 claim that OpenWSFZ "reports DT ≈ 0 regardless of the true offset"
   is **VOID as evidence** (it was drawn from clamped audio — the synth artefact), but the
   behaviour has never actually been measured on genuinely early audio. This is the first
   look at it.
6. **Cluster composition per part** — which parts dropped out entirely vs decoded badly.
   `E(p)` alone cannot tell those apart (HK-022).
7. The fixed `sigma` value from §3.2(2), and `p_max` (where the analysis set ended).

---

## 8. The regression check to hand forward, if ROW 2 fires

State it in the report so the Developer session inherits it rather than inventing one: the
§1.1 fix touches **only** decodes with `time_offset < 0`, so on any corpus where every
decode has `dt >= 0` the replay must be **bit-identical, decode for decode**. The eight
committed `results/replay_*.json` files from AC-N1 are exactly such a corpus. Mechanical,
hard pass/fail, and stronger than "tests still green".

Add one this arm makes possible: **B-dt-C3 itself is the post-fix acceptance run.** Under
the fix, `E(p)` should be flat across the whole sweep and `Δ(p)` should fall below 8.0 dB
everywhere — the same harness, the same seeds, the same pinned grid, re-run. Commit the
pre-fix `results/*.json` so that comparison is available without a re-render.

---

## 9. What this document does NOT license

- Does **not** authorise any `src/` or `native/` change. §1.1 of the 14:11Z spec names a
  fix; naming is not applying. **HK-011: the Captain opens a Developer session or nothing
  happens** — including if ROW 2 fires.
- Does **not** cancel B-dt-C2. It supersedes it *as the next action*; the live arm stays
  available as confirmation after ROW 2, at the Captain's discretion, and would still need
  the PID 37432 daemon confirmed and torn down first (HK-019).
- Does **not** reopen AC-N2/N3/N4, the getter, or the Amendment 2/3 acceptance.
- Does **not** substitute for `tasks.md` §11 (Phase B's ROW 0g re-run), still open and
  unscheduled, nor bear on the Captain's outstanding merge decision on the Amendment 2 work.
- Does **not** license any statement about **decode rate** at negative DT (that is S3b,
  unrun, and this arm's 5 trials/part cannot carry it), about `dt_s` beyond −1.20 s, or
  about the SNR *formula* (`− 26.5`), H5, suppression, Route B2/B3, C2, C3.
- Does **not** license reading §3 of the 14:11Z spec (the corpus collinearity) as evidence
  for the mechanism. It is predicted by it and cannot discriminate.

---

## 10. Architect predictions — recorded before the arm runs

| # | Prediction | Confidence |
|---|---|---|
| 1 | ROW 0 does not fire on any limb | 70 % |
| 2 | ROW 0(b) exact reproduction passes to the printed digit | 90 % |
| 3 | ROW 2 fires — a `>= 8.0 dB` step exists and is co-located with the sign change | 65 % |
| 4 | `p_sign = p3` (`true_dt = −0.16`), i.e. the ≈ +0.16 s offset holds on the negative side | 45 % |
| 5 | `p_max >= 7` — the sweep still decodes at 4.5 symbols lost | 60 % |
| 6 | `local_noise_db` flat across all parts, spread `< 1.0 dB` | 85 % |
| 7 | Negative-side flatness (§7.3) `< 5.0 dB`, i.e. flat not ramped | 55 % |
| 8 | The measured deficit exceeds the §2.3 rival prediction by `> 10×` at every negative part in the analysis set | 60 % |

Prediction 3 at 65 % is deliberate: three mechanism proposals on this dataset have now
failed, one of them mine and one an assertion of impossibility that data on disk already
refuted (HK-018, 2026-08-21 23:34Z). This one is better supported than those were — it
names two lines, predicts the `local_noise_db` null, and survived B-dt-C1 — but the base
rate on this dataset says do not write 85 %.

---

## 11. Handover

QA runs §3 and reports against §6/§7 in the usual QA→Architect form, then **stops** —
whichever row fires, the consequence is either "escalate" or "recommend to the Captain".
Nothing here is a licence to change, build, push or merge anything (HK-011/HK-014/HK-010).
