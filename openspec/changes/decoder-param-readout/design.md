## Context

`DENSITY-REMEDY` spec §4 and §10.2 (Architect, `arch/density` `563e08ed`; the Captain's ruling quoted at §10). Stage 0 (the live regime census) is accepted, and it gates only Stages 2 and 3: **Stage 1 needs no change** as a result of it, because `ft8_set_supp_params` already takes `snr_max` (§11.3).

The native decoder's behaviour is governed by three groups of values that are, today, invisible from outside the DLL:

1. **Runtime-settable** through `ft8_set_decode_params(k_min_score_pass2, osd_corr_threshold, osd_nhard_max)`, which has **no getter**. The compiled defaults are `10 / 0.10 / 60`; the live app overrides `nhard` to `40` from `DecoderConfig`.
2. **Compile-time** `#define`s in `ft8_shim.c` (read from `decoding_improvement` at `6cb98c52`): `K_MIN_SCORE`, `K_MAX_CANDIDATES`, `K_MAX_CANDIDATES_PASS2`, `K_LDPC_ITERATIONS`, `K_LDPC_ITERATIONS_PASS2`, `K_FREQ_OSR`, `K_TIME_OSR`, `K_MAX_PASSES`, `K_SOFT_SUPP_SNR_MIN_DB`, `K_SOFT_SUPP_SNR_MAX_DB`, `K_LOCAL_NOISE_WINDOW`, `K_MAX_DECODED`, and the derived `K_MAX_CANDIDATES_ANY_PASS`. The spec's list is a **floor**, not a ceiling.
3. **Literals that are not named constants at all**: the candidate passband `.f_min = 140.0f, .f_max = 3075.0f` appears at **two** call sites (`ft8_decode_all` and `ft8_extract_llrs_at`), and `decode.c` calls `osd_decode(..., 2, ...)` with a bare `2`.

The goal is that **a value shown to an operator is, by construction, the value the decoder uses**.

## Goals / Non-Goals

**Goals**
- Every decoder parameter readable from the native library itself, in one call.
- A runtime setter and getter for the soft-suppression ramp, defaults unchanged.
- A read-only daemon endpoint and a read-only GUI page over the table.
- **Byte-identical decode output at defaults.**

**Non-Goals**
- **No tuning.** No default moves. No constant changes value.
- **No managed setter** for the suppression parameters (the live app never calls it; the setter is for QA harnesses and the DENSITY-REMEDY bench).
- **No change to the existing editable Advanced Decoder Settings section.**
- No route to `main`: that is the Captain's call under HK-010.

## Decisions

### D1 — One table export, not one getter per value

```c
typedef struct {
    char    name[48];       /* NUL-terminated: "K_MAX_CANDIDATES", "osd_nhard_max", ... */
    double  value;          /* what the native decoder reports NOW                        */
    double  default_value;  /* the compiled-in default (== value for compile-time entries) */
    int32_t kind;           /* 0 = compile-time constant, 1 = runtime-settable             */
    int32_t reserved;       /* 0                                                           */
} Ft8ParamEntry;            /* 72 bytes, blittable; _Static_assert(sizeof == 72)           */

/* Returns the TOTAL entry count; writes min(capacity, total) entries. out==NULL or capacity<=0
 * writes nothing and still returns the total, so a caller can size its buffer. */
int ft8_get_decoder_params(Ft8ParamEntry* out, int capacity);
```

Rationale: a table means **a constant added later cannot be silently left out**, which is the failure mode one-getter-per-value invites. `double` carries both the `int` and `float` entries exactly (the largest, `K_MAX_DECODED`, is 340). The layout is the Developer's to adjust; the semantics are not.

### D2 — Completeness is derived, and checked mechanically

The table is built from a single X-macro list so that each row reads the **same macro or variable the decode path reads** (a value cannot drift from a copy). Completeness is nevertheless **not** trusted to the list: acceptance gate **S1-f** greps every `#define K_*` in `ft8_shim.c` that the decode path reads and every `ft8_set_*` setter, and asserts each has an entry, and that each compile-time entry's value equals its `#define`.

### D3 — Each row carries `value` **and** `default_value`

For a runtime entry, `value` is the current setting and `default_value` is the compiled default. **This is the point of the feature:** `osd_nhard_max` reads `value = 40`, `default_value = 60` when the daemon has applied `DecoderConfig`, and the `nhard` 60-versus-40 split that cost this programme three re-cuts is visible at a glance. A GUI MAY highlight rows where the two differ.

### D4 — ✅ DECIDED (Architect, spec §12, `arch/density` `9c5622aa`): hoist the OSD depth and table it

`native/ft8_lib_build/patched/ft8/decode.c:666` passes a bare `2` as OSD depth (`osd_decode(llr_for_osd, 2, plain174)`, verified by the Architect on `origin/decoding_improvement`), and `DENSITY-MECH`'s harness had to pin it as `OSD_DEPTH = 2 # decode.c:666 production hardcode`. It is a decode-path tuning value the original spec list did not name. **It is hoisted to a named macro and included in the table.** Cost: one further existing line edited in a **vendored, patched** file, arithmetic-identical, and gate S1-a binds it.

### D12 — Completeness covers **bare literals**, not only `#define K_*` (Architect, spec §12)

D4 is the proof that a `#define K_*` grep is not enough: the OSD depth was invisible to it. So the Developer **audits the decode path for any other bare numeric tuning literal**, in `ft8_shim.c` **and** the patched `native/ft8_lib_build/patched/ft8/*.c`, and **reports every one found**. Each is then exactly one of:

- **hoisted to a named constant and tabled** (arithmetic-identical, bound by S1-a);
- **derived**: a value derived from a constant that **is** tabled (see below). It is **listed as derived from that constant**, in the report and on the page's note, and is **never excluded as "protocol"**; or
- **named on the read-only page's "Not included" note** with its location, value and the reason it is not tabled.

**Nothing is omitted silently.**

*Definition, so the audit is not a matter of taste.* A **tuning literal** is a numeric literal that, if changed, would change decode results **without changing the FT8 protocol**: a threshold, an iteration count, a depth, a window, a cap, a scale, a limit.

**Protocol constants, and only these:** the **6.25 Hz tone spacing**, the FT8 dimensions **79 symbols / 174 bits / 91 bits**, the **Costas** pattern, the **8 tones**, and the **12 kHz** sample rate. An array size or loop bound that follows directly from one of them is not a tuning literal either.

🔴 ~~*"…the 6.25 Hz / 3.125 Hz bin spacing"* listed as a protocol constant~~ **CORRECTED (Architect, spec §12): that was wrong.** The **3.125 Hz sub-bin** is `6.25 Hz / K_FREQ_OSR`, and the **half-symbol time sub-step** is `symbol period / K_TIME_OSR`. Both are the decoder's **own oversampling choices**, not the protocol's. A literal such as `3.125f` or `0.5f` that is really `1 / K_FREQ_OSR` or `1 / K_TIME_OSR` is therefore a **derived value of a tabled tuning constant**: list it as **derived from `K_FREQ_OSR` / `K_TIME_OSR`**, never as protocol.

Where the Developer is unsure which category a literal falls in, they **list it** *with that doubt stated*, rather than deciding silently.

**How QA checks it (and what is judgment).** QA runs its own grep of the same files for numeric literals on the decode path and diffs it against the Developer's report: every literal QA finds must appear in the report as *hoisted-and-tabled*, *derived (from which tabled constant)*, or a *"Not included"* entry, and every derived or "Not included" entry must appear on the page. **That comparison is mechanical. Whether a literal is a "tuning" literal at all is not**, so any disagreement goes to the Architect, not to QA alone.

### D5 — Hoist the passband literals

`K_PASSBAND_MIN_HZ 140.0f` and `K_PASSBAND_MAX_HZ 3075.0f`, used at **both** `monitor_config_t` sites. Today the value is written twice, so a table entry could disagree with one of them. `PASSBAND-140` (the last change in this area) had to edit both lines by hand for exactly this reason. Arithmetic-identical.

### D6 — Suppression parameters (spec §4.1, restated)

```c
/* Returns 0 on success; -1 and leaves ALL THREE unchanged if: any arg is non-finite,
 * snr_min_db >= snr_max_db, or side_weight is outside [0, 1].  Defaults: -5.0f, 15.0f, 1.0f. */
int ft8_set_supp_params(float snr_min_db, float snr_max_db, float side_weight);
int ft8_get_supp_params(float* out3);   /* {snr_min_db, snr_max_db, side_weight}; returns 0 */
```

In `suppress_candidate_tiles`: the ramp uses the runtime min/max; the tone bin (`d = 0`) gets `factor`; the side bins (`d = ±1`) get `factor_side = 1 − side_weight · (1 − factor)`.

🔴 **The default path must be arithmetic-identical.** When `side_weight == 1.0f` the side bins use `factor` **itself**, not the recomputed expression, because `1 − (1 − f)` is not bitwise `f` in float. Acceptance gate S1-a catches any slip.

`snr_max` has **no upper bound** other than `> snr_min` and finite: the Stage 2 bench will sweep it above `+15` (Architect §11.3), so a validator that rejects `snr_max > 15` would break the arm.

The compile-time `K_SOFT_SUPP_SNR_MIN_DB` / `MAX_DB` **remain**, as the defaults of the runtime values, and appear in the table as compile-time entries (the S1-f grep requires it).

### D7 — Thread-safety contract

Module-level state with **the same contract as `ft8_set_decode_params`**: set before the decode that should see it; not synchronised against a concurrent `ft8_decode_all`. `ft8_get_decoder_params` performs plain aligned reads; a concurrent set may be observed torn *between* entries, never within one. Documented in the header.

### D8 — The endpoint reads the native library at request time

`GET /api/v1/decoder/params` →

```json
{ "shimVersion": 20260054,
  "entries": [ { "name": "osd_nhard_max", "kind": "runtime", "value": 40, "default": 60 }, ... ] }
```

- Served from `IFt8NativeInterop` **on each request** (no cache), so it shows what the decoder reports, **not** what `app.json` says. That difference is the feature.
- `shimVersion` from the existing `ft8_lib_version_check`.
- **Read-only:** `POST`/`PUT`/`PATCH`/`DELETE` on the route return `405`.
- Same authentication as the other `/api/v1` routes. AOT-safe (`AppJsonContext`).
- If the native library cannot be loaded: `503` with a message, never an empty table.

### D9 — The GUI page

`web/decoder-params.html` (+ `web/js/decoderParams.js`): two groups, *Runtime-settable* and *Compile-time*, each row `name · value · default`; the shim version at the top; **no `<input>`, `<select>`, `<textarea>`, and no mutating control**. One link to it from `web/settings.html`. **The `#advanced-decoder-settings` block is byte-for-byte unchanged.**

### D10 — Shim version `20260054`

Verified free by QA on 2026-09-19: the highest version defined on any ref is `20260053`; `20260054` appears only in the Architect's spec text and is never defined; **`20260052` stays reserved** by the queued rc4 renumber task and must not be reused. **The Developer re-runs the uniqueness check at pickup** (history may have moved); the dev-task carries the command.

### D11 — The Windows export trap

`rebuild_shim.bat` needs **three** new `/EXPORT:` lines. Linux exports by default visibility, so **a missing Windows export builds clean on Linux and fails only at P/Invoke.** Verify with `dumpbin /exports` (26 → 29 exports).

## Risks / Trade-offs

- **Scope.** This is more than a diagnostic build: a user-visible page on `decoding_improvement`. Its route to `main` is the Captain's (HK-010).
- **Vendored-file edit (D4)** touches `patched/ft8/decode.c`. Mitigated by S1-a. Further hoists found by the D12 audit add to it; each is arithmetic-identical.
- **Table drift.** Mitigated by construction (D2) *and* by grep (S1-f); either alone would be weaker. **A `#define` grep is blind to bare literals**, hence D12.
- **A readout that lies is worse than none.** Hence D3, D8 and S1-g (round-trip): the page must show a value the native library returns, after a real set.

## Migration Plan

Additive. Deploy = ship the new binaries and page. Rollback = revert; nothing persists, no `app.json` field is added. The DENSITY-REMEDY arm's Stage 1 **acceptance** (QA) begins only after CI is green on all three platforms.

## Open Questions

1. ~~**D4:** hoist and include the OSD depth?~~ **Decided: yes** (Architect, spec §12).
2. Should the GUI highlight rows where `value != default`? (Recommended, optional, Developer's choice; the Architect endorsed the `default` column, D3.)
