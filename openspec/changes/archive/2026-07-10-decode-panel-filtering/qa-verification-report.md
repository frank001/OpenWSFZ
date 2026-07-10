# QA Verification Report — `decode-panel-filtering`

**Date:** 2026-07-10
**Change:** `openspec/changes/decode-panel-filtering/`
**Branch:** `feat/decode-panel-filtering`
**Commit at time of this report:** `3cd9c74`
**Prepared by:** QA Engineer

---

## 1. Summary

`decode-panel-filtering` adds a daemon-owned, ephemeral, per-column filter over
`#decodes-table` (four attribute allow-list axes — DXCC entity, continent, CQ zone, ITU zone —
plus five worked-before tri-state axes), consulted both by the frontend for row visibility and
by `QsoAnswererService`/`QsoCallerService` at their engagement-decision points so TX automation
never engages a station the operator has filtered out.

This report covers the full QA pass on this change: the initial backend/frontend review, a
Captain-directed UI polish round, and — the bulk of this report — an escalating series of
verification passes prompted by the Captain repeatedly and correctly pushing back on
insufficient proof, ending in a live, hardware-in-the-loop verification of all nine filter axes
against a real running daemon. **Verdict: approved.** No outstanding defects. One new standing
policy was established as a direct result (§6).

---

## 2. Why this verification effort was structured the way it was

The implementation's own `tasks.md` (task 6.4) had left its end-to-end check as an unattempted
manual item, reasoning that it exercised "the real audio-capture → FT8-decode → TX pipeline
against a live/simulated signal... outside what could be driven headlessly here." That
reasoning turned out to be only partly correct — a live audio pipeline genuinely could be driven
headlessly in this environment, once actually attempted, and everything reported as
"unverifiable" was in fact verifiable. Each escalation below was prompted by the Captain
declining to accept the previous level of proof as sufficient, which is the reason this report
documents four distinct verification tiers rather than one:

1. Static code review (read the diff, matched it against design.md's decisions).
2. In-process verification using hand-typed `DecodeResult`s (the pre-existing unit tests).
3. In-process verification using genuinely synthesised-and-decoded audio, but still not a real
   running daemon (built, then corrected after being challenged on scope, then corrected again
   after being challenged on whether it was really "standalone").
4. Live, hardware-in-the-loop verification against the real running daemon, real virtual-cable
   audio injection, and the real HTTP API — the tier that finally closes task 6.4's original gap.

---

## 3. What was done, in order

### 3.1 Initial implementation review

Reviewed the full diff against `proposal.md`/`design.md`/the delta specs: `DecodeFilterState`,
`DecodeFilterEvaluator`, `IDecodeFilterStore` (`src/OpenWSFZ.Abstractions/`), the
`QsoAnswererService`/`QsoCallerService` gating hooks, the `GET`/`POST /api/v1/decode-filter`
endpoints and `decodeFilterChanged` WebSocket broadcast (reusing the N6 scope-guard pattern
correctly), and the frontend popup UI (`web/js/main.js`, `web/js/decodeFilter.js`,
`web/css/app.css`).

Ran, independently rather than trusting the branch's own claims: `dotnet build` (0/0),
`dotnet test` (**1006/1006**, matching the claimed count), `openspec validate --strict --all`
(**51/51**).

**One blocking defect found and returned for fix:** `web/js/decodeFilter.test.js`'s own header
comment contained a literal `**/` inside an example glob (`node --test "web/js/**/*.test.js"`),
which is JavaScript's block-comment-closing token — it silently truncated the file's own
JSDoc header, so `node --test` threw a `SyntaxError` and 0 of the file's 21 tests ever actually
ran, despite `tasks.md` claiming all 21 passed. Verified underlying logic was correct once the
comment was reworded in a scratch copy (all 21 passed) — a self-inflicted parse error, not a
logic defect, but still a hole in what had been claimed as verified.

### 3.2 Dev-task and re-review — popup UI polish

Drafted `dev-tasks/2026-07-10-decode-panel-filtering-popup-ui-polish.md` covering three items:
Captain-reported checkbox-alignment inconsistency in the filter popups, a request for Select
All/Select None controls on the four attribute-allow-list sections, and the JS test-file defect
from §3.1.

Root-caused the alignment issue by direct pixel measurement in a real headless browser (not by
eye) before handing it off: the codebase's global `input, select { width: 100%; }` rule was
stretching the popup checkboxes to inconsistent widths depending on each row's label length; the
fix mirrors two existing precedents (`.checkbox-label input[type="checkbox"]`,
`.waterfall-hold-label input[type="checkbox"]`) rather than inventing a new pattern.

Re-reviewed the implementation: checkbox sizing fixed and confirmed via `getBoundingClientRect()`
measurement (uniform 13×13 px, previously as wide as 89 px on the shortest-label row); Select
All/Select None correctly scoped to the attribute section only (not the worked-before section,
not the Ctc popup, which has no attribute section); the JS test file fixed exactly as
recommended and additionally wired into CI (`.github/workflows/ci.yml`, Linux-only leg) — a
step beyond what was strictly required. Approved, zero outstanding findings.

### 3.3 First "standalone test" attempt — corrected after Captain pushback

Asked to "design a stand-alone test to verify the working of the filtering and sending and
answering CQ while the filter is engaged, using the synthesiser to generate signals." Two rounds
of correction followed, both initiated by the Captain rather than self-caught:

- **First attempt** embedded two synthesised-signal test cases directly into
  `OpenWSFZ.Daemon.Tests` — which meant it ran as part of `dotnet test OpenWSFZ.slnx`, not
  standalone at all. Caught by the Captain asking directly whether that was what had happened;
  reverted in full (test file, fixture WAVs, `csproj` changes all removed).
- **Rebuilt as a genuinely separate console tool**, `qa/decode-filter-synth-verify/` — its own
  `.csproj`, not referenced by `OpenWSFZ.slnx`, run manually via `dotnet run`. Initially covered
  only one of `DecodeFilterState`'s nine axes (`AllowedEntities`) against one of the two gated
  services. Challenged again ("are you sure two signals are enough to test all the different
  filtering options?") — answer was no; expanded to cover **all nine axes** (one real-decoded
  scenario per axis) plus the all-candidates-filtered-out case against `QsoAnswererService`, and
  three distinct `QsoCallerService` gating mechanisms (`First`-mode skip, `First`-mode
  all-filtered, `None`-mode `SelectResponderAsync` rejection) — **13 scenarios total, all
  passing**, stable across repeated runs.
- Still, when asked directly "did you run this against the application?", the honest answer was
  no — every one of the 13 scenarios instantiates the real `Ft8Decoder`/`QsoAnswererService`/
  `QsoCallerService` classes *in-process*, inside a throwaway console process. The real
  `OpenWSFZ.Daemon.exe`, its audio-capture pipeline, its HTTP/WebSocket API, and real PTT were
  never touched by this tier.

### 3.4 Live, hardware-in-the-loop verification

The Captain proposed driving this for real: start the daemon with its input routed through a
virtual audio cable, and have QA inject the synthesised signal and verify via the real API. This
required several things worked out live rather than assumed in advance:

- Confirmed this environment can see real (virtual) audio hardware at all —
  `qa/rr-study/list_devices.py` found both VB-CABLE and Voicemeeter installed and enumerable.
- **Discovered a real constraint**: the production `callsign-regions.json` seed data
  (`CallsignRegionDefaults.cs`) maps the *entire* Q-prefix synthetic-callsign range to one shared
  catch-all entity (`"Synthetic (R&R Study)"`, continent/CQ-zone/ITU-zone all `null`). Two
  different synthetic test callsigns are therefore indistinguishable on any of the four
  attribute axes against real, unmodified region data. Resolved by writing an **isolated,
  instance-local** `callsign-regions.json` override (still Q-prefix, NFR-021-compliant) giving
  the two test callsigns two distinct, non-synthetic entities/continents/zones — confirmed via
  the real `GET /api/v1/region-data/lookup` diagnostic endpoint before relying on it.
- **Caught a real operational near-miss before it could do any harm**: the isolated instance's
  first startup left `decodeLog.path` at its default, which resolved (via
  `Path.GetDirectoryName` on a bare relative path) to the *real* repository-root `ADIF.log`
  (757 real callsigns) for the worked-before index's read — caught immediately, confirmed
  read-only (file size/timestamp unchanged, `757 distinct callsign(s)` was visibly wrong for a
  fresh isolated instance), and fixed by writing the full corrected config (isolated
  `decodeLog.path`, audio devices, `tx.autoAnswer`) before any further action. The daemon's
  real, shared `ADIF.log`/`callsign-regions.json` were never written to at any point.
- Pre-seeded an isolated `ADIF.log` with one prior QSO for one test callsign, set
  `contactStates: ["never"]` via the real `POST /api/v1/decode-filter`, and played the combined
  two-station CQ signal into the cable, timed to the real FT8 15-second cycle boundary. Real
  result, confirmed both via the real `GET /api/v1/tx/status` and the daemon's own unedited log:
  the filtered station was never engaged; the other was answered, with a genuine
  `IPttController.KeyDownAsync` → real WASAPI playback of one full FT8 transmission
  (606,720 samples).
- **Extended to all nine axes on request**, using the isolated region override above so every
  attribute axis (not just worked-before) had genuinely distinguishable real data to filter on.
  Built a script that loops all nine axes (set filter → abort-and-re-arm → inject at the next
  cycle boundary → poll the real API), cross-checked independently against the daemon's raw log
  (not just the polling result) — **all nine passed**, confirmed via 9 distinct
  `QsoAnswererService: CQ detected from Q1BBB` log lines and zero `Q1AAA` detections.
- Torn down cleanly: isolated daemon process stopped, all temp artefacts removed, real
  `ADIF.log` re-confirmed untouched (unchanged size and timestamp throughout).

### 3.5 Made permanent

The live-hardware script existed only as an ad hoc, deleted-after-use set of shell/Python
commands through §3.4. Per the Captain's direction this session, it has now been rebuilt as a
committed, repeatable tool — `qa/decode-filter-synth-verify/live_verify_9_axes.py` — that
performs the same nine-axis live verification end to end from a single invocation (device
auto-discovery, isolated config/ADIF/region-override generation, daemon start, the nine-axis
loop, teardown) and **automatically writes its own timestamped Markdown report** to
`qa/decode-filter-synth-verify/live-reports/` on every run, success or failure, including a
distinct outcome for "no virtual cable found on this machine" so a report is never silently
skipped. Verified by running it fresh end-to-end after being written (not merely reviewed as
code) — see `qa/decode-filter-synth-verify/live-reports/2026-07-10T163715Z-3cd9c74.md` for that
run's own auto-generated report, referenced in §5 below. A new standing policy governing when
this script must be re-run is recorded in `MEMORY.md` (§6).

---

## 4. Results — full picture

| Layer | What it exercises | Result |
|---|---|---|
| `DecodeFilterEvaluatorTests.cs` | All 9 axes, fail-open-on-unresolved, combinations — hand-typed `DecodeResult`s | 21/21 pass |
| `decodeFilter.test.js` | JS-ported predicate, mirrored 1:1 with the C# suite | 21/21 pass (0/21 before the fix in §3.1) |
| `QsoAnswererServiceTests.cs` / `QsoCallerServiceTests.cs` (decode-panel-filtering additions) | Gating logic at both services' engagement-decision points, hand-typed `DecodeResult`s | all pass, part of full suite |
| `DecodeFilterEndpointTests.cs` | `GET`/`POST /api/v1/decode-filter`, WebSocket broadcast | all pass, part of full suite |
| Full `dotnet test OpenWSFZ.slnx` | Whole-solution regression | **1006/1006** |
| `openspec validate --strict --all` | Spec/delta-spec conformance | **51/51** |
| `qa/decode-filter-synth-verify` (in-process console tool) | Real native decoder + real `QsoAnswererService`/`QsoCallerService`, synthesised-and-decoded audio, no hardware | 13/13 scenarios pass, stable across repeated runs |
| `qa/decode-filter-synth-verify/live_verify_9_axes.py` (real daemon, real hardware) | Real daemon process, real VB-CABLE audio injection, real native decoder, real API, all 9 axes | **9/9 pass**, cross-checked against the daemon's raw log |

---

## 5. Evidence retained

- `qa/uat-tmp/popup-dxcc-polished.png`, `popup-dxcc-select-all.png`, `popup-dxcc-select-none.png`,
  `popup-ctc-polished.png` — real-browser screenshots from the §3.2 re-review.
- `qa/decode-filter-synth-verify/README.md` — full description of both the in-process tool and
  the live-hardware script.
- `qa/decode-filter-synth-verify/live-reports/2026-07-10T163715Z-3cd9c74.md` — the auto-generated
  report from the verification run of the finished `live_verify_9_axes.py` script itself,
  confirming all nine axes pass at commit `3cd9c74`.

---

## 6. Standing policy established as a result

Recorded in `MEMORY.md` → `decode-panel-filtering-live-verification-policy.md`: any future
change touching `DecodeFilterState`, `DecodeFilterEvaluator`, `IDecodeFilterStore`, or the
filtering hook inside `QsoAnswererService`/`QsoCallerService` must re-run
`live_verify_9_axes.py` against a real daemon before merge, with its auto-generated report
committed alongside the change. This is additive to, not a replacement for, the existing
in-process test coverage. Full rationale, including the `ADIF.log` near-miss from §3.4 as the
concrete argument for why in-process coverage alone is insufficient, is recorded in that memory
file.

## 7. Known residual gap (accepted, not blocking)

The live script routes audio through a virtual cable and drives TX via
`AudioOnlyPttController` (a WASAPI output device) — real physical RF hardware and a real
serial/CAT-keyed PTT line are still not exercised. This was discussed explicitly and accepted as
out of scope for this capability: physical-hardware verification is a daemon-wide concern, not
specific to filtering, and is not part of this policy going forward without a separate, explicit
decision to extend it.
