# QA (k) review, P0 included: issue #262, opt-in PSK Reporter upload (Architect spec `8a83507c` + §10 `a23c19b5`)

Written 2026-10-25 11:39Z (`date -u`). Reviewed: `qa/rr-study/2026-10-25-1131-architect-to-qa-spec-262-psk-reporter-upload.md` on `arch/psk-reporter-262`, FILE:LINE against `origin/main` `d20059c3`.
The protocol page was fetched **raw** with `curl` at 11:34:26Z (HTML SHA-256 prefix `fba4c8f173952488`, 27,434 bytes) and read in full, not through a summarising tool.

## Verdict

**ACCEPTED, subject to seven spec amendments (F1 to F7 below) that the Architect makes in the spec text before the handoff.** P0 found **no contradiction of §1's byte values** (so the stop rule does not fire): every port, template id, field id, length, cadence and dedup rule in §1 is on the page as stated. It found **omissions and two defects in the spec's own tests and wording**, which is what the review is for. D4's question is answered: **no fixed sender descriptor has `sNR` without `iMD`** (the page lists four; both with `sNR` also carry `iMD`), so D4 stood, and the Captain chose iMD = 0.

## P0: §1 against the page

| §1 claim | Page | Result |
|---|---|---|
| UDP to `report.pskreporter.info` port 4739; `pskreporter.info` no longer works for production since August 2018 | "Data Reporting" | ✓ |
| Test listener `pskreporter.info` port 14739, results at `/cgi-bin/psk-analysis.pl` | "Testing"; the link is `href="/cgi-bin/psk-analysis.pl"` | ✓ |
| All datagrams from one source port | "the same UDP source port number should be used to send each of the datagrams" | ✓ (but not a requirement or test in §2/§3: **F6**) |
| Simplified IPFIX (RFC 5101), enterprise 30351, big-endian | "Cookie Cutter"; `00 00 76 8F` = 0x768F = 30351 | ✓ |
| Header 16 bytes: `00 0A`, length, export time, sequence, random session id | `00 0A ll ll tt tt tt tt ss ss ss ss ii ii ii ii` | ✓ |
| Sequence counts **records**, not datagrams | "incremented by the number of reports ... the count of reports and not the count of packets" | ✓ (what counts as a record, and the start value, are not on the page: **F7**) |
| Receiver template `0x9992`: callsign .2, locator .4, software .8, optional antenna .9 | `99 92`, `80 02`, `80 04`, `80 08`, `80 09` | ✓ |
| Sender template `0x9993`; fields callsign .1, frequency .5 (4 B), mode .10, informationSource .11 (1 B), flowStartSeconds IANA 150 (4 B); optional sNR .6 + iMD .7 (1 B each), senderLocator .3 | four descriptors with 5, 6, 7 and 8 fields | ✓ |
| Each set padded to a multiple of 4 | receiver record, sender block and the template sets all end in `00 00` padding; every length field includes header and padding | ✓ |
| At most one datagram per 5 minutes unless full; timer not synchronised to the clock; may run from program start | "Data Reporting" | ✓ |
| Templates in the first three datagrams, then at least hourly | "first three datagrams ... and then once per hour" (and "first few" elsewhere on the page) | ✓ |
| `informationSource` = 1 | "must be set to the value 1" (0x80 bit = test transmission) | ✓ |
| Each call at most once per 5 minutes, ideally once per hour unless changed (a band change is the example) | "Data Gathering" | ✓ (the spec's own test of it is wrong: **F1**) |
| Reported call = the whole text after DE, prefixes and suffixes; case-insensitive | "Notes" | ✓ |
| `decodingSoftware` names the software and version | statistics page shows it | ✓ |

**The page is self-consistent on lengths** (QA recomputed every one): receiver descriptor 0x24/0x2C, sender descriptors 0x2C/0x34/0x3C/0x44, the page's complete example datagram 0xAC = 172 bytes, the later one 0x5C = 92.
**Two page typos, immaterial:** the attribute table says `decoderSoftware` and the descriptor text `decodingSoftware`; the page's two worked datagrams disagree on the mode bytes (`50 53 4B` "PSK" in the complete one, `50 53 4C` elsewhere).

## T1 fixtures, hand-built (committed with this review)

`qa/rr-study/psk-reporter-262/build_t1_fixture.py` builds the bytes **from the page's byte tables**, independent of any product code, and its first act is a **self-check: it reproduces the page's own two worked datagrams byte for byte** (172 bytes, sequence 1, and 92 bytes, sequence 4), and with `--page` every byte of both is found in order in the page text. The page's examples carry real third-party callsigns, so (NFR-021) the script encodes them with same-length Q-calls and compares with only those ASCII bytes swapped.
Fixtures (Q-prefix calls only, fixed numbers, written as `.hex`): `t1_8field_and_7field` (272 bytes: receiver Q1OFZ/JO33/"OpenWSFZ 0.63"; Q1ABC with grid in the 8-field block, Q2DEF without in the 7-field block), `t1_with_antenna` (296 bytes, the 4-field receiver descriptor), `t1_templates_not_due_snr_clamped` (80 bytes: no descriptors, sequence 9 after 2 records, SNR −132 clamped to −128 = `0x80`, for T3 and T13).

## Findings: required amendments to the spec text (F1 to F7)

- **F1 (T6 contradicts itself, and R6).** T6 expects 1 record "again at 6 min" and then "none" at 30 min on the same band, but R6 says once per hour per (call, band). Both cannot hold. **Restate the rule** as the page gives it: a hard minimum of **5 minutes per call** (any band) AND **60 minutes per (call, band)** unless it changed; then T6 reads: 3× in 4 min → 1 record; again at 6 min, same band → **0**; at 61 min on another band → 1; same call at 30 min after that, same band → 0.
- **F2 (R4/T4 CQ modifiers).** The existing helper keys on token count (`Ft8Decoder.cs:1671-1675`: 2 or 3 tokens → token 1, 4 or more → token 2), so `CQ DX Q1ABC` (3 tokens, no grid, a directed CQ) would be read as call "DX". R4's strict rule needs a **classifier, not a count**: a token is a callsign only if it contains a digit; a directed-CQ modifier is letters only (1 to 4) or 3 digits. **Add to T4:** `CQ DX Q1ABC` (no grid), `CQ Q1ABC` (2 tokens), `CQ POTA Q1ABC JO22`, `CQ 000 Q1ABC JO22`, and a DXpedition-style `Q1ABC RR73; Q2DEF <Q3GHI> -08` (expected: not reported, with its reason).
- **F3 (field order on the wire).** §10 lists the 8-field descriptor with `senderLocator` **last**, but on the wire the page puts it **before `flowStartSeconds`**: `callsign, frequency, sNR, iMD, mode, informationSource, senderLocator, flowStartSeconds`. A record's bytes follow the descriptor's order, so a Developer reading §10's list would produce a datagram the server mis-parses. R2 must **cite the fixtures and the page's descriptor order, not the prose list**. R2 should also state what the page shows and the spec omits: the receiver descriptor is an **options template, set id 3** (field count, then a **scope-field count of 1**), the sender descriptor is **set id 2**, and a string is a 1-byte length (≤ 254) then UTF-8.
- **F4 (two sender templates in one datagram).** D4 means 8-field and 7-field sender records in the **same datagram**, hence **two template ids and two sender blocks**. The page requires distinct ids per descriptor (range 256 to 65535) but shows no datagram with two sender blocks. QA's fixture uses `0x9993` (8-field) and `0x9994` (7-field). **State the ids in R2, and make L1 decide:** L1 PASS needs 0 parse errors **and** record counts matching in both blocks. If the analyser rejects the second block, the fallback is **not decided here**: stop and return to the Architect (candidates: send one block only, the 7-field one; or the 8-field one with an empty locator string). Nothing on the page supports either.
- **F5 (placeholder identity).** `TxConfig` defaults are `Callsign = "Q1OFZ"`, `Grid = "JO33"` (`TxConfig.cs:81`, `:87`; "replace before operating"). With the checkbox on and the placeholders left in, the service would publish receiver "Q1OFZ" to a public service. **Add to R1/R13:** no upload while the receiver call is empty, a Q-prefix (ITU-unallocated) call, or the locator is empty; one Warning per window, counted by reason; and a test (**T14**, injected socket factory never used). The own-call exclusion in R4 compares case-insensitively **and on the base call** (`PD2FZ/P` is the station).
- **F6 (one source port).** The page asks for the **same UDP source port** on every datagram. Add to R1/R6 and as a test (**T15**): one socket for the lifetime of the service (the injected factory is called once), IPv4, source port constant across datagrams, no socket created while disabled (extends T8).
- **F7 (sequence number).** The page says the number counts reports, and its examples show 1 for the first datagram and 4 for a later one without saying whether the receiver record counts or where it starts. **Decide and state it:** count **sender records actually sent** (consistent with T3's s, s+2, s+7), starting at 0, the receiver record not counted. The page does not make this testable at the server, so it is a stated decision value (HK-038), not a measured one.

## Advisory (no spec change required; the Architect may take or leave)

- **A1 L3 outside check.** The retrieve API (`https://retrieve.pskreporter.info/query`) returns, by the page, "the last 100 reception records ... for no more than 6 hours in any event", with `rptlimit`, `rronly` (only reception reports) and `noactive` (no active-monitor entries) parameters. L3's count must use `receiverCallsign=<own>&flowStartSeconds=-7200&rronly=1&noactive=1&mode=FT8` plus a raised `rptlimit`, and **a returned count at the cap is INCONCLUSIVE, never PASS or FAIL**. QA tried to measure the cap with one read-only query for the station's own call over 24 h and got 0 reports: the WSJT-X spots of 2026-10-24 10:18Z were then 25 hours old. The cap behaviour is therefore **unmeasured**; the page's "6 hours" and "24 hours" statements also disagree. The page asks API users to add `appcontact=<email>`; QA would not send the Captain's address without his say-so.
- **A2 Resolved hashed calls** appear in the decoded text as `<CALL>`; R4 as written reports none of them. That is conservative and loses spots; the R9 counter by reason will show how many. Acceptable, say so.
- **A3 Nested config overlay (HK-035).** Add a test (**T16**) that `POST {"pskReporter":{"enabled":true}}` leaves `host`, `port` and `antennaInformation` as saved (the overlay for a new nested block is the same class as the `decoder` one, which holds).
- **A4 Datagram size.** The 1,400-byte limit in R6 is derived (the page: about 16 bytes a record and 80 to 90 records a datagram), not stated on the page; say where it comes from.
- **A5 `DecodePump` dependencies.** Carrying the dial frequency and adding a channel changes `DecodePumpDeps` (`DecodePump.cs:27` lists the channel writers) and `DecodeBatch`'s constructor; existing test constructors of both need the new parameter with a default. `dialFreq` is already a parameter of both publish methods (`DecodePump.cs:199`, `:241`), so R5 is cheap.
- **A6 Clock.** The export time is the PC clock; the server corrects a skew above one minute (page, "Data Storage"), so a drifting PC clock costs nothing but is worth a line in the log of the first datagram.

## FILE:LINE audit, against `d20059c3`: all correct

`REQUIREMENTS.md:278` and `:444` ✓ (the first says "HTTPS / telnet", as the spec says); `DecodePump.cs:124-125` and `:129` ✓; `PublishFirstAsync` `:197-232` with the reporting write at `:231`, noise suppression at `:207` ✓; `PublishSecondAsync` `:240-254`, write at `:253` ✓; early rows never reach the reporting channel (only `:231` and `:253` write to it), so "never the early-decode preview rows" holds automatically; `DecodeResult.cs:39-47` ✓; `ExternalReportingService.cs:515-521` ✓ and `:603-609` ✓ (current dial via `WebApp.ResolveEffectiveFrequency`); `Ft8Decoder.cs:1664-1689` ✓ (token-0 fallback at `:1685-1686`, suffix stripping throughout); `TxConfig.cs:81`, `:87` ✓; `Program.cs:357-362` (capacity 2, DropOldest) ✓ and `:346-351` (the 4 × 2 + 2 rule) ✓.

## Prediction scoring (for the ledger)

**PR1** ("P0 finds no contradiction of §1's byte values", P 0.70): **HIT**: no value in §1 contradicts the page. The review did find omissions and test defects (F1 to F7) that a contradiction-only criterion does not count.

## What QA does next

On the Architect's acceptance of this review and the F1 to F7 amendments: the OpenSpec change `psk-reporter-upload` (capability spec with the T1 to T16 scenarios), `tasks.md`, the Developer handoff (HK-000), and the FR numbers (R12). Nothing in `src/` is touched by QA. L1 to L3 stay the Captain's call.
