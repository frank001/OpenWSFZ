## Context

The OSD gate parameters introduced by D-009 (`K_MIN_SCORE_PASS2 = 10`, `OSD_CORR_THRESHOLD = 0.10`, `OSD_NHARD_MAX = 60`) are compile-time constants in `ft8_shim.c` and `patched/ft8/decode.c`. The R&R study established the calibrated operating point; however, on-air conditions (unusually crowded bands, new propagation paths) may justify expert adjustment without a full native rebuild and deployment cycle.

The goal is a thin runtime-configuration seam: three scalar values stored as module-level C statics, set once per config-change event, read on every decode cycle. The UI surface is an "Advanced Decoder Settings" section in the existing `settings.html` page, visible but clearly labelled as expert-only.

## Goals / Non-Goals

**Goals:**

- Expose `KMinScorePass2`, `OsdCorrThreshold`, and `OsdNhardMax` as live-configurable fields in `AppConfig` under a new nullable `decoder` sub-object.
- Provide a `ft8_set_decode_params` native entry point (shim v20260030) so the three values can be updated at runtime without restarting the daemon.
- Wire the config-change event in the daemon so the next decode cycle picks up the new values automatically.
- Add a validated "Advanced Decoder Settings" section in `settings.html`/`settings.js` with three numeric inputs, range hints, a disclaimer, and a "Reset to defaults" button.
- Maintain the existing clamped-validation pattern for `POST /api/v1/config`.
- Ensure existing `app.json` files without a `decoder` key continue to deserialise without error, defaulting to the calibrated R&R values.

**Non-Goals:**

- Exposing `K_LDPC_ITERATIONS` — 50 iterations is the H_ITER-established optimum; operator adjustment offers no benefit and risks regression.
- Exposing the D-001 AP-decode mechanism — it is driven by QSO state, not operator preference.
- Per-cycle parameter changes (i.e., the parameters are per-config-save, not per-decode-call).
- UI automation tests — the section targets expert operators; manual UAT is sufficient.
- Live reload without a save — parameters apply only when the operator explicitly saves settings.

## Decisions

### D1 — Native parameter storage: module-level statics (not TLS)

`ft8_set_decode_params` writes three module-level `static` C variables. `ft8_decode_all` reads them on every call.

**Why not TLS?** The existing TLS variables (`tls_ap_num_mycall_bits`, `tls_pass_counts`, etc.) exist because those values are set and consumed on the same thread within a single decode call. Decoder parameters are global operator preferences — they must be visible to all threads and need not be per-thread. Module-level statics are the correct mechanism.

**Thread safety:** `ft8_set_decode_params` is called on the .NET thread-pool from the `OnSaved` event handler. `ft8_decode_all` runs on a `Task.Run` thread-pool thread. A write-before-read pattern is maintained in practice (settings saved before decoding resumes), but we cannot guarantee an exact memory ordering guarantee across threads via raw C statics. Given the low-stakes nature of these parameters (a missed update at config-save time simply means the old values persist for one more cycle), we accept this without an explicit fence or `volatile`. If stricter ordering is ever required, a future shim revision can add `_Atomic` or use a mutex.

### D2 — `SetDecodeParams` call site: daemon startup + `IConfigStore.OnSaved`

Two call sites:

1. **Daemon startup** — after `Ft8LibInterop.EnsureInitialized()` (triggered implicitly by the first `DecodeAll` call), the daemon calls `Ft8LibInterop.SetDecodeParams(...)` with the values from the loaded config. In practice, `EnsureInitialized` is private; the startup call is placed just before the audio pipeline starts, ensuring the library is loaded.
2. **`IConfigStore.OnSaved` event** — the daemon subscribes once at startup and calls `SetDecodeParams(...)` on every config save. No restart required.

**Why not wire through `Ft8Decoder`?** `Ft8Decoder` already receives its config implicitly (AP constraints are per-cycle via `SetApConstraints`). Decoder parameters are a singleton concern — wiring them through `Ft8Decoder` would require either constructor injection of `DecoderConfig` (making it stale) or a live-update interface (overengineered for three scalars). Calling `Ft8LibInterop.SetDecodeParams` directly from the daemon startup code is the simplest correct approach.

### D3 — `DecoderConfig` follows the `TxConfig`/`CatConfig` nullable pattern

`AppConfig` gains `public DecoderConfig? Decoder { get; init; } = null`. Null is treated as "use calibrated defaults" in the config-change handler: `config.Decoder ?? new DecoderConfig()`.

The `[JsonConstructor]` pattern (Lesson 6) is required for `DecoderConfig` because its fields have non-zero defaults (`KMinScorePass2 = 10`, etc.). Without it, a JSON object with missing fields would deserialise those fields as `0`, not their declared defaults.

### D4 — API validation: clamp-with-warning, matching `cat` / `tx` pattern

| Field | Min | Max | Calibrated default |
|---|---|---|---|
| `KMinScorePass2` | 5 | 30 | 10 |
| `OsdCorrThreshold` | 0.05f | 0.40f | 0.10f |
| `OsdNhardMax` | 30 | 100 | 60 |

Values outside these ranges are clamped to the nearest bound and a `LogWarning` is emitted. The `LogWarning` message SHALL state the original and clamped values, consistent with the CAT and TX validation pattern.

**Why these bounds?**
- `KMinScorePass2 = 5`: below 5 the D-009 pass-1 sweep shows FP rates in excess of 0.3/slot (approaching the pre-D-009 baseline of 0.675/slot). 30 is a conservative upper bound above which pass-1 admits almost no candidates.
- `OsdCorrThreshold ∈ [0.05, 0.40]`: 0.05 is too permissive (historical R4 data shows FPs begin to dominate below 0.10); 0.40 is the ceiling where genuine co-channel decodes begin to be rejected (R4 single-knob calibration data).
- `OsdNhardMax ∈ [30, 100]`: 60 is the calibrated value. Below 30, genuine decodes at moderate SNR start being rejected. Above 100, the metric provides no discrimination (174/2 = 87 is the noise centroid).

### D5 — Settings UI: collapsible `<details>` section

The Advanced Decoder Settings section uses a native HTML `<details>`/`<summary>` element so it is collapsed by default and requires no additional JS to toggle. This keeps the expert controls out of sight for non-expert operators while remaining accessible with a single click.

A "Reset to defaults" button sets the three inputs to their calibrated values (`10`, `0.10`, `60`) and marks the form dirty, requiring the operator to save explicitly.

## Risks / Trade-offs

- **Native rebuild required** — shim v20260030 requires rebuilding all three platform binaries. The CI `commit-native-binaries` job handles Linux and macOS automatically after the Windows build and push. The Windows binary must be built and committed manually (established procedure).
- **Race window at startup** — if `IConfigStore.OnSaved` fires between native library load and the first `DecodeAll` call, `SetDecodeParams` may be called before `EnsureInitialized` has run, causing a deadlock on `_initLock`. Mitigation: call `EnsureInitialized` explicitly (or trigger a no-op `DecodeAll` on a silent buffer) before subscribing to `OnSaved`. Alternatively, `SetDecodeParams` can call `EnsureInitialized` internally (the same guard used by `DecodeAll`, `GetLastPassCounts`, etc.).
- **Operator misconfiguration** — a user setting `KMinScorePass2 = 5` may re-introduce partial D-009 FP behaviour. The UI disclaimer and clamped API validation reduce this risk; the operator cannot set values below the safe floor without editing the JSON file directly (which is intentional — direct JSON editing is an unsupported expert action).
- **D-009 text-layer rules are not exposed** — the `IsPlausibleMessage` rules (D9-R1 through D9-R4) remain hardcoded. These are structural correctness rules, not tuning parameters; there is no valid use case for disabling them.
