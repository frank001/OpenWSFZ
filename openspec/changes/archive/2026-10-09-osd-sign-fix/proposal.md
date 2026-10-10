**User-facing:** no

## Why

The native decoder's ordered-statistics (OSD) fallback reads its input with the **opposite sign** to everything that feeds it. The
LLR extractor and belief propagation use positive = bit 1; `osd_decode` (`native/ft8_lib_build/patched/ft8/decode.c:507`, header
comment `:501`, hard decision `llr < 0 ? 1 : 0`) uses positive = bit 0; the three call sites hand it the same array un-negated.
Since shim 20260025 every OSD accept has therefore been a chance CRC-14 hit (GitHub #215). QA found it on 2026-10-06 (forced OSD
on 50 real rows: **0/50** true payloads as shipped, **16/50** with the sign negated); the Architect verified it from source.

Removing the inverted OSD gains **+0.074 pp** [+0.020, +0.146] (OSD-OFF, ruled O-GAIN), so the defect is small in decode-rate terms.
The Captain reversed the earlier park on 2026-10-07 (~15:3xZ, the Architect's window): *"not switching it off but actually fixing
it. this is hurting the first pass decode. make it part of the build with prio 1."* The Architect's spec is
`qa/rr-study/2026-10-07-1545-architect-to-qa-spec-osd-fix.md` (`arch/osd-fix` `a6079ff6`), amended by QA's review
(`qa/rr-study/2026-10-08-1540-qa-to-architect-osd-fix-review.md`) and the Architect's ruling
(`qa/rr-study/2026-10-08-1545-architect-osd-fix-review-ruling.md`, `e6dd1272`); both are on local branches until pushed, read them
with `git show arch/osd-fix:<path>`.

Two facts shape the build:

- **The acceptance gate reads the same array as OSD**, so OSD and the gate are wrong *together* today (`decode.c:680-683`,
  `:989-992`, `:1098-1101`). A fix that negates a private copy for OSD alone leaves the gate on the old array: every correct
  codeword then fails the gate and the build looks neutral. One array, read by both, is the requirement (design D1).
- **`nhard` 40 and corr 0.10 were set on the inverted output** and do not carry over; the value is re-derived by QA on the corrected
  output (spec §5.2) and changed, if at all, in a second small commit.

## What Changes

- `native/ft8_lib_build/patched/ft8/decode.c`: one helper writes OSD's convention into a buffer the call site owns; the three
  `osd_decode(` callers and their gate blocks read that buffer. A process-global switch (default **corrected**) selects the old
  behaviour bit-for-bit.
- `ft8_shim.c/.h`: `ft8_set_osd_sign_fix(int)` and `ft8_get_osd_sign_fix(void)`; **`FT8_SHIM_VERSION` bump**.
- `src/OpenWSFZ.Ft8`: P/Invoke declarations, `IFt8NativeInterop` / `Ft8LibInterop` / `Ft8Decoder` access and the test double
  (harness use only: **not** wired to config, UI or API).
- Tests: the sign test on a known codeword (including the gate), a no-bare-callers source scan, the all-ones word, the switch-0
  characterisation (flag-OFF-like identity), re-baselines only where an existing test encoded the inverted behaviour.
- Nothing else changes: not BP, not the extractor, not subtraction, not the early decode, not any default.

## Out of scope

The `nhard` choice (QA's calibration on TRAIN, the Architect's ruling, then a one-line default change in a second commit); any
decode-rate claim; the COH fallback step-3 build, which stacks **on top of** this change's tip; the OSD-off default (parked).

## Capabilities

### Modified Capabilities

- `ft8lib-interop`: ADDED requirements for the OSD sign convention and the harness-only switch exports.
