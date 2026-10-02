**User-facing:** yes

## Why

OpenWSFZ decodes substantially fewer FT8 signals per cycle than WSJT-X on the same off-air audio.
Three prior attempts at native signal subtraction (`fix-d001-pcm-sic`, `diag-d001-h3b-gfsk-sic`,
`diag-d001-three-pass-sic`, all 2026-06) were reverted: two independent production `0xC0000005`
crashes with zero accuracy gain, and a modulation/phase model mismatch that made the subtraction a
no-op. `openspec/specs/iterative-subtraction/spec.md`'s existing "Option C approval gate" requirement
(added after that history) required a Python PoC to demonstrate the precondition before any further
production code — that PoC has now run.

`SUB-FEAS` (`arch/subtraction-feasibility` / `qa/sub-feas`, 2026-09-27–28) measured a **different**
method from all three prior attempts — a data-aided fit of each already-decoded signal's true
position, frequency drift, and time-varying amplitude against the real recorded audio, rather than a
fixed-phase synthesis model — offline, in Python, on a real 40m off-air corpus. Stage 1 (residual
suppression depth as a proxy) FAILed its pre-registered PASS/PARTIAL bar. The Captain authorised
Stage 2 anyway, as a labelled diagnostic measuring the outcome directly: **net +8.89 pp [8.01, 9.75]
WSJT-X-corroborated new decodes**, after the Architect's own replay-vs-live control ruled out the
obvious artifact (`dc9fceed`, ruling `qa/rr-study/2026-09-28-1100-…`). That is roughly a quarter of
the OWS-vs-WSJT-X decode gap in the measured cycles.

On 2026-09-28 the Captain lifted the standing subtract-and-resynthesise BUILD prohibition for **one
scoped, flag-gated build** of this specific method — explicitly choosing to sequence the Architect's
recommended second-corpus/runtime-bar acceptance check **after** this build exists rather than before
it (full record: `qa/rr-study/2026-09-28-1601-qa-to-architect-sub-feas-build-authorised.md`). This
change is that scoped build.

## What Changes

- **A new, additive decode pass** (distinct from and unrelated to `K_MAX_PASSES`, the existing
  2-pass spectrogram-domain candidate-search mechanism this same capability already specifies):
  after the existing decode pipeline runs unmodified ("pass 0"), every one of pass 0's own decoded,
  re-encodable messages in that cycle is independently fit against the **original** PCM (position,
  linear frequency drift, residual frequency, time-varying complex amplitude envelope), all fits
  subtracted from one copy of the original buffer, and the existing decode pipeline run **once more,
  unmodified**, on that residual. This is a batch/parallel fit against the original signal, not
  sequential iterative SIC, and not a change to `K_MAX_PASSES`.
- **Ported, not redesigned:** the fit/subtract algorithm is a direct port of the already-validated
  method in `qa/rr-study/sub-feas/fitter.py` (`fine_fit_with_drift`, `lp_envelope`, `subtract`) and
  its per-cycle application in `qa/rr-study/sub-feas/stage2.py` — see `design.md` for the exact
  parameters and the dedup/merge rule (payload-bit comparison, not text; RR73 on-air-sentinel
  asymmetry handled per `stage2.py`'s own documented reasoning).
- **Flag-gated, default OFF.** A new decoder-settings config field, following the existing
  decoder-settings page convention (`openspec/changes/archive/2026-07-02-decoder-settings-page/`),
  gates the feature; with the flag OFF, decode behaviour is unchanged (byte-identical output) from
  today.
- **BREAKING (conditional):** `FT8_SHIM_VERSION` bump. Any `libft8` binary at the prior version is
  rejected by the managed ABI self-test after this change lands, matching this project's existing
  convention for any native shim change.
- **Supersedes, does not silently drop, the existing Option C gate requirement** in
  `openspec/specs/iterative-subtraction/spec.md` (synthetic-S7, ≥+5pp/10-trials PoC): SUB-FEAS's
  actual PoC used a different, real-corpus, decode-rate-corroboration methodology, Captain-approved
  on its own terms. The spec delta records what was actually measured and approved, rather than
  claiming the old criterion was literally met.
- **Corrects stale spec content found in passing:** `iterative-subtraction/spec.md`'s "Current
  deployed shim" line (`49ea303` / `FT8_SHIM_VERSION 20260009`) is many shim versions and months out
  of date (current: `main`=`20260051`, `decoding_improvement`=`20260054`). This change's spec delta
  corrects it; this is a documentation-debt fix incidental to this proposal, not new investigation.
- **Out of scope:** the pre-build second-corpus/runtime-bar acceptance the Architect originally
  recommended still happens — reordered to run against the finished native build (§ tasks.md), before
  any live A/B endurance run. It is not skipped, only resequenced, per the Captain's explicit choice.
- **Out of scope:** any change to `K_MAX_PASSES`, the existing spectrogram-domain soft-SNR
  suppression mechanism, or the site-6 `TryParseResponder` L1/L2 restriction (unrelated defect,
  #192, separate track).

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `iterative-subtraction`: adds a new, additive residual-decode-pass requirement (data-aided fit +
  time-varying envelope subtraction, distinct from `K_MAX_PASSES`); adds a config-flag requirement
  (default OFF); extends the existing heap-allocation-only requirement to the new per-signal
  template/envelope/FFT buffers; records the Option C gate's actual satisfaction (real-corpus PoC,
  not the original synthetic-S7 criterion) and the Captain's build-authorisation decision; corrects
  the stale "current deployed shim" record.

## Impact

- **Code (`src/`, `native/` — HK-011, Developer session required):** `src/OpenWSFZ.Ft8/Native/ft8_shim.c`
  and `.h` (new fit/subtract implementation and the residual decode-pass call; exact placement —
  native C vs the C# `Ft8Decoder` wrapper boundary — is an open decision for `design.md` to resolve,
  not pre-empted here), `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs`, `src/OpenWSFZ.Ft8/Ft8Decoder.cs`,
  `src/OpenWSFZ.Config/` (new flag), decoder-settings config UI/API surface, all three platform
  native binaries rebuilt.
- **Runtime risk (primary open question, not settled by this proposal):** the validated Python fit
  costs ~3.9 s/signal; a busy cycle can carry ~24 signals (~90+ s of Python-equivalent fitting work)
  against a 13 s hard / 30 s CI decode-cycle budget (`openspec/specs/ft8-decoder/spec.md:10`). A
  native port must be dramatically faster for this to be viable in the live path at all. Feasibility
  is unmeasured until this build exists — that measurement is one of this change's own acceptance
  gates (`tasks.md`), not a precondition already cleared.
- **Stability risk:** this is the 4th native subtraction attempt; the 1st caused two independent
  production crashes never caught by decode-rate testing. `design.md` and `tasks.md` both treat
  memory safety and a stability/stress gate as requirements independent of decode-rate accuracy.
- **Behaviour when the flag is ON:** decode output changes — additional decodes appear per cycle,
  sourced from a second pass over a subtraction residual. QSO panel, ADIF log, and hash-table
  occupancy are all downstream of decode output and are therefore affected when enabled.
- **Docs:** `openspec/specs/iterative-subtraction/spec.md` delta (this change);
  `REQUIREMENTS.md` gains an FR entry for the new config flag (design.md / tasks.md).
