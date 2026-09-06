# `FP-PARITY` P3 — Architect → QA spec: decode-param parity, path identity, and the normalisation paired re-decode

**Architect, 2026-09-06 09:51Z** (`date -u`, HK-017). Base `main`@`1b7ca29` (PR #140, shim
`20260050`). Docs-only; `git diff --stat -- src/ native/` empty, verified before commit (HK-014).

**This document is `FP-PARITY` Amendment 3.** 🔴 **Numbering collision, stated once so it cannot be
misread:** the `AWGN-FP` spec (`2026-09-02-1906-…-awgn-fp-offline-replay.md`) *also* has an
`A3.1`–`A3.4`, and they are a **different document** — `AWGN-FP` A3.1 is the ROW 0a pin ruling
reverted onto today. **When citing either, name the spec.** Everything numbered `A3.x` below is
**`FP-PARITY` A3.x**.

**Executes:** `qa/rr-study/2026-09-04-1322-architect-to-qa-execution-pack-post-shim-bump.md` block
**P3**, whose two-line brief (*"these need a binary ⇒ they run after P2, on whichever binary ROW 0r
leaves valid"*) turned out to be the whole problem — ROW 0r left **neither** binary trivially
valid. §0.2 settles it.

**Preconditions you must have read (HK-018):** `FP-PARITY` §1–§4 (the row definitions this amends),
`FP-PARITY` Amendment 2 (A2.1 ROW 0m stands, A2.2 the `≤20260049` label, A2.4 the POST-REGRESSION
label), and the ROW 0r report `qa/rr-study/fp-parity/results/2026-09-04-row0r-carry-forward-report.md`.

---

## 0. What P3 is, and the three things it must not become

**P3 answers one question:** *is the offline replay seam measuring the same instrument production
runs?* Two parity assertions (`0o`, `0p`) and one paired measurement (`0n`). Nothing else.

🛑 **What P3 is NOT.** (1) **Not a capture run** — no radio, no Voicemeeter, no sweep; proposing one
is a separate pre-registration (`FP-PARITY` §5 step 7). (2) **Not a licence to build the emission
filter** — that is ROW 2, and ROW 2 is P4b, and P4b is not in this document. (3) **Not a tuning
exercise.** `NormalisePcm` parity is *matching production*, not scaling input; the candidate-budget
family stays closed twice over. **Input scaling remains a closed arm** (standing prohibitions).

🔴 **Standing disclosure, unchanged:** the Architect is de-blinded on the offline excess
distributions (`AWGN-FP` A1.0). **Prediction scoring stays suspended.** §7 is calibration only and
**nothing gates on it.**

### 0.1 What P3 inherits, and what is void — checked at source today, not carried from prose

| Object | Status going into P3 | Verified today at |
|---|---|---|
| ROW 0m (in-chain recount) | ✅ **STANDS.** Not void — `FP-PARITY` A2.1 | `fp_parity_checks.py:34-41` — all six sweeps dated ≤ 2026-09-02, wholly pre-bump; `:198` performs **no decode** |
| The in-chain comparator | ✅ `12/360 = 3.333%` CP95 [1.934%, 5.345%] — **label: in-chain, `≤20260049`, POST-REGRESSION** (A2.2 + A2.4) | as above |
| ROW 0q (int-SNR rule) | ✅ **RE-CONFIRMED on `20260050`** — `round_half_away_from_zero`, unanimous over 3,510 rows | ROW 0r report §4 |
| ROW 1 (`F = +8.00 dB`) | ✅ Stands, **straddle disclosed** (48 slots ≤`20260049` + 12 on `20260050`); leave-one-out `F` unchanged | `FP-PARITY` A2.3 |
| M1–M4 message-text results | 🛑 **VOID on `20260050`** (`AWGN-FP` A3.2) | ROW 0r fired: 246/435 event slots differ in message text |
| M1–M4 **numeric** results | ⚠️ **Re-measured and unchanged.** 🔴 **CORRECTED BY A3.3 — cite ROW 0r for this, NOT ROW 0s.** ~~see ROW 0s, which asserts it rather than assuming it~~ — **ROW 0s reads `slots.csv` alone and could not detect a numeric change if one existed; its whole scope is the aggregate event count.** | ROW 0r §2: `0/435` differ in decode count, `freq_hz`, `dt_s`, `reported_snr_db`; *"no slot appears or disappears"* |
| `AwgnFpReplayTests.PinnedShaWinX64` | ✅ `ce02c7ba…153e`, the `20260049` landed-row identity — **restored `7cf11d7`, PO-directed** | `AWGN-FP` A3.1; `tests/…/AwgnFpReplayTests.cs:58` |
| `_work/m1m4_s5/` corpus | ✅ **4,000 WAVs present** — enumerated directly, because `ARTEFACT_INVENTORY.md`'s only root is `artefacts/` and cannot see `_work/` (HK-026) | direct `ls` |
| `qa/ARTEFACT_INVENTORY.md` | 🔴 **STALE** — `--check` fails. Regenerate before §5 step 1 | `python qa/artefact_inventory.py --check` |

### 0.2 🔴 A3.1 RULING — the binary P3 runs on, decided deliberately rather than by drift

`FP-PARITY` ROW 0p as written asserts *"binary SHA256 equal to the pinned `ce02c7ba…153e`"* — the
`20260049` value. **On current `main` that assertion fires and stops the arm.** It cannot simply be
edited, because ROW 0r proved the two binaries are not interchangeable (246/4,000 slots differ). So
the choice is made here, in writing, with its price stated.

**The two candidates:**

- **Run P3 on `20260049`.** 🛑 **Not reachable.** `Ft8LibInterop.ExpectedShimVersion` is a
  compile-time constant, now `20260050`; loading the old DLL throws in `LoadAndVerify()` before any
  decode call (ROW 0r's disclosed obstacle). It would need a second checkout and build at `3b52608`
  — and it would measure an instrument **production no longer runs**, which is the opposite of what
  a parity arm is for.
- **Run P3 on `20260050`.** ✅ **Ruled.** It is what `main` ships and what the daemon loads.

**⇒ RULING: P3 runs on `20260050`, and its ROW 0p pin is a NEW literal in a NEW class.**

🛑 **`AwgnFpReplayTests.PinnedShaWinX64` is NOT touched.** It stays `ce02c7ba…153e` — the
`20260049` identity of every landed row, per `AWGN-FP` A3.1. **This is the second time that pin has
come under pressure from a green-suite motive in four days; the answer is the same both times.**
P3's own pin lives in a new file, `tests/OpenWSFZ.Ft8.Tests/FpParityP3Tests.cs`, exactly following
the `Row0rCarryForwardTests.cs` precedent — a parallel class, its own pin, the landed class
untouched.

🛑 **A3.2 — THE LABEL, and it is mandatory on every P3 number.** Every figure P3 produces is
**offline, `20260050`, and (for ROW 0n's normalised leg) under the production input contract.**
**Pooling any P3 figure with a `≤20260049` offline figure is a NEW pre-registration, not an
extension** — the same discipline A2.2 imposed on the in-chain comparator, for the same reason, and
here with a *measured* 246/4,000 difference behind it rather than an inference.

---

## 1. What P3 changes about `FP-PARITY` §4, and why — read before the rows

Three defects in my own original row definitions, all exposed by ROW 0r's fire and all corrected
below rather than executed as written.

### 1.1 🔴 ROW 0n compared two different populations. Corrected to an exactly paired design.

**As written:** *"FIRES iff the normalised pooled rate's 95% CI excludes 10.875%"*, at
**N = 1,000 per part** (2,000 slots).

**Two things wrong with that.** First, `10.875%` is a **4,000-slot** figure; comparing a 2,000-slot
normalised rate against it folds sampling variation from a *different sample* into what is supposed
to be a normalisation effect. Second, `10.875%` was measured on **`20260049`**, and M1–M4 are void
on `20260050` — the predicate compares across the very bump ROW 0r fired on.

**The fix is free, because the un-normalised leg already exists on the new binary.** ROW 0r decoded
the identical 4,000-WAV population fresh on `20260050` and committed
`qa/rr-study/fp-parity/results/m1m4_s5_20260050_{slots,decodes}.csv`. So both legs can be run on
**the same 4,000 slots, on the same binary**, and compared **slot by slot**.

⇒ **ROW 0n becomes an exactly paired comparison over all 4,000 slots, tested with McNemar's exact
test on discordant pairs**, not two independent CIs.

### 1.2 🔴 N goes 2,000 → 4,000. Pre-registered here, before any normalised decode exists.

The `N = 1,000/part` sizing was fixed when the run was assumed expensive. **It is not:** ROW 0r
decoded all 4,000 slots on this machine in **3 m 48 s**. Raising N to the full 4,000:

- makes the design **exactly paired** (§1.1) — the actual reason, not the precision;
- can only **tighten**, never bias — it is a precision change, not a validity change (HK-021(k));
- readout quantum becomes **1/4,000 = 0.025%**;
- **is made before the data exists.** No normalised decode has ever been run. Nobody, including me,
  can know which way this moves.

⚠️ **Consequence for supervision: none needed.** HK-013/HK-023 supervisor machinery is **NOT
required** for a ~4-minute run — the execution pack's *"supervised if it runs long"* is discharged
by ROW 0r's measured 3 m 48 s on the identical population, not by assumption.

### 1.3 🔴 The false-accept ceiling `C` was never re-measured under the production contract — and P4b depends on it.

`ROW 2`'s threshold is `T ≜ C + 1.0 dB`, with `C = +1.622 dB` — the max `excess` over 454 false
accepts, measured **offline, un-normalised, on `20260049`**. If normalisation moves the excess
distribution, **`T` is wrong and P4b would inherit it silently.**

There is a tempting source argument — `Ft8Decoder.cs:265-270` states both `signal_db` and
`noise_floor_db` are waterfall-derived, so uniform amplitude scaling cancels in the difference.
🛑 **It is barred here on exactly the ground `AWGN-FP` A3.2 barred its twin:** a source-level "it
cannot matter" may not substitute for the measurement, and ROW 0r is why — the same reasoning said
an additive, never-called export could not perturb decoding, and it perturbed 246 slots.

⇒ **New row `0n-C`**, measured on the same paired run at no extra decode cost.

---

## 2. Units and definitions — unchanged, restated because they are where this arm died once

- **`slot`** — one 15 s cycle of one part of one scenario. The unit of every rate.
- **`event`** — a slot carrying **≥ 1** decode. **Rates are `events / slots`, always.**
- 🛑 **A decode row is NOT an event.** M1's 435 events produced 454 decode rows (`FP-PARITY` §2.1,
  `AWGN-FP` A2.4). Every P3 rate is over **slots**; every ceiling statistic is over **rows**. State
  which, per number.
- **`excess ≜ signal_db − local_noise_db`** — the separate terms, read from `GetLastSnrTerms`,
  float. Immune to the `c3a9ea8` SNR-scale change.
- **`Δ ≜ (normalised event rate) − (un-normalised event rate)`**, over the same 4,000 slots.
  🛑 **Signed, always. Never `|Δ|`** (HK-021(l)).

---

## 3. The instrument work — tests-only, and the clobber guard that is now mandatory

### 3.1 No HK-011 cycle. Verified, not assumed.

`Ft8Decoder.NormalisePcm(float[], float)` is **`internal static`** (`src/OpenWSFZ.Ft8/Ft8Decoder.cs:497`)
and `[assembly: InternalsVisibleTo("OpenWSFZ.Ft8.Tests")]` is present
(`src/OpenWSFZ.Ft8/AssemblyAttributes.cs:3`). `tests/OpenWSFZ.Ft8.Tests/PcmNormalisationTests.cs:30`
**already calls it today**. ⇒ **zero `src/`/`native/` diff, no Developer session, QA executes the
whole of P3.** 🔴 **Assert it and say so in the report:** `git diff --stat -- src/ native/` must be
empty at commit time.

### 3.2 🛑 MANDATORY — P3 may not write to any tracked results path

On 2026-09-06 an unfiltered `AwgnFpReplayTests` run **clobbered 12 redaction-mapped committed CSVs**
with raw decoder output, twice in one day, because `DecodeDirectory` writes
`{label}_{slots,decodes}.csv` straight into `qa/rr-study/awgn-fp-replay/results/`
(`AwgnFpReplayTests.cs:471-472`, `:98`). Contained, restored, and now a gate:

1. **`FpParityP3Tests` writes to `qa/rr-study/fp-parity/_out/`** — a **new, `.gitignore`'d**
   directory, never to `results/`. Labels are P3-specific (`p3_norm_*`, `p3_unnorm_*`) and collide
   with nothing existing.
2. **A pre-run assertion in the fixture itself:** every output path it is about to open must be
   **untracked** (`git ls-files --error-unmatch <path>` must fail). **Throw before decoding if not.**
   A guard that runs after the write is not a guard.
3. **Promotion into `results/` is a separate, deliberate step**: redact per the existing
   `REDACTION-MAP*` convention, re-scan to 0 with `nfr021_pre_merge_scan.py`, then copy and commit.
   **Never the fixture's own write.**
4. `[Trait("Category", "AwgnFpReplay")]` on the new class, so the filter now in `ci.yml:336`,
   `TESTING_STRATEGY.md` §4.7 and `tools/pre_merge_check.py` covers it. ⚠️ **HK-022: a filtered-out
   suite is SILENT, not green** — the report quotes the exact `--filter` line used **and** ROW 0p's
   printed actual/pinned SHA pair. **A report with neither is not a result.**

🟡 **Architect ruling on QA's clobber-report §6 recommendation** (*"consider gitignoring
`results/*_decodes.csv` outright"*): **no — do the above instead.** Gitignoring them would untrack
evidence the `REDACTION-MAP*` files and every landed report reference, trading a privacy failure for
a provenance failure. **Separating the write path from the commit path removes the clobber without
losing the audit trail.** ⚠️ Migrating `AwgnFpReplayTests` itself to `_out/` is the right follow-up
and is **deliberately NOT folded into P3** — it changes where landed rows write. Its own small task.

### 3.3 The two production-parity changes

1. **`NormalisePcm` behind a parameter**, so ROW 0n is one code path over identical WAVs, not two
   runs of different code. 🔴 **The target RMS must be read from production, not typed:**
   `PcmNormalisationTargetRms` is a private const (`Ft8Decoder.cs:52`) — read it by reflection
   (`GetField(..., NonPublic|Static).GetRawConstantValue()`) and assert it equals `0.20f`.
   **Hard-coding `0.20f` in the test would let production drift away from the parity run silently**
   (HK-022: what could this check *not* detect?).
2. **`Ft8LibInterop.SetDecodeParams(...)` called before decoding**, at the machine's effective
   values (ROW 0o). `public static`, `Ft8LibInterop.cs:903`.

---

## 4. Pre-registered rows

Every predicate ships **as code** (HK-021(r)) in `qa/rr-study/fp-parity/p3_parity.py` +
`FpParityP3Tests.cs`, printing each row's inputs, its threshold, and its verdict. **Print every row,
then the first firing verdict.** Inherited constants go in the code **as assertions**, not in the
prose as reminders — QA's own `== 72` caught a fabricated citation before a single number was
computed; that lesson is binding here.

### ROW 0s — re-establish the un-normalised `20260050` baseline as an assertion. No decode.

ROW 0n's paired design rests on ROW 0r's committed CSVs being the un-normalised leg. **Assert it;
do not inherit my reading of their report.** From `m1m4_s5_20260050_slots.csv` alone, recompute:
total slots, and slots with `n_decodes ≥ 1`.

**FIRES iff** slots ≠ **4,000**, or events ≠ **435**, or the event rate ≠ **10.875%**.

⇒ **Consequence, asserted either way:** does not fire ⇒ that file is P3's un-normalised leg and
`10.875%` is a **`20260050`** figure, not merely a carried-over one. **Fires ⇒ STOP** — the paired
design has no baseline and ROW 0n must be re-scoped to decode both legs fresh (which is affordable,
~8 minutes, but it is a different row and needs saying, not doing).
⚠️ **What this row cannot detect** (HK-022): whether ROW 0r's own decode was correctly configured.
That is ROW 0p's job, and ROW 0p runs **before** ROW 0n for exactly this reason.
🔴 **Nor can it detect a numeric-field change** (`freq_hz`, `dt_s`, `reported_snr_db`, decode count)
— it reads `slots.csv` **alone** and never opens `decodes.csv`. **That is ROW 0r's claim and ROW 0r
has already made it** (`0/435`). **Added by A3.3; see the amendment at the foot of this document.**

### ROW 0o — decode-param parity

Read the machine's effective `(KMinScorePass2, OsdCorrThreshold, OsdNhardMax)` from the live
`config.json`, falling back to `DecoderConfig`'s defaults **`10 / 0.10f / 60`** when the key is
absent — the fallback production itself performs (`src/OpenWSFZ.Daemon/Program.cs:727-731`:
`configStore.Current.Decoder ?? new DecoderConfig()`; defaults verified today at
`src/OpenWSFZ.Abstractions/DecoderConfig.cs:50,59,68`). Assert the offline seam is configured
identically.

**FIRES iff** any of the three differs.

⇒ **Consequence:** **every offline absolute rate this project holds is void** until re-run at
parity — including `10.875%`, ROW 0s's baseline, and ROW 0n's. 🛑 **Say that plainly and STOP. Do
not re-run first and report second.**

### ROW 0p — path identity and the `20260050` binary pin

Assert, in the new class: 180,000 samples per slot, no resample, no DC removal, AP bits cleared
before every decode, exactly one `DecodeAll` per slot, and **SHA256 of the loaded `libft8.dll`
equal to a literal pin for `20260050`**.

🔴 **How the pin is established, once, and then frozen:** compute the SHA256 of
`src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll` at `main`@`1b7ca29` **yourself** — do not copy a value
from any document, including this one, which deliberately states none. Cross-check the same file
with `tools/check_native_version.py <path> 20260050`. Write the verified value as a **literal
constant** in `FpParityP3Tests.cs`, **quote it in the report**, and it is thereafter this arm's
pre-registered manifest value.

**FIRES iff** any assertion fails ⇒ **STOP**; the instrument is not the one P3 specified.

⚠️ **What this row cannot detect** (HK-022): that the binary was already the wrong one **at pinning
time** — a pin compared against the file it was derived from is self-fulfilling on its first run.
The `check_native_version.py` cross-read is what covers that, and it is why it is required rather
than optional. From the second run onward the pin detects drift, which is its actual job.

### ROW 0n — normalisation parity, exactly paired, N = 4,000

Decode all 4,000 `_work/m1m4_s5/` WAVs **with** `NormalisePcm(pcm, 0.20f)` applied (target read by
reflection, §3.3). Pair each slot with its un-normalised counterpart from ROW 0s's file. Let
**b** = slots that are events un-normalised only, **c** = events normalised only.

**Report, all of them:** `b`, `c`, both marginal rates, **`Δ` signed**, and the **exact McNemar
(binomial) two-sided p-value and 95% CI on `Δ`**.

**Three mutually exclusive, exhaustive verdicts, fixed here before any normalised decode exists:**

| | Predicate | Consequence |
|---|---|---|
| **0n-i** | McNemar 95% CI on `Δ` **excludes 0** and **`\|Δ\| ≥ 2.0 pp`** | 🔴 The offline seam has been measuring a materially different instrument. `10.875%` is **retired outright**, and the offline-vs-in-chain gap must be **recomputed and re-reported** before any P4b work. |
| **0n-ii** | CI **excludes 0** and **`\|Δ\| < 2.0 pp`** | Real but immaterial. The normalised figure becomes the citable offline rate; the gap conclusion stands, **with `Δ` and its sign disclosed in every future citation.** |
| **0n-iii** | CI **includes 0** | The two agree. The normalised figure still becomes the citable offline rate (it is the only one under the production contract), **and the ≈6.9 dB offline/production level difference is excluded as an explanation of the gap.** |

🔴 **Where `2.0 pp` comes from — consequence and instrument precision, not the data.** The in-chain
comparator is `3.333%` with CP95 **[1.934%, 5.345%]**, so the gap ratio the comparator alone can
support spans **2.035× – 5.623×**. A ±2.0 pp shift in the offline rate moves the point estimate
from 3.263× to **2.663× or 3.863×** — **well inside** that interval. ⇒ **A `Δ` smaller than 2.0 pp
cannot move any conclusion the comparator is precise enough to support.** Below that the honest
statement is "real, and too small to matter here" — which is 0n-ii, and 0n-ii carries a reporting
cost rather than a free pass (HK-021(t)).

🛑 **In all three branches the normalised figure becomes the only citable offline absolute rate from
this day forward**, because it is the only one measured under the production input contract. **A
non-fire does not restore `10.875%`** — it means the two agree.

### ROW 0n-C — the false-accept ceiling under the production contract

On the **same** normalised run, over **decode rows** (not slots), compute `excess` for every false
accept and report min / median / **max `C′`**, `n`, and the **signed** difference `C′ − 1.622 dB`.

**FIRES iff** any normalised-leg false accept has **`excess > 2.622 dB`** (i.e. exceeds the standing
`T = C + 1.0`).

⇒ **Consequence:** fires ⇒ 🛑 **`T` is not conservative and must be re-derived before P4b runs at
all** — ROW 2/ROW 3 may not be evaluated against a ceiling the production contract has moved past.
Does not fire ⇒ `T = 2.622 dB` carries forward **to `20260050`, normalised**, and P4b may proceed.
⚠️ **The non-fire branch's honest limit, stated in the same row** (HK-021(t)): it shows no false
accept **on this 4,000-slot noise-only population** exceeded `T` — it does **not** show `C` is
stable, and a sample maximum over `n≈454` is not a stable statistic. **Report the distribution, not
just the max.**

### ROW 4 — anything else

Report the numbers, fire no conclusion. **A row that does not fire is not a licence to narrate.**

---

## 5. What QA does, in order

1. **Regenerate `qa/ARTEFACT_INVENTORY.md`** (`--check` currently FAILS) and confirm what is on
   disk. ⚠️ Its only root is `artefacts/` ⇒ **it cannot see `_work/`; enumerate that directly**
   (HK-026). `_work/m1m4_s5/` was verified at 4,000 WAVs on 2026-09-06 — re-verify, do not inherit.
2. **ROW 0s** — pure analysis of a committed CSV. Minutes, no decode.
3. **ROW 0o**, then **ROW 0p**. 🛑 **Both before any decoding.** If either fires, **STOP and
   report** — do not proceed to ROW 0n to "have the number anyway."
4. **ROW 0n + ROW 0n-C** — one paired run, ~4 minutes, no supervisor (§1.2).
5. **Report per HK-001.** Headline carries §0's three bars: **P3 proposes no capture, builds no
   filter, and tunes nothing.**
6. **Commit and STOP.** 🛑 **HK-030: a written hard stop means pause and hand back, not merely "do
   not push."** A later step being unblocked by dependency does not lift an earlier stop — this is
   the exact reading that went wrong in the P1→P2 handoff, and it is called out here so it cannot go
   wrong the same way twice. **P4b is not in this document and is not authorised by it.**

**HK-025 stands: QA may refuse any row here on HK-021(k) grounds without the Architect's
agreement.** Classify (validity vs precision), evaluate **both** branches, and if the same row fires
either way it is decorative — **refuse it and say why.** 🔴 That right was exercised correctly on
ROW 0m and the refusal was upheld; it is not a formality.

---

## 6. Standing bars this arm does not lift

- 🛑 **Input scaling is CLOSED** (P2, ROW 2). `NormalisePcm` here is **parity with production**, a
  fixed 0.20 RMS contract — **not a lever, not a sweep, not varied for any purpose.**
- 🛑 **The candidate-budget family is CLOSED twice** (`s_k_min_score_pass2`, `K_MAX_CANDIDATES*`,
  the pass table). ROW 0o **asserts** production's values; it may not vary them. If a row implicates
  them, that is a **finding to report**, and it earns its own pre-registration.
- 🛑 **Subtract-and-resynthesise stays dead.** Three builds, three reverts, two crashes.
- 🛑 **No root-cause investigation of ROW 0r's fire.** Why 246 slots changed message text is a
  **new pre-registration** (`AWGN-FP` A3.2), not a P3 sub-question. **Do not chase it here**, however
  tempting it becomes while looking at normalised output.

---

## 7. Predictions — calibration only, NOTHING GATES ON THEM

Recorded because I am de-blinded and the record should show it. **Scoring suspended** (`AWGN-FP`
A1.0); these may not be cited, and no row's threshold was chosen with reference to them.

- ROW 0o: does not fire (~0.7). ROW 0p: does not fire (~0.9). ROW 0s: does not fire (~0.9).
- ROW 0n: **0n-iii** (~0.55), 0n-ii (~0.3), 0n-i (~0.15). Reasoning, such as it is: the shim's own
  comment argues uniform scaling cancels in both waterfall terms — **and that same class of argument
  was wrong about ROW 0r**, which is why the row exists.
- ROW 0n-C: does not fire (~0.8).
- 🔴 **My directional calls in this programme are poor** (0/2 at last count, plus a ROW 1 miss). If
  a result contradicts the above, **the prediction is what is wrong.**

---

## 8. Reporting obligations, in addition to HK-001

1. `git diff --stat -- src/ native/` **empty**, stated (§3.1).
2. The exact `--filter` line used, **and** ROW 0p's printed actual/pinned SHA pair (§3.2.4).
3. Every P3 number carries its label: **offline, `20260050`**, and normalised-or-not (A3.2).
4. `Δ` **signed**, with `b`, `c`, `n`, the exact McNemar p, and the readout quantum **0.025%**.
5. **NFR-021 before commit:** the normalised decode writes fresh unredacted callsign-shaped tokens
   over a noise-only population. `_out/` is gitignored; **anything promoted to `results/` is redacted
   and re-scanned to 0 first**, and **report prose is scanned too** — a "gitignored" claim once named
   three real callsigns in the same sentence.
6. Any HK-021 fault found in **this** spec: flag and escalate (HK-025), do not silently repair. **Three
   of my own row definitions needed correcting before P3 could run at all (§1); assume there is a
   fourth.**

**Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>**

---

# AMENDMENT A3.3 — 2026-09-06 10:25Z: §0.1 over-attributed scope to ROW 0s

**Architect, 2026-09-06 10:25Z** (`date -u`, HK-017). **Found by QA in review, before executing —
accepted in full.** 🛑 **DEFERRED DELIBERATELY until QA handed back the working tree, so the record
shows a scope correction and not a goalpost moving mid-run.** Docs-only.

🔴 **NOTHING IN THIS AMENDMENT CHANGES A PREDICATE, A THRESHOLD, A VERDICT, OR A STOP BRANCH.** P3
executed against §4 exactly as written, and its results are unaffected.

**The defect.** §0.1's inheritance table read: *"M1–M4 **numeric** results — ⚠️ Re-measured and
unchanged — **see ROW 0s**, which asserts it rather than assuming it."* ROW 0s's own predicate (§4)
reads `m1m4_s5_20260050_slots.csv` **alone** and recomputes only `4,000 slots / 435 events /
10.875%`. It **never opens `decodes.csv`**, never cross-references `20260049`'s `freq_hz`, `dt_s` or
`reported_snr_db`, and **could not detect a numeric-field change if one existed.** The table
therefore handed a confirmatory scope to a row whose predicate cannot carry it.

**The correction — two claims, two rows:**

| Claim | The row that actually supports it |
|---|---|
| Decode **count**, `freq_hz`, `dt_s`, `reported_snr_db` unchanged across the `20260049`→`20260050` bump (`0/435`) | **ROW 0r** — already measured and landed, `2026-09-04-row0r-carry-forward-report.md` §2 |
| The **aggregate event count** on `20260050` is `4,000 / 435 / 10.875%`, recomputed rather than inherited from anyone's reading of ROW 0r's prose | **ROW 0s** — and that is its **entire** scope |

🛑 **"See ROW 0s" for numeric invariance is an OVER-CITATION and must not be made.** Cite **ROW 0r**.

**Added to ROW 0s's "what this row cannot detect" note (HK-022):** it cannot detect a numeric-field
change. That is ROW 0r's job and ROW 0r has already done it.

🔴 **The pattern, recorded because it is the useful part:** this is the **fourth** defect found in
this spec, and **all four are scope-and-citation faults — not one touches a fire condition.** That
is either the truth about this spec or the Architect's blind spot, and it cannot be told apart from
the inside. **A future review of an Architect spec should attack the predicates first**, on the
working assumption that the prose is the weak surface and the gates are not — or that the gates have
simply never been caught.

**Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>**
