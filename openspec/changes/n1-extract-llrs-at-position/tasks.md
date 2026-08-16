## 1. Native — decode.c probe

- [x] 1.1 Add `ftx_extract_likelihood_at()` to `native/ft8_lib_build/patched/ft8/decode.c` per
      design.md D1 — non-static, builds a synthetic `ftx_candidate_t` from the four lattice-index
      parameters, calls the existing `static ft8_extract_likelihood()` unchanged. Declare its
      prototype alongside `ftx_compute_candidate_llr_stats`'s (same non-static-probe declaration
      block, `decode.c:90-93` area, or the matching spot in `decode.h` if that's where the project
      keeps probe prototypes — confirm by checking how `ftx_compute_candidate_llr_stats` itself is
      declared and match it exactly).
- [x] 1.2 Confirm `ft8_extract_likelihood()`'s own body is byte-for-byte unchanged (diff against
      `git show HEAD:native/ft8_lib_build/patched/ft8/decode.c` before/after) — this change must
      not touch it, only call it.

## 2. Native — `ft8_shim.c`/`ft8_shim.h` export

- [x] 2.1 Add `int ft8_extract_llrs_at(const float* pcm, int pcm_len, float freq_hz, float
      time_offset_s, float* out_llr174)` to `ft8_shim.h`, documented (return codes 0/-1/-2/-3 per
      design.md D3, explicitly states it returns RAW pre-normalisation LLRs and that
      `ftx_normalize_logl` is deliberately not called).
- [x] 2.2 Implement it in `ft8_shim.c` per design.md D2's sketch: build the waterfall exactly as
      `ft8_decode_all` does (same `monitor_config_t` literal — copy it, do not refactor
      `ft8_decode_all` to share it, minimality), invert the `freq_hz`/`time_offset_s` mapping using
      `ft8_shim.c:1422-1427`'s own forward formula, guard `freq_offset` against `mon.wf.num_bins`
      (D3), call the new probe, return raw `log174`, wrap in the same `_MSC_VER`/`__try`/`__except`
      SEH pattern `ft8_decode_all` already uses (copy the shape, including the comment about `mon`
      needing to be declared before `__try`).
- [x] 2.3 Unit-check the inverse-mapping arithmetic in isolation before wiring it to the full
      export: for a handful of known `(freq_offset, freq_sub, time_offset, time_sub)` quadruples,
      run them through the *forward* formula (`ft8_shim.c:1422-1427`) to get `(freq_hz,
      time_offset_s)`, then through the new *inverse* code, and confirm the exact same quadruple
      comes back — covering at least one case with a negative `time_offset` (a candidate near the
      start of the buffer) to exercise the negative-modulo normalisation in design.md D2.
- [x] 2.4 Round-trip sanity check against a REAL candidate (design.md Risks, last bullet): take any
      candidate `ft8_decode_all` reports for a real capture (its own `freq_hz`/`dt`), feed those
      straight back into `ft8_extract_llrs_at`, and confirm the LLRs it returns are close to (ideally
      identical to, modulo the raw-vs-normalised difference) what a raw-LLR-capture run would have
      recorded for that same candidate at its own grid position — this is the mechanical check that
      the new inverse mapping actually lands on the SAME lattice point production already uses, not
      an adjacent one off by a rounding convention.

## 3. Export list, version bump, build

- [x] 3.1 Add `/EXPORT:ft8_extract_llrs_at` to `native/ft8_lib_build/rebuild_shim.bat`'s link step
      (design.md D4) — confirm no other line in that export list changes.
- [x] 3.2 Bump `FT8_SHIM_VERSION` in `ft8_shim.h` from `20260041` to `20260042`, and
      `ExpectedShimVersion` in `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs:281` to match.
- [x] 3.3 Rebuild Windows x64 (`rebuild_shim.bat`); record the new DLL's SHA256. Confirm via
      `dumpbin /exports` that `ft8_extract_llrs_at` is present and every previously-exported symbol
      is unchanged (same symbol set as `20260041` plus this one addition).
- [x] 3.4 Confirm CI (`.github/workflows/ci.yml`) rebuilds Linux x64 and macOS ARM64 from the same
      updated `ft8_shim.c`/`decode.c` without a workflow-file change — the export mechanism on those
      platforms is compiler default visibility, not an explicit `/EXPORT` list (`build_linux.sh` has
      no `/EXPORT`-equivalent lines, confirmed while drafting this proposal). If CI needs a change to
      pick up the new symbol, make it here and say so in the report; otherwise state explicitly that
      no CI change was needed and why.

## 4. Byte-identical production-replay check

- [x] 4.1 Re-run the same production-decode-equality replay R1/R1b used (≥200 contiguous cycles,
      pinned corpus, pre-change `20260041` vs. new `20260042`,
      `qa/cycleframer-alignment-replay/r0_ac1_ac2_replay.py` + `r0_ac1_ac2_diff.py` or their current
      equivalents) to confirm **zero** decode-output differences. This is the mechanical proof this
      change is purely additive, not an assertion.

## 5. Tests

- [x] 5.1 Add a native or Python smoke test (design.md Open Questions — either satisfies this)
      exercising `ft8_extract_llrs_at` against a real-binary decode: (a) a valid position returns
      `rc=0` and 174 finite floats; (b) a `pcm_len` mismatch returns `-1`; (c) a frequency far outside
      `[200, 3000)` Hz returns `-3`; (d) the round-trip check from task 2.4 is captured as a
      repeatable test, not a one-off manual check.
- [x] 5.2 `dotnet build`: 0 warnings. `dotnet test`: full suite green — this change adds no C# code
      (design.md D5), so this is a regression check, not new coverage; confirm nothing in
      `Ft8LibInterop`'s ABI self-test path broke from the version bump alone.

## 6. Reporting and wrap-up

- [x] 6.1 Write the QA→Architect report: new DLL SHA256 (Windows; Linux/macOS if task 3.4 rebuilt
      them locally, otherwise note CI will produce them), shim `20260042` confirmed via
      `ft8_lib_version_check()`, task 2.3/2.4's round-trip results, task 4.1's replay result (must
      read zero differences before this is reported as safe), and explicit confirmation that no
      existing exported symbol's signature or behaviour changed.
- [x] 6.2 State plainly whether N1's harness (§4-§5 of the N1 spec: population, pairing, the gate,
      the mandatory sign unit test) is now unblocked. It should be, once 4.1 and 5.1 are green — say
      so, or say what's still missing.
- [x] 6.3 Stop. No push, no merge, no `pre_merge_check.py` (HK-014/HK-010/HK-006) — the Captain
      reviews the diff and decides on merge; this task does not declare readiness unprompted.
