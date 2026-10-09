# Developer handoff: #215 OSD-FIX — give the OSD fallback the sign it expects, and let its acceptance gate read the same array

**Date:** 2026-10-08. **From:** QA. **To:** Developer. **Priority:** 1 (the Captain, 2026-10-07 ~15:3xZ, Architect's window: *"not switching it off but actually fixing it … make it part of the build with prio 1"*). This is your **FIRST native item**; the COH fallback step-3 build stacks on top of this branch's tip.
**Spec (Architect):** `qa/rr-study/2026-10-07-1545-architect-to-qa-spec-osd-fix.md` (`a6079ff6` on local `arch/osd-fix`), as amended by QA's review and the Architect's ruling `qa/rr-study/2026-10-08-1545-architect-osd-fix-review-ruling.md` (`e6dd1272`). Read with `git show arch/osd-fix:<path>`. **Where the spec's R1/R2 and the ruling differ, the ruling governs** (this handoff follows the ruling).
**OpenSpec:** change `osd-sign-fix` (`proposal.md`, `design.md` D1 to D6, `specs/ft8lib-interop/spec.md`, `tasks.md`), on QA's local `qa/osd-fix-docs`. **`design.md` carries the FILE:LINE; read it first.**

## 1. Context

`osd_decode` reads positive = bit 0; the extractor and belief propagation produce positive = bit 1; the three callers pass the same array un-negated, so every OSD accept since shim 20260025 is a chance CRC-14 hit (#215). The acceptance gate after OSD (`nhard`, corr/norm) reads **the same array** as OSD, so today OSD and the gate are wrong together.

## 2. Branch

`feat/osd-sign-fix` off the current `origin/main`. NEVER commit to `main`. This is `native/` **and** `src/OpenWSFZ.Ft8` (shim bump, rebuild, interop). Merge is the Captain's (HK-010).

## 3. The one thing that must not go wrong (read twice)

**OSD and its gate must read the SAME, corrected array.** If a helper negates a private copy for `osd_decode` and the gate keeps reading `llr_for_osd`, the gate then measures agreement with the *inverted* decisions: a correct codeword shows `nhard` near 174 − true and corr < 0, every OSD decode is rejected, and the build looks like "no effect". Either write the negated values into a buffer the call site owns and pass that buffer to both, or negate `llr_for_osd` in place. The unit test of task 3.1 must **fail** if the gate is left on the old array (QA will mutate it).

## 4. Actions (details in `tasks.md`)

1. **Decisions first** (tasks 1.x): re-check the FILE:LINE; list every `osd_decode(` hit; helper form; **shim number** (see 5).
2. **Native** (tasks 2.x): helper at the three callers (`decode.c` `:666`, `:978`, `:1089`); `int s_osd_sign_fix = 1;` and `ft8_set_osd_sign_fix(int)` / `ft8_get_osd_sign_fix(void)` in the shim; header comments that state the old convention corrected; do **not** touch `native/ft8_lib_vendor/ft8/ldpc.c:9`. The setting is **not** wired to config, UI or API.
3. **Managed** (task 2.2/2.3, design D3): P/Invoke, `IFt8NativeInterop`, `Ft8LibInterop`, `Ft8Decoder.SetOsdSignFix/GetOsdSignFix`, the test double; the ABI sentinel and its test move with the shim number.
4. **Tests** (tasks 3.x): 3.1 sign test including the gate assertions (switch 1: payload equal, `nhard` ≤ injected flips, corr/norm > threshold; switch 0: no decode); 3.2 no-bare-callers scan (exempt the definition `:507`; every caller preceded by the helper on the array the gate reads); 3.3 all-ones word; 3.4 switch-0 characterisation; 3.5 interop round trip; 3.6 not-configurable. Existing tests re-baselined **only** where they encoded the inverted behaviour, each listed with the reason.
5. **Diagnostics** (task 4.1): per accepted OSD decode `nhard`, corr/norm, depth, batch, **aggregates only, no message text** (HK-037), if not already returned to the harness.
6. **Docs/version** (tasks 5.x): FR row and `FR-nnn:` test prefix (gate G3); `proposal.md` says **User-facing: no**; tell QA if you think a VERSION bump is warranted.
7. **Full unfiltered** `dotnet test OpenWSFZ.slnx` and `node --test web/js/*.test.js`; quote the exact commands and counts (a filtered-out suite is silent, not green, HK-022). Bracket the station config's mtime around the run. Tell QA before you start the full suite (CPU).

## 5. Shim number: a collision to know about

The Architect's ruling assumed **20260059**. `origin/feat/sub-feas-stage-b` (Stage B item B2, not merged) already holds `20260059`. Take the **next free above every number on any live ref** (`git grep -h "define FT8_SHIM_VERSION" origin/*`): at the time of writing that is **20260060**. The step-3 build takes the one after. Whichever of B2 and this merges second renumbers itself. Report the number you used.

## 6. Acceptance (what QA checks)

| Row | Predicate |
|---|---|
| **U1** | Existing suite green; each re-baselined test listed with the reason |
| **U2** | The sign test passes at switch 1 **with** the gate assertions, and fails when QA leaves the gate on the old array; no decode at switch 0 |
| **U3** | The no-bare-callers scan fails when QA adds a fourth `osd_decode(` caller |
| **U4** | Switch 0: same calls, results and order as the previous shim (characterisation) |
| **U5** | `git diff --stat origin/main -- native` shows only the helper, the three call sites, the switch exports and the shim bump; the shim literal identical everywhere; the DLL SHA-256 in `libft8.version.txt` matches the file; `check_native_version.py` OK on each binary built |
| **U6** | The switch is reachable from no config key, UI control or API field |

After U1 to U6, **QA** runs A-SIGN′ and A-OFF against your DLL, then the V2′ probe, the TRAIN calibration and TEST (spec §5). Those are QA's measurements and gate the merge (F-GO or F-NEUTRAL, spec §4); your build and unit tests do not.

## 7. Out of scope

Changing `nhard` or the corr threshold (QA calibrates, the Architect rules, a second small commit follows); the COH fallback (step 3); the OSD-off default; any default or UI change; BP, the extractor, subtraction, the early decode.

## 8. Report back (in this order)

1. The `osd_decode(` hit list with FILE:LINE and the helper's form. 2. The shim number and every file changed for it; the `libft8.dll` SHA-256 (actual) and the `check_native_version.py` output. 3. The new tests by name, the re-baselined tests with reasons, and the exact `dotnet test` / `node --test` lines with counts. 4. What you could not do, said plainly.
