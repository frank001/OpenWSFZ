# Developer handoff (Engineer's workstream): config save preserves unsent settings (#193)

**Whose:** Engineer's (Eng). **Status:** DRAFT. Not for the Developer until the Captain hands it over. The
Developer session also serves QA; no second handoff is queued behind this one without the Captain's say.

## 1. Context

`POST /api/v1/config` resets every key the Settings page does not send (#193 is the `cycleAudioArchive`
case). Fix the class: omitted means unchanged. Full reasoning: `openspec/changes/config-save-preserves-unsent-settings/`
(`proposal.md`, `design.md`, `specs/`, `tasks.md`). Source spec: `qa/2026-09-29-2112-architect-to-eng-spec-config-save-preserves-unsent-settings.md`
on `arch/config-save-preserves-settings` @ `6fb71458`.

## 2. Branch

`feat/config-save-preserves-unsent-settings`, off `eng/config-save` (which holds the OpenSpec change), or off `main` once it has
merged. Never commit to `main`.

## 3. Actions

Follow `tasks.md` sections 1 to 4 in order. In short:

1. Write the tests first (T1, T2, T4 to T12) and record which fail on the unfixed handler.
2. Implement the overlay merge in `src/OpenWSFZ.Web/WebApp.cs` per `design.md` D1. Remove the redundant
   guards and the two stale comments. Keep the `nhard40MigrationApplied` force.
3. List every existing test whose assertion changed, one justified row each, in `design.md` D6.
4. Add the change-log line (Part D) with allowlisted values only, and T14.
5. Read `CycleArchiveService` before validating (D5), record the findings, then build the Settings-page
   Audio archive group with **all four** modes (`off`, `all`, `decoded`, `noDecodes`), T13 and T15.
6. Amend `REQUIREMENTS.md`, bump `VERSION` to 0.52.

Do not run `tools/pre_merge_check.py` (HK-000 amendment). Do not touch `qa/` (Part E is the Engineer's).

## 4. Acceptance

T1 to T16 as defined in the source spec §7 and the delta specs. L1 is the Engineer's, on the station.

## 5. References

- Issue #193; HK-035 (memory); `cycle-audio-archive` and `configuration` OpenSpec specs.
- 🔒 NFR-021 / HK-037: no callsign, passphrase, host or directory value may be logged or committed in a fixture. Use `Q`-prefix calls.
