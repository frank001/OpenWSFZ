## Context

N1 (`qa/rr-study/2026-08-15-1840-architect-to-qa-N1-ber-at-refined-position-spec.md`) is a paired
BER measurement: for each candidate-present-and-failed row, extract hard-decision LLRs twice on the
identical audio — once at the candidate's own grid position (control, "GRID"), once at grid +
`ft8_refine_candidate`'s reported `(Δf, Δt)` (treatment, "REFINED") — and compare BER against a
bar already measured and reproduced (`B50 = 11.3%`, this branch's own reproduction landed at
11.65%, within the pre-registered 1 pp tolerance).

The existing BER instrument, `c2_phase2c_ber_measurement.py` (recovered from `d001-c4-min-score-
sweep`'s `7a604b4`, now on this branch), only *reads back* LLRs a decode run already captured at a
candidate's own grid position (`candidate_diag.csv`'s `llr174` column, itself produced by a
raw-LLR-capture export — `ft8_get_last_candidate_llr` — that also does not exist on this branch;
see the N1 §3.1 reproduction report). Neither existing mechanism can extract at an arbitrary
caller-supplied position. N1 needs that, and only that.

`ft8_extract_likelihood()` (`patched/ft8/decode.c:353`) is the exact, already-correct extraction
logic — it is what production calls, unmodified, for every candidate. It is `static`. The
project already has a working pattern for exposing a `static` decode.c routine to `ft8_shim.c`
without changing its signature or its callers: `ftx_compute_candidate_llr_stats()`
(`decode.c:90-93`), a non-static probe added specifically to let `ft8_shim.c` call in without
touching `ftx_decode_candidate`'s own call sites. This change follows that exact pattern.

The forward mapping from a candidate's lattice indices to physical units is already implemented,
once, at `ft8_shim.c:1422-1427` (where a decoded `FT8Result`'s `freq_hz`/`dt` are computed from
`cand->freq_offset`/`freq_sub`/`time_offset`/`time_sub`):

```c
float freq_hz = (mon.min_bin + cand->freq_offset + (float)cand->freq_sub / mon.wf.freq_osr)
              / mon.symbol_period;
float dt      = (cand->time_offset + (float)cand->time_sub / mon.wf.time_osr)
              * mon.symbol_period;
```

This change needs the **inverse**: given `(freq_hz, time_offset_s)`, find the nearest
`(freq_offset, freq_sub, time_offset, time_sub)` quadruple on the same lattice.

## Goals / Non-Goals

**Goals**
- Let a caller extract raw, pre-normalisation LLRs at any `(freq_hz, time_offset_s)` position,
  using the exact extraction code production uses, on the exact lattice production candidates
  already live on.
- Keep the diff to the smallest addition that satisfies N1 — one native export, one decode.c probe,
  no other file touched except the export list and the version constant.
- Byte-identical production decode behaviour before and after — provable, not asserted (task 6).

**Non-Goals**
- **Not** a continuous-position extractor. The waterfall itself is discretised at `K_FREQ_OSR` /
  `K_TIME_OSR` (currently 2×2); this export snaps to the nearest lattice point exactly as every
  existing candidate already does. See Risks below — this is intentional and matches what N1's
  GRID arm is measured on too, so the paired contrast stays apples-to-apples.
- **Not** a change to `K_FREQ_OSR`/`K_TIME_OSR` — barred on P3's own evidence (board), and out of
  scope regardless.
- **Not** a change to candidate selection, `ft8_decode_all`, or any existing decode path.
- **Not** C# interop wiring in this change (Decision D5).
- **Not** N1's harness itself (population, pairing, gate, sign unit test) — that is QA's own
  follow-on work once this export exists and its DLL is validated.

## Decisions

### D1 — new non-static probe in `decode.c`, not a visibility change on the existing function

Add `ftx_extract_likelihood_at()`, matching the existing non-static-probe pattern:

```c
/* Non-static diagnostic probe -- called from ft8_shim.c (N1, shim 20260042).
 * Builds a synthetic candidate at the caller-supplied lattice position and
 * runs the SAME static ft8_extract_likelihood() every production candidate
 * uses -- no change to that function, no change to its existing callers. */
void ftx_extract_likelihood_at(
    const ftx_waterfall_t* wf,
    int16_t time_offset, int16_t freq_offset,
    uint8_t time_sub,     uint8_t freq_sub,
    float*  out_log174 /* [FTX_LDPC_N] */)
{
    ftx_candidate_t cand = {
        .score = 0,
        .time_offset = time_offset, .freq_offset = freq_offset,
        .time_sub = time_sub,       .freq_sub = freq_sub,
    };
    ft8_extract_likelihood(wf, &cand, out_log174);
}
```

`ft8_extract_likelihood` itself is untouched — same reasoning R1/R1b used for
`ft8_refine_candidate`: instrumentation of existing logic, not a modification of it. Declare the
probe's prototype in `decode.h` (or wherever `ftx_compute_candidate_llr_stats` is declared) so
`ft8_shim.c` can call it without a forward declaration hack.

### D2 — `ft8_shim.c` wrapper: build the waterfall, snap the position, call the probe, return raw LLRs

```c
int ft8_extract_llrs_at(
    const float* pcm, int pcm_len,
    float freq_hz, float time_offset_s,
    float* out_llr174 /* [FTX_LDPC_N] */)
{
    if (pcm_len != FT8_EXPECTED_SAMPLES || out_llr174 == NULL) return -1;

    monitor_t mon;
#ifdef _MSC_VER
    __try {
#endif
    monitor_config_t cfg = {
        .f_min = 200.0f, .f_max = 3000.0f,
        .sample_rate = FT8_SAMPLE_RATE,
        .time_osr = K_TIME_OSR, .freq_osr = K_FREQ_OSR,
        .protocol = FTX_PROTOCOL_FT8
    };
    monitor_init(&mon, &cfg);
    for (int pos = 0; pos + mon.block_size <= pcm_len; pos += mon.block_size)
        monitor_process(&mon, pcm + pos);

    /* Inverse of ft8_shim.c:1422-1427's forward mapping. */
    float raw_freq_bin = freq_hz * mon.symbol_period - mon.min_bin;
    float raw_time_bin = time_offset_s / mon.symbol_period;

    long total_freq_sub = lroundf(raw_freq_bin * mon.wf.freq_osr);
    long total_time_sub = lroundf(raw_time_bin * mon.wf.time_osr);

    long freq_offset = total_freq_sub / mon.wf.freq_osr;
    long freq_sub     = total_freq_sub % mon.wf.freq_osr;
    long time_offset  = total_time_sub / mon.wf.time_osr;
    long time_sub      = total_time_sub % mon.wf.time_osr;
    /* C's truncating %/ can give a negative sub for a negative dividend --
       normalise so freq_sub/time_sub stay in [0, osr). */
    if (freq_sub < 0) { freq_sub += mon.wf.freq_osr; freq_offset--; }
    if (time_sub  < 0) { time_sub  += mon.wf.time_osr;  time_offset--; }

    /* D3 guard: get_cand_mag() does no bounds checking on freq_offset before
       indexing wf->mag -- an out-of-[0,num_bins) value is an out-of-bounds
       read, not a graceful failure. Production never hits this because
       ftx_find_candidates() only enumerates in-range positions; a caller-
       supplied position has no such guarantee. */
    if (freq_offset < 0 || freq_offset >= mon.wf.num_bins) {
        monitor_free(&mon);
        return -3;
    }

    ftx_extract_likelihood_at(&mon.wf,
        (int16_t)time_offset, (int16_t)freq_offset,
        (uint8_t)time_sub, (uint8_t)freq_sub,
        out_llr174);
    /* Deliberately NOT calling ftx_normalize_logl() -- N1 and
       c2_phase2c_ber_measurement.py both require raw, pre-normalisation
       LLRs; normalisation is a positive scale factor and does not change
       hard-decision sign, but the harness's own documented convention is
       to work from the raw value. */

    monitor_free(&mon);
    return 0;
#ifdef _MSC_VER
    } __except(EXCEPTION_EXECUTE_HANDLER) {
        return -2;
    }
#endif
}
```

(Sketch, not final code — the Developer session should follow `ft8_decode_all`'s own established
SEH-containment shape exactly, including its comment about `mon` needing to be declared before
`__try`, rather than re-deriving it.)

Out-of-range `time_offset`/`time_sub` is **not** guarded the same way, because
`ft8_extract_likelihood` already bounds-checks `cand->time_offset + sym_idx` against
`wf->num_blocks` per-symbol and zero-fills gracefully (`decode.c:365-372`) — that existing
behaviour is sufficient and is not duplicated here. Only the `get_cand_mag()` base-pointer
computation (called once, unconditionally, before that per-symbol loop) is unguarded for
`freq_offset`, which is why D3 adds exactly one check there and no other.

### D3 — three return codes, not silent clamping

`0` success · `-1` bad `pcm_len` or null output pointer (matches `ft8_decode_all`'s own `-1`
convention) · `-2` SEH-caught internal fault (matches `ft8_decode_all`'s own `-2`) · `-3` requested
position's frequency bin falls outside the waterfall's valid range. `-3` is new precisely because
this export, unlike `ft8_decode_all`, accepts an arbitrary caller-supplied position rather than one
`ftx_find_candidates` already validated — silently clamping would let N1's harness misattribute a
GRID+refiner-Δf that has walked off the passband edge to a real in-band extraction. The harness
(N1's own future work) must treat `-3` as "no candidate available at this position," matching how
`measure_population()` already treats `no_candidate_or_llr` today.

### D4 — export list and version

Add `/EXPORT:ft8_extract_llrs_at` to `native/ft8_lib_build/rebuild_shim.bat`'s link step (immediately
after the existing `/EXPORT:ft8_refine_candidate` line — the file's existing exports are otherwise
untouched). Bump `FT8_SHIM_VERSION` `ft8_shim.h`) and `ExpectedShimVersion`
(`Ft8LibInterop.cs:281`) from `20260041` to `20260042`. Pin and assert the new DLL's SHA256 in the
task-6 report — never inferred from the version label alone (board's own standing instruction,
fired against `d001-*` branches' colliding version integers more than once).

### D5 — no C# interop wiring, and why that's a considered choice here (unlike R1/R1b)

R1/R1b's `ft8_refine_candidate` — also diagnostic-only, also no production call site — *did* get
full `Ft8LibInterop`/`IFt8NativeInterop` P/Invoke wiring plus test-double updates across all
existing fakes. This change does not do that, for three reasons:
1. **N1's own spec never asks for it.** §3.2 specifies the native export signature and stops there;
   it frames the consumer as the Python QA harness, the same way the (now-precedented, on
   `d001-c4-min-score-sweep`) raw-LLR-capture family (`ft8_get_last_candidate_llr` and siblings)
   was never given C# bindings either, despite being used repeatedly by W1/N1's own precondition.
2. **No managed consumer exists or is proposed.** R1/R1b's wiring earned its keep because
   `RefineCandidateTests.cs` and the validation harness's C#-adjacent tooling needed it; nothing
   analogous is proposed for this export.
3. **Minimality.** Per proposal.md's own framing ("scoped as narrowly as it can be" — the N1 spec's
   words), skipping a managed surface nobody will call keeps the diff to native files only, which
   is easier to review against "no change to what production does."

If the Captain wants this wired into C# anyway (for consistency with R1/R1b, or because a future
arm turns out to need it from managed code), that is a small, separable follow-up — flagged in
Open Questions, not decided here.

## Risks / Trade-offs

- **Lattice-snap, not continuous extraction.** If `ft8_refine_candidate`'s `(Δf, Δt)` is smaller
  than half a lattice step, REFINED can snap to the *same* `(freq_offset, freq_sub, time_offset,
  time_sub)` as GRID — `d_ber` for that row is then mechanically ≈0, correctly, not an instrument
  artefact. N1's own ROW 0d (median `|Δf|`/`|Δt|` below a floor ⇒ "the treatment isn't a treatment")
  already exists to catch this at the population level; nothing new is needed here beyond making
  sure the harness reports the *snapped* position actually used, not just the refiner's raw
  `(Δf, Δt)`, so a reviewer can tell the two apart per-row if ROW 0d is close to its bar.
- **`get_cand_mag`'s missing bounds check is pre-existing, not introduced here** — production never
  exercises it because `ftx_find_candidates` only enumerates valid positions. This change is the
  first caller that can supply an invalid one, hence D3. Worth flagging to the Architect as a
  latent robustness gap in `decode.c` independent of this change, not something to fix here (fixing
  `get_cand_mag` itself would touch decode-path code this change deliberately avoids touching).
- **Two independent inverse-mapping implementations** (this change's C code and any future
  Python-side sanity check) can drift. Task 3 asks for a mechanical round-trip test — feed a real
  candidate's own reported `(freq_hz, dt)` back through the new export and confirm it recovers
  that exact candidate's `(freq_offset, freq_sub, time_offset, time_sub)` before trusting it for
  anything else — cheaper than a second implementation and catches a transcription error directly.

## Migration Plan

Purely additive; no migration. Existing candidates, decode output, and every existing exported
symbol are unaffected — task 6's byte-identical production-replay check (same shape as R1/R1b's
task 6.5) is how that gets proven rather than assumed.

## Open Questions

- Should `ft8_extract_llrs_at` get C# `Ft8LibInterop` wiring for consistency with R1/R1b, even
  though nothing calls it from managed code today? Left to the Captain — D5 states the case for
  not doing it now; reversing that later is a small follow-up, not a rework.
- Should the round-trip sanity check (Risks, last bullet) be a native unit test, a Python harness
  smoke test, or both? Left to the Developer session's judgement in task 3 — either satisfies the
  acceptance criterion, Python is cheaper to write given the Python harness will exercise this
  export directly anyway.
