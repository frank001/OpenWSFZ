# D-001: QA -> Architect report — Q1-Q4 actioned from the consolidated handoff

**Author:** QA, 2026-07-27 (18:12 UTC, `date -u`, per HK-017). **For:** the Architect (§1-§4), and the
record (§5).
**Answers:** `2026-07-27-1752-architect-to-qa-consolidated-handoff.md` §4, all four tasks.
**This is a notification, not an escalation.** Nothing here asks for a re-ruling.

---

## 1. Q3 — uncommitted `src/` state: resolved by committing

Committed as `7c90638` (`qa+dev(d001): commit shim 20260035 (C.2 Phase 2c raw-LLR/shrinkage) +
tls_diag_llr174 gate`). Before committing, re-verified from a clean context rather than taking the
prior session's word for it (72b090d/c97ce90 already reviewed and accepted this diff, but that
review happened in a different context than this one):

- `dotnet build OpenWSFZ.slnx -c Release` — clean, 0 warnings/errors.
- `dotnet test tests/OpenWSFZ.Ft8.Tests -c Release --no-build` — 297/297 green.
- `tools/check_native_version.py` against `win-x64/libft8.dll` — confirms `FT8_SHIM_VERSION=20260035`
  at 60,416 bytes, matching the accepted state.
- Diff content cross-checked against both dev-tasks that produced it
  (`dev-tasks/2026-07-26-d001-c2-phase2c-shrinkage-trial-and-ber.md`,
  `dev-tasks/2026-07-27-d001-gate-tls-diag-llr174-compile-time.md`) — no surprises, no scope creep.

No new `src/` or native work performed (HK-011) — this only formalises already-reviewed
Developer-session output into history. `git status` is now clean on this branch.

## 2. Q1 — shim version correction: dev-task authored

`dev-tasks/2026-07-27-d001-shim-version-correction-and-capabilities.md`. Implements the four parts
specified in the handoff, expanded with exact line numbers and code against the now-committed
(`7c90638`) source: version bump 20260035 → 20260036 (both `ft8_shim.h` and
`Ft8LibInterop.cs`), the new `ft8_get_shim_capabilities()` bitmask export, the managed
`LoadedShimCapabilities` property mirroring the existing `LoadedShimVersion` pattern exactly (same
`internal`-on-`Ft8LibInterop`/`public`-forward-on-`Ft8Decoder` shape, same startup-log site in
`Program.cs`), and the `SetCandidateDiagLlrCapture(true)` throw plus the native `-1`/managed
distinguish-from-`0` defence in depth.

One thing I tightened beyond the handoff's four bullets: the throw in §2.3.7 only guards
`enable == true`, not `enable == false` — `Ft8Decoder.cs:402` re-asserts this call unconditionally
every cycle with the production default (`false`), so a blanket throw would have broken every
decode cycle on a gate-off binary, not just diagnostic ones. Flagging in case that reasoning wants a
second look, though I'm confident in it — traced the call site myself rather than assuming.

## 3. Q2 — `MaxPass0Candidates` truncation guard: dev-task authored, shape decided

`dev-tasks/2026-07-27-d001-max-pass0-candidates-truncation-guard.md`.

The handoff left the shape as QA's call. Before designing, I read all five capacity-bound getters in
`Ft8LibInterop.cs` (per HK-018 — check whether the axis can actually distinguish the two states
before applying a rule) and found the naive version — throw whenever any of them returns exactly its
`capacity` — is wrong for three of the five: `GetLastPassCounts`/`GetLastCandidateCounts`/
`GetLastLlrStats` are all sized to `MaxDecodePasses` (2), the *exact* expected pass count, not
headroom, so `n == capacity` is the normal case on every single production decode cycle. Applying the
guard there would have thrown constantly. It correctly applies only to
`GetLastCandidateDiagnostics`/`GetLastCandidateLlr174`, both sized to `MaxPass0Candidates` (600) as
deliberate over-provisioned headroom — hitting that cap exactly is the actual anomaly C.4 was.

The guard itself needs no new native export: `GetLastCandidateCounts(MaxDecodePasses)[0]` already
carries an independent, same-cycle, non-`MaxPass0Candidates`-bounded pass-0 candidate count
(`ft8_shim.c:1534`, `tls_candidate_counts[pass] = ncands`), which is exactly the cross-check needed —
if the diagnostic capture hit its cap while this independent count is higher, candidates were
confirmed dropped, not merely suspected. Comparison logic is a pure function of four `int`/`string`
arguments (`GuardCandidateCaptureTruncation`), deliberately separated from the TLS-reading wiring, so
it is unit-testable without a real decode cycle — four cases specified in the dev-task's acceptance
criteria.

Noted a residual gap explicitly rather than claiming full closure: this cannot see truncation
happening one layer deeper, inside `ftx_find_candidates` itself if it silently drops candidates
beyond its own cap — that native counter would already be wrong before this guard ever runs. Not
this task's job; C.1 already established 600 as a verified crash-free ceiling and the study has
never seen populations anywhere near it (~220-295/cycle per the handoff §2.2).

## 4. Q4 — R.3 held

No action taken; not started, per the handoff's explicit instruction. Waiting on the Architect's
replacement design (handoff §6).

## 5. What this does not settle

- **No push, no merge** (HK-014/HK-010) — Captain sign-off and `pre_merge_check.py` (Captain's
  trigger, HK-006) both still pending, neither run by me.
- **Branch disposition** remains the Captain's call, unaffected by any of Q1-Q4.
- **Q1 and Q2 are dev-tasks, not applied changes** — both need a Developer session before either
  lands (HK-011). They are written to stack cleanly on top of each other and on `7c90638`; noted in
  each dev-task's header where their edits are close enough to require hand-merging if both run in
  the same session.
- This closes all four items in the handoff's §4 task list. §6 (the R.3 replacement design) remains
  the Architect's.

## 6. Cross-references

- `2026-07-27-1752-architect-to-qa-consolidated-handoff.md` — the handoff this report answers.
- `dev-tasks/2026-07-27-d001-shim-version-correction-and-capabilities.md` — Q1.
- `dev-tasks/2026-07-27-d001-max-pass0-candidates-truncation-guard.md` — Q2.
- Commit `7c90638` — Q3.

---

*Per HK-015, this is a report back to the Architect on a handoff's implementation, not an escalation.
Per HK-014, nothing is pushed or merged. Per HK-011, no `src/` or native edits were made beyond
committing an already-reviewed diff (§1) — Q1/Q2 are dev-tasks only.*
