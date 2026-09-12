# `osdNhardMax` default: 60 → 40, with a one-time migration for existing installs

**Date:** 2026-09-12
**Prepared by:** QA
**Audience:** Developer (to execute), Captain (sign-off required before merge, HK-010)
**Authorised by:** Architect acceptance rulings `2026-09-12-0956-architect-nhard40-default-nt-acceptance.md`
and `2026-09-12-1029-architect-nhard40-default-cc-acceptance.md` §6, on `arch/osd-nhard40-default`.
Both halves of the pre-registered gate fired (`NT-S1 ∧ CC-S1`); this task carries the PO's Q2 answer
(**M2**: migrate a persisted exactly-60 to 40 once, not a silent blanket change).
**Status:** Proposed. Per HK-011, needs the Captain's explicit sign-off before pickup; the Developer
session implementing this does not run `pre_merge_check.py` or push/merge on its own initiative
(QA verifies, Captain signs off the merge, HK-010).
**Branch:** new branch off `main`, name at the Developer's/Captain's discretion.
**Revision note (2026-09-12, same day, before any pickup):** the Architect found a BLOCKING defect
in this task's first draft — §1.3's migration marker, as first specified, is silently cleared by
every ordinary Settings-page save (HK-035-class: `POST /api/v1/config` full-replaces `AppConfig`;
the client only ever sends 3 of the decoder's 4 fields). §1.3 and §2 below are corrected in place
(marked 🔴) to make the marker server-owned and add the test that catches a regression of that fix.
**No Developer session should have started on the pre-revision text; if one did, discard that work
and restart from this version.**

---

## 0. Executive summary

Two independent measurements (`NHARD40-DEFAULT` `NT` + `CC`, 4,391 genuine synthetic decodes across
an isolated near-threshold AWGN ladder and all 5 families of S7's co-channel/compounding battery)
found **zero genuine decodes recovered by OSD that BP-only decoding would have missed, at any
`nhard` setting tested**, while `nhard=40` removes 95–98% of false decodes relative to `nhard=60` in
both arms. The CC leg also directly overturned the calibration note `decode.c:41` currently carries
(`"60 calibrated against S7 genuine histograms"`): the 2026-06-20 R6 diagnostic's "genuine" S7
population was false accepts, not genuine ones. **Change the code default from 60 to 40**, with a
one-time migration for existing config files that persist an explicit 60 (every `config.json` this
project has ever written includes an explicit `decoder` section — the code default alone reaches no
existing install).

**Caveat this task must carry forward, verbatim, into every doc-comment/spec change below** (the
Architect's own citation guard): *"no genuine loss detected, at 60 → 40, in isolated near-threshold
or S7 co-channel conditions on AWGN; 95–98% fewer false decodes."* **Never write "safe"** — fading,
drift, Doppler, timing spread (E4) and any live corroborated-loss floor remain untested/unbounded.

## 1. Precise scope

1. **`DecoderConfig.cs` default: 60 → 40**, both places (Lesson 6 / D-WFC-001 pattern — a
   `[JsonConstructor]` parameter default and a property initialiser must agree, or a partial JSON
   object and a fully-absent key deserialise to *different* effective values):
   - `src/OpenWSFZ.Abstractions/DecoderConfig.cs:36` — `int osdNhardMax = 60` → `= 40`
   - `src/OpenWSFZ.Abstractions/DecoderConfig.cs:68` — `public int OsdNhardMax { get; init; } = 60;`
     → `= 40;`
   - Update the doc comment above line 68 (currently: *"Default: 60 (D-009 calibrated: S5/S7
     histogram operating point)."*). **Drop the "S5/S7 histogram operating point" framing** (the S7
     half of that claim is now known false per `CC`'s R6 finding) and cite this arm instead, e.g.
     *"Default: 40 (`NHARD40-DEFAULT` arm, 2026-09-12: 60→40 removes 95–98% of false decodes with
     zero measured genuine loss on AWGN near-threshold/co-channel; native default unchanged, see
     below)."*
2. **Native binary default stays 60. No native rebuild in this task.** `ft8_shim.c`'s own
   `decode.c:41` constant is untouched — this task only changes the *managed* default that gets
   passed to `SetDecodeParams` at startup. **State the deliberate C#/native divergence explicitly**
   in the `DecoderConfig.cs` doc comment (the shim's compiled-in default and the daemon's own
   effective default are now different numbers on purpose; a future native-side change to match is
   a separate, native-rebuild-gated task, not this one).
   - While in the area, `decode.c:41`'s own comment (native source, not touched by this task) should
     be flagged to the Architect separately as carrying a now-known-false calibration claim — this
     task does not edit native code, but do not let the false claim go unflagged just because this
     task can't fix it.
3. **M2 migration — a persisted exactly-60 becomes 40 once, with a marker that stops it re-applying
   after an operator deliberately sets 60 again.** Implement in `JsonConfigStore.Load()`
   (`src/OpenWSFZ.Config/JsonConfigStore.cs:133-257`), alongside the existing null-vs-initialiser /
   legacy-field migration guards already in that method (`audioDeviceName` → `audioDeviceId`,
   `Logging`, `DecodeLog`, etc. — same file, same method, same pattern to extend, HK-018).
   - **Marker shape (this task's own choice, per the ruling — "shape to be specified in the
     dev-task"):** add a 4th `DecoderConfig` constructor parameter / property,
     `bool nhard40MigrationApplied = false` (JSON key `nhard40MigrationApplied`), following the
     exact Lesson-6 pattern the other three fields already use (`[JsonConstructor]` parameter
     default **and** property initialiser both `false`, so an absent key and a partial JSON object
     both resolve to "not yet migrated").
   - **Migration predicate, checked once per `Load()` call, after the existing STJ deserialisation
     and before `Load()` returns:** `config.Decoder is { OsdNhardMax: 60, Nhard40MigrationApplied:
     false }` → `config = config with { Decoder = config.Decoder with { OsdNhardMax = 40,
     Nhard40MigrationApplied = true } }`.
   - **This must be written back to disk immediately**, unlike the `audioDeviceName` legacy-rename
     guard (which is idempotent and doesn't need to persist itself every load). Without a disk
     write, the marker never survives a restart and the "stops it re-applying after an operator
     deliberately sets 60" guarantee is not met. Reuse `SaveAsync`'s own temp-file-then-rename
     pattern (`JsonConfigStore.cs:94-113`) rather than a bare `File.WriteAllText`, so a migration
     write is exactly as crash-safe as an operator-triggered save — or factor the write-then-rename
     block into a small private helper both call, at the Developer's discretion.
   - Log the migration at Warning level to `Console.Error` (matching the file's existing
     `Load()`-time warnings, e.g. the `tx.retryCount`/`tx.watchdogMinutes` clamp warnings just above
     — `Load()` runs before the `ILogger` exists, per the constructor's own comment at line 32-33),
     e.g. `"[OpenWSFZ] osdNhardMax: migrated persisted default 60 -> 40 (NHARD40-DEFAULT arm,
     2026-09-12). Set decoder.osdNhardMax explicitly to restore 60."`
   - **Do not migrate a 60 that is absent from the file entirely** (an absent `decoder` key, or a
     `decoder` object missing the `osdNhardMax` field) — that case already resolves to the *new*
     code default (40) automatically via the `[JsonConstructor]` parameter default, with no
     migration needed and no marker to set. The migration exists specifically for a file that
     spells out `"osdNhardMax": 60` explicitly, because every `config.json` this project has ever
     written does exactly that (`CreateDefault()`, `JsonConfigStore.cs:259-281`, always includes a
     fully-populated `decoder` section).
   - 🔴 **BLOCKING DEFECT, found by the Architect (HK-035 — verify an API's write semantics before
     trusting a partial update) after this task's first draft — read this before implementing §1.3
     at all:** `POST /api/v1/config` (`WebApp.cs:349-372`) deserialises the request body as a
     **full-replace** `AppConfig`, not a merge against `store.Current`. `web/js/settings.js:1328-1332`
     builds and sends the `decoder` object with **exactly three keys**
     (`kMinScorePass2`/`osdCorrThreshold`/`osdNhardMax` — never the marker). Under `[JsonConstructor]`'s
     own Lesson-6 semantics, a JSON `decoder` object that omits a key gets that field's *parameter*
     default, not whatever `store.Current` already held. **The consequence: every ordinary
     Settings-page save silently resets `Nhard40MigrationApplied` back to `false`.** An operator who
     had deliberately set `60` back via the UI would then get **silently re-migrated to `40` on the
     next restart** — exactly the outcome M2's marker exists to prevent, defeated by the one API path
     operators actually use to change this setting. (The Settings page does expose the field —
     `web/settings.html:359` — so this is the live, expected path, not a hypothetical one.)
     - **Binding fix: the marker is SERVER-OWNED.** No request body, however constructed, may ever
       set or clear it — only `JsonConfigStore.Load()`'s own migration logic (§1.3 above) may flip it
       to `true`. In the `POST /api/v1/config` handler, **before** the existing "Decoder config
       validation" clamp block (`WebApp.cs:586-622`), carry the marker forward from `store.Current`
       regardless of what (if anything) the body's `decoder` object contains — mirroring the
       `Ptt`/`CycleAudioArchive` "preserve what's already persisted" idiom immediately above it in
       the same handler (`WebApp.cs:501,515-516`, `if (config.Ptt is null) config = config with
       { Ptt = store.Current.Ptt ?? new PttConfig() };`):
       - if the body's `decoder` is present (the normal case — the real UI always sends one), force
         its `Nhard40MigrationApplied` to `store.Current.Decoder?.Nhard40MigrationApplied ?? false`
         before the existing clamp block runs, so the clamp block's own `sanitisedDecoder` carries the
         correct marker straight through;
       - if the body's `decoder` is `null` (test 7.2m's case, or any future caller that omits it) AND
         `store.Current.Decoder?.Nhard40MigrationApplied == true`, materialise `config.Decoder =
         store.Current.Decoder` (the whole object, not just the marker — there is nothing else to
         reconcile in this branch, since the client sent nothing at all for decoder). If
         `store.Current.Decoder` is `null` or its marker is `false`, leave `config.Decoder` as `null`
         — do **not** manufacture a `decoder` section out of nothing just to carry a `false` marker;
         this preserves test 7.2m's existing "a null decoder is valid" behaviour exactly.
   - **Rollback (ruling §6 item 6) — the Settings page IS the natural rollback path, not only
     hand-editing `config.json`** (corrects this task's first draft, which mentioned only the file):
     an operator sets `60` in the Settings page's decoder `nhard` field and saves. Because of the
     server-owned-marker fix above, this reaches disk as `{"osdNhardMax": 60,
     "nhard40MigrationApplied": true}` — the explicit `60` persists, and the `true` marker (correctly
     carried forward, not reset) stops the next `Load()` from re-migrating it back to `40`. Hand-editing
     `config.json` directly works too (same mechanism, same file), but is no longer the only path —
     say so in whatever operator-facing decoder-settings docs exist alongside the Settings-page UI
     (check `web/` for an existing help/tooltip string first, HK-018).

## 2. Tests (per the ruling, all four required; write them, do not just describe them)

- **`DecoderConfigTests.cs`** (`tests/OpenWSFZ.Config.Tests/DecoderConfigTests.cs`): the three
  calibrated-default assertions (7.1b, 7.1c, 7.1d — **not** 7.1a, which passes an explicit override
  and is unaffected) currently assert `OsdNhardMax` == `60`; change to `40`. Update each test's own
  `.Should().Be(60, "...")` failure-message string too, not just the numeric literal (a stale
  message that still says "60" once the assertion checks 40 is a small but real trap for the next
  reader).
- **New migration tests**, in `tests/OpenWSFZ.Config.Tests/JsonConfigStoreTests.cs` (that file
  already exists and is the right home — `JsonConfigStore.Load()` is what's under test, not
  `DecoderConfig` itself):
  1. A config file with `"decoder": {"osdNhardMax": 60}` (no marker key) → after `Load()`, effective
     `OsdNhardMax == 40` and the marker is now `true` **in the file on disk** (re-read the file
     after constructing the store to confirm the write-back happened, not just the in-memory
     `Current`).
  2. The same file, but with `"osdNhardMax": 60, "nhard40MigrationApplied": true` already present →
     `Load()` leaves it at 60 (an explicit post-migration rollback is respected, not silently undone).
  3. `"osdNhardMax": 55` and `"osdNhardMax": 70` (each without the marker) → both pass through
     `Load()` unchanged — the migration is exact-60-only, not a range clamp.
  4. A config file with **no `decoder` key at all** → `Load()` yields the new code default (`40`)
     via the existing null-guard path, and no migration marker is written (there is nothing to
     migrate; confirm the guard added in item 1 above doesn't fire when `config.Decoder` is null).
- 🔴 **New, required (§1.3's blocking-defect fix — this is the test that catches a regression of the
  fix, not the migration itself):** `tests/OpenWSFZ.Web.Tests/DecoderConfigApiTests.cs`, the natural
  home for `POST /api/v1/config` handler behaviour. **Correction to the ruling's own framing:**
  `WebTestFactory` substitutes a genuinely **in-memory** `TestConfigStore` (`AudioConfigIntegrationTests.cs`
  — no file, no `JsonConfigStore` in the loop at all), so this suite cannot exercise "the persisted
  file has 60 and the marker" — that's what `JsonConfigStoreTests` items 1-2 above already cover, in
  full, against real temp files. What this suite CAN and must cover, at the handler level: **a client
  can never clear the marker by POSTing a body shaped like the real Settings-page payload.**
  1. `POST` a `DecoderConfig` constructed directly (`kMinScorePass2:10, osdCorrThreshold:0.10f,
     osdNhardMax:40, nhard40MigrationApplied:true`) via `client.PostAsJsonAsync(...,
     AppJsonContext.Default.AppConfig)` — same technique 7.2a-l already use — to seed
     `TestConfigStore.Current` as "already migrated." (Each test method must do this seeding step
     itself, self-contained — `WebTestFactory` is `IClassFixture`-shared across the whole test class,
     so relying on another test's leftover state is not safe and must not be done.)
  2. `POST` again, this time with a **raw JSON body containing only the three keys the real
     Settings-page JS actually sends** (`{"kMinScorePass2":10,"osdCorrThreshold":0.10,
     "osdNhardMax":60}` — no `decoder` wrapper is wrong; check the exact `AppConfig`/`decoder` JSON
     shape against `GetConfig_IncludesDecoderSection`'s own response first). Use raw
     `StringContent`/`PostAsync`, not the typed `DecoderConfig`-object helper, so the marker key is
     genuinely **absent** from the wire payload, matching the real client exactly — constructing a
     full C# `DecoderConfig` and serialising it would always include every field and silently fail to
     reproduce the defect this test exists to catch.
  3. Assert the response's `Decoder.OsdNhardMax == 60` **and** `Decoder.Nhard40MigrationApplied ==
     true` — proving the handler carried the marker forward rather than letting the partial body
     reset it. This is the one assertion that fails on the unfixed handler and passes once §1.3's
     server-owned-marker fix lands; write it first, watch it fail against the old handler, then fix.
- **`FpParityP3Tests.cs` ROW 0o** (`tests/OpenWSFZ.Ft8.Tests/FpParityP3Tests.cs:118-141`): **this
  row's meaning changes and must say so explicitly in its own doc comment and `DisplayName`.**
  `ReadLiveEffectiveDecoderConfig` (`:258-276`) reads the **raw file** at
  `ConfigPathResolver.ResolvePath()` directly — it does **not** go through `JsonConfigStore.Load()`,
  so it never sees the migration. Before this change, ROW 0o asserted "the live file's effective
  params match the code default (60)"; after, it asserts "match the code default (40)" — which is
  **only true on a machine whose actual `config.json` has already been migrated (or never had a
  `decoder` key)**. On a machine holding an un-migrated, explicit `"osdNhardMax": 60` (this file's
  helper reads that literally, bypassing the migration path), **ROW 0o will now FIRE where it did
  not before this change** — correctly, since the live-effective value genuinely differs from the
  code default in that state, but this is a new, disclosed failure mode this task must document in
  the test's own comment, not leave for the next reader to rediscover. State plainly, in the class or
  method doc comment: *"ROW 0o now asserts parity against 40, not 60. It reads the config file
  directly, bypassing JsonConfigStore's migration, so it will legitimately FIRE on any machine whose
  config.json still has an un-migrated explicit osdNhardMax:60 — that is not a test bug, it is ROW
  0o doing its job. Re-run pre_merge_check.py's own gate list is unaffected; this is a QA-owned
  measurement test, not a merge gate (HK-006)."* Also update every offline-rate citation this test
  file's comments carry (`10.875%`, `10.325%`, etc.) to state its own `nhard` explicitly from this
  change onward, per the ruling — check the file for every bare percentage and prefix it.

## 3. Spec-doc consistency (found while scoping this task, HK-018 — read before concluding a spec
doesn't need touching)

Three normative-spec files and one front-end file currently assert or default to `60` and will be
**wrong**, not just stale, once §1 lands:

- `openspec/specs/decoder-settings/spec.md` — lines 19 (defaults table), 31, 47, 68, 80, 97: five
  separate `SHALL be 60` / "calibrated defaults: 10, 0.10, 60" statements, all normative. Change
  `60` → `40` in every one; leave `10` and `0.10` untouched (only `osdNhardMax`'s default moved).
- `openspec/specs/configuration/spec.md` — lines 416, 422, 427, 437, 485: same pattern (four `SHALL
  be 60` statements plus the `osdNhardMax (int, default 60, ...)` field description). Same fix.
  Line 485's example (`POST /api/v1/config` with an explicit `"osdNhardMax": 60` body) is a **caller
  explicitly setting 60** and is a valid API example either way — leave the example body's `60` as
  written (it demonstrates explicit-set behaviour, not the default), but confirm the surrounding
  prose doesn't call it "the default" anywhere.
- `web/js/settings.js` — three hardcoded `60` fallbacks that duplicate the C# default in JS and will
  silently drift out of sync with it if left alone:
  - line 874: `decoderNhard.value = String(dec.osdNhardMax ?? 60);` → `?? 40`
  - line 1116: `decoderNhard.value = '60';` (the "Reset to defaults" button handler) → `'40'`
  - line 1331: `osdNhardMax: Number.isFinite(decoderNhardRaw) ? decoderNhardRaw : 60,` (payload
    fallback when the input is somehow non-numeric) → `: 40`
  Check whether any Settings-page UI test (`tests/OpenWSFZ.Web.Tests/DecoderConfigApiTests.cs` and
  any Playwright/UI test under `tests/`) asserts the literal `60` as an expected pre-populated or
  reset value; if so, update those assertions too (grep the test tree for `osdNhardMax` again after
  the JS edit, don't assume the earlier `grep -l` pass above was exhaustive for UI-test literals).
- `openspec/changes/archive/2026-07-02-decoder-settings-page/**` — these are **archived** change
  records of the original feature. **Do not edit them** — they are a historical record of what
  shipped in that change, not a live spec; only `openspec/specs/**` (the live spec tree) reflects
  current behaviour.

## 4. Rigour controls

1. **Do not touch `ft8_shim.c` / `decode.c` or trigger a native rebuild.** The native default stays
   60; only the managed default and the migration path change. If CI's "Detect native-relevant
   changes" gate fires on this PR, something in scope leaked into `src/OpenWSFZ.Ft8/Native/` or
   `native/` — stop and check the diff.
2. **The migration is exact-60-only, never a range/clamp operation.** A persisted 55 or 70 is an
   operator's own deliberate choice (within the already-validated `[30,100]` range) and must pass
   through untouched — test 3 in §2 exists specifically to catch a future edit that widens this to
   "anything ≥ some threshold."
3. **The marker must be written to disk atomically**, using the same crash-safety discipline
   `SaveAsync` already uses for every other write to this file (§1 item 3) — a migration that
   updates `_current` in memory but dies before the temp-file rename leaves the marker unset on disk,
   so the next restart migrates again. This is directly testable (test 1 in §2 re-reads the file,
   not just `Current`) — don't skip that half of the assertion.
4. **Never write or imply "safe."** Every doc-comment, spec-doc, and log-line change in this task
   carries the Architect's own citation guard from §0 verbatim or in substance. A reviewer finding
   "OSD is safe to disable down to 40" anywhere in this diff is a defect in this task, not a
   stylistic nit.

## 5. Scope guardrails — what this is NOT

- **Not a native rebuild.** `decode.c:41`'s compiled-in 60 is untouched; flagging its now-false
  calibration comment to the Architect is a separate, follow-up conversation, not part of this diff.
- **Not a change to `KMinScorePass2` or `OsdCorrThreshold`.** Only `OsdNhardMax`'s default and its
  migration are in scope; the other two D-009-calibrated defaults (10, 0.10) are untouched everywhere
  in this task, including the spec-doc edits in §3.
- **Not a re-opening of `NT`/`CC`'s own measurements or gates.** Both are accepted and closed; this
  task implements their licensed consequence, it does not re-derive it.
- **Not `qa/cycleframer-alignment-replay/p23_common.py`'s `DECODE_PARAMS` relabelling** (ruling §6
  item 5) — that is a QA-owned harness-constant comment change in `qa/`, not `src/`, and QA is
  handling it directly, not via this dev-task.
- **Not a decision about when the Captain's own live station adopts this build.** The Captain has
  separately said he is not running 40 on his own station yet ("not now") — that is a deployment
  timing choice for him to make when he chooses to pull this change, entirely independent of whether
  this task is implemented and merged.

## 6. Deliverables

1. `DecoderConfig.cs` default change (§1.1) + doc-comment update, both sites.
2. `JsonConfigStore.Load()` M2 migration, with the new `Nhard40MigrationApplied` field on
   `DecoderConfig` (§1.3), atomic write-back included.
3. The `POST /api/v1/config` server-owned-marker fix (§1.3's blocking-defect correction).
4. All test additions/changes in §2, passing: 3 `DecoderConfigTests` value updates, 4
   `JsonConfigStoreTests` migration cases, 1 new `DecoderConfigApiTests` marker-preservation test,
   and the `FpParityP3Tests` ROW 0o doc-comment update.
5. All spec-doc and `settings.js` edits in §3.
6. A short PR description stating, verbatim, the citation guard from §0, and confirming (per §4
   item 1) that `git diff --stat main -- src/OpenWSFZ.Ft8/Native/ native/` is empty.

QA verifies against this task before recommending merge (HK-002/HK-006); the Captain signs off the
merge itself (HK-010). Neither step is implied by this task's own authorship.

## 7. References

| Reference | Content |
|---|---|
| `qa/rr-study/2026-09-12-0912-architect-to-qa-spec-nhard40-default-preregistration.md` | Base spec, `NT` leg, `BAR_S=0.05`, PO's M2 answer to Q2 |
| `qa/rr-study/2026-09-12-1000-architect-to-qa-nhard40-default-amendment-1-cc-leg.md` | Amendment 1, `CC` leg, the consequence table this task implements item 3 of |
| `qa/rr-study/2026-09-12-0945-qa-to-architect-nhard40-default-nt-result.md` / `…-0956-…-acceptance.md` | `NT-S1` result + acceptance |
| `qa/rr-study/2026-09-12-1025-qa-to-architect-nhard40-default-cc-result.md` / `…-1029-…-acceptance.md` | `CC-S1` result + acceptance, R6 finding, this task's exact §6 scope |
| `src/OpenWSFZ.Abstractions/DecoderConfig.cs:16-69` | The record to edit — read the Lesson-6 comment at the top before touching either default |
| `src/OpenWSFZ.Config/JsonConfigStore.cs:133-257` (`Load`), `:43-129` (`SaveAsync`) | Where the migration goes, and the write pattern to reuse for it |
| `tests/OpenWSFZ.Config.Tests/DecoderConfigTests.cs`, `JsonConfigStoreTests.cs` | Existing + new tests |
| `src/OpenWSFZ.Web/WebApp.cs:349-372` (POST body deserialisation, full-replace), `:497-516` (`Ptt`/`CycleAudioArchive` preserve-what's-persisted idiom to mirror), `:586-622` (existing decoder clamp block, the marker fix goes just before it) | The blocking-defect fix's exact location |
| `tests/OpenWSFZ.Web.Tests/DecoderConfigApiTests.cs`, `AudioConfigIntegrationTests.cs` (`TestConfigStore`, in-memory, shared per test class — not file-backed) | Where the new marker-preservation test goes, and why it can't test the file round-trip (that's `JsonConfigStoreTests`' job) |
| `tests/OpenWSFZ.Ft8.Tests/FpParityP3Tests.cs:118-141,258-276` | ROW 0o and its raw-file reader — document the meaning change here |
| `openspec/specs/decoder-settings/spec.md`, `openspec/specs/configuration/spec.md` | Normative spec text asserting the old default — five-plus-four `SHALL` lines to update |
| `web/js/settings.js:874,1116,1331` | Front-end hardcoded `60` fallbacks that duplicate the C# default |
| `qa/cycleframer-alignment-replay/p23_common.py:49` | QA's own harness constant — QA relabels this directly, not part of this task |

---

*Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>*
*Claude-Session: https://claude.ai/code/session_018hitYaAmoBNwbRKNMuCk3m*
