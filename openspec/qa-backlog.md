# QA Backlog

Observations that are not merge-blocking but must be addressed in a future change.
Each item is classified with a severity and the change in which it was first noted.

---

## Process notes (read before authoring a `proposal.md`)

**Every `proposal.md` MUST declare its user-facing status.** On a single line, before the
`## Why` heading, add exactly one of:

```
**User-facing:** yes
```
```
**User-facing:** no
```

A change is **user-facing** if and only if it ships operator-visible behaviour (e.g. a new or
changed feature, UI, API response, or stdout the operator sees). Defect fixes, diagnostics,
QA-study runs, CI/tooling, and documentation-only changes are **not** user-facing.

This declaration is the sole input to the "one user-facing feature = one minor version bump"
rule, enforced mechanically by CI gate **G9** (`version-governance` job in
`.github/workflows/ci.yml`, backed by `tools/check_version_bump.py`). When a PR archives a
`**User-facing:** yes` change, G9 fails the build unless the root `VERSION` file is also bumped;
when the declaration is missing or malformed, G9 fails and names the offending change. The
canonical definition lives in the `release-versioning` capability spec
(`openspec/specs/release-versioning/spec.md`).

The OpenSpec CLI's stock `proposal` template does not scaffold this line (it ships inside the
globally-installed npm package, not the repo), so it is added by convention — don't forget it.

---

## N1 — `Ft8LibInterop`: retry-after-failure produces a confusing exception

**Severity:** Low
**Source:** p13-cross-platform-decoder QA review
**File:** `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs` — `LoadAndVerify()`

`LoadAndVerify()` registers `NativeLibrary.SetDllImportResolver` as its first step, then performs
the native binary existence check. If the existence check throws (file not present in output dir),
`_initialized` remains `false` and the double-checked lock permits a subsequent retry. On that
second call, `SetDllImportResolver` throws `InvalidOperationException: "A DllImportResolver is
already set for this assembly"`, which buries the original `DllNotFoundException` about the
missing binary.

This path is unreachable in normal operation (a built project always has the binaries in the
output directory), but it would confuse a developer investigating a broken local build.

**Suggested fix:** Guard the `SetDllImportResolver` call with a separate `_resolverRegistered`
volatile flag, or wrap it in `try { … } catch (InvalidOperationException) { /* already
registered */ }` to make it idempotent.

---

## N2 — `Ft8LibInterop`: platform filename computed twice in `LoadAndVerify()`

**Severity:** Cosmetic
**Source:** p13-cross-platform-decoder QA review
**File:** `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs` — `LoadAndVerify()`

The platform-appropriate filename (`libft8.dll` / `libft8.so` / `libft8.dylib`) is computed once
inside the resolver lambda and a second time outside it for the `File.Exists` check. Both
computations produce the same result via identical `RuntimeInformation.IsOSPlatform` chains.

**Suggested fix:** Extract a `static string GetPlatformLibFileName()` private method and call it
from both sites.

---

## N3 — `Ft8LibInterop`: 6 720-byte heap allocation on every decode cycle

**Severity:** Low
**Source:** p12-ft8lib-port QA review (carry-through); confirmed in p13
**File:** `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs` — `DecodeAll()`

```csharp
var results = new Ft8NativeResult[MaxResults];   // 140 × 48 bytes = 6 720 bytes, every cycle
```

A fresh 140-element array is heap-allocated on every 15-second decode cycle. The allocation
is negligible at current cycle rates but will appear prominently in any allocation profiler
trace.

**Suggested fix:** `ArrayPool<Ft8NativeResult>.Shared.Rent(MaxResults)` with a corresponding
`Return()` after the slice is extracted, eliminating the per-cycle heap pressure.

---

## N4 — 11 main specs lack a `## Purpose` section (fail `validate --strict`)

**Severity:** Minor
**Source:** p19/p20 archive (2026-06-05); logged as F-011
**Files:** `openspec/specs/{audio-capture, audio-device, build-pipeline, ci-quality-gates, daemon-host, decode-control, decode-log, decoder-ground-truth, dependency-licence-policy, file-logging, requirement-traceability}/spec.md`

OpenSpec's current validation requires every spec to carry both a `## Purpose` and a
`## Requirements` section. Eleven main specs predate that rule and open directly with
`## Requirements`, so they fail `openspec validate --all --strict` (8 passed, 11 failed as of
2026-06-05). This is latent debt, not a regression: the four specs touched by the p19/p20 archive
(`cat-control`, `configuration`, `web-frontend`, `web-server`) were brought into compliance at
that time, but the remaining eleven were deliberately left untouched to keep the archive in scope.

Because the rule only bites when a spec is rebuilt during `openspec archive`, any future change
whose delta touches one of these eleven capabilities will abort mid-archive until the Purpose
section is added — a latent trip-hazard for the next developer.

**Suggested fix:** Add a concise, content-neutral `## Purpose` paragraph above `## Requirements`
in each of the eleven specs (one short sentence describing the capability), then confirm
`openspec validate --all --strict` reports 19/19 passing. Doc-only; no behaviour change.
