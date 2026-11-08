# Developer task: issue #262 follow-up round (accounting line, Settings status, placement, 6-character locator)

**Date:** 2026-10-26
**Prepared by:** QA
**Audience:** Developer (to execute); Captain (sign-off before merge, HK-010)
**Authorised by:** Architect Amendment 2 (§14, `42664e92`, corrected `74b04d23`, A2.3 F-a to F-e) and the Captain's choices of 2026-10-25: the optional 6-character locator (option 2) and the placement **at the top of the External Programs tab**.
**Status:** Proposed. HK-011: a `src/` change for a separate Developer session. **No push, no PR, no merge, no `pre_merge_check.py` on your own initiative.**
**Branch:** continue on `feat/psk-reporter-262` (head `6ef0b33b`, v0.64, QA-approved). Same PR, one round, one re-review. Never commit to `main`.
**OpenSpec change:** `openspec/changes/psk-reporter-upload/` on `qa/refset`: refresh your copy of `design.md` (decisions 15 to 19), `tasks.md` (section 1b, tasks 2.8, 2.9) and `specs/psk-reporter-upload/spec.md` unchanged, with `git show qa/refset:<path>`. New fixture: `qa/rr-study/psk-reporter-262/t1_receiver_locator6.hex` (builder `build_t1_fixture.py`, case: `tx.grid` `JO33`, locator `JO33ed`). Spec text wins over this note.
**Version:** G9b decides; the same PR with no merge between, so 0.64 may stand (`python tools/check_version_bump.py origin/main`).
🔒 NFR-021: Q-prefix calls only in tests; counts, never calls, in every log line and in the status endpoint. 🛑 No `native/` change; no WSJT-X source.

## 1. What to build

| Id | What | Spec / tasks |
|---|---|---|
| F-a | One Information line at the end of **every** send window, even when nothing is sent: `PSK Reporter: N decodes seen, M reported: region=a, no-dial=b, identity=c, hashed=d, own-call=e, dedup=f`. `0 decodes seen` for an empty window. Counters restart each window. | "Each send window is accounted for", T17 (1.19) |
| F-b | Read-only endpoint under `/api/v1/` (counts and a reason code; no callsign) and a status line next to the checkbox: `off`; `on, waiting for the first datagram`; `on, last datagram at HH:MM:SSZ with N records`; `on but nothing is being reported: <dominant of identity / no dial / region>`. **Same counters as F-a**, one source. | "The Settings page shows what the upload is doing", T18 (1.20) |
| F-c | The "PSK Reporter" box is the **first box on External Programs**, above the GridTracker checkbox and target table. | FR-094 scenario "Where the control is", 1.23 |
| F-d | `pskReporter.locator` (string, default `""`). Valid: empty or `[A-Ra-r]{2}[0-9]{2}[A-Xa-x]{2}`. Stored as typed, **sent normalised** (first 4 upper, last 2 lower: `JO33ed`). Used only when valid **and** its first 4 characters equal `tx.grid` (case-insensitive); else `tx.grid` is sent with **one Warning per window** naming invalid or mismatch, no callsign. Identity guard unchanged (`tx.grid` non-empty). Field "Locator for PSK Reporter (6 characters, optional)"; page refuses to save an invalid value; the server answers **400** and leaves the config unchanged. Nested overlay keeps the other keys (HK-035). Nothing in the transmit path changes. | "The receiver locator may be a 6-character locator", T19, T20 (1.21, 1.22) |
| F-e | The daemon never queries the retrieve interface. A test that the only network activity is the injected socket and resolver. | "The product never queries...", 1.24 |

Also: `settings-payload-shape.json` and `settingsPayload.test.js` gain `locator`; `REQUIREMENTS.md` gets FR-095 and FR-096 and FR-094 widened (wording below).

## 2. `REQUIREMENTS.md` wording (QA's)

| id | title | text |
|---|---|---|
| FR-095 | Every PSK Reporter send window is accounted for, and the Settings page shows the state | At the end of every send window while the upload is active the service SHALL log one Information line with the decodes seen, the records reported and the exclusions by reason (counts only, no callsign), whether or not a datagram was sent; the Settings page SHALL show a status line (off, waiting, last datagram time and record count, or the dominant refusal reason) from the same counters through a read-only endpoint carrying no callsign. |
| FR-096 | The receiver locator may be a valid 6-character locator that matches `tx.grid` | `pskReporter.locator` SHALL be empty or six Maidenhead characters; it SHALL be sent, normalised, only when valid and its first 4 characters equal `tx.grid`, otherwise `tx.grid` SHALL be sent with one Warning per window and no callsign; the server SHALL answer 400 for an invalid value. |
| FR-094 (widened) | The Settings page has the opt-in control | A "PSK Reporter" box at the top of the External Programs tab with the checkbox, the antenna field, the locator field, the stated opt-in text and the status line; `host` and `port` stay configuration-file only. |
| FR-093 (add) | | The daemon SHALL NOT query the PSK Reporter retrieve interface. |

Each new row needs a test whose DisplayName starts with its id (gate G3).

## 3. Acceptance (what QA checks)

- T17 to T20 and 1.23, 1.24, each able to fail. QA's mutation set for this round: counters not reset per window (T17); the accounting line skipped when no datagram is sent (T17); the status endpoint computed from its own counters instead of the shared ones (T18, the move-one-counter test); locator used without the `tx.grid` match, or not normalised, or the 400 removed (T19/T20); the box moved below GridTracker (1.23); a reason code replaced by a callsign in the endpoint body (T18).
- Full unfiltered `dotnet test OpenWSFZ.slnx` green, exact command lines and per-project counts (HK-022); `openspec validate --all --strict`; version and traceability gates clean; the existing suite unchanged and green.
- Then QA reviews (HK-039, `Reviewed-commit:` before any acceptance run), runs `pre_merge_check.py` on a clean checkout of the exact commit (HK-006), and asks the Captain for the push go and the merge sign-off. The Captain's two-instance live run (8080 and 8081) is his.

## 4. Report back

Commit hashes; test command lines with counts; which test carries which FR id; the endpoint's path and body shape; where the counters live; existing tests whose fixtures changed (FILE:LINE); `git diff --stat -- native/` empty. Do not push.
