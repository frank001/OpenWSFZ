# QA → Architect — Items 1-4 results (2026-08-27 outstanding work order)

**Author:** QA, 2026-08-28 00:30Z (`date -u`, HK-017).
**Responds to:** `qa/rr-study/2026-08-27-2141-architect-to-qa-outstanding-work-order.md`.
**Status:** Items 1-2 done and committed (`d565c57`). Item 3 **declined as specified** — see §1,
a correction, not a refusal on HK-021(k) grounds. Item 4 verified — see §2.

---

## 1. Item 3 — declined as specified: this is not a new defect, it's a rediscovery

**Do not file a new dev-task for the self-contained-publish crash.** Before authoring one, HK-018
said to check what's already gathered — I did, and found this is fully covered by two existing
dev-tasks, both from 2026-07-18:

- `dev-tasks/2026-07-18-aot-comwrappers-audio-migration.md` — the real fix (ComWrappers rewrite of
  NAudio's `[ComImport]` WASAPI COM interop). **Status: DEFERRED, Captain's explicit decision,
  backlog, not scheduled** — "revisit only when Native AOT specifically... becomes the actual
  goal."
- `dev-tasks/2026-07-18-self-contained-non-aot-working-binary.md` — the working alternative.
  **Status: implemented and gated.** `tools/publish_selfcontained.py` overrides `PublishAot=false`
  at the command line and is the project's canonical publish path — wired into
  `.github/workflows/ci.yml`, `tools/pre_merge_check.py` (`step_selfcontained()` vs. the
  deliberately-separate, known-broken `step_aot()`), and documented prominently in `README.md`
  (lines 259-280), in bold: **"Do not run `dotnet publish src/OpenWSFZ.Daemon -c Release -r <rid>
  --self-contained` directly... that produces an AOT binary with broken audio."**

That bolded line is character-for-character the command I ran during the sweep setup. I hit a
documented, already-solved footgun because I didn't check `README.md`'s publish section or
`tools/` before reaching for a raw `dotnet publish` invocation — not a fresh discovery.

**Correction owed to the 2026-08-27 sweep report itself:** Section 1 item 1 characterizes this as
"a build defect found and fixed before arming anything." That framing is wrong — it should read as
"used the wrong publish command; `tools/publish_selfcontained.py` is the documented correct one."
I'm not editing that report again (it's already Rev 2, committed, and this doesn't change any
number or verdict in it) — flagging it here so the record is straight and recorded once, not
silently left wrong. Happy to add a Rev 3 addendum if you'd rather it live in the report itself.

No action taken on `PublishAot`/`RuntimeIdentifier`/the NativeAOT TODO — that's Item 5/6-shaped
(a Captain decision on priority, not a QA-tooling fix), and it's already exactly where the
2026-07-18 dev-task left it.

## 2. Item 4 — verified, does not currently reproduce; a different sibling does

Ran `dotnet test tests/OpenWSFZ.Daemon.Tests` (Release, full project — same invocation shape as
the original repro) **3 times** back to back: **621/621, 620/621, 621/621.**

- **`CycleArchiveServiceTests.Manifest_WritesOneRowPerArchivedCycle_InOrder`** (the test named in
  the work order) **did not fail in any of the 3 runs.** Per your instruction ("if it no longer
  does [reproduce], say so and retire the note rather than leaving it open indefinitely") — said
  so, in a dated update appended to `flaky-cyclearchiveservice-manifest-test-todo.md`. **Not
  reclassified as fixed** — the underlying tight-timeout code is untouched, so 0/3 today most
  plausibly reflects lighter concurrent load, not a resolved race. Left open as a latent risk,
  not closed, and no dev-task filed.
- **A different test flaked instead, first occurrence:**
  `QsoAnswererServiceTests.PendingTarget_LateStart_FiresImmediatelyInSameWindow`, same
  `Poll.UntilAsync`-timeout family, confirmed load-dependent (passed 121 ms in isolation). Logged
  as its own first-flake memory TODO
  (`flaky-qsoanswererservice-pendingtarget-latestart-todo.md`), per TESTING_STRATEGY §11.3 — a
  first occurrence, not yet a blocker. Full mechanism (a real wall-clock-vs-`FakeTimeProvider` race
  the test's own comment already names, masked by a flat `Task.Delay(50)`) is in that note.

Net: the specific item you asked about checks out clean; the general pattern it belongs to (tight
`Poll` timeouts losing their margin under full-suite CPU contention) is still live and just landed
on a different test this time. Nothing filed as a dev-task for either — both stay as tracked,
open, load-dependent risks per the existing handling convention for first/unconfirmed flakes in
this codebase.

## 3. Housekeeping note (your Item 7, partial)

While verifying Item 4 I had to stop a stale `OpenWSFZ.Daemon.exe` (PID 17968, left running from
the sweep setup) — it was file-locking the build output and blocking `dotnet test` entirely
(`MSB3027`/`MSB3021` copy failures). Stopped cleanly; no other effect. Doesn't answer your Item 7
questions (orphaned `2ae939c/` results dir, the untracked run logs, `_pre-run-backups/`,
`daemon_rr_setup_2026-08-22.log`'s tracked-but-modified status) — those are still the Captain's to
weigh in on, not mine to decide unilaterally per your own instruction.

---

## 4. Not started (per your §8 blocklist, restated for the record)

`NBR-A`, the coherent extractor, any `src/` change, and PR #133 — untouched, as instructed.
