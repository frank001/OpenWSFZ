# `AWGN-FP` — ROW 0 (instrument validity) result

**QA, 2026-09-02.** Spec: `qa/rr-study/2026-09-02-1906-architect-to-qa-spec-awgn-fp-offline-replay.md`
(Architect → QA, 19:06Z), base `main`@`b4dd754`, shim `20260049`.

Everything in this directory is **untracked, nothing committed** — pending review (Recommendation 4
below explains why, and it is not merely the standing "Captain go/no-go" convention this time).

---

## 1. What this run tests

Per the spec's §5 execution order: "Pin the binary (ROW 0a). Author the harness (§2). Run ROW 0b,
then 0c, then 0d. Stop on any failure and report it — a failed ROW 0 is a complete, publishable
result, not a wasted run." This run built the harness and executed ROW 0 (a→d) only — the
instrument-validity gate that decides whether the N≥2,000/part M1–M4 measurement (§3) is worth
running at all. **M1–M4 were NOT run.** No claim is made here about the actual false-accept rate,
the escalation question, or the ROW 2/3 separation claim — only about whether the offline
instrument reproduces the in-chain phenomenon closely enough to trust a larger run on it.

## 2. Method

- **Render:** the shipped generator only, no second noise source.
  `harness/run_scenario.py --dry-run --dump-wav-dir` against `scenarios/s5-noise.json` (ROW 0b,
  unmodified) and three scratch scenario files under `scenarios/` (ROW 0c's two ±10 dB variants,
  ROW 0d's S1-ladder-at-N=25 complement) — each a copy of a shipped scenario with only
  `level_dbfs`/`trials` changed, same `id`/`part_index`/`trial_index` so
  `harness.common.compute_seed()` derives identical seeds. Cross-checked directly against the
  merged sweep's own `truth.csv`: `compute_seed('S5',0,0)=1561858501`,
  `compute_seed('S5',0,1)=960283802` — byte-identical to
  `qa/rr-study/results/2026-09-02-3b52608/truth.csv` rows 2–3.
- **Decode:** new `tests/OpenWSFZ.Ft8.Tests/AwgnFpReplayTests.cs` — the "equivalent under
  tests/OpenWSFZ.Ft8.Tests/" the spec names as QA's own call (HK-015), required because
  `Ft8LibInterop.DecodeAll`/`GetLastSnrTerms` are `internal` and only reachable from an assembly
  with `InternalsVisibleTo("OpenWSFZ.Ft8.Tests")` — no `tools/` project has that grant, and adding
  one would touch `src/OpenWSFZ.Ft8/AssemblyAttributes.cs`, which the spec's §5 step 1 forbids.
  No `src/`/`native/` file was touched by this arm.
- **Build note:** `dotnet build`/`test` run at `-c Debug`, not `-c Release` — the live
  `OpenWSFZ.Daemon.exe` process (PID 37944, left running from the prior R&R sweep) holds its own
  `bin\Release\...` output DLLs open, and `OpenWSFZ.Ft8.Tests.csproj` legitimately
  `ProjectReference`s `OpenWSFZ.Daemon.csproj`. Debug and Release write to separate `bin/` trees, so
  this sidesteps the lock without touching the running process — no source or binary difference
  between configurations affects `libft8.dll` (it is copied unmodified as content either way; SHA256
  confirmed identical, see ROW 0a).

## 3. Results

| Row | Check | Result | Verdict |
|---|---|---|---|
| 0a | `libft8.dll` SHA256 == pinned `ce02c7ba10e2…ca153e` (shim 20260049, win-x64) | exact match | ✅ PASS |
| 0b | Anchor: offline replay of the sweep's own 60 S5 seeds, events ∈ [2,10] | 6 events | ✅ PASS |
| 0c | Level dependence: same seeds at level ±10 dB, each count must stay ∈ [2,10] | baseline 6, −10 dB 7, +10 dB 7 (all in-band) | ✅ PASS — **not level-dependent** |
| 0d | Complement: M3 (S1 ladder, N=25/part) ≥ 200 genuine decodes | ~~336 decodes~~ → **250 genuine** (+86 spurious) — see §7 | ✅ PASS (verdict unchanged) |

**All four ROW 0 checks pass.** Per spec §5 step 3, the instrument is validated to proceed to the
N≥2,000/part M1–M4 measurement — **not run in this session** (see Recommendation 1).

ROW 0c's PASS means the offline instrument's *absolute* false-accept rate is not measurably
sensitive to a real ±10 dB level change over this range — ROW 1 (the "chronic, not escalating"
comparison against the in-chain gate history) is **not** downgraded to relative-only on this
evidence. Substantively consistent with the spec's own §0.1 mechanistic account: a false accept is
a CRC-14 escape with ~zero excess over the decoder's own noise estimate (`signal_db ≈
local_noise_db`), a *relative* statistic — raising both terms together by shifting the input level
should not, and here does not, move the false-accept rate much.

## 4. A finding this run surfaced, not asked for: ROW 0c's first attempt was invalid

The obvious way to render ROW 0c — copy `scenarios/s5-noise.json`, shift `level_dbfs` ±10 dB, reuse
`harness/run_scenario.py --dry-run --dump-wav-dir` unmodified — silently produced **no level change
at all**. `run_scenario.py`'s main loop peak-normalises every rendered slot to a fixed 0.9 peak
amplitude before *either* live playback or `--dump-wav-dir` writes it out (headroom for PortAudio).
For a pure-Gaussian buffer this is not cosmetic: `normalised = raw_draw × (0.9 / max(|raw_draw|))`
is algebraically **independent of the `level_dbfs` amplitude term** — it cancels exactly, up to
floating-point rounding, for the same seed. Measured directly on the unmodified, real
`scenarios/s5-noise.json` render (`_work/row0b_baseline/`): S5 part 0 (declared −20 dBFS) and part 1
(declared −10 dBFS) — a supposed 10 dB gap the scenario file has carried since 2026-06-20 — both land
at **−20.5 to −22.2 dBFS actual RMS**. Not 10 dB apart. Not measurably apart at all.

This is **not** an artefact of the offline replay path — the identical normalisation call runs
before live hardware playback too (same code, same unconditional call site), so **this has applied
to every S5 sweep this scenario has ever produced, on real hardware, since 2026-06-20.** The
"moderate vs. hotter band" framing in `scenarios/s5-noise.json`'s own part notes does not describe
what has actually been delivered to either decoder.

**Corrected for this arm only:** `render_row0c_level_preserving.py` calls the same shipped
`harness.run_scenario._render_noise()` directly (identical RNG/amplitude formula — not a second
noise source) and skips the peak-renormalise step before quantising, matching `_dump_slot_wav`'s
resample/clip/quantise chain otherwise exactly. Verified: baseline/−10 dB/+10 dB parts land at
−26.2/−16.2, −36.2/−26.2, −16.2/−6.5 dBFS respectively — exact 10 dB steps, both parts, both
directions. This is a narrow, ROW-0c-only workaround, not a fix to `harness/run_scenario.py` itself
(that would be a separate `qa/rr-study/harness/` change, outside this arm's scope and outside what
QA may do unilaterally without flagging it — see Recommendation 2).

## 5. Recommendations

1. **N≥2,000/part M1–M4 has NOT been run.** ROW 0 validates the instrument; it does not itself
   measure the false-accept rate. Recommend the Captain/PO authorise the larger run as a separate,
   explicitly-scoped step — at ~4–15 s/slot decode time observed here, N=2,000×2 parts + the M3
   complement is a multi-hour unattended job, which needs the same HK-013/HK-023 supervised-run
   treatment as any other long unattended run, not an ad hoc foreground `dotnet test`.
2. **Flag to the Architect: `scenarios/s5-noise.json` parts 0/1's declared 10 dB level gap has
   never actually been delivered**, on hardware or offline, because of the shared
   peak-renormalise-to-0.9 step in `harness/run_scenario.py`. This is a genuine, previously
   undocumented validity finding about the R&R harness itself — out of this arm's scope to fix
   (a `qa/rr-study/harness/` change), but it should be assessed for whether it changes the reading
   of *any* historical S5 part-0-vs-part-1 comparison, not just this arm's ROW 0c. Recommend a
   dedicated, separately pre-registered look rather than folding it into this arm's own rows.
3. **`OpenWSFZ.Daemon.exe` (PID 37944) is still running** from the prior R&R sweep session. Not
   touched by this session (a running process is not this QA task's to kill unilaterally) — flagged
   so the Captain can confirm whether it is still needed or should be stopped before any `-c Release`
   rebuild.
4. **NFR-021 — do not commit `results/*.csv` or `_work/*.wav` as they stand.** The decode CSVs
   record the actual message text of every false-accept event, which (same root cause the routine
   sweep's own Recommendation 5 already documents for `*_matched.csv`) are noise-hallucinated
   strings that can be callsign-shaped (e.g. plausible-looking prefix/suffix patterns) without being
   Q-prefix synthetic calls. None of `qa/rr-study/awgn-fp-replay/` matches an existing `.gitignore`
   rule — everything here is currently **untracked**, which is sufficient for now, but a redaction
   pass (same `<RDCTnn>` placeholder convention the routine sweep's result directory used, guarded
   against `truth.csv` collision) is required before any commit. Do not run a blanket `git add -A`
   in this directory.

## 6. What is / is not committed

Nothing from this arm is committed. New paths, all untracked:
`qa/rr-study/awgn-fp-replay/` (scenarios, `_work/` WAV populations, `results/` CSVs and this
report), `tests/OpenWSFZ.Ft8.Tests/AwgnFpReplayTests.cs`. No `src/`/`native/` file was touched.

---

## 7. Architect addendum — 2026-09-02 20:00Z (redaction pass + a ROW 0d correction)

**Added by the Architect on the PO's go-ahead to redact-and-commit (Recommendation 4).** §1–§6 above
are QA's and are unedited apart from one struck-through cell in the §3 table, which points here.
This section carries the redaction record, one correction to ROW 0d's stated count, and one
**exploratory** re-read that must not be cited as a result.

### 7.1 NFR-021 redaction — done, verified clean

Scanned with the project's own `qa/rr-study/nfr021_pre_merge_scan.py` — its `scan()`/`classify()`
imported and driven over a **directory walk**, because the shipped `changed_files()` is
`git diff --name-only base...HEAD` and reports "CLEAN — 0 text files" when pointed at an
uncommitted directory (the standing HK-022 false-green gap; wiring a real directory mode into the
tool remains an unclaimed follow-up).

| | |
|---|---|
| text files scanned | 25 |
| distinct flagged tokens | **73** |
| total occurrences | **92**, all inside `results/*_decodes.csv` |
| `ROW0-report.md` prose | **clean — 0 hits** |
| `scenarios/*.json`, `*_slots.csv`, `row0_verdicts.txt` | clean — 0 hits |
| re-scan after redaction | **0 distinct / 0 occurrences** |

**Pre-redaction guard, run before any byte was rewritten:** none of the 73 tokens appears in any
`truth.csv` or scenario file (**0 collisions**), and the injected corpus itself carries **zero**
non-Q-prefix callsign-shaped tokens. So all 73 are decoder output, never injected truth — rewriting
them cannot corrupt a future truth-join.

Replaced with distinct `<RDCTnn>` placeholders, **deliberately not Q-prefix** (a Q-prefix
placeholder would be indistinguishable from an injected synthetic call). **Byte-level rewrite**:
the files are UTF-8-with-BOM and CRLF, and a text-mode rewrite would have silently normalised every
line ending — BOM preservation and exact CRLF counts asserted per file, and all seven CSVs re-parsed
at their original row/column counts afterwards. Map: `results/REDACTION-MAP.md` (placeholder ↔
one-way token fingerprint; it identifies nothing on its own).

`_work/` — 610 WAVs, 210 MB — is now **gitignored**, not committed. It is deterministically
regenerable from the seeds in the committed `results/*_slots.csv` (60 per ROW 0 leg, 250 for the
0d complement, all distinct), which is the entire point of a seeded replay.

### 7.2 🔴 ROW 0d's "336 genuine decodes" is wrong — it is 250 genuine and 86 spurious

Found while auditing why 57 of the 73 flagged tokens sat in `row0d_s1_complement_decodes.csv`, the
*genuine-decode* file. If the injected truth carries zero non-Q tokens, a row containing one is not
a decode of the injected signal. Joining every decode row to its own `(part, trial)` truth slot:

| | count | reported SNR (dB) |
|---|---|---|
| message **==** injected truth | **250** | min −12, median +4, max +16 |
| message **≠** injected truth | **86** | min −28, median −18, max −1 |
| decode row with no truth slot | 0 | — |

250 is exactly the number of truth slots ⇒ **recall on the injected ladder is 250/250, perfect.**
The other 86 are spurious decodes riding alongside real signal.

🛑 **The ROW 0d verdict does not change: the gate is ≥ 200 genuine decodes and 250 ≥ 200 — PASS,
on the corrected number, with margin.** The instrument is still validated. What changes is the
*claim*: "336 genuine decodes" conflated two populations, and 336 must not be carried forward as a
recall figure anywhere.

### 7.3 ⚠️ EXPLORATORY — the emission-side discriminant, re-read on the separate terms. NO ROW. DO NOT CITE.

**This was not pre-registered.** It fell out of §7.2 while the data was open, it de-blinds the
M-row measurement, and it is reported here only so the M-row spec can be written knowing it.
It is **hypothesis-generating, not a result.**

The board's standing signature (12 of 12 ratified-era S5 false positives at reported SNR ≤ −25 dB
vs a lowest genuine decode of −17/−18) is expressed on the derived `snr`, which `c3a9ea8` changed
inside the very window the distribution shift is suspected in — the spec already flags that as
partly circular and prescribes reading `signal_db` and `local_noise_db` as **separate terms**
(ROW 2). Both columns are in these CSVs, so the circularity can simply be stepped around:

`excess = signal_db − local_noise_db`

| population | n | min | p05 | median | max |
|---|---|---|---|---|---|
| truth-matching (genuine) | 250 | **+14.99** | +15.38 | +30.58 | +42.61 |
| spurious | 86 | −1.63 | −0.61 | +8.82 | +25.16 |

The populations overlap at the top — a spurious decode can reach +25 dB excess — but at the bottom
they separate cleanly. **No genuine decode in this population has less than ~15 dB of excess over
the decoder's own noise estimate.** Sweeping the emission-side cut the board identifies as the one
surviving lever ("refuse to emit a decode with no excess over its own noise floor"):

| cut | spurious removed | genuine lost |
|---|---|---|
| excess ≤ 0.0 dB | 20 / 86 (23.3%) | **0 / 250 (0.00%)** |
| excess ≤ 0.5 dB | 25 / 86 (29.1%) | **0 / 250 (0.00%)** |
| excess ≤ 1.0 dB | 26 / 86 (30.2%) | **0 / 250 (0.00%)** |
| excess ≤ 2.0 dB | 26 / 86 (30.2%) | **0 / 250 (0.00%)** |

A cut at 0 dB sits **~15 dB below the weakest genuine decode** and removes roughly a quarter of the
spurious output at zero measured cost.

🛑 **Four limits, all binding:**

1. **Not pre-registered, n=86 spurious.** The 23–30% figures carry wide intervals and no gate was
   declared in advance. Earn them a pre-registration.
2. **Wrong population for the failing gate.** This is **signal-present S1**. The gate that FAILs
   reads **S5, noise-only**. Whether the excess distribution looks the same when there is no signal
   in the slot is *exactly* what M1–M4 measures and is not answered here.
3. **A cut at 0 dB is not free by construction** — it is free *on decodes the harness injected at
   the ladder's own levels*. The genuine population here has no weak tail below −12 dB reported SNR;
   a real off-air corpus does.
4. **HK-026 check, run and passed:** the discriminant is built from the decoder's own noise
   estimate, and it is used only to judge decodes the decoder **emitted** — the population the
   emission-side lever acts on. It says nothing about decodes never emitted, and no claim here
   ranges over those.

### 7.4 Consequence for M1–M4 — the gate is wrong, not the measurement

My first instinct on writing this up was that M1–M4 should be switched to the separate terms.
**That was already the case** — the spec's M2/M3 and ROW 2/ROW 3 are written on
`signal_db − local_noise_db` throughout. No change needed there; recording the correction so the
non-change is not re-proposed.

🔴 **The real consequence is worse and it is my drafting error.** The spec's ROW 2/ROW 3 pair is a
**disjointness test**: ROW 2 fires only if the maximum false-accept excess is strictly below the
1st percentile of genuine excess, and ROW 3 fires "iff the two distributions overlap at all",
with the consequence *"the emission-filter route is dead on this evidence and is not to be
re-proposed without a new pre-registration."*

On the §7.3 data the distributions **do** overlap (spurious reaches +25.16, genuine starts at
+14.99) — so **ROW 3 would fire and kill the route**, while the same data shows a cut at 0 dB
removing ~23% of spurious output at **zero** genuine cost with ~15 dB of margin. A filter does not
need disjoint distributions; it needs a threshold with an acceptable cost. The gate as drafted
tests the wrong property and its failure branch is far too strong for what it evidences
(HK-021(x) — a falsification gate scoped past the population its claim ranges over).

**Amended in the spec before M1–M4 runs** — see
`qa/rr-study/2026-09-02-1906-architect-to-qa-spec-awgn-fp-offline-replay.md` **Amendment 1**, which
replaces the disjointness pair with a threshold-and-margin test and discloses that §7.3 de-blinded
the numbers the new thresholds are anchored on.
