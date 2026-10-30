> **Status note (QA, 2026-10-30).** Authorised by the Captain ("go", after "go, write the build spec"). Build spec `qa/rr-study/2026-10-30-1322-architect-to-qa-build-spec-late-sub-l1p.md` with section 7 Amendment 1 (`33c50bd6`, `arch/late-sub`). Developer commit `b1d8a06e` (`dev/late-sub-round`), reviewed by QA (HK-039 record next to the build spec). Nothing pushed.

## 1. Implementation (Developer, `src/`; C# only) - done in `b1d8a06e`

- [x] 1.1 `decoder.lateSubtractionRound` (bool, absent or false = off): `DecoderConfig.LateSubtractionRound`, a volatile field on `Ft8Decoder`, set by the daemon before the first window and on save, read once per window; config overlay (HK-035); no Settings control.
- [x] 1.2 The round runs on Deep only, with the fallback ran, after the fallback's batch, on the buffer `CohFallbackAudioSelector.Select` returns (skipped when it would return the original audio).
- [x] 1.3 The fit list is the natives behind the decodes `MapNative` published in batches 3 and 4 (F1); `alsoKnown` is batch-1 natives plus the raw batch-2 natives; one `SubtractionPass.RunThirdPassAsync` call with the remaining cycle budget; no copy of the buffer (`SubtractionPass.cs:425`, doc `:215`).
- [x] 1.4 New decodes go through `MapNative(..., PathResidual)` with the cycle's text set and out as batch 5 through the existing batch delegate, only when non-empty (F4). No new callback.
- [x] 1.5 One `Late subtraction round:` log line per Deep cycle while ON, with `fbEndMs`.
- [x] 1.6 **No native change**: `git diff --stat <base> -- native/ src/OpenWSFZ.Ft8/Native/` empty; `libft8.dll` SHA-256 `1ba8dc3d6a7d032764b3eaf65e7e5ef850c56b35569ad880b53d6708524db914`.

## 2. Tests (Developer; no fixed sleeps, TESTING_STRATEGY section 11) - done

- [x] 2.1 OFF is a no-op; each skip reason; abandoned and failed publish nothing and do not throw; batch-5 number and order; the fit list (the F1 case); the refusal count; the hash-table ordering; the config key (absent, round trip, overlay); the pump routes batch 5.

## 3. Housekeeping (Developer) - done

- [x] 3.1 `VERSION` 0.67 to 0.68 everywhere the gates check; `check_version_bump.py` and G9a/G9b.
- [x] 3.2 `REQUIREMENTS.md` FR-102 and changelog row 1.64; every requirement in the delta spec has scenarios; `openspec validate late-sub-round --strict`.

## 4. Acceptance (QA; PC first, then sol; order matters)

- [ ] 4.1 HK-039 review record of the Developer's commit as a `qa/rr-study/*code-review*.md` FILE with `Reviewed-commit:` and `Verdict:` BEFORE any acceptance run (hook-enforced).
- [ ] 4.2 **B-TOOL** (Replay81 carries batch 5, `bc5e844d`): the tool's own checks pass against the real product build.
- [ ] 4.3 **B-NAT** native diff empty AND DLL SHA-256 equal to the pin.
- [ ] 4.4 **B-OFF** setting OFF, refset night `20260925_2010`, 1,200 cycles, one process from cycle 1: the published output (batches 1 to 4, every field) is byte-identical to `raw_main\main` on the columns both sides have, 1,200 of 1,200 cycles.
- [ ] 4.5 **B-EQ-1** setting ON (Amendment F3): up to and including the first cycle with a batch 5, batches 1 to 4 identical to B-OFF's; afterwards identical modulo `<...>` tokens with equal row counts; every cycle that differs only in a hashed token is listed; any other difference stops the row.
- [ ] 4.6 **B-EQ-2** setting ON: batch 5 equals the harness's L1' refset rows (`b7c17464`) cycle by cycle on plain text, 0 cycles differ; hashed-text differences listed, allowed. If it fails, stop at the first differing cycle and reconcile; neither side is assumed right.
- [ ] 4.7 **B-AB** residual pass, third pass and fallback abandoned in ON equal OFF; the round's own abandoned count reported. Descriptive: the round's `elapsedMs` median, p90, max, and `endMs` max.
- [ ] 4.8 **Third night** `20260930_1930` on sol (800 cycles, stride 3, offset 1; Original arm 200 cycles, with the HK-026 condition): rows V-3N-AB, V-3N-REF, N-GO, N-STOP, U-OK, U-FAIL, H-SHARE; ACCEPT-3N iff N-GO and U-OK and H-SHARE not fired; FAIL-3N iff N-STOP or U-FAIL; OPEN-3N otherwise. Bars BAR_G 0.5 pp, U_bar_G 0.021, h 0.5; cycle bootstrap B = 2000, seed 20261030. Timing reported, not a veto. Freeze commit (selection, classes, `.so` SHA-256, build commit, analysis code) before the first replay output.
- [ ] 4.9 `pre_merge_check.py` from a clean checkout of the exact commit (HK-006) before any push.
- [ ] 4.10 The Captain's push go (HK-033), CI green on the branch (macOS included), the Captain's merge sign-off (HK-010). Only ACCEPT-3N lets the Captain be asked about merging and, separately, about default ON (a new era).
