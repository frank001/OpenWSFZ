## Context

All FILE:LINE are `origin/main` `81f74ede`, `native/ft8_lib_build/patched/ft8/decode.c` unless stated. The Developer re-checks them
on the branch tip and records any drift (task 1.1).

| fact | where |
|---|---|
| `osd_decode` takes positive = bit 0 | definition `:507`, header comment `:501`, hard decision `(llr[perm[i]] < 0.0f) ? 1 : 0` `:~527` |
| BP and the extractor take positive = bit 1 | `bp_decode` / `ft8_extract_likelihood` (`:~1248`) |
| caller 1, `ftx_decode_candidate` | `llr_for_osd` memcpy `:645-646`; `osd_decode(llr_for_osd, 2, …)` `:666`; gate `:680-683` |
| caller 2, `ft8_ldpc_decode_llrs` export | `llr_for_osd` memcpy `:962-963`; `osd_decode(llr_for_osd, osd_depth, …)` `:978`; gate `:989-992` |
| caller 3, the AP path | `llr_for_osd` memcpy `:1072-1073`; `osd_decode(llr_for_osd, 2, …)` `:1089`; gate `:1098-1101` |
| gate arithmetic | `hard_pm1 = (plain174[i]==0) ? +1 : -1`, `hd = (llr_for_osd[i] > 0) ? 0 : 1`, on `llr_for_osd` |
| tunables | `s_osd_corr_threshold`, `s_osd_nhard_max` are non-static globals defined in `ft8_shim.c:~480`, `extern` in `decode.c:~58`; setter `ft8_set_decode_params` `ft8_shim.c:488` |
| managed binding | `Ft8Decoder.SetDecodeParams` `Ft8Decoder.cs:158`, `Ft8LibInterop.SetDecodeParams`, `IFt8NativeInterop` |

## Decisions

**D1. One array, read by both OSD and the gate (Architect's amended R1/R2, review A1).** A static helper, for example
`static void osd_llr_from_bp(const float *llr_bp, float *llr_osd)`, writes `llr_osd[i] = (s_osd_sign_fix ? -llr_bp[i] : llr_bp[i])`
into a buffer the call site owns (or negates `llr_for_osd` in place; either is acceptable). Each of the three sites calls it once
and passes the resulting array to **both** `osd_decode` and its gate loop. The gate's arithmetic is not touched. With the switch
at 1 the gate then measures distance to the true hard decisions; with the switch at 0 the helper copies unchanged and the code path
is today's. *Why not negate inside a wrapper around `osd_decode`:* the gate would keep reading the un-negated array, reject every
correct codeword, and the result would look like "no effect" (the failure the review and the ruling both name).

**D2. The switch is a non-static int in `ft8_shim.c`, read per call.** `int s_osd_sign_fix = 1;` beside `s_osd_nhard_max`
(`ft8_shim.c:~480`), `extern` in `decode.c`; `ft8_set_osd_sign_fix(int)` and `ft8_get_osd_sign_fix(void)` beside
`ft8_set_decode_params` (`:488`). Not TLS, not configuration, not API. The harness sets it before any decode and reads it back
before and after (the spec's V2). The value is a process-global for the same reason `nhard` is.

**D3. The managed side (Architect's A2).** P/Invoke declarations, `IFt8NativeInterop` members, `Ft8LibInterop` implementations and
the test double, plus `Ft8Decoder.SetOsdSignFix(int)` / `GetOsdSignFix()` for the replay harness. They are **not** called from the
daemon. The ABI sentinel (`ExpectedShimVersion`) and its test move with the shim number. No struct layout changes.

**D4. Shim number.** `origin/feat/sub-feas-stage-b` already carries `FT8_SHIM_VERSION 20260059` (Stage B item B2, not merged). The
Architect's ruling assumed 20260059 for this change; that number is taken on a live ref. This change takes the **next free
number above every live ref: 20260060** (re-check with `git grep` over `origin/*` when you start; use the next free above whatever
you find) and the step-3 build takes the one after. Whichever of B2 and this merges second renumbers itself, as step 4 and B2 agreed.

**D5. Existing tests that encoded the inverted behaviour are re-baselined only where they did, and each re-baseline is listed in
the PR with the reason.** A test that fails after the change is first assumed to be a real regression. Expect candidates among the
OSD gate tests (`D-009 R5`, calibrated on chance-valid output) and the `ft8_ldpc_decode_llrs` tests.

**D6. `nhard` stays 40 in this change (R4).** QA runs the TRAIN calibration on the built DLL; the Architect rules `n*`; the code
default (`Config` / `DecoderConfig.OsdNhardMax`) and any migration then change in a separate small commit. Check how
`decoder.nhard` is stored first: v0.54's `Nhard40MigrationApplied` marker in `JsonConfigStore.cs:~270` shows a stored value can
override a new default (HK-035). Not part of this change's first commit.

## Risks

- A fourth `osd_decode` caller added later reintroduces the bug: the no-bare-callers scan fails the build (task 3.2).
- The corrected OSD may accept more false words than the inverted one rejected, or fewer true words: that is the replay's question
  (spec §5.3), not the build's, and the switch exists so the two arms run in one binary.
- The unit test for the gate (task 3.1) is the guard against D1's failure mode; do not weaken it to payload-only.
