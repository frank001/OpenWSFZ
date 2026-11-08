# Developer task: issue #262, OpenWSFZ uploads its own decodes to PSK Reporter (opt-in, off by default, inert)

**Date:** 2026-10-25
**Prepared by:** QA
**Audience:** Developer (to execute); Captain (sign-off required before merge, HK-010)
**Authorised by:** the Captain, 2026-10-25, in the Architect's window: *"write the spec for the gh #262 issue"*, then his answers D1 yes (opt-in), D2 all batches 1 to 4, D3 a Settings checkbox plus an antenna field, D4 send iMD as 0 (Architect build spec §10, `a23c19b5`). Architect spec: `qa/rr-study/2026-10-25-1131-architect-to-qa-spec-262-psk-reporter-upload.md` on `arch/psk-reporter-262` (`8a83507c`), **Amendment 1 (§11, `c6f9712f`) wins wherever it differs**. QA's (k) review, P0 against the raw protocol page: `qa/rr-study/2026-10-25-1139-qa-to-architect-k-review-psk-reporter-262.md` (`qa/refset` `1dc69a8e`).
**Status:** Proposed. Per HK-011 this is a `src/` change for a separate Developer session. **No push, no PR, no merge, no `pre_merge_check.py` on your own initiative** (QA runs it on a clean checkout of the exact commit before any push).
**Branch:** `feat/psk-reporter-262`, cut from **`origin/main`** (`d20059c3` or later). Never commit to `main`.
**OpenSpec change:** `openspec/changes/psk-reporter-upload/` (proposal, design, tasks, ADDED capability `psk-reporter-upload`, `.openspec.yaml`) on QA's branch `qa/refset`: copy the five files onto your branch unchanged in your first commit (`git show qa/refset:<path>` per file). It is valid under `openspec validate --strict`.
**Version:** the proposal says `User-facing: yes`: bump `VERSION` (G9b; `origin/main` is 0.63, so 0.64 unless it moved) and update what carries the version; confirm with `python tools/check_version_bump.py origin/main`. **No `native/` change and no shim bump.**
🛑 **Licence (Captain, 2026-10-24):** method only. The protocol is a public page; **no WSJT-X source is opened, copied, transliterated or ported.** Permissive licences only; no new package is expected (UDP and byte building need none).
🔒 **NFR-021:** tests and fixtures use **Q-prefix callsigns only**; the service logs counts, never calls.

---

## 0. What you build, in one paragraph

A new `PskReporterService` that, when the operator has opted in, turns the decoded stream (batches 1 to 4, after noise suppression) into PSK Reporter datagrams (simplified IPFIX over UDP) and sends them from one IPv4 socket every 5 minutes to `report.pskreporter.info:4739`. It is inert until `pskReporter.enabled` is true, sends nothing under the placeholder identity, never touches decoding when it fails, and has a Settings checkbox with the stated opt-in text.

## 1. The wire format: the fixtures are the reference, not prose

**Do not write the encoder from any prose list, including the specs' and this one.** The reference is the public protocol page (`https://pskreporter.info/pskdev.html`) and QA's hand-built fixtures in `qa/rr-study/psk-reporter-262/` on `qa/refset`: `build_t1_fixture.py` (stdlib Python; it first reproduces the page's own two worked datagrams byte for byte, then builds the three fixtures; run it, read it, it is short) and the three `.hex` files. Points the Architect's own earlier prose got wrong, so read the bytes:

- 16-byte header: `00 0A`, total length, export time (Unix seconds), sequence number, a random 4-byte session id (constant for the process). All big-endian.
- The **receiver** descriptor is an options template: **set id 3**, template id `0x9992`, field count, **scope-field count 1**; fields `receiverCallsign` (30351.2), `receiverLocator` (.4), `decodingSoftware` (.8), plus `antennaInformation` (.9) only when the antenna text is non-empty. The **sender** descriptors are **set id 2**.
- Sender template `0x9993`, 8 fields in this order: `senderCallsign` (.1), `frequency` (.5, 4 bytes), `sNR` (.6, 1 byte), `iMD` (.7, 1 byte), `mode` (.10), `informationSource` (.11, 1 byte), **`senderLocator` (.3), then `flowStartSeconds` (IANA 150, 4 bytes)**. Sender template `0x9994`: the same 7 fields without `senderLocator`. A record's bytes follow its descriptor's order.
- Strings: a 1-byte length (at most 254) then UTF-8. Every set is padded with zero bytes to a multiple of 4, and each set's length field includes its header and padding.
- A datagram carries the template sets when due, then **one receiver record**, then **one sender block per template that has records** (the `0x9993` block, with a grid, first; then `0x9994`). `informationSource` = 1; `mode` = `FT8`; `decodingSoftware` = `OpenWSFZ <VERSION>`; `frequency` = dial Hz at capture + audio offset Hz; `flowStartSeconds` = the cycle start; `sNR` = the SNR as a signed byte clamped to [-128, 127]; **`iMD` = 0 always** (not measured; say so in a code comment).
- At most 1,400 bytes per datagram (a decision value from the MTU, not from the page).
- **The page shows no datagram with two sender blocks.** If the live test listener rejects either block, work stops and goes back to the Architect through QA. Do not invent a workaround.

## 2. Precise scope (line numbers on `origin/main` `d20059c3`; re-find them, they may have moved)

| Where | What |
|---|---|
| `src/OpenWSFZ.Abstractions/` (new `PskReporterConfig.cs`; `AppConfig.cs`) | A record with `enabled` false, `antennaInformation` "", `host` `report.pskreporter.info`, `port` 4739; a `[JsonConstructor]` so absent JSON fields take the intended defaults (pattern: `ExternalReportingTarget.cs`, `TxConfig`); a member in `AppConfig`. |
| `src/OpenWSFZ.Config/ConfigJsonContext.cs`, `src/OpenWSFZ.Web/AppJsonContext.cs` | Register the new type (source-generated serialisation). |
| `src/OpenWSFZ.Web/ConfigOverlay.cs:42-50`, `:70-83` | Add `"pskReporter"` to `NonNullableSections` and to the explicit fallbacks in `Apply`. The overlay merges nested objects, so `{"pskReporter":{"antennaInformation":"X"}}` keeps `enabled`, `host`, `port` (HK-035; test T16). |
| `src/OpenWSFZ.Daemon/DecodeBatch.cs:16` (`DecodeBatch`) | A nullable dial-frequency member, default null, so every existing construction compiles. |
| `src/OpenWSFZ.Daemon/DecodePump.cs:125`, `:197-232`, `:240-254` | `dialFreq` is already a parameter of `PublishFirstAsync` (`:197`) and `PublishSecondAsync` (`:240`): set the new member when building the batch (`:229`-`:231`, `:250`-`:253`), write the batch to the new channel next to `ExternalReportingChannel` (`:231`, `:253`). Early-decode preview rows never reach the reporting channels today; keep it so. |
| `src/OpenWSFZ.Daemon/DecodePump.cs:27` (`DecodePumpDeps`) | Add the new channel writer with a default so existing fixtures compile; update the pump tests' fixtures. |
| `src/OpenWSFZ.Daemon/Program.cs:346-351`, `:357-362`, `:860` | Create the new queue with the sizing rule of `LateBatch.CreateQsoQueue` (`LateBatch.cs:97`, which returns a `QsoBatchQueue`: 10 with the fallback on, 8 off, `DropOldest`; reuse it if its reader and writer shape fits the service, otherwise a bounded `DropOldest` channel with the same capacity function, and say which in the report), separate from the capacity-2 `externalReportingChannel`; wire the service. |
| `src/OpenWSFZ.Daemon/ExternalReportingService.cs:515-521` | The absolute exclusion (`Region` null or `Synthetic`): share or duplicate it, **never weaken it**; leave `ExternalReportingService` itself unchanged. |
| `src/OpenWSFZ.Ft8/Ft8Decoder.cs:1664-1689` (`ExtractPrimaryCallsignToken`) | **Do not touch or reuse.** It counts tokens, falls back to token 0 and strips suffixes (right for the region lookup, wrong for a public spot). The new extractor is separate. |
| `src/OpenWSFZ.Abstractions/TxConfig.cs:81`, `:87` | Source of the receiver call (`Callsign`, default `Q1OFZ`) and locator (`Grid`, default `JO33`). |
| new `PskReporterService` (Daemon), encoder, extractor | Per `tasks.md` 2.2 to 2.4 and the capability spec; injected clock, socket factory and resolver so every test runs without a network. |
| `web/settings.html`, `web/js/settings.js`, `tests/OpenWSFZ.Web.Tests/settings-payload-shape.json`, `web/js/settingsPayload.test.js` | The checkbox, the antenna field and the opt-in text: *"Sends the calls and locators of stations you receive, with your call and locator, to the public PSK Reporter service."* `host` and `port` are NOT on the page. |
| `REQUIREMENTS.md:278`, `:444`, new rows | See section 4. |
| `VERSION` (+ README/REQUIREMENTS/anything `check_version_docs.py` names) | The bump. |

## 3. Behaviour in short (the capability spec has every SHALL and scenario)

- **Inert by default (FR-088):** `enabled` false or the block absent: no socket, no DNS, no timer work, nothing queued.
- **Identity guard (FR-088):** with an empty or Q-prefix receiver call, or an empty locator, send nothing (one Warning per window as a count without a call; records counted by reason). The own-call exclusion compares the **base call** (prefix and suffix stripped), case-insensitively.
- **Sender extraction (FR-090):** classify tokens, never count them. Callsign: a digit and a letter, optionally with `/` parts; `<...>` is a hash (resolved hashed calls are NOT reported either); CQ modifier: 1 to 4 letters or exactly 3 digits; grid: `[A-R]{2}[0-9]{2}` and not `RR73`. `CQ [modifier] <call> [grid]` gives the call; the standard form gives token 1; **no fallback to token 0**; the sender locator only when this message carries a grid in the grid position; nothing cached across messages.
- **Source (FR-091):** every batch the pump writes (1 to 4), after noise suppression; the band and frequency are those **at capture**, carried on the batch; a cycle with no dial frequency reports nothing (counted). #260 is not fixed here.
- **Dedup (FR-092):** at least 5 minutes between records of one call (any band); at most one record per 60 minutes per (call, band); a band change starts a new key but respects the 5 minutes.
- **Cadence (FR-092):** one datagram per 5 minutes from a timer started with the service plus a random 0 to 60 s offset (not clock-aligned), a full datagram at once, an empty window sends nothing; templates in the first three datagrams and then hourly; the sequence number starts at 0 per process, counts **sender records** sent, receiver record not counted, unsent datagrams do not advance it; **one IPv4 socket per enable**, never bound to 4739.
- **Failure (FR-093):** errors never reach the pump; Warning once per window; the queue is bounded, oldest dropped and counted; nothing on disk. One Information line per datagram: UTC time, records in it, exclusions by reason, sequence after; **no callsigns**.

## 4. `REQUIREMENTS.md` (QA's wording; confirm the numbers are free on `origin/main`, else the next ones)

Add these rows after the last FR (format as the table's other rows; each needs a test whose DisplayName starts with its id for gate G3, mapping in `tasks.md` section 1):

| id | title | text (SHALL) |
|---|---|---|
| FR-088 | The PSK Reporter upload is opt-in, inert by default, and never runs under a placeholder identity | `pskReporter.enabled` SHALL default to false; with it false or the block absent the service SHALL create no socket, resolve no host and queue nothing. With an empty or Q-prefix `tx.callsign`, or an empty `tx.grid`, nothing SHALL be sent. A configuration POST SHALL leave the block as stored unless it names a key of it, and a partial nested update SHALL leave the other keys as saved. |
| FR-089 | A PSK Reporter datagram is the protocol page's simplified IPFIX, byte for byte | Each datagram SHALL be built as the protocol page specifies: the 16-byte header, the receiver descriptor (set id 3, template `0x9992`), the sender descriptors (set id 2, template `0x9993` with 8 fields including the sender locator before the start time, `0x9994` with 7), one receiver record and one sender block per template in use, zero padded to multiples of 4, at most 1,400 bytes; `sNR` a signed byte clamped to the byte range and `iMD` 0 in every record. |
| FR-090 | The reported sender is extracted strictly | The sender SHALL be derived by classifying tokens; a hashed (also a resolved hashed), keyword, free-text, telemetry, unparseable or own-call sender SHALL NOT be reported, and there SHALL be no fallback to the addressee. |
| FR-091 | The upload uses the GridTracker decode stream, minus the exclusions, at the dial frequency of capture | The service SHALL receive batches 1 to 4 after noise suppression through its own channel, never early-decode rows; decodes with an unknown or synthetic region SHALL never be encoded; the frequency and band SHALL be those at capture. |
| FR-092 | Reports are deduplicated and rate limited as the protocol asks | Per call at least 5 minutes between records; per (call, band) at most one per 60 minutes; at most one datagram per 5 minutes unless full; templates in the first three datagrams and hourly; the sequence number counts sender records from 0; one IPv4 source port for the life of an enabled period. |
| FR-093 | An upload failure never reaches the decoder, and every datagram is accounted for in counts | DNS and socket errors SHALL be logged once per window and retried; the queue SHALL be bounded; each datagram SHALL produce one log line with counts by reason and no callsign. |
| FR-094 | The Settings page has the opt-in control | A checkbox bound to `pskReporter.enabled` and an antenna text field, with the stated opt-in text; `host` and `port` are configuration-file only. |

Also: the integrations row at `REQUIREMENTS.md:278` ("**Future** PSK Reporter / DX cluster | HTTPS / telnet") is corrected to UDP / IPFIX and "implemented, opt-in" for PSK Reporter; the glossary line at `:444` ("Not in v0.x") is updated; add an NFR-021 note (the upload sends received stations' calls and locators, only with `enabled` true).

## 5. Acceptance criteria (what QA checks)

- **T1 to T16** per `tasks.md` section 1, each able to fail: QA's mutation checks at review include a swapped field order in the 8-field descriptor (T1 must fail), the sequence counting datagrams instead of records (T3), `iMD` not forced to 0 (T13), the own-call check on the full string instead of the base call (T4), a token-0 fallback (T4), a dedup key without the band (T6), a per-window socket (T15), and the identity guard removed (T14).
- The full unfiltered `dotnet test OpenWSFZ.slnx` is green (exact command lines and per-project counts, HK-022), `openspec validate --all --strict` clean, `check_version_bump.py origin/main` OK, the traceability gate clean.
- QA then runs `pre_merge_check.py` from a clean checkout of the exact commit (HK-006) before any push. Live L1, L2 and L3 are QA's, on the Captain's go; merge needs his sign-off (HK-010).

## 6. Report back

Commit hashes; the exact test command lines with counts; which test names carry which FR id; where the Settings control sits; the list of existing tests whose fixtures you changed (FILE:LINE); confirmation that the diff touches nothing under `native/`; any place where the fixtures and the code disagree (the fixtures win until QA and the Architect rule). Do not push.

## 7. References

Architect spec `8a83507c` + §10 `a23c19b5` + Amendment 1 `c6f9712f`; QA (k) review `1dc69a8e`; the fixtures `qa/rr-study/psk-reporter-262/`; the protocol page `https://pskreporter.info/pskdev.html`; issue #262; OpenSpec change `psk-reporter-upload`; `external-reporting` capability (`openspec/specs/external-reporting/spec.md`) for the exclusion rule; `LateBatch.CreateQsoQueue` for the channel sizing.
