# Architect to QA: issue #262. OpenWSFZ uploads its own decodes to PSK Reporter (opt-in, off by default)

**Stamped:** 2026-10-25 11:31:48Z (`date -u`, when drafting began). **To: QA.** QA writes the OpenSpec change and the
Developer handoff (HK-015, HK-000). Branch `arch/psk-reporter-262`, off `origin/main` `d20059c3` (local).

**The Captain, first-hand in the Architect's window:** *"write the spec for the gh #262 issue"*. The issue is labelled
"Idea, no priority". This spec is written. QA may start the (k) review now. **The handoff waits on the Captain's four
decisions in §7.**

## 0. Evidence this rests on

- **Issue #262** (Captain, 2026-10-24):
  - With only OpenWSFZ feeding GridTracker2, nothing reaches PSK Reporter under the station's call.
  - With WSJT-X's "Enable PSK Reporter Spotting" on, 58 reports appeared (10:18–10:20Z, 40 m), credited to WSJT-X 2.7.0.
- **`REQUIREMENTS.md:278`** and **`:444`** list PSK Reporter as future work ("Not in v0.x"); `src/` has no upload.
  - ⚠️ `:278` says the transport is "HTTPS / telnet". The protocol page says UDP (§1). The table row is corrected by
    this change (R12).
- **Protocol: `https://pskreporter.info/pskdev.html`, read by the Architect on 2026-10-25** (through a fetch tool that
  summarises the page; **QA confirms every byte value in §1 against the page itself in the (k) review**, see P0).
- **Product code, on `origin/main` `d20059c3`:**
  - `DecodePump.cs:197-232` (`PublishFirstAsync`) and `:240-254` (`PublishSecondAsync`; the writes at `:231` and `:253`) write batches 1–4 to
    `ExternalReportingChannel`, **after** `ApplyNoiseSuppression`. `ALL.TXT` gets the unfiltered list.
  - The pump knows the cycle's **dial frequency at capture** (`DecodePump.cs:124-125`: `windowDialFreq ??
    FallbackDialFrequency()`) and the band derived from it (`:129`). `DecodeBatch` (`DecodeBatch.cs`) carries neither.
  - `DecodeResult` (`DecodeResult.cs:39-47`): `Time`, `Snr`, `Dt`, `FreqHz` (audio offset), `Message`, `Region`, `Band`.
  - `ExternalReportingService.cs:515-521`: the **absolute exclusion** of decodes whose `Region` is null (unknown) or
    `Synthetic` (R&R Q-calls). It is not operator-configurable.
  - `ExternalReportingService.cs:603-609`: today's Status uses the **current** dial frequency
    (`WebApp.ResolveEffectiveFrequency`), not the frequency at capture. That is the root of #260's band alternation.
  - `Ft8Decoder.cs:1664-1689` (`ExtractPrimaryCallsignToken`):
    - it **falls back to token 0** (the addressee) when token 1 is a hash or a keyword;
    - it **strips portable suffixes**.
    - Both are right for the region lookup and **wrong for a PSK Reporter sender** (R4).
  - `TxConfig.cs:81` (`Callsign`, default `Q1OFZ`) and `:87` (`Grid`, default `JO33`) hold the station's call and locator.
  - `Program.cs:357-362`: the reporting channel has capacity **2**, `DropOldest`, while a fallback-ON cycle delivers up
    to **4** batches (`Program.cs:346-351`, `LateBatch.CreateQsoQueue`).

## 1. The protocol, as read (QA re-checks it against the page in P0)

- **Transport:** UDP datagrams, all from **one** source port.
  - Production: `report.pskreporter.info`, port **4739**.
  - Test listener: `pskreporter.info`, port **14739**; results on `/cgi-bin/psk-analysis.pl`.
- **Format:** simplified IPFIX (RFC 5101), enterprise number **30351**, every value big-endian.
  - Header, 16 bytes: version `00 0A`; total length; export time (Unix seconds); a sequence number that counts
    **records**, not datagrams; a random 4-byte session id, constant for the process.
  - Then templates (when due), one receiver record, and the sender records. Each set is padded to a multiple of 4 bytes.
- **Templates:**
  - Receiver template `0x9992`: `receiverCallsign` (30351.2), `receiverLocator` (.4), `decodingSoftware` (.8); optional
    `antennaInformation` (.9).
  - Sender template `0x9993`. The page lists fixed descriptors with 5–8 fields:
    - `senderCallsign` (.1), `frequency` (.5, 4 bytes), `mode` (.10), `informationSource` (.11, 1 byte), `flowStartSeconds` (IANA 150, 4 bytes);
    - optionally `sNR` (.6, 1 byte) with `iMD` (.7, 1 byte), and `senderLocator` (.3).
  - The page asks developers whose fields do not fit to contact the author for a custom descriptor. **OpenWSFZ has no
    iMD**: see R2 and decision D4.
- **Rules:**
  - At most **one datagram every 5 minutes** unless one is full.
  - The timer runs from program start and is not synchronised to the clock.
  - Templates go in the **first three datagrams** and then **at least hourly**.
  - `informationSource` = **1** (automatically extracted).
  - Each call **at most once per 5 minutes**, ideally **once per hour unless it changed** (a band change is the
    page's example). Duplicates are removed before formatting.
  - The reported call is the **whole** text after "DE", prefixes and suffixes included.
  - `decodingSoftware` names the software and version.

## 2. Requirements (for the Developer, via QA)

- **R1 Opt-in, inert by default.** A new `pskReporter` config block:
  - `enabled` (default **false**);
  - `antennaInformation` (default `""`);
  - `host` (default `report.pskreporter.info`) and `port` (default `4739`), so the test listener (`pskreporter.info`,
    `14739`) can be selected without a rebuild.
  - With `enabled` false: **no socket, no DNS lookup, no timer work**, the same posture as `ExternalReportingService`.
  - The config POST is an overlay (HK-035), so a body without the key leaves it unchanged.
- **R2 Encoder (new, clean-room, no WSJT-X source read; licence policy).** A pure function from (session id, sequence,
  export time, receiver info, sender records, templates-due flag) to bytes, as in §1.
  - The sender template is the **8-field descriptor** if D4 accepts it, or the **6-field one without SNR** otherwise.
  - The receiver template is the 3- or 4-field one, by whether `antennaInformation` is empty.
  - `decodingSoftware` = `"OpenWSFZ <VERSION>"`. `frequency` = dial Hz + audio offset Hz (4 bytes is enough below
    4.29 GHz). `mode` = `"FT8"`. `flowStartSeconds` = the cycle start, Unix seconds.
- **R3 Source stream: the same decodes GridTracker gets, minus the exclusions.** Batches from the pump (1–4), after
  noise suppression, **never** the early-decode preview rows.
  - The same absolute exclusion as `ExternalReportingService.cs:515-521` (unknown region or synthetic). It is shared or
    duplicated, never weakened.
  - Which batches are reported is **D2**.
- **R4 Sender extraction, strict (new; not `ExtractPrimaryCallsignToken`).**
  - `CQ <call> [grid]` and `CQ <mod> <call> [grid]` give `<call>`.
  - The standard `<to> <from> <ext>` form gives token 1 (`<from>`).
  - **No fallback to token 0.** A hashed `<…>` sender, a keyword, free text, telemetry, or anything unparseable is
    **not reported**.
  - The suffix is kept as decoded (`/P`, `/R`, prefixes).
  - The sender locator is the 4-character grid **only when this message carries one** in the grid position (`RR73` is
    never a grid); nothing is cached across messages.
  - **The station's own call is never reported as a sender.**
- **R5 Frequency and band = those at capture.** The pump's per-cycle `dialFreq` (`DecodePump.cs:125`) is carried with
  the batch to the reporter, for example as a new `DecodeBatch` field that defaults to null so existing calls still
  compile. A cycle with no known dial frequency reports nothing (it is counted).
  - This makes reports immune to #260's band alternation. **#260 itself is not fixed here.**
- **R6 Dedup and cadence.**
  - Per (call, band): at most once per **5 minutes**, and once per **hour** unless the band changed.
  - One datagram per **5 minutes** from a timer started at service start (with a random first offset of 0–60 s), or
    earlier when a datagram is full.
  - Templates in the first three datagrams, then hourly.
  - Datagram size ≤ **1,400 bytes**; overflow goes in the next datagram, with no record split across two.
  - An empty window sends nothing.
- **R7 Its own channel, sized for four batches.** A dedicated bounded channel from the pump, `DropOldest`, with
  capacity per `LateBatch`'s rule (4 × 2 + 2 = 10 with the fallback ON). It must not share the capacity-2 reporting
  channel (`Program.cs:357`). Records are queued in memory until sent and are **never written to disk**.
- **R8 Failure never touches decoding.**
  - DNS or socket errors are logged at Warning (once per window, not per record) and retried next window.
  - A queue held across failures is bounded (oldest dropped, counted).
  - The service never throws into the pump.
- **R9 Counters and log line (for the outside check, §5 L3).** One Information line per datagram sent: UTC, records
  in it, records excluded by reason (synthetic/unknown, hashed or unparseable sender, own call, no dial, dedup), and the
  sequence number after. **No calls in the log line** (HK-037 spirit: counts, not text).
- **R10 Settings page:** a checkbox and an antenna text field, if D3 says so. The opt-in text states plainly: *"Sends
  the calls and locators of stations you receive, with your call and locator, to the public PSK Reporter service."*
- **R11 Version and OpenSpec.**
  - The OpenSpec change is `psk-reporter-upload`, with a new capability spec (requirements R1–R9 with scenarios).
  - `VERSION` bump per G9b (user-facing).
  - No `native/` change, so no shim bump.
- **R12 `REQUIREMENTS.md`:** new FR numbers (QA assigns them).
  - The integrations row `:278` is corrected to UDP/IPFIX and to "implemented, opt-in".
  - The glossary line `:444` is updated.
  - The NFR-021 note in R13 is added.
- **R13 Privacy (NFR-021), what the code guarantees:**
  - Tests and fixtures use **Q-prefix calls only**.
  - Nothing is stored beyond what is already logged today.
  - Calls are not logged by this service.
  - The upload happens only with `enabled` true. Whether that is acceptable at all is **D1**.

## 3. Tests (the Developer writes them; QA reviews per HK-039). Q-calls only

| id | arrange | assert |
|---|---|---|
| T1 encoder golden bytes | fixed session id, sequence, time; 1 receiver and 2 sender records (one with a grid, one without); templates due | the bytes equal a fixture **hand-built by QA from the protocol page**, not generated by the code under test; length fields and padding correct |
| T2 templates cadence | 5 windows, then a clock 61 min later | templates present in datagrams 1–3, absent in 4–5, present again after 1 h |
| T3 sequence | 3 datagrams with 2, 0 (none sent), 5 records | the sequence advances by records sent: s, s+2, s+7 |
| T4 sender extraction | a table: `CQ Q1ABC JO22`, `CQ DX Q1ABC JO22`, `Q2DEF Q1ABC -12`, `Q2DEF Q1ABC R-05`, `Q2DEF Q1ABC RR73`, `Q2DEF <...> -12`, `<...> Q1ABC 73`, `Q1ABC/P`, free text, own call as sender | the expected sender and grid, or "not reported" with its reason; **no case returns token 0** |
| T5 exclusions | synthetic and unknown-region decodes in a batch | never encoded; counted by reason |
| T6 dedup | the same call 3× in 4 min; again at 6 min; again at 61 min on another band | 1 record, then 1, then 1; on the same band at 30 min: none |
| T7 dial at capture | a batch captured at 7.074 MHz, delivered after CAT moved to 14.074 MHz | the record frequency = 7,074,000 + audio offset |
| T8 inert | `enabled` false through a full run of fake batches | no socket created (by the injected socket factory), no DNS |
| T9 failure | a socket that throws on send | no exception reaches the pump; one Warning per window; the next window retries |
| T10 cadence | 20 min of batches with a fake clock | ≤ 1 datagram per 5 min unless full; a full datagram goes at once; size ≤ 1,400 |
| T11 four batches | a fallback-ON cycle with batches 1–4 | every batch reaches the reporter (no DropOldest loss at the documented capacity) |
| T12 regression | existing ExternalReporting, pump and config suites | unchanged and green |

## 4. QA steps

- **P0, in the (k) review, before the handoff:**
  - Check every value in §1 against `pskdev.html` itself: ports, template ids, field ids and lengths, the cadence and
    dedup rules.
  - Build T1's fixture by hand from the page.
  - **Check whether the fixed descriptors list a sender template with `sNR` and without `iMD`.** If none does, D4
    stands as written.
  - Any contradiction of §1: **stop and come back to me.**
- **P1** the OpenSpec change, `tasks.md`, and the handoff; branch `feat/psk-reporter-262` off `origin/main`.
- **P2** the HK-039 review of the Developer's commit, the unfiltered suite, `pre_merge_check.py` before any push (HK-006).

## 5. Live acceptance (the Captain's go; his station, his call)

- **L1 Test listener first.** Set `host` `pskreporter.info`, `port` `14739`, `enabled` true, for **30 minutes**.
  - **PASS** if `psk-analysis.pl` shows datagrams from the station that parse with **0 errors**, with the receiver
    record (call, locator, `OpenWSFZ 0.6x`) and sender records whose count equals the sum of the R9 log lines over the
    same minutes.
  - QA records counts only.
- **L2 Production**, only after L1 PASS and the Captain's go. The station runs as usual, with `enabled` true for
  **2 hours**, and **WSJT-X's own spotting is OFF for those 2 hours** (D-ops below).
- **L3 Outside check (the issue's "verification already possible").** PSK Reporter's page for the station shows
  software `OpenWSFZ 0.6x`.
  - **PASS** if the number of reports it lists for those 2 hours is within **±10 %** of the records the R9 log lines
    say were sent.
  - The 10 % is a decision value, for the service's own dedup and windowing. It is not measured, and it is not
    tightened after the data is seen.
  - A count of **0** is FAIL, whatever else.
- 🔴 **D-ops (operational, the Captain's habit, not code):** WSJT-X and OpenWSFZ both uploading under PD2FZ would credit
  spots to two programs and could double-count. Recommendation: one uploader at a time. With OpenWSFZ's upload on,
  WSJT-X's "Enable PSK Reporter Spotting" is off.

## 6. Limits, stated in the report

- No sandbox has been verified beyond the test listener. Live checks use the station's real call and the public site.
- The outside check is a count, not a record-by-record match.
- False decodes become public spots. §7 D2 is where that is decided.

## 7. For the Captain: four decisions before the handoff (data and consequences each)

- **D1 Privacy: may OpenWSFZ send received stations' calls to a public service at all?**
  - **Data:** that is the service's purpose, and WSJT-X does exactly this on his station today when spotting is on.
    NFR-021 governs what enters **version control**; it says nothing about an operator-chosen upload. Off by default,
    with the opt-in text (R10).
  - **Options:** (a) yes, opt-in as specified (recommended); (b) no, and the issue is closed as won't-do.
  - **Matters:** yes, it is a policy ruling.
- **D2 Which decodes are reported?**
  - **Data:**
    - On the MS replay night (`20260925_2010`, 2,882 cycles, all batches, the build now on his station), the
      instrument found **77 not-confirmed decodes tested absent over about 12 h, about 6 an hour**.
    - Those are upper-bound candidates for false spots, before the R4 sender rule and the dedup remove some.
    - Hashed and unencodable decodes are never reported (R4).
    - The fallback's batch 4 is where the coherent fallback adds its gain: about +3.8 pp for the shipped fallback
      (step 4, night `20260922_2056`) and +1.45 pp more for the sets (night `20260925_2010`). They are different nights
      and are never added.
  - **Options:**
    - (a) all batches 1–4, like the GridTracker stream (recommended: the public spot list then matches what he sees,
      and the false rate per hour is small next to dozens of real spots);
    - (b) batches 1–3 only, which drops the fallback's decodes from the public record and loses their spots;
    - (c) batch 1 only, the most conservative, and the furthest from what he sees.
  - **Matters:** yes. It decides what the public sees from his station.
- **D3 A Settings-page control, or config only?**
  - (a) A checkbox and the antenna field with the opt-in text (recommended: it is a public-facing switch).
  - (b) Config file only: less UI work, and the upload is invisible in the UI.
  - **Matters:** a little. It changes the Developer's scope (web page plus tests).
- **D4 SNR in the reports.**
  - **Data:** the page's fixed sender descriptors with SNR also carry `iMD`, which OpenWSFZ does not have.
  - **Options:**
    - (a) send iMD as 0 (wrong data in a field);
    - (b) a 6-field descriptor without SNR (allowed, and loses SNR on the map);
    - (c) ask the PSK Reporter author for a descriptor with SNR and without iMD (the page's own route; needs an email
      from the Captain, so it waits on a reply).
  - **Recommended:** (b) now, and (c) in parallel; a later change adds SNR if the author agrees.
  - **Matters:** a little. SNR is a nicety on the map.

## 8. Predictions (blind; scored at the rulings)

| # | prediction | P | class |
|---|---|---:|:---:|
| PR1 | P0 finds no contradiction of §1's byte values | 0.70 | C |
| PR2 | T1 (golden bytes) passes on the Developer's first commit | 0.60 | C |
| PR3 | L1 shows 0 parse errors on the first test-listener run | 0.60 | H |
| PR4 | L3 count within ±10 % on the first production run | 0.55 | H |

⚠️ PR1 rests on a page read through a summarising tool. The (k) byte check is there for exactly that reason.

## 9. For QA, in order

1. The (k) review of this spec, P0 included: FILE:LINE against `origin/main` `d20059c3`, and the protocol bytes against the page.
2. Wait for D1–D4 (the Architect puts them to the Captain).
3. P1, then the Developer, then P2, then L1, L2 and L3 on the Captain's go.

## §10 The Captain's decisions D1–D4 (recorded 2026-10-25 11:37:29Z by `date -u`, his answers in the Architect's window)

| # | his answer | what it fixes in the spec |
|---|---|---|
| D1 | **Yes, opt-in** | R1/R10/R13 stand as written; the feature goes ahead |
| D2 | **All batches 1–4** | R3: every batch the pump writes (1–4), after noise suppression, with the absolute exclusions and R4's sender rule |
| D3 | **A checkbox and the antenna field** | R10 is in scope: a Settings-page checkbox, a free-text antenna field and the opt-in text; the web page and its tests are added to the Developer's tasks |
| D4 | **Send iMD as 0** | R2: the **8-field** sender descriptor (`senderCallsign`, `frequency`, `sNR`, `iMD`, `mode`, `informationSource`, `flowStartSeconds`, `senderLocator`) when the message carries a grid, and the **7-field** one without `senderLocator` otherwise. `sNR` = the decode's SNR as a signed byte, clamped to [−128, 127]; `iMD` = **0** always |

- **The concern on D4, stated once:** an iMD of 0 is a value OpenWSFZ never measured, and it is published as data.
  - The Captain chose it knowing that. It stands.
  - The code comment and the capability spec say that iMD is a constant 0 because it is not measured.
- **Added to the tests:** T1's fixture uses the 7- and 8-field descriptors. A new T13 checks that `iMD` is 0 in every record and that SNR is clamped at the byte limits.
- **QA may write the OpenSpec change and the handoff once its (k) review, P0 included, is accepted.**

## §11 Amendment 1: QA's (k) review adopted, F1–F7 and the advisories (Architect, 2026-10-25 11:40:18Z by `date -u`)

**QA's review:** `qa/rr-study/2026-10-25-1139-qa-to-architect-k-review-psk-reporter-262.md` (`qa/refset`, local), ACCEPTED subject to seven amendments.
- **P0 was done against the raw page** (27,434 bytes): every value in §1 is on it, with no contradiction.
- The FILE:LINE audit against `d20059c3` is all correct.
- I fetched the raw page myself (same size) and confirmed F3's descriptor bytes. Every amendment is adopted, as below. **Where this section and §1–§10 disagree, this section wins.**

- **A1.1 (F1) Dedup, one rule.** For each call, a hard minimum of **5 minutes** between records. For each (call, band),
  at most one record per **60 minutes**. A band change starts a new (call, band) key, but still respects the 5-minute
  minimum. T6 is restated:
  - the same call 3× in 4 min on one band ⇒ 1 record;
  - at 6 min on the same band ⇒ **0**;
  - at 61 min on the same band ⇒ 1;
  - at 7 min on **another** band ⇒ 1.
- **A1.2 (F2) Sender extraction classifies tokens; it never counts them.**
  - A **callsign** token contains at least one digit and one letter, optionally with `/…` parts; `<…>` is a hash.
  - A **CQ modifier** is 1–4 letters (`DX`, `NA`, `POTA`, …) or exactly 3 digits.
  - A **grid** is `[A-R]{2}[0-9]{2}` and is not `RR73`.
  - `CQ [modifier] <callsign> [grid]` gives the callsign.
  - Five cases are added to T4: `CQ DX Q1ABC` (no grid) ⇒ Q1ABC; `CQ POTA Q1ABC JO22` ⇒ Q1ABC + JO22;
    `CQ 123 Q1ABC` ⇒ Q1ABC; `CQ Q1ABC/P` ⇒ Q1ABC/P; `CQ DX` (no call) ⇒ not reported.
  - **Resolved hashed calls** (`<Q1ABC>`, where the hash table resolved them) are **not reported** either: the text
    on air was a hash.
- **A1.3 (F3) The wire format is the page's descriptor bytes, not my prose lists.** R2 cites QA's fixtures in
  `qa/rr-study/psk-reporter-262/` (the builder script and three `.hex` files, Q-calls only). The builder first
  reproduces the page's two worked datagrams byte for byte.
  - The order is fixed by the page:
    - **8 fields:** `senderCallsign, frequency, sNR, iMD, mode, informationSource, senderLocator, flowStartSeconds`;
    - **7 fields:** the same without `senderLocator`.
  - §10's list put `senderLocator` last. That is wrong (ledger E69) and corrected here.
  - The receiver template goes in set id **3**, with scope-field count 1; the sender template in set id **2**.
  - Variable-length strings are encoded as the page shows.
- **A1.4 (F4) Two sender templates, and two sender blocks in one datagram.** D4 gives records with and without a
  locator.
  - Template ids **`0x9993`** (8-field, with locator) and **`0x9994`** (7-field, without), both announced in the
    template set.
  - A datagram carries one block per template that has records.
  - The page shows no such datagram, so **L1 also checks that the test listener parses both blocks**. If it rejects
    either, stop and come back to me. I would not invent a workaround.
- **A1.5 (F5) No upload with placeholder identity.** While the receiver call is empty or Q-prefix (the `TxConfig`
  default is `Q1OFZ`, `TxConfig.cs:81`), or the locator is empty, the service sends **nothing**.
  - It logs that once per window (a count, no call).
  - The own-call exclusion compares **base calls** (prefix and suffix stripped), so `PD2FZ/P` as a sender is excluded
    for receiver `PD2FZ`.
  - New test **T14**.
- **A1.6 (F6) One UDP source port for the life of the service, IPv4.** The socket factory is called once per enable.
  It is re-created only after `enabled` goes false and then true again, never per window, and it is never bound to
  4739. New test **T15**.
- **A1.7 (F7) Sequence number.** It starts at **0** for each process (with a new random session id). It increases by
  the number of **sender records** in each datagram sent; the receiver record is not counted. An unsent datagram does
  not advance it. T3 stands under this rule.
- **A1.8 Advisories, adopted.**
  - **L3 query:** use `receiverCallsign` with `rronly=1`, `noactive=1` and a raised `rptlimit`.
    - A returned count **at the cap is INCONCLUSIVE**, never PASS or FAIL. The cap is unmeasured, because QA's one
      read-only query found 0 records (the 10-24 WSJT-X spots were older than the 24 h window).
    - L3's window is chosen so the expected count stays under the cap. QA states that count before the run.
  - **T16:** a nested config overlay. A POST that changes only `pskReporter.antennaInformation` leaves `enabled`,
    `host` and `port` unchanged (HK-035).
  - **The 1,400-byte limit** is a decision value derived from a 1,500-byte Ethernet MTU minus IP/UDP headers and
    margin. It is not from the page.
  - **`DecodePump`'s dependencies change** (the new channel writer, R7). The pump tests' fixtures are updated.
- **A1.9 Errors in my spec, in the ledger now:** E69 (F3 order), E70 (F1 contradiction), E71 (F2 by-count), E72 (F4
  unstated consequence of D4), E73 (F5 placeholder identity), E74 (F6/F7: §1 rules not carried into R, and the sequence
  left open).
- **QA may now write the OpenSpec change, `tasks.md` and the Developer handoff.** PR1 is scored HIT (ledger).

**A1.10 The L3 expected count (QA asked me to state it; 2026-10-25 11:45:08Z by `date -u`).**
- **The comparator is a count, not an estimate:** the sum of the R9 log lines' sent records over the L2 window.
  - It is known **before** the PSK Reporter query is made.
  - So the query's `rptlimit` is set to **at least 2 ×** that sum.
  - A returned count equal to `rptlimit` is still INCONCLUSIVE (A1.8). With the limit at twice the comparator, that
    can only happen if PSK Reporter returns far more than was sent, which is a finding in itself.
- **The prior, for planning only and not a bar:** about **300–800 records** for 2 h on 40 m in the evening. That is
  my estimate from the dedup rule (one record per call per hour) and an unmeasured guess of 150–400 distinct callers an
  hour. It is not a count.
  - If the R9 sum falls outside that range, nothing fails. The ±10 % row compares PSK Reporter with R9, never with
    this prior.
- **QA's two corrections in the handoff are accepted:** `DecodeBatch` is at `src/OpenWSFZ.Daemon/DecodeBatch.cs:16`;
  `LateBatch.CreateQsoQueue` (`LateBatch.cs:97`) returns a `QsoBatchQueue`, so R7 means "the same sizing rule", and the
  Developer states which shape he used.
## §12 Rulings on QA's build review N-1 to N-3 (Architect, 2026-10-25 12:22:53Z by `date -u`)

**QA's review:** `4ca20699` (`Reviewed-commit: 275b9cbd…`), RETURNED for one test, R-1 (the 0–60 s first-send offset
has no test; mutation Q31 survives). There is no product defect.
- The encoder agrees with QA's independent builder on 300 cases, 0 differences.
- The full suite is green, and 31 of 35 mutations are killed.

- **N-1. My D1 premise was wrong (ledger E75). The decision goes back to the Captain before any merge.**
  - D1 said NFR-021 *"says nothing about an operator-chosen upload"*. **`REQUIREMENTS.md:320`, NFR-021(3), says:**
    *"Personal data captured at runtime (decoded callsigns, ALL.TXT) is processed locally on the operator's own
    machine, is not transmitted off-host (NFR-004), and is retained solely at the operator's discretion…"*.
  - I had read the memory policy note, not the requirement. The Captain's "yes" was given on that incomplete premise.
  - The Developer's proposed clause is accurate and narrow. NFR-021(3) gains *"except by the opt-in PSK Reporter upload
    (FR-088–FR-094), which sends the calls and locators of received stations, with the operator's own call and locator,
    to the public PSK Reporter service only while `pskReporter.enabled` is true (default false; the service logs counts,
    never calls)"*.
  - **It stands only if the Captain approves that wording.** If he does not, the feature is not merged.
  - For his information: the existing GridTracker reporting (FR-053) can already be pointed at a non-localhost target.
    Whether that is consistent with (3) is a separate question, and it is not decided here.
- **N-2. The 4-token reply `<to> <from> R <grid>` IS reported**, with `<from>` (token 1) as the sender and token 3 as the
  grid. A1.2 meant every standard form; it did not mean "exactly 3 tokens". T4 gains `Q2DEF Q1ABC R JO22` ⇒ Q1ABC + JO22.
- **N-3. A dial frequency outside the band table is NOT reported.** It is counted under the no-dial reason (R9), and T7
  gains that case. A report must carry a known band (R5's intent).
- **R-1** is the Developer's to fix, and it is QA's to re-review (HK-039).
- **Then:** `pre_merge_check.py` on the final commit, L1 on the Captain's go (including whether both sender blocks
  parse), his push go and merge sign-off. **The NFR-021(3) wording must be approved first.**
- ✅ **2026-10-25 12:23:57Z (`date -u`), CAPTAIN: the NFR-021(3) wording is APPROVED exactly as quoted in N-1.** He was
  given the corrected premise (the original clause's text) in the Architect's window and answered "Approve the
  wording". N-1 is closed.

- **Handoff:** QA's `8d8949b8` (OpenSpec `psk-reporter-upload`, FR-088–FR-094, VERSION 0.64) waits on the Captain's
  word to give it to a Developer. The issue is labelled "Idea, no priority".

*Architect. Docs only; `src/`/`native/` diff empty.*
