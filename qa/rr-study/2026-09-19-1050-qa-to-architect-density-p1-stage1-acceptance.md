# `DENSITY-P1` Stage 1 acceptance — **S1-a / S1-b / S1-c PASS, S1-e PASS; S1-d (CI ×3) NOT YET RUN** — the pass-1 tap is read-only and reads what `ft8_extract_llrs_at` reads

QA, 2026-09-19 10:50Z (`date -u`, HK-017). Per spec
`2026-09-18-1758-architect-to-qa-spec-density-pass1-probe.md` §1.3 (`arch/density` `ea69d8a3`), on the
Developer's build `3ad5504e` (`feat/density-p1-stage1-probe-tap`, shim `20260053`, **not pushed**). Dev-task:
`dev-tasks/2026-09-19-density-p1-stage1-pass1-probe-export.md` (`05163092`). Acceptance harness
`qa/rr-study/density-p1/stage1_acceptance.py`, committed **before any run** as `af61c4e7` with every bar in
its docstring. 🛑 **Stage 2 has NOT started and needs its own Captain go.**

**Headline: on the pre-registered replay set (500 calls, 2 DLLs, 4 modes) the new DLL's decode output is
byte-identical to the old one with the probe disarmed, and byte-identical to itself with the probe armed.**
The pass-0 tap equals `ft8_extract_llrs_at` bit-for-bit on **all 500 calls** (in-band and out-of-band), and the
pass-1 tap differs from the pass-0 tap in 183/264 synthetic and 39/190 real calls, so it does sit after the
suppression. **S1-d is the one gate left, and it needs a push, which needs the Captain (HK-011).**

---

## 1. HK-020 — critical config, and HK-022 — what was pinned and what was NOT filtered

| item | value |
|---|---|
| Binary pin, **OLD** | `91997e38038d9328edcb49cd1e8661706d0092ed2c73e808094c96c3980ad2c6`, shim `20260051`, from `git show origin/decoding_improvement:…/libft8.dll`, SHA-checked in the run (ROW 0a) |
| Binary pin, **NEW** | `50e94e7d73e33050ac37145ac675ad467415324b9cbc5183dc47f3e361829bb7`, shim `20260053`, from `git show feat/density-p1-stage1-probe-tap:…/libft8.dll`, SHA-checked in the run |
| Working-tree DLL | **never used.** Both DLLs are extracted from git into `artefacts/density-p1-stage1-accept/bin/` |
| Test filter | **none.** This is a Python/ctypes harness, not `dotnet test`; nothing could be filtered out silently |
| Params | `ft8_set_decode_params(10, 0.10, 40)` explicit in **every** run: the LIVE app's `nhard` **40**, not the shim default 60 |
| Isolation | one **process** per (DLL, mode, leg), so thread-locals and the session-scoped callsign hash table start identical. Nine processes ran in parallel |
| **SYNTH leg** | `DENSITY-MECH`'s 12 cells (9 primary + 3 strong-victim) × 25 trials, E present, seeds `SR.trial_seed(t, part_index)` = **300 calls** |
| **REAL leg** | 200 live cycles, `artefacts/20260908_live_run_1827-fp-floor-live-2/cycle-audio`, sorted, every 27th; 0 skipped |
| Runs | `old_dis`, `new_dis`, `new_dis2`, `new_arm` × 2 legs, plus `ctl_pass2` (REAL) = 9 |

**Why QA defined the replay set:** the spec says "the fixed replay set used for the last shim bump", but the
last bump's regression net was the live S1–S8 battery, which is not an offline diff set. The set above was
fixed in the harness docstring and committed before the first run.

## 2. ROW 0 — all silent

| row | check | result |
|---|---|---|
| **0a** | both SHA pins and both `ft8_lib_version_check` values match | ✅ |
| **0b** | determinism: `new_dis` vs `new_dis2`, byte-identical, both legs | ✅ |
| **0c** | non-vacuity: REAL decodes ≥ 1000; armed REAL ≥ 50 % cycles with ≥ 1 suppression record; ≥ 10 pass-1 decodes | ✅ **2,329** decodes; **157/200** cycles with records; **70** pass-1 decodes |
| **0d** | the instrument can say NO: `k_min_score_pass2` 30 vs 10 (a real pass-1 change) must change the stream | ✅ differs at the first data line |
| **0e** | coverage: 300 SYNTH calls, ≥ 190 REAL | ✅ 300 / 200 |

## 3. Verdicts

| gate | predicate | result |
|---|---|---|
| **S1-a** | `canon(OLD disarmed) == canon(NEW disarmed)`, byte-identical, both legs | ✅ **PASS**. SYNTH `33d5640188851009` = `33d5640188851009`; REAL `1bf6deb97821aec5` = `1bf6deb97821aec5` (sha256 prefixes) |
| **S1-b** | `canon(NEW armed) == canon(NEW disarmed)`, byte-identical, both legs | ✅ **PASS**, same digests as above (armed at F's true position, arbitrary in-band positions, and out-of-band 50 / 5000 Hz) |
| **S1-c** | tap pass-0 status and 174 float bit patterns equal `ft8_extract_llrs_at`'s on every call; and `ft8_extract_llrs_at` NEW = OLD bit-for-bit | ✅ **PASS**. 0 mismatches in 300 SYNTH + 200 REAL; **156/156** true-position calls status 0; NEW = OLD on both legs |
| **S1-e** | every recorded factor = `1 − clamp((snr+5)/20, 0, 1)` within 1e-6 and in [0,1]; `n_supp == pass_counts[0]` when < 140 | ✅ **PASS**. 3,013 SYNTH + 2,259 REAL records; **0** violations; **1,800 + 999** strictly inside the ramp, so a clamp-only implementation could not have passed |
| **S1-d** | CI green on all three platforms | ⏳ **NOT RUN**: nothing is pushed |

The canonical stream is one line per call: `rc`, every `FT8Result` (with `dt` as IEEE-754 bits), `pass_counts`,
`candidate_counts`, `noise_floor`, `llr_stats`, `snr_terms`, and the five process-global hash/h12 counters.
The hash table persists across calls, so any state leak would cascade into later lines.

**Reporting only (gates nothing):** pass-1 tap ≠ pass-0 tap in **183/264** SYNTH and **39/190** REAL calls
(REAL positions are arbitrary, so most miss any suppressed signal). Suppression-record SNR range: SYNTH
−26.8…+9.4 dB, REAL −29.9…+41.8 dB.

## 4. What this acceptance could NOT have detected (HK-022 / HK-026)

1. 🔴 **The 140-record cap is unexercised.** Busiest cycle: **27** pass-0 decodes (REAL), **11** (SYNTH). The
   `index >= K_MAX_CANDIDATES` guard in `probe_record_suppression` was never reached. It is defensive code
   over an accumulator already capped upstream, so the risk is low, but it is **untested by data**.
2. **Armed↔disarmed interleaving was not exercised by me.** Every armed run is all-armed, every disarmed run
   all-disarmed. The "a disarmed call after an armed one reads NOT_ARMED, never stale" property is covered
   only by the Developer's own T3 (C#), which **I have not independently re-run**. Stage 2 always arms, so
   the practical exposure is small.
3. **One thread.** `_Thread_local` isolation across threads was not tested. The probe is not reachable from
   the managed layer (verified: no `DllImport`/`GetProcAddress` for any of the four symbols in `src/`).
4. **S1-c compares two copies of the same snapping arithmetic.** Agreement proves the tap reads where
   `ft8_extract_llrs_at` reads. It cannot detect an error in the shared *convention* (the `dt + 0.16 s`
   origin); that was established earlier (`B-orig-A`) and is inherited, not re-tested here.
5. **Windows DLL only.** Linux/macOS are S1-d.
6. **Byte-identity is on 500 calls, not a proof.** It is strong evidence over a corpus with 2,329 real decodes
   and 43 empty cycles.

## 5. The Developer's completion record — what I verified independently, and what I did not

**Verified by me, mechanically:** branch and parent (`3ad5504e` ← `e5c79aa4`); diffstat 9 files +959/−6; the
**only two existing lines** of `ft8_shim.c` changed (`static void`→`static float` and the call site, whose
braces preserve the original `if`/`for` binding); `decode.c` and the vendored tree: zero diff; both DLL SHAs;
export list **22 → 26**, none removed, OLD has none of the four (checked by loading both with ctypes); no
`DllImport` for the new symbols; shim version `20260053` unused everywhere and `20260052` still reserved.
**I also read all 187 lines of the `ft8_shim.c` diff:** tap placement, applied-factor return, `valid` set only
after the copy, reset on every call. No defect found.

**Not verified by me:** the full `dotnet test` tally (1,483) and the 21 `DensityP1ProbeTapTests`. CI (S1-d)
will run them.

**Deviations, assessed:** (a) return codes `-1/-3/-4/-5` chosen by the Developer: fine, `#define`d, my harness
uses them. (b) a wrong-length call does not consume a pending arm: literal to spec §1.2.1, harmless (Stage 2
always passes 180,000 samples). (c) `ft8_set_probe` does not invalidate earlier captures: Stage 2 must read
after each armed decode, which it does. (d) `_Static_assert` on the record size: additive, good. (e) `[In, Out]`
marshalling: C# tests only. **One minor note:** `ft8_get_last_suppression` returns `0` both for "not armed"
and for "armed, nothing suppressed". Stage 2 must read `ft8_get_probe_llrs`'s status first.

**Pre-existing drift the Developer flagged and did not repair (correctly):** `openspec/specs/ft8lib-interop/
spec.md:53`'s Scenario still says `20260049`; `BUILD.md`'s `/EXPORT` list already lacked three exports and its
"fifteen symbols" note is stale; `libft8.version.txt` had no `20260051` entry. Not chased. Flagged for the
Architect.

## 6. Status and what is needed

- ✅ **Stage 1 build is technically accepted on S1-a, S1-b, S1-c and S1-e.**
- ⏳ **S1-d needs a push.** The Developer's branch and QA's `qa/density-p1` are both unpushed. **Captain's
  pre-push sign-off is required (HK-011; HK-033 for QA's own commits).** Base and PR target:
  `decoding_improvement`.
- 🛑 **Stage 2 is held.** It needs the Captain's second, separate go. Nothing of Stage 2 was computed; the
  aggregate SNR range above is Stage 1's `S1-e` sanity, not Stage 2's §2.5 reporting (E's applied factor per
  cell). ROW 0c stays the load-bearing row.
- **Merge to `main`:** not required for Stage 2 (spec §4); a separate Captain sign-off if ever wanted (HK-010).
- Data point for the Architect's ledger (scored by the Architect, not by QA): spec prediction #1 was "Stage 1
  passes S1-a…d first time, 0.70, class C"; S1-a/b/c/e passed first time and S1-d is unrun.
- Artefacts: `artefacts/density-p1-stage1-accept/` (gitignored, real-callsign text stays there). Committed:
  the harness and `results/stage1_verdict.json` (counts and hashes only).

---

*Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>*
