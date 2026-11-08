# #262 live test L1 (PSK Reporter test listener): attempted 2026-10-25, BLOCKED, no verdict on the two-sender-block question

QA, written 2026-10-25 (`date -u` read 13:23:52Z before this file was written). Build under test: `feat/psk-reporter-262` `6ef0b33b` (VERSION 0.64, `libft8.dll` `1ba8dc3d…db914`), deployed on the Captain's station at 13:10:22Z, daemon started 13:10:30Z, on the Captain's go ("go for L1"). Counts only; no callsign, no IP address, no message text in this record (NFR-021).

## Verdict

**L1 could not be completed: the test listener's analysis page showed 0 packets for every packet sent, including a plain-socket baseline of the protocol page's own worked example.** The two-block acceptance question (8-field and 7-field sender blocks in one datagram) is therefore **still open**; nothing observed counts for or against it. No product defect was found by this attempt.

## Timeline (UTC)

| time | event |
|---|---|
| 13:10:50 | `pskReporter` set by the overlay POST to `enabled` true, `host` `pskreporter.info`, `port` 14739 (the spec's and the protocol page's test listener); every other config section identical before and after |
| 13:11:17 | datagram 1: 49 records (a full datagram, sent at once: the templates take room), sequence after 49 |
| 13:11:50 | datagram 2: 13 records (the first timed window; `dedup=37`, `hashed=1`), sequence after 62 |
| 13:11:37 onward | the analysis page lists **Packet count: 0**, with cache-busting requests every 20 to 25 s |
| 13:13:42 | **cause of the first miss found:** `pskreporter.info` resolves to Cloudflare addresses (104.21.x, 172.67.x and 2606:4700 IPv6), which do not carry UDP 14739; `report.pskreporter.info` resolves directly to one server (15.204.212.142). The analysis page's own text says "packets received at report.pskreporter.info" |
| 13:13:58 | host switched by the overlay POST to `report.pskreporter.info`, port 14739 (a changed host starts a fresh socket and restarts the template cadence, as designed); the L1 window restarted |
| 13:14:28 | datagram 3: 47 records, sequence after 109 (the first to the corrected host; templates included) |
| 13:17:06 | **baseline experiment:** QA sent the protocol page's own worked example (172 bytes, one 5-field sender block, Q-prefix calls, the current time) from a plain Python UDP socket on the same PC to `report.pskreporter.info:14739`; no product code involved |
| 13:18:30, 13:19:28 | datagrams 4 and 5: 47 and 5 records, sequence after 156 and 161 |
| 13:22:53 | analysis page still **Packet count: 0** after 8.5 minutes and 3 product datagrams to the corrected host plus the baseline |
| 13:23:25 | **UDP egress check:** a DNS query over UDP to 8.8.8.8 and 1.1.1.1 was answered in 18 and 8 ms: UDP leaves this PC normally |
| 13:23:35 | upload disabled and `host`/`port` restored to the defaults (`report.pskreporter.info`, 4739) by the overlay POST; other sections identical; the console monitor window closed |

R9 totals for the session: 5 datagrams, 161 records; 2 datagrams and 62 records went to the Cloudflare-fronted host (lost by construction), 3 datagrams and 99 records to the corrected host.

## What this establishes, and what it does not

- **Established:** the product's behaviour in the live station: one IPv4 socket per enabled period, a full datagram sent at once, the 0 to 60 s first-window offset, the per-call dedup (`dedup=364` in one window), the hashed counter, the templates cadence, a host change taking effect through the configuration overlay without a restart, the sequence advancing by records sent (49, 62, 109, 156, 161), and the log line carrying counts only. The station kept decoding normally throughout.
- **Established, a finding for the specification:** the host `pskreporter.info` named in the Architect's spec (R1, §1, L1) and in QA's OpenSpec text for the test listener **cannot receive UDP** (it is Cloudflare-fronted); the page's statement about the test listener is stale in the same way as its 2018 note about production. The directly resolving name is `report.pskreporter.info`, which is also the product's production default.
- **Not established:** whether the collector accepts two sender blocks in one datagram, whether the listener parses the datagrams without error, and whether the count equals the R9 sum. The listener's analysis page did not show even the baseline, so either the test listener at `report.pskreporter.info:14739` is not running or its analysis page is not working; QA cannot tell which from here. There is no response to a UDP datagram to check against.

## Options (the decision is the Captain's, the specification's the Architect's)

1. **Ask the PSK Reporter author** whether the test listener still exists (the Captain would write; the page names him).
2. **A short, bounded production pilot** in place of L1/L2: enable the upload with the default host and port for a limited time, WSJT-X's own spotting OFF, and verify through the retrieve API that spots for the station appear, with and without a grid (both blocks accepted), comparing the count with R9 (the Architect's A1.10 rules for the cap). This puts real spots under the Captain's call on the public map; it needs his explicit go and the Architect's ruling that it replaces L1.
3. Leave the feature merged but off until the listener question is answered (the feature is off by default; a merge alone changes nothing on air).
