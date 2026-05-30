# QA Review — p14 Decode Start/Stop (FR-017)

**PR:** #18 `feat(p14): FT8 decode start/stop control (FR-017)`
**Reviewer:** QA
**Date:** 2026-05-31
**Verdict:** ✅ APPROVED

---

## Summary

The implementation is sound and well-structured. The design document, spec, tasks, and code are all aligned. Migration safety is handled correctly (`DecodingEnabled = true` default), the `OnSaved` handler cleanly separates device-change and enable/disable transitions, the `restartSemaphore` is applied correctly in both the enable and disable background tasks, and all six integration tests cover the required scenarios with meaningful assertions. The UI visibility rule is respected.

Both items raised in the initial review (R1, R2) have been addressed and verified. The full test suite — 156 tests, 0 failures — is green.

---

## Initial Review Findings and Resolution

### R1 — Missing idempotency tests ✅ RESOLVED

**Severity:** Medium
**File:** `tests/OpenWSFZ.Web.Tests/DecodeControlEndpointTests.cs`

Two idempotency tests required by the spec were absent in the first submission. Both are now present:

- `PostDecodeStop_WhenAlreadyStopped_IsIdempotent`
- `PostDecodeStart_WhenAlreadyRunning_IsIdempotent`

Both assert HTTP 200 and verify the stored `DecodingEnabled` value is not incorrectly mutated. ✅

---

### R2 — `DaemonStatus` construction duplicated in three places ✅ RESOLVED

**Severity:** Medium
**File:** `src/OpenWSFZ.Web/WebApp.cs`

The `new DaemonStatus(...)` construction was duplicated across three endpoint handlers. A `private static DaemonStatus BuildStatus(IConfigStore, CaptureManager?, AudioActivityMonitor?)` helper has been extracted and is now used at all three call sites. ✅

The method's XML doc comment also addresses advisory A1, explicitly noting that `CaptureActive` in start/stop responses reflects the pre-transition state due to the async `OnSaved` pipeline. ✅

---

## Advisory Items (No Action Required)

### A1 — `CaptureActive` in start/stop responses is structurally stale ✅ DOCUMENTED

Addressed via the `<remarks>` block in `BuildStatus`. Clients requiring a post-transition view are directed to poll `GET /api/v1/status`. ✅

### A2 — Uncommitted local changes to `findings.md` ⬜ OPEN

`openspec/changes/p10-decoder-ground-truth/findings.md` remains locally modified and unstaged. This must not be swept into a subsequent commit on this branch. To be resolved separately.

---

## Final Checklist

| # | Item | Status |
|---|---|---|
| R1 | Idempotency tests added (`stop-when-stopped`, `start-when-running`) | ✅ Done |
| R2 | `DaemonStatus` construction extracted to `BuildStatus` helper | ✅ Done |
| A1 | Stale `CaptureActive` documented in `BuildStatus` XML remarks | ✅ Done |
| A2 | `findings.md` local modification resolved separately | ⬜ Pending (out of scope for this PR) |
| — | Full test suite green (156 passed, 0 failed) | ✅ Confirmed |

This PR is approved to merge.
