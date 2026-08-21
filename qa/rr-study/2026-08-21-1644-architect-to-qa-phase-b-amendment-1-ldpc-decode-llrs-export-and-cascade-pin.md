# Architect → QA: PHASE B **AMENDMENT 1** — add B4 (`ft8_ldpc_decode_llrs`, diagnostic-only) and the C1 cascade pin

**Author:** Architect · **UTC:** 2026-08-21 16:44Z
**Amends:** `qa/rr-study/2026-08-21-1525-architect-to-qa-spec-phase-b-origin-and-fusion-fix-and-row0g-rerun.md`
**Authority:** Captain's ruling 2026-08-21 16:4xZ — *fold C2 into the Phase B Developer session* (option (a)),
and *draft C3 after C2* (deferred, not specced here).
**Origin:** `qa/rr-study/2026-08-21-1634-architect-to-qa-ruling-stage1re-n5-fbreak-and-null-calibration.md` §4.

🔴 **This is a POINTER AMENDMENT, not a rewrite.** Everything in the 1525Z spec stands exactly as
written — B1, B2, §4's version mechanics, §5's ordering, §6's ROW 0g pre-registration, §9's
prohibitions. This document adds **one inert export (B4)** and **one docs edit (C1)**. If any
sentence here appears to conflict with the 1525Z spec, **the 1525Z spec wins and you escalate.**

---

## A. Why B4 exists, in one paragraph

Every limb-2 number this project has ever produced — N5's `0/403`, Stage 1RE's `f_cross = 2.47%`,
its `f_break = 60.66%`, its `f_net = +0.6227%` — is a crossing of **B50, a modelled BER threshold**,
not a decode. The 1634Z ruling establishes that this metric has no null: flux across a fixed
threshold in a population that is **14,934 rows above it and 455 below** is positive by
construction, and an information-free placebo out-reads the real result 500/500. **B4 replaces the
model with the machine.** `bp_decode`, `ftx_normalize_logl`, `osd_decode` and the CRC-14 check are
already in the tree and already constitute production's own definition of "decoded". Exposing them
on a caller-supplied LLR vector converts every one of those numbers into a **CRC-verified message
count**, on rows already measured — no new WAV pass, no new population, no new anchor.

---

## B. B4 — the export

### B4.1 Where it lives (this is forced, not a preference)

- `bp_decode` is public — `native/ft8_lib_vendor/ft8/ldpc.h:17`.
- 🔴 **`ftx_normalize_logl` (`decode.c:391`) and `osd_decode` (`decode.c:507`) are BOTH `static` in
  `decode.c`.** The probe therefore **must live in `decode.c`**, exactly as
  `ftx_extract_likelihood_at` (`decode.c:838`) already does, with a thin wrapper in `ft8_shim.c` —
  the established two-file pattern for both existing diagnostic exports.
- 🛑 **Do not un-static anything, do not move `osd_decode`, and do not duplicate the CRC or
  normalisation arithmetic into the shim.** A copy that drifts from production silently answers a
  different question than the one asked.

### B4.2 Signature

```c
/* Diagnostic-only. Decodes a caller-supplied 174-bit LLR vector through the
 * EXACT production sequence and reports whether it yields a CRC-valid message.
 * Returns 0 on success (a decode was attempted and the outputs are valid),
 * negative on argument/precondition failure. crc_ok is the answer; the return
 * code is only "did the probe run". */
int ft8_ldpc_decode_llrs(
    const float* llr174,      /* IN  : 174 RAW, PRE-NORMALISATION LLRs             */
    int          max_iters,   /* IN  : bp_decode iteration cap                     */
    int          osd_depth,   /* IN  : OSD ndeep; <0 = disable the OSD fallback    */
    uint8_t*     out_a91,     /* OUT : 91 bits (12 bytes), payload+CRC, may be NULL */
    int*         out_ldpc_errors,  /* OUT : bp_decode's own error count            */
    int*         out_path,    /* OUT : 0 = BP converged, 1 = OSD fallback, -1 = neither */
    int*         out_crc_ok); /* OUT : 1 iff extracted CRC-14 == computed CRC-14   */
```

### B4.3 What it must do, in this order — mirroring `decode.c:641-713` and nothing else

1. `memcpy` the caller's vector into a local `float log174[FTX_LDPC_N]`. 🛑 **Never modify the
   caller's buffer** — `bp_decode` writes through its argument.
2. **Degenerate guard FIRST**, copying `decode.c:799`'s own guard verbatim in spirit: if the
   variance is zero, `ftx_normalize_logl` divides by zero. Return a negative rc; do not normalise.
3. `ftx_normalize_logl(log174)` — 🔴 **mandatory, and it is what makes the arm sound.** It rescales
   to a fixed variance (`norm_factor = sqrtf(24.0f / variance)`, `decode.c:404`), so **any global
   scale difference between the V0 grid vector and the V3_cum coherent vector is removed before BP
   sees it.** Without this step B4 would silently measure LLR scale rather than LLR quality, and the
   V0-vs-V3_cum comparison would be void. Callers pass RAW LLRs because that is what both existing
   exports return (`decode.c:826`, `ft8_shim.c:1522`).
4. Save the normalised vector for OSD (`decode.c:643-646`).
5. `bp_decode(log174, max_iters, plain174, out_ldpc_errors)`.
6. Pack to `a91`, `ftx_extract_crc` / `ftx_compute_crc(a91, 96-14)`, compare — the same arithmetic
   as `decode.c:707-713`.
7. 🔴 **If and only if the CRC fails and `osd_depth >= 0`, run the OSD fallback exactly as
   production does** and re-check the CRC. Production decodes with OSD; a BP-only probe would
   **under-count** relative to the pipeline we are trying to size, and that under-count would land
   in the conservative-looking direction where it is least likely to be questioned. Report which
   path succeeded in `out_path`.

### B4.4 Version, pin, CI

Unchanged from 1525Z §4 — **B4 rides the same single `FT8_SHIM_VERSION` bump to `20260044`** (still
assert mechanically that `20260044` is unused across all branches before adopting it) and the same
one-place harness re-pin. ⚠️ **B4 adds an export, so re-check the CI recipe question of 1525Z §4
rather than inheriting its "no new source file" answer** — no new *file*, but a new *symbol*. Verify
mechanically.

---

## C. Acceptance for B4 — mandatory, two-sided, and one of them is against known ground truth

These run in the Developer session's own test suite. 🔴 **They do NOT change §5's ordering.** B4 is
inert — nothing calls it — so **a B4 test failure does not block ROW 0g**; report it and continue.

| # | check | bar | why |
|---|---|---|---|
| **B4-a** | Encode a known message, build its exact codeword LLRs (`+1`/`-1` scaled, no noise), decode | `crc_ok == 1` **and** `a91` payload matches the encoded message bit-for-bit | positive control — the probe decodes what is decodable |
| **B4-b** | Pure Gaussian LLRs, fixed seed, 20 trials | `crc_ok == 0` on **all 20** | negative control (HK-021(n) — this bar is load-bearing; a probe that reports success on noise reports success on anything) |
| **B4-c** | Caller's input buffer after the call | byte-identical to before | B4.3 step 1 — `bp_decode` writes through its argument |
| **B4-d** | Zero-variance input | negative rc, no crash, no NaN | B4.3 step 2 |
| **B4-e** | 🔴 **Cross-check against the production decoder on real audio** — take rows `ft8_decode_all` DID decode live, extract with `ft8_extract_llrs_at` at the grid candidate's own position, feed B4 | **≥ 90 % agreement** (`crc_ok == 1`) on rows production decoded, and the recovered message text matches | the only check here with **known ground truth** (HK-026: the instrument is not bounding its own blind spot — WSJT-X's own decode is the reference). ⚠️ Agreement will not be 100 % — production searches candidates, B4 is handed one position — so the bar is a floor, not an identity. **If it lands below 90 %, STOP and escalate: B4 is not reproducing the production decode path and no C2 number can be read.** |

---

## D. C2 — the analysis arm. **SPECCED LATER. DO NOT RUN IT IN THIS SESSION.**

Once Phase B's binary is **merged and its SHA256 pinned**, C2 re-runs Stage 1RE's *already
delivered* rows through B4 and reports CRC-verified counts in place of B50 crossings.

🛑 **Do not run C2 against an unmerged branch build.** The board already records one confound of
exactly this shape (P2/P3/P1a ran `39aa1031…`, an unmerged `d001-rc4-decode-depth` build, ~+0.70 pp).
🔴 **Assert the SHA against a pre-registered manifest; never infer it from a shim-version label.**

C2 will be pre-registered on its own, two-sided, after Phase B lands. What it will answer:
`n_cross`, `n_break` and `f_net` in **decodes**; how many of the 455 breakable rows the grid leg
*actually* decodes (which is what §2 of the 1634Z ruling flagged as the cascade's one real caveat);
and it hands C3 a response variable that threshold geometry cannot manufacture.

**C3 (the dither null arm) is DEFERRED by the Captain's ruling — not drafted, not pre-empted.**

---

## E. C1 — pin the cascade in `design.md`. Docs only, QA's edit, no run.

Route B2's design has never stated whether the coherent path **replaces** the grid path or **falls
back behind it**. This is the whole of the 1634Z ruling §2, and it is the difference between
`f_break = 60.66 %` being a cost and being irrelevant. Add to
`openspec/changes/r2-coherent-llr-instrument/design.md`, in QA's own house style:

> **D-B2-1 — the coherent path is a FALLBACK LEG, never a replacement.** Production decodes with the
> grid LLRs first. Only where the decode fails its CRC-14 does the coherent extraction run, on that
> candidate, and emit only if *its* CRC-14 passes. Consequences, and they are the reason this is
> pinned before any integration work: (a) rows the grid path already decodes **cannot be lost** —
> the second leg never runs on them, so `f_break` is not a recall cost under this shape; (b) the
> trigger is a **real CRC-14, not a modelled BER threshold** — no oracle, nothing estimated at run
> time; (c) false emissions stay bounded by the same CRC-14 the existing path relies on; (d) the
> remaining cost is **compute** — measured 2026-08-21: coherent **8.32 ms**/call vs grid
> **4.22 ms**/call, second leg on the miss population only. ⚠️ A cascade protects rows the grid
> **actually** decodes; `f_break`'s breakable subset is defined by the B50 model, and B50 is not the
> decoder. C2 settles that gap.

🔴 `openspec validate --strict` must pass after the edit. ⚠️ This does **not** amend `design.md` D1
(the 1201 §5 ruling is still owed and still separate).

---

## F. Prohibitions (additional to 1525Z §9, which stands in full)

- 🛑 **B4 gets no production call site.** Same discipline as `ft8_extract_llrs_at` and
  `ft8_coherent_llr_at`: reachable from tests and harnesses only.
- 🛑 **B4 must not alter `decode.c`'s existing decode paths.** Additive function only; the diff on
  every existing function is zero and should be demonstrated by direct diff, not asserted (HK-022).
- 🛑 **Do not re-read Stage 1RE's ROW 1 with B4.** ROW 1 fired and stands. C2 is a NEW question with
  a NEW pre-registration; it is not a re-scoring of a closed gate.
- 🛑 **Do not quote N5's 4.37 % as a bound anywhere, ever again** (1634Z §1).
- ⚠️ HK-025 remains available on every pre-registered check here.

---

## G. What I have NOT established

- **That B4 will reproduce production's decode outcome.** B4-e exists precisely because I do not
  know that, and it is a stop condition.
- **That the CRC-verified count will be non-zero.** If it is zero, limb 2's entire conversion
  reading was the threshold's geometry, and Route B2's value collapses to whatever Phase B's origin
  fix recovers. **That outcome must be reportable without anyone treating it as a failure of QA.**
- **That the OSD fallback belongs in the comparison.** I have specced it IN because production runs
  it; if it turns out to dominate the result, the arm will need a with/without split. Report
  `out_path` per row so that split remains possible **without re-running anything**.

## H. Predictions (Architect, recorded before any B4 number exists)

- B4-e clears its 90 % floor: **80 %.**
- C2's CRC-verified cross count comes in **below** the 369 B50 crossings: **55 %.**
- It is non-zero: **85 %.**
- OSD, not BP, accounts for **the majority** of whatever C2 recovers: **40 %.**

⚠️ Current calibration: categorical 9/16 · ranges 12/20 · directional 2.5/5.5 · mechanical 4/6, and
my last three categorical misses all under-predicted the signal.
