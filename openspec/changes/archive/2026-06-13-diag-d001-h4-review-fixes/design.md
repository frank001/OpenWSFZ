## Context

Two source files were left with stale narrative content when the H3b PCM-domain SIC mechanism
was removed in H4 (shim 20260010). Both omissions were identified in the mandatory QA code
review and must be corrected before the S7 validation run is authorised.

This change touches no logic, no APIs, no binaries, and no spec requirements. It is purely
corrective documentation work on two files.

## Goals / Non-Goals

**Goals:**
- Correct all three H3b/20260009 narrative strings in `GfskQuadratureSynthTests.cs` so the
  test's visible identity matches what it actually exercises (spectrogram suppression, shim 20260010).
- Append four missing version entries to the shim history comment in `Ft8Decoder.cs`.

**Non-Goals:**
- Any logic changes to the test itself — the assertions are correct; only the descriptive
  strings are wrong.
- Any logic changes to `Ft8Decoder.cs`.
- Renaming the test file on disk (optional quality improvement; not required for merge).
- Touching any other file.

## Decisions

### D1 — Class rename is preferred but not blocking

**Decision:** Rename `GfskQuadratureSynthTests` to `SpectrogramSuppressionSmokeTests` if the
developer elects to, but it is not required. Updating the three narrative strings (class doc,
DisplayName, assertion message) is the minimum required change.

**Rationale:** A class name ending in `GfskQuadratureSynthTests` attached to a test that
exercises spectrogram suppression will mislead future contributors. However, renaming also
requires renaming the file and updating any tooling references — low cost but slightly more
scope than the minimum. Either way is acceptable; the review finding is satisfied once the
three strings no longer assert H3b/20260009 identity.

### D2 — Version history style: match existing entries exactly

**Decision:** The four new entries in `Ft8Decoder.cs` SHALL follow the existing single-line
format (`/// VVVVVVVV — <change-name>: <description>.`) used by all prior entries. No
additional formatting, no bullet sub-items.

**Rationale:** Consistency. The history comment is a quick-reference narrative, not a
full changelog — brevity is the point.

## Risks / Trade-offs

**[Risk: class rename breaks a test runner filter or CI step that matches by class name]**
→ Mitigation: grep for `GfskQuadratureSynthTests` across the repo before renaming; update
any references found. If no references exist outside the file itself, rename is safe.

**[Risk: version history entries contain inaccurate shim descriptions]**
→ Mitigation: cross-reference the four entries against `ft8_shim.h` history comment and the
committed R&R result reports. All four descriptions are already documented in those sources.

## Open Questions

None.
