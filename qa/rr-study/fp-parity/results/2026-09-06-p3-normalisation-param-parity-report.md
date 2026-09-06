# `FP-PARITY` Amendment 3 (P3) result — decode-param parity, path identity, and the normalisation paired re-decode

**QA, 2026-09-06 ~10:19Z** (`date -u`, HK-017). Spec:
`qa/rr-study/2026-09-06-0951-architect-to-qa-spec-fp-parity-p3-normalisation-and-param-parity.md`
("`FP-PARITY` Amendment 3" — a document distinct from `AWGN-FP`'s own A3.1–A3.4; naming the spec on
every A3.x citation below per that spec's own numbering-collision note). Base `main`@`1b7ca29`
(PR #140, shim `20260050`). Branch: `qa/2026-09-06-fp-parity-p3-execution`.

🔴 **Headline: ROW 0o, ROW 0p and ROW 0s do NOT fire. ROW 0n → verdict 0n-iii (the two agree). ROW
0n-C does NOT fire.** `10.325%` (offline, `20260050`, normalised) becomes the only citable offline
absolute rate from this day forward; `10.875%` is not restored, it is agreed with. `T = 2.622 dB`
carries forward to `20260050`, normalised, and P4b may proceed on that ground — **P4b is not
authorised by this document.**

**What P3 is NOT, restated per spec §0 (all three hold):** this arm proposed no capture run, built
no emission filter, and tuned nothing. `NormalisePcm` here is parity with production's fixed 0.20
RMS contract, not a lever — the candidate-budget family and input-scaling arm stay closed.

---

## 0. Preconditions and reconnaissance

- `git diff --stat -- src/ native/`: **empty**, verified before and after this session's work
  (§3.1). No Developer session was used or needed — `NormalisePcm` is `internal static`
  (`Ft8Decoder.cs:497`) and `[assembly: InternalsVisibleTo("OpenWSFZ.Ft8.Tests")]` is present
  (`AssemblyAttributes.cs:3`), independently re-verified today before starting.
- `qa/ARTEFACT_INVENTORY.md` was stale (`--check` failed); regenerated (`python
  qa/artefact_inventory.py`), now current. Its root is `artefacts/` only and cannot see `_work/`
  (HK-026) — `qa/rr-study/awgn-fp-replay/_work/m1m4_s5/` was enumerated directly: **4,000 `.wav`
  files**, confirmed independently of any prior report's claim.
- **Shared-tree note:** a second session briefly also identified as QA on this same checkout. The
  PO designated this session (`qa/2026-09-06-fp-parity-p3-execution`) as sole executor before any
  decode began; the other session confirmed it started nothing. No collision occurred.
- `qa/rr-study/awgn-fp-replay/results/row0_verdicts.txt`'s uncommitted +14 lines: **discarded**
  (`git checkout --`) per PO instruction — those lines logged `20260050` runs into a provenance
  file with no binary column, after ROW 0r established the binaries differ on 246/4,000 slots.

## 1. ROW 0p — path identity and the `20260050` binary pin

Pin computed by QA, not copied from any document (spec is explicit it states none):

```
git show 1b7ca29:src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll | sha256sum
  -> 6b2e16a6991ae953d18c85e5f0fea99d1e003c84b90ae5a69a8f1cfade34f85c
python tools/check_native_version.py <extracted dll> 20260050
  -> "Result: OK -- binary contains shim version 20260050"
```

This value is now `FpParityP3Tests.PinnedShaWinX64` — a **new literal in a new class**.
`AwgnFpReplayTests.PinnedShaWinX64` (`ce02c7ba…153e`, the `20260049` identity of every already-landed
row, `AWGN-FP` A3.1) was **not touched**.

Test output (actual, printed at run time):

```
ROW 0p: actual SHA256 = 6b2e16a6991ae953d18c85e5f0fea99d1e003c84b90ae5a69a8f1cfade34f85c
ROW 0p: pinned SHA256 = 6b2e16a6991ae953d18c85e5f0fea99d1e003c84b90ae5a69a8f1cfade34f85c
ROW 0p: files scanned = 4000, files NOT exactly 180,000 samples = 0
```

**FIRES iff any assertion fails → confirmed: match, 0/4,000 wrong-length → ROW 0p does NOT fire.**
No resample/DC-removal: `WavReader.cs` is a pure int16→float conversion (cited, not
re-implemented). AP-bits-cleared-per-decode and one-`DecodeAll`-per-slot are structural invariants
of ROW 0n's own decode loop (§4 below), asserted there via a call counter equal to the slot count.

## 2. ROW 0o — decode-param parity

Read from the live `config.json` (`ConfigPathResolver.ResolvePath()` →
`C:\Users\Frank\AppData\Roaming\OpenWSFZ\config.json`, exists, `decoder` key present) against
`DecoderConfig()`'s code default:

```
ROW 0o: live-effective (K,Corr,Nhard)               = (10, 0.1, 60)
ROW 0o: DecoderConfig() code default (K,Corr,Nhard) = (10, 0.1, 60)
ROW 0o: FIRES (any of the three differs) = False
```

**Does not fire.** Cross-checked against the native shim's own module-level defaults as documented
in `Ft8LibInterop.cs`'s changelog (20260030 entry: "Default values identical to shim 20260029" —
`K_MIN_SCORE_PASS2=10`, `OSD_CORR_THRESHOLD=0.10f`, `OSD_NHARD_MAX=60`) — no changelog entry between
20260030 and 20260050 touches any of the three names, consistent with the standing "candidate-budget
family CLOSED twice" prohibition. Since neither `AwgnFpReplayTests.cs` nor `Row0rCarryForwardTests.cs`
ever calls `SetDecodeParams`, every existing offline measurement (including the `10.875%` baseline)
was, by this chain, already running at production parity — not by assumption but by the module's own
compiled-in defaults matching production's effective config exactly, both cited and confirmed here.

`FpParityP3Tests` calls `Ft8LibInterop.SetDecodeParams(10, 0.10f, 60)` explicitly before decoding
(§3.3 item 2), rather than relying on the native default by omission, so ROW 0n's own decode is
parity-by-construction as well as parity-by-measurement.

## 3. ROW 0s — un-normalised `20260050` baseline, recomputed as an assertion

From `qa/rr-study/fp-parity/results/m1m4_s5_20260050_slots.csv` alone (ROW 0r's already-committed
file), recomputed independently — not inherited from any report's prose:

```
slots = 4000  (expected 4000)
events (n_decodes>=1) = 435  (expected 435)
event rate = 10.875%  (expected 10.875%, exact fraction compare)
ROW 0s FIRES = False
```

**Does not fire** → this file is P3's un-normalised leg and `10.875%` is confirmed a `20260050`
figure by direct recount, not merely carried over by reading.

**What this row cannot detect** (HK-022, and the arm's own fourth defect — §7 below): whether
ROW 0r's own decode was correctly configured (that's ROW 0o/0p's job, both run first and both
non-firing above), and it cannot re-verify ROW 0r's own numeric-invariance claim (0/435 differ in
`freq_hz`/`dt_s`/`reported_snr_db` against `20260049`) — ROW 0s never opens `decodes.csv` at all.
Cite ROW 0r for numeric invariance; cite ROW 0s only for the `4,000/435/10.875%` recount.

## 4. ROW 0n — normalisation parity, exactly paired, N = 4,000

`FpParityP3Tests` decoded all 4,000 `_work/m1m4_s5/` WAVs with `NormalisePcm(pcm, 0.20f)` applied —
target RMS **read by reflection** from `Ft8Decoder`'s private const (`PcmNormalisationTargetRms`),
confirmed `0.2` at run time, not hard-coded into the call. Wall time: **5 m 18 s** (ROW 0r's
identical, un-normalised population took 3 m 48 s; the difference is consistent with the added
`NormalisePcm` pass and this run's additional per-slot output, not investigated further — no
supervisor was needed either way, both comfortably under any HK-013/HK-023 threshold).

**Mandatory clobber guard**: both output paths (`qa/rr-study/fp-parity/_out/p3_norm_{slots,decodes}.csv`)
were asserted untracked by `git ls-files --error-unmatch` *before* either file was opened; the guard
did not fire (both paths were, correctly, untracked — `_out/` is gitignored, `.gitignore` updated
this session with the rationale recorded there). Neither file is committed; both stay local evidence
under `_out/`, exactly as the spec requires — promotion into `results/` is explicitly out of scope
for P3.

Paired against ROW 0s's baseline, slot-by-slot, all 4,000 slots:

| | Count |
|---|---|
| Both legs event | 72 |
| Neither leg event | 3,224 |
| **b** — un-normalised only (lost under normalisation) | 363 |
| **c** — normalised only (gained under normalisation) | 341 |
| n discordant (b+c) | 704 |

- Un-normalised rate: **10.875%** (matches ROW 0s exactly, as it must — same baseline file)
- Normalised rate: **10.325%**
- **Δ (signed, normalised − un-normalised) = −0.550 pp**
- Readout quantum: **1/4,000 = 0.025%**
- Exact McNemar two-sided p-value: **0.4287**
- 95% exact conditional CI on Δ: **[−1.870, +0.774] pp** — method, named for reproducibility per the
  Architect's adjudication (`2026-09-06-1025-...-p3-adjudication.md`): exact (Clopper-Pearson)
  binomial CI on `p = c/(b+c)` via `scipy.stats.binomtest(c, n_disc).proportion_ci(confidence_level=0.95,
  method="exact")`, then transformed to the Δ scale via `Δ_bound = (2·p_bound − 1) · n_disc / N`
  (implemented in `p3_parity.py`'s `row0n_paired_mcnemar()`) — an exact, non-bootstrap method per
  HK-021(o). The Architect's independent paired-Wald recomputation gives **[−1.850, +0.750] pp**,
  0.02 pp apart; both include zero and both put `|Δ|` far under the 2.0 pp band. This report's
  figure (Clopper-Pearson-transformed) is the citable one; the two methods' agreement to 0.02 pp is
  itself part of the evidence that 0n-iii is not a close call.

**CI includes 0 ⇒ verdict 0n-iii.** The two agree. Consequence, binding per the spec regardless of
this branch: **the normalised figure (`10.325%`) is the only citable offline absolute rate from this
day forward** — `10.875%` is not restored by this non-fire, it is agreed with. The ≈6.9 dB
offline/production level difference is excluded as an explanation of the offline-vs-in-chain gap.

Every figure above: **offline, `20260050`, normalised, under the production input contract.**
Pooling any of them with a `≤20260049` offline figure is a new pre-registration (A3.2).

## 5. ROW 0n-C — false-accept ceiling under the production contract

Over every decode row in the normalised leg's `p3_norm_decodes.csv` (all treated as false accepts —
S5 is noise-only), `excess ≜ signal_db − local_noise_db`:

```
n = 432
excess: min = -2.113 dB, median = -0.018 dB, max C' = 1.652 dB
Signed C' - 1.622 dB = +0.030 dB
ROW 0n-C FIRES (any excess > 2.622 dB) = False  (0 of 432 rows exceed T)
```

**Does not fire.** `T = 2.622 dB` carries forward to `20260050`, normalised, and P4b may proceed on
this ground. **Honest limit, stated per HK-021(t):** this shows no false accept on this 4,000-slot
noise-only population exceeded `T` — it does **not** show `C` is stable; a sample maximum over
n = 432 is not a stable statistic.

## 6. NFR-021

`qa/rr-study/fp-parity/_out/p3_norm_decodes.csv` contains callsign-shaped tokens (decoder output on
a noise-only population, exactly as `AWGN-FP` and ROW 0r's own decode CSVs do) — scanned directly by
importing `nfr021_pre_merge_scan.scan()` (not a git-diff-based dir walk, since `_out/` is untracked
and invisible to that path per the standing note) against both output files. `p3_norm_slots.csv`:
0 tokens. `p3_norm_decodes.csv`: 264 distinct callsign-shaped tokens found, all confined to a file
under the gitignored `qa/rr-study/fp-parity/_out/` directory (confirmed via `git status --short`
showing nothing for that path both before and after the run). **No token is quoted in this report or
its evidence trail** — the "gitignored" claim is checked, not just asserted, per the standing note
that it once failed in the same sentence as three real callsigns.

## 7. HK-025 — the fourth defect

Per spec §8.6, three of the Architect's own row definitions in `FP-PARITY` §4 needed correcting
before P3 could run at all (§1.1–1.3 of the spec: ROW 0n's population mismatch, the N=2,000→4,000
sizing, and the never-measured ROW 0n-C ceiling). Instructed to assume there is a fourth rather than
report none found.

**Found, and ratified by the Architect in-session (not silently repaired):** spec §0.1's inheritance
table cites ROW 0r §2 correctly for numeric invariance (0/435 differ in decode count/`freq_hz`/`dt_s`/
`reported_snr_db`, already run and landed) — but its middle column then reads "see ROW 0s, which
asserts it rather than assuming it." **ROW 0s's own predicate never opens `decodes.csv` and never
cross-references `20260049`'s numeric fields at all** — it recomputes only `4,000/435/10.875%` from
the `20260050` `slots.csv` file in isolation. The table hands ROW 0s a broader confirmatory scope
than its own mechanical predicate can carry; citing "see ROW 0s" for numeric invariance would be an
over-citation of a check that never made that comparison (HK-022 applied to the spec's own
inheritance table, not to a gate). **No predicate, fire condition, or verdict changed** — ROW 0s ran
exactly as specified and its own non-fire stands untouched; this is a citation/scope fault in
§0.1's prose, not a validity fault in ROW 0s itself. The Architect will land a dated amendment
splitting that table row so each claim names the row that actually supports it; not folded into
this report or acted on unilaterally.

No fifth defect found; not fished for, per the spec's own "a row that does not fire is not a licence
to narrate" discipline applied to this review as well.

## 8. Reporting obligations (spec §8)

1. `git diff --stat -- src/ native/`: **empty**, confirmed before this session's first commit.
2. Filter used to run the rows: `dotnet test --filter "FullyQualifiedName~FpParityP3Tests.<Fact>"`
   (per-Fact, pre-registered order 0p → 0o → 0n/0n-C). ROW 0p's printed actual/pinned SHA pair: both
   `6b2e16a6991ae953d18c85e5f0fea99d1e003c84b90ae5a69a8f1cfade34f85c` (match). **HK-022 check,
   verified not assumed:** `dotnet test --filter "Category!=AwgnFpReplay&FullyQualifiedName~FpParityP3Tests"`
   → *"No test matches the given testcase filter"* — confirmed the production CI/pre-merge filter
   (`ci.yml:336`, `tools/pre_merge_check.py:611`, `Category!=AwgnFpReplay`) silently excludes this
   new class exactly as intended, not merely assumed from the shared trait.
3. Every number above carries its label: **offline, `20260050`**, normalised-or-not, stated inline.
4. Δ signed (`-0.550 pp`), `b=363`, `c=341`, `n=4,000`, exact McNemar `p=0.4287`, readout quantum
   `0.025%` — all reported in §4.
5. NFR-021 handled per §6 above; `_out/` gitignored and verified untracked, not merely claimed.
6. Fourth HK-021 fault: flagged and escalated in §7, not silently repaired; Architect ratified.

## 9. What's next — commit and STOP

Per HK-030: a written hard stop means pause and hand back, not merely "do not push." **P4b (ROW 2 /
ROW 3) is NOT in the P3 spec and is NOT authorised by it or by this report**, regardless of ROW 0n-C's
non-fire above making it *reachable*. This session commits its work on
`qa/2026-09-06-fp-parity-p3-execution` and stops.
