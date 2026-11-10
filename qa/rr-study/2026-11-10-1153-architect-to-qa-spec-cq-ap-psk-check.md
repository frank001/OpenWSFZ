# `CQ-AP-PSK` spec: can PSK Reporter confirm decodes that WSJT-X cannot? A desk check on today's live session, before any CQ-AP build

**From:** Architect · **To:** QA · **Date:** 2026-11-10 11:53:05Z (`date -u`) · **Branch:** `arch/cq-ap-psk-check`
**Authority:** the Captain, 2026-11-10: "yes, write the CQ-AP spec. give qa a nudge when the spec is done." This is candidate #2 of the re-evaluation list on the programme page (`todo-decode-improvement-prio1-2026-10-05.md`, top): "first a cheap check whether PSK Reporter can corroborate AP extras."
**Base:** `origin/main` `98332f2a` (v0.69). **No build, no `src/` or `native/` change, no decoder setting touched, no station time taken.** The test passively records the public PSK Reporter MQTT feed during the live session that started at 11:35:28Z (era "RF4+L1′ ON"), then analyses it offline. This document is docs only.
🟢 **Size rule (the Captain, 2026-11-08: "keep the verification tests small").** One capture over today's live session, one analysis, one short report. A second session or any added arm needs his word.

---

## §0. Why, in one paragraph

- **CQ-AP** means decoding with *a priori* bits: assume a message starts with `CQ` and fix those bits before LDPC/OSD. WSJT-X calls this AP type 1. We already have the native mechanism (`ap_overrides`, `native/ft8_lib_build/patched/ft8/decode.c:121`), but use it only in QSO context.
- **It was demoted on 2026-10-05** because our reference WSJT-X runs with **AP OFF** (programme page, section A). Any extra decode CQ-AP produced is one the reference cannot confirm. Our instrument would score it as an unconfirmed extra, which is at best an upper bound on false decodes (HK-026).
- **The way out is a different reference.** PSK Reporter collects spots from thousands of receivers. A real station calling CQ is usually heard by someone else at the same time and frequency, while a false decode (a random callsign) is not.
- **The question:** is that reference good enough? Specifically, how often does PSK Reporter confirm decodes we *know* are real, **at the weak end where AP decodes would sit**, and how often does it "confirm" a random callsign?
- If it is good enough, a CQ-AP build becomes measurable and goes back to the Captain as a build proposal. If not, CQ-AP stays demoted with a reason on file.

## §1. What is recorded, and the privacy boundary

**Source:** the PSK Reporter MQTT feed, `mqtt.pskreporter.info` (public, no authentication).
- Topic layout per its own page: `pskr/filter/v2/{band}/{mode}/{tx_call}/{rx_call}/...`, with `+` and `#` wildcards. Subscribe to **`pskr/filter/v2/+/FT8/#`** (all bands, so a band change by the Captain is still covered) and keep only spots whose frequency lies within the station's dial band.
- 🔴 **The feed is live only, with no history.** Spots that are not captured while the session runs are lost. **The recorder may therefore start before the freeze (§4 step 1).** Capturing raw data reads nothing. No analysis code runs and no rate is looked at until the freeze commit exists.
- **What QA confirms from the live feed in the (k) review:** the payload keys for spot time, frequency, tx call, rx call and mode, and whether the time key is reception time or report time. Name them; do not assume them from this spec.
- 🔴 **How receivers report (it shapes the match rule).** A spot is not one decode. PSK Reporter's developer page asks clients to report a callsign "no more than once per five minute period ... ideally once per hour unless changed". Our own uploader follows that: at least 5 min per call and **one record per (call, band) per 60 min** (`PskReporterEngine.cs:42–46`; design `openspec/changes/psk-reporter-upload/design.md` item 6). Its record time is `flowStartSeconds` = **the cycle start of the decode reported** (`PskReporterEncoder.cs:18`). A station that other receivers hear all the time therefore shows up as **about one spot per receiver per hour**, not one per cycle. The match window in §2 is sized for that.
- **Client:** QA's choice. If `paho-mqtt` is used, take it under its **EDL-1.0** licence (BSD-3-style; the licence policy allows permissive only). It is QA tooling and never a product dependency.

🔒 **NFR-021 / HK-037.** Every spot carries real callsigns, and so do the ghost callsigns of §2.
- The raw spot file lives **only** in `D:\Projects\claude\_qa-scratch\cq-ap-psk\`. It is never committed and is deleted at job close.
- The matching code reads `ALL.TXT` (both decoders) and the spot file inside one function and returns **aggregates only**: counts and rates per bin.
- The report and anything committed carry no callsigns, no message text, and no per-decode rows.

## §2. Populations and the match rule

**Window:** decodes whose cycle start lies in **[capture start + 1800 s, capture end − 1800 s]**, minus any feed gap (row V-FEED) widened by 1800 s each side. Decodes outside the window are excluded, not counted as unconfirmed.

**CQ decode:** a decoded message whose first token is `CQ` (with or without a modifier such as `CQ DX`). Its **sender** is the callsign token after `CQ` and any modifier. Hashed calls (`<...>`) and messages with no standard sender are excluded and counted.

**Populations** (each is a set of CQ decodes, one per cycle and sender):
| name | what | role |
|---|---|---|
| **P_T** | every CQ decode in **WSJT-X's** live `ALL.TXT`, binned by **WSJT-X's** SNR | the known-true population; it calibrates the instrument |
| P_T-ours | the part of P_T that we also decoded (same cycle, same message) | descriptive split |
| P_T-missed | the part of P_T we did not decode | descriptive; these are the kind of decodes AP would target |
| P_X | our CQ decodes with no WSJT-X match in the same cycle (today's unconfirmed extras), binned by our SNR | descriptive only; a mix of real and false that nothing gates on |
| **P_G** | **ghosts:** 10,000 callsigns made by unpacking uniformly drawn standard-callsign `c28` values (the inverse of ft8_lib's `pack28` over the standard-call range; seed **20261110**). Each ghost takes the cycle time and absolute frequency of a P_T decode drawn with replacement | the false-decode null: a false AP decode is a random `c28` |
| P_S | **shuffle:** P_T's senders, each re-paired with the time and frequency of another P_T decode at least **2 h** and 200 Hz away (pairs that cannot be formed are dropped and counted) | descriptive: how much the time-and-frequency rule does on its own |

**Absolute frequency** of a decode = dial frequency (`ALL.TXT` field [1], MHz) + audio offset (field [6], Hz).

**Match rule (CORROBORATED):** at least one spot with
- `tx_call` equal to the sender (exact, upper case),
- **`rx_call` not the station's own callsign** (exclude any `rx_call` that contains `PD2FZ`, so our daemon's uploads and any WSJT-X/GridTracker uploads from this station never count),
- mode FT8,
- **|spot time − cycle start| ≤ 1800 s**, and
- **|spot frequency − absolute frequency| ≤ 50 Hz**.

The window and tolerance are fixed here.
- **Why ±1800 s:** with one report per receiver per hour (§1), any 60-min interval around our cycle holds one spot from each receiver that heard the station throughout. A ±300 s window would catch only the receivers whose hourly report happened to fall near our cycle.
- **Why ±50 Hz:** the spot's frequency is where the station was at the receiver's report time, up to 30 min away. Stations calling CQ mostly hold their audio offset, but not always.
- The rule asks whether that callsign was on the air near that frequency within the half-hour, as someone else heard it. A random `c28` ghost almost never is, which is the property the test needs.
- QA reports the time-offset distribution of matched P_T spots (D-T) and C per bin under **call + band only** (no time or frequency limit beyond the band and the window) as descriptive lines, so both choices can be judged afterwards. **The rule does not change after the freeze.**

**SNR bins** (WSJT-X's SNR for P_T, P_G inherits its donor's): **≥ −10**, **−11 to −15**, **−16 to −18**, **≤ −19** dB. The **weak bin** is **≤ −19 dB** (stated below). The −16 to −18 bin is the **next bin** for the slope row.

## §3. Rows

**Freeze:** before any rate is computed, one commit records the analysis code (SHA), the capture start and end (`date -u`), the spot file's row count and SHA-256 (the SHA only; the file stays in scratch), the ghost seed, the window, the match rule, the bins and the station's `rx_call` exclusion.

| row | predicate (mechanical) | where its bar comes from |
|---|---|---|
| **V-REF** | WSJT-X's live `ALL.TXT` has CQ decodes in the window, and its run overlaps the capture by ≥ 1 h | mechanical: P_T needs a live reference. A fail means waiting for a session with WSJT-X running |
| **V-FEED** | no gap > 120 s without any spot in the capture; gaps that occur are excluded per §2 and counted | design choice: 20 m FT8 worldwide carries many spots per second, so a 2-min silence is a feed fault, not quiet. No prior data on file |
| **V-SELF** | over the capture, (spots in the feed with `rx_call` containing `PD2FZ`) ÷ (sum of `{Reported}` in the daemon's per-window accounting lines, "PSK Reporter: N decodes seen, M reported: ...", `PskReporterEngine.cs:344`, for windows whose send fell inside the capture) ≥ **0.90** | checks the feed against records we know were sent: our daemon has PSK Reporter upload ON (QA's 11:35Z readback) and logs how many records each window reported. Counting per decode would be wrong, because the uploader deduplicates (§1). 0.90 is a design choice, no prior data on file. QA confirms in the (k) review that the line reaches `daemon.out` at the live log level. **A fail caps the verdict at BETWEEN** (the feed loses spots, so coverage reads low) |
| **G-COVER** | Wilson 95 % lower bound of **C_weak** (the P_T corroborated share in the weak bin) ≥ **0.40** | design choice, see "Why 0.40" below. No older bar exists; the project has never measured PSK Reporter coverage (HK-038) |
| **G-SLOPE** | the point C(next bin) − C_weak ≤ **0.20** | HK-026: AP decodes would sit at or below the weak bin. If coverage is still falling steeply there, P_T cannot vouch for even weaker decodes. Design choice |
| **G-GHOST** | Wilson 95 % upper bound of the P_G corroborated share ≤ **0.02** | design choice: at C_weak 0.40 a ghost rate of 0.02 shifts an estimated true fraction by at most 0.05 |
| **N-INSUFF** | P_T has **fewer than 30** decodes in the weak bin | mechanical floor for a Wilson bound worth reading |

**Verdict (exclusive, evaluated in this order):**
1. **VOID**: V-REF fails.
2. **INSUFFICIENT**: N-INSUFF fires. Reported as is; a second session needs the Captain's word.
3. **NOT-USABLE**: Wilson 95 % **upper** bound of C_weak < 0.40, **or** the P_G point share > 0.05.
4. **USABLE**: G-COVER, G-SLOPE and G-GHOST all pass **and** V-SELF passes.
5. **BETWEEN**: anything else, including a V-SELF fail.

**Why 0.40.** Suppose a CQ-AP build produced about 200 AP-only extras. The true share of those extras would be estimated as t̂ = (corroborated share) / C_weak. At C_weak = 0.40 the binomial part alone gives t̂ a 95 % half-width of about ±0.17, the widest that still separates "mostly real" from "mostly false". Below 0.40 the readout cannot tell them apart. This is arithmetic, not station data.

**Descriptive lines (no gate):** C per bin for P_T, P_T-ours and P_T-missed; P_X corroborated share per bin; P_S share; **D-T**, the median and 5–95 % range of (spot time − cycle start) on matched P_T; counts of excluded hashed or non-standard senders; capture length and spot count.

## §4. Order and cost

1. **QA starts the recorder now** (allowed before the freeze, §1), writing to `_qa-scratch\cq-ap-psk\`, and stamps the capture start with `date -u`. Passive; it does not touch the daemon. The station has no CPU-exclusivity rule here because no timings are compared.
2. QA's (k) review, rows only: the payload keys and what the time key means; the `c28` unpack; whether WSJT-X is running live today (V-REF).
3. Capture end: when the Captain ends the live session (the window loses 30 min at each end, so a capture shorter than about 2 h leaves little). If he keeps it running past QA's §3 report, the capture keeps going until he stops it. Stamp it.
4. Freeze, then the analysis (one script).
5. A short report: rows table, verdict, descriptive lines. Aggregates only.
6. My ruling; the programme page's top updated in the same edit.

**Cost:** about an hour of QA desk time for the recorder and the script; no PC exclusivity, no build. It runs in parallel with the §3 first-live-session report and does not delay it.

## §5. What this does not measure

- **The gain from CQ-AP.** Nothing is built here. USABLE only says that a CQ-AP gain *could* be measured.
- **Whether false AP decodes look like uniform `c28` draws.** OSD and LDPC may favour some codewords, so ghost callsigns are a model of a false decode, not a sample of one. A real CQ-AP test would check its own unconfirmed extras against P_G's rate.
- **Other bands, other times of day, and propagation.** Coverage depends on who else is listening; this is one session on whatever band the Captain runs.
- **Non-CQ messages.** AP type 1 is CQ only. Our existing QSO-context AP is not in scope.

**If USABLE, what follows (not pre-registered here):** a CQ-AP build spec for the Captain's decision (a Developer session, HK-011), measured live with the MQTT capture as the reference for AP-only extras, plus the usual U′ watch.

## §6. Predictions (Architect; scored at the ruling)

| # | prediction | P | class |
|---|---|---:|:---:|
| CA-1 | V-SELF passes (≥ 0.90) | 0.65 | C |
| CA-2 | C in the ≥ −10 dB bin ≥ 0.80 (point) | 0.65 | H |
| CA-3 | verdict USABLE | 0.45 | H |
| CA-4 | G-SLOPE fails | 0.35 | H |
| CA-5 | verdict INSUFFICIENT | 0.15 | H |

**Reasoning:**
- A station that is weak here is often strong somewhere else, and stations calling CQ on 20 m are heard by many receivers. So coverage should be high at the strong end and should fall off less than our own SNR scale suggests.
- But the weakest decodes include stations that are weak everywhere, such as low power or poor antennas, and those are exactly the ones AP would reach. That is why G-SLOPE is the row most likely to bite.
- A random `c28` is almost never a callsign that is on the air near that frequency within the half-hour, so G-GHOST should pass easily.
- The hourly dedup (§1) cuts coverage for stations with few listeners. That is the second reason the weak bin may come in below 0.40.
- 🔴 **Bias check:** HYPOTHESISED calls lean toward "the instrument works / a findable gain". USABLE is held below even odds.

## §7. Amendment 1 (2026-11-10 11:57:42Z, `date -u`): QA (k) review part 1 adopted; a reference-free truth population added; before any freeze

QA's findings (message received after 11:56:28Z): payload keys `b f md ra sa rc rl sc sl rp sq t t_tx`; **`t_tx` is the transmission slot start** (94.6 % on 15 s boundaries); `t` − `t_tx` is 0 to 20 s in the sample; the accounting line reaches `daemon.out` at INF; 🔴 **WSJT-X is not running today** (no process, no `ALL.TXT`), so P_T would be empty and the check VOID.

- **A1.1 Time key.** The match window keys on **`t_tx`**; `t` is used only when `t_tx` is missing, and those spots are counted. The ±1800 s window stays: QA's 0–20 s figure concerns how fast one report reaches the feed, not how often a receiver reports a callsign (once per hour, §1).
- **A1.2 V-SELF scope.** V-SELF counts only the send windows when our daemon was running inside the capture.
- **A1.3 A truth population that needs no WSJT-X: P_R (repeat-confirmed).** A CQ decode of ours belongs to P_R when **the same sender is decoded by us in at least 2 other cycles within ±600 s of it, each within ±10 Hz of its audio offset**. A false decode is a random callsign, so the chance of it recurring twice more at the same frequency within 10 min is negligible. P_R is binned by **our** SNR (`ALL.TXT` field [4]); the ghosts (P_G) and the shuffle (P_S) take their donors from P_R instead of P_T.
- **A1.4 Which population gates (mechanical, fixed now).** If V-REF passes, P_T gates as in §3 and P_R is descriptive. **If V-REF fails, the verdict is NOT VOID: P_R takes P_T's place in N-INSUFF, G-COVER, G-SLOPE and NOT-USABLE, with the same bars and bins**, and the report labels the verdict **"(P_R)"**.
- **A1.5 What P_R costs (stated, not gated).** P_R holds only stations steady enough at our end to decode three times in 20 min. At the weak bin these are steady weak signals, which is close to what CQ-AP would target, but it misses one-off weak CQs. The P_R verdict therefore speaks for repeat callers. A USABLE (P_R) carries that limit into any CQ-AP build spec. The weak bin on our SNR scale (≤ −19 dB) may hold few decodes, since we decode less deep than WSJT-X; N-INSUFF catches that.
- **A1.6 Still owed from QA:** the `c28` unpack (part 2 of the review).
- **Predictions:** unchanged. CA-5 (INSUFFICIENT) was priced on P_T; it is not restated, and the ruling notes which population scored it.

## §8. Amendment 2 (2026-11-10 11:58:40Z, `date -u`): QA (k) review part 2 (the ghosts) adopted; before any freeze

- **A2.0 Range and unpack (QA, confirmed).** Standard-call `n28` runs from NTOKENS + MAX22 = 6,257,896 to 2^28 − 1, which is 262,177,560 values. The unpack is the mixed-radix inverse over " 0-9A-Z" (37), "0-9A-Z" (36), digit (10), then " A-Z" (27) three times. The constants go in the code as assertions. The unpack is checked by round-trip against ft8_lib `pack28` on ≥ 1,000 calls (Q-prefix or generated, never real calls committed). Seed 20261110, numpy `Generator(PCG64)`, drawn once and stored in the freeze.
- **A2.1 Only publishable ghosts.** Most uniform draws are strings no decoder publishes, and keeping them would let G-GHOST pass for free. A ghost is kept only if the message **"CQ <ghost> <donor's grid token>"** passes the same check our decoder applies before `ALL.TXT`: `IsPlausibleMessage` (`Ft8Decoder.cs:1461`, applied at `:803`), **with the live grammar store** (its second argument). Either call it through the product assembly or port it and prove the port equal on the round-trip set; QA names which in the freeze. Rejection sampling keeps the first 10,000 accepted ghosts and reports the rejected share.
- **A2.2 Same string rule as real senders.** A ghost is trimmed and compared exactly to the feed's `sc` (no case or slash folding), as §2 does for real senders. (`rc` is used only for the own-station exclusion.)
- **A2.3 What the ghost row is (QA's note, adopted).** At an expected chance rate of about 1e-4, G-GHOST cannot fail unless the matcher is broken. It is a **guard**, not a discriminating row, and the report says so. The ghost remains a model of a false decode (§5).
