# Developer task: PAYLOAD-FIT, the lean decoder fits every result from its payload (drop the text gate)

**Date:** 2026-11-27
**Prepared by:** QA, from the Architect's spec `docs/decoder-rebuild/spec-payload-fit.md` §2 (`arch/decoder-rebuild` `b28f6c6e`; the file is not on `main` yet, it rides in the next sprint PR, so this task repeats what you need) and QA's R1-R4 split (`qa/rr-study/results/2026-11-26-lc-base/r1r4-split-result.md`, QA `2dda1d07`)
**Audience:** Developer (to execute)
**Authorised by:** the Captain, 2026-11-27 ("go. write it").
**Status:** Proposed. HK-011: `native/` and `src/` changes for a separate Developer session. Hand back the commit; QA reviews it (HK-039). **Do not push, open a PR or merge**; QA pushes (once, in the sprint PR).
**Branch:** `feat/payload-fit`, from `main` (`326538fb` or later; check `git fetch origin`). `feat/sub-probe` is merged (#298), so branch from `main`, not from it. You can start now.
**Test requirement (the Captain's rule, 2026-11-24):** unit tests and QA's review. No replay by you. Read the per-assembly "Passed: N" lines (HK-022).

---

## 0. Why

QA's R1-R4 split shows the largest reason a K2 neighbour (a decoded signal beside a missed weak one) is never subtracted is the **text gate**: 71 / 17 / 50 % of the never-subtracted K2 neighbours on S40 / H40 / H20 (112 / 18 / 134 cases). 91 to 96 % of those have a `<...>` hash placeholder in the text; the rest have fewer than three tokens.

The code, at `main` `326538fb`, `native/ftz_decoder/ftz_decoder.c`:

- `:744` `ftz_text_reencodable` is false if the text contains `<` or has fewer than three space-separated tokens; `:1501` stores it in `reenc[slot]`.
- `:1029` the round loop does `if (!reenc[k]) continue;` when it chooses what to fit.
- `:1076` the fit takes its tones from `ft8_encode(res_pl[k], ...)`: the decoded 77-bit **payload** (stored at `:1500`), not the text.

The gate came from the classic `SubtractionPass.IsReencodable`, which built the tones from the text and so could not pack `<...>`. The lean fit never reads the text, and the payload holds the hash bits exactly as received, so `ft8_encode` returns the tones that were sent whether or not the hash resolves. **In lean the gate protects nothing.**

## 1. The change (lean only)

| Id | What |
|---|---|
| **P1 Remove the gate** | At `:1029` delete `if (!reenc[k]) continue;`. Every result not yet subtracted then goes through the step-2e rule (`ftz_fit_needed`) **unchanged**. |
| **P2 Dead code** | Remove what becomes dead (`reenc`, its allocation, `ftz_text_reencodable`) **or** keep it where a test or the probe still reads it. Your choice; say which and why in the report. |
| **P3 Nothing else changes** | Not the step-2e skip rule (`:1031`), the rounds, the deadline reserve, the DR-3 duplicate rule, the probe, the candidate search, or any default. **No new flag**: the change is the whole decoder change. The classic decoder (`SubtractionPass`, C#) **keeps its gate**: it encodes from the text, and it is no longer the default. |
| **P4 Versions** | The shim version moves (a rebuilt `libft8.dll`, as in 2e, DR-3 and SUB-PROBE; state the new number and the SHA256). Run `tools/check_version_bump.py` and follow what it says about `VERSION` (this changes what the default decoder produces, so QA expects it may demand a bump; if it does, bump as DR-3 did and keep the doc references in step, G9a). The OpenSpec change `lean-decoder` gets a short section (tasks and delta spec, strict). `check_native_version.py` for the Windows binary; the Linux and macOS libraries are CI's. |

## 2. Tests (unit tests; the spec's §2)

1. **(a) A `<...>` result is fitted.** A synthetic message whose unpacked text carries a hash placeholder (a hashed call that is **not** in the hash table of a fresh process), with a **failed candidate inside its patch window** `[f - 50, f + 100]` Hz of it (so the step-2e rule asks for the fit). With the probe on, there is a `SUB` row at its position and the round's `n_fits` counts it. **Run it on `main` first and say that it fails there** (red before, green after): that is the proof it tests the gate. Build the message with the existing modulator test helpers (as the two-copy fixture of `LeanEngineDuplicateRuleTests` and the SUB-PROBE test `LeanEngineProbeTests` do). If the helpers cannot make a hashed-call message directly, build the 77-bit payload by hand (a type-1 message whose callsign field carries the hash) and say how. **NFR-021: only `Q`-prefix synthetic callsigns.**
2. **(b) The same for a result with fewer than three tokens**, if the helpers can build one. If they cannot, say so: (a) is enough.
3. **(c) Nothing else moved:** the existing determinism tests (1, 2, 4, 8 and 16 threads give the same bytes) and the DR-3 duplicate tests, the lean golden tests and the SUB-PROBE tests pass **unchanged**. If a golden test changes because a `<...>` result is now fitted, **do not edit the golden**: stop and report which one and by how much (QA decides).
4. **Run each project separately** and quote each "Passed: N": Config, Web, Daemon, Ft8 (the Ft8 project also at `DOTNET_PROCESSOR_COUNT=4`), and the JS runner. The ASan + UBSan job and the fuzz (10,000 runs) cover the native side; run the native fuzz locally if you can.

## 3. After your hand-back (QA, not you)

HK-039 review, `pre_merge_check` (once, at the sprint PR), then **one replay**: exactly the SUB-PROBE arm (lean, 16 threads, `--lean-probe 1`, LC-BASE's L flags) on S40 (170 cycles), H40 and H20 (240 each), about 20 minutes, against the SUB-PROBE runs already on disk as the baseline. QA reports: Table 1 with the deltas, the cost (CPU-s per cycle, `last_p95`, fits, `fitNone`, rounds), how many of the 112 / 18 / 134 R1 cases now have a `SUB` row and a matched T, the new never-subtracted split (R1 should be 0), and the knock-on gains and losses. No bars; the Captain decides.

## 4. Out of scope

XC (the cross-cycle results; parked until these numbers are in), a change to the step-2e rule, the duplicate rule, the decode step (BP / bit metrics), the probe, the daemon, the Settings page, the classic decoder, any default.

## 5. Report back

The commit SHA; the new shim number and the `libft8.dll` SHA256; the per-project "Passed: N" lines (Ft8 also at 4 processors) and the JS result; **the red-on-`main` result of test (a)** (the failing assertion); what you did with `reenc` (P2); and anything that differs from the neighbouring tests' pattern.
