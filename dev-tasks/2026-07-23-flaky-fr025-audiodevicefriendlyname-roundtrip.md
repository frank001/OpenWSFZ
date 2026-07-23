# Flaky test — FR-025 `AudioDeviceFriendlyName round-trips via config file`

**Date surfaced:** 2026-07-23, during PR #104's (`docs(d001): correct two errors in the H7
go/no-go brief before it reaches the Captain`) pre-merge HK-006 gate run.
**Test:** `tests/OpenWSFZ.Config.Tests/JsonConfigStoreTests.cs:266`
`FR-025: AudioDeviceFriendlyName round-trips via config file`
**Owner area:** `p7-device-display-name` (config layer) — NOT the D-001 H7 brief-correction
work that surfaced it. That PR touches zero `.cs` files.

## Symptom

Failed in a local full `python3 tools/pre_merge_check.py` run (Windows) — "9/10 pass," per
the PR body. Verified three ways before being waved through as unrelated:

1. Passes in isolation — 1/1, 65 ms.
2. Passes the WSL Debian full-suite leg (same suite, Linux/glibc).
3. The diff touches zero `.cs` files.

**Important correction to the PR body's stated worry:** actual GitHub Actions CI on #104
(`windows-latest`, `ubuntu-latest`, `macos-latest` — `gh pr checks 104`) came back **all
green**, including the Windows leg. The red signal was local-only (HK-006's gate script),
not a real CI failure. So the "you'll be merging over a known-flaky signal that will go red
on GitHub too" prediction did not materialize this time — worth noting so the next occurrence
isn't assumed to auto-fail CI without checking.

No `.trx`/console capture of the actual exception survived — same evidence gap FR-060 had at
first. If this fires again, capture output before rerunning.

## Why this was untracked until now

Only existed as a line in QA session memory from the #101 (`2026-07-22`) session — never
promoted to a `dev-tasks/*.md` file, unlike FR-060. It has now failed a real gate, so per
HK-000 it gets one.

## Root-cause hypothesis — matches FR-060, and corroborates it

`JsonConfigStoreTests.AudioDeviceFriendlyName_RoundTrips` (line 267) does:

```csharp
var store = new JsonConfigStore(configPath);
await store.SaveAsync(new AppConfig(...));
var reloaded = new JsonConfigStore(configPath);   // re-reads from disk immediately
```

`JsonConfigStore.SaveAsync` (`src/OpenWSFZ.Config/JsonConfigStore.cs:43-107`) uses the exact
same write-to-temp-then-`File.Move(tmp, _path, overwrite: true)` pattern (line 91) that
`CallsignRegionStore.SaveAsync` uses, and **has no retry-on-`IOException` around the
`File.Move` call** — same gap FR-060 flagged. `JsonConfigStore` does already have a
`SemaphoreSlim _saveLock` guarding *concurrent callers of itself* (see the comment at line
17-23, added for `dev-tasks/2026-07-10-config-store-concurrent-save-race.md`), but that only
serializes this store's own writers against each other — it does nothing against an external
process (antivirus/indexer) transiently holding a handle on the just-closed temp file in the
instant before rename, which was FR-060's hypothesis for `CallsignRegionStore`.

This fires the exact re-open condition the Captain set on FR-060's dev-task
(`dev-tasks/2026-07-21-flaky-fr060-isseeddata-saveasync.md`, "Captain's decision" section,
second bullet):

> The same failure signature turns up in a *different* store's `SaveAsync` test (e.g.
> `FrequencyStoreTests`), which would corroborate the "shared write-then-rename helper"
> theory rather than something specific to `CallsignRegionStore`.

It wasn't `FrequencyStoreTests` as guessed, but `JsonConfigStoreTests` — a different store,
same helper shape, same symptom profile (full-suite-only, Windows-only-so-far, passes
isolated, passes WSL, no surviving exception capture). That is corroboration, not proof, but
it is exactly the second data point FR-060 was written to watch for.

**Scope of the shared pattern**, confirmed by direct read of all five stores using
write-temp-then-`File.Move`: `JsonConfigStore`, `FrequencyStore`, `CallsignRegionStore`,
`CallsignGrammarStore`, `PropModeStore` (grep for `File.Move(tmp` across `src/`). None of the
five wrap the `File.Move` call in a retry/backoff. Only `JsonConfigStore` additionally has an
in-process `SemaphoreSlim` against its own concurrent callers — irrelevant to the
cross-process AV/indexer-handle hypothesis.

## Verdict

Low severity, not a blocker — matches FR-060's own assessment. But the re-open trigger the
Captain set has now been hit. Recommend this go back to the Captain as a decision point:
whether to scope the shared retry-on-`IOException` wrapper (2-3 attempts, short backoff)
around `File.Move` in the shared write helper(s) as a proper dev-task now that two
independent stores have shown the same signature, or continue monitoring for a third.

**Status: OPEN, monitor + escalate.** Not fixed here — no `src/` change made; this is a
tracking/cross-reference write-up only, consistent with FR-060's own handling.

## Cross-reference

See `dev-tasks/2026-07-21-flaky-fr060-isseeddata-saveasync.md` for the original hypothesis,
the ruled-out state-isolation theory, and the Captain's original accept-as-tracked-flake
decision. This file's "corroborates it" section above should be read as an addendum to that
one's re-open condition, triggered today.

## Captain's decision (2026-07-23)

Presented with the choice of (a) scoping the shared retry-wrapper dev-task now, (b)
continuing to monitor with no code change, or (c) deliberately reproducing under load to
capture a real exception first — the Captain chose **(b): continue monitoring, no code
change yet.** Both occurrences remain low-severity and self-resolving on rerun, and actual
GitHub CI has stayed green through both. **Status: OPEN, monitor only** — same disposition as
FR-060.

Re-open condition carried forward unchanged from FR-060, now watching for a **third**
independent occurrence (any store, any test, same write-temp-then-`File.Move` signature) or a
captured `.trx`/exception confirming the AV/indexer-handle hypothesis — either should trigger
scoping the retry-wrapper as a proper dev-task rather than deferring further.
