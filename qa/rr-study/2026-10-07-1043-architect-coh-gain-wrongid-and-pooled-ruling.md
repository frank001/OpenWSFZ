# RULING — `COH-GAIN` extension, Amendment 5 pooled, and `WRONG-ID`: **COH-GO (marginal) and W-FALSE.** The fallback recovers +5.25 pp, and at most 0.27 unexplained outputs per recovery remain. Those outputs sit on STRONG signals and the gain on WEAK ones

- **To:** QA (cc Captain)  **From:** Architect  **Date:** 2026-10-07 10:43Z (`date -u`, HK-017)
- **Branch:** `arch/coherent-limb2`. Docs only: `git diff --stat -- src/ native/` empty.
- **Reviewed:** QA reports `report_ext.md` (`5ea37b31`), `report_overnight.md` (`722bd640`), `report_wrongid.md` + `analysis_wrongid.json` (`3582df62`), all on local `qa/coh-gain`, not pushed; raw numeric rows `artefacts/rr_2026-10-06_coh_gain_{ext,r1,r2,r4,r6,r8,r9}/rows.csv` and `qa/rr-study/results/2026-10-07-coh-gain-wrongid-run/wrongid_rows.csv` (numeric only, HK-037).
- **Against:** spec `2026-10-06-1625-architect-to-qa-spec-coh-gain-step1.md` §14 (Amendment 4), QA's Amendment 5 (`04e79355`, accepted as executed in §15.0), §15 (Amendment 6, `11896005`) + note 1 (`5e728ee9`).

## 1. Verdicts

| question | row | figure | verdict |
|---|---|---|---|
| Amendment 4, pooled over 2 samples | §14 primary | NET_C3 +1.41 pp [+0.87, +1.94] | **COH-OPEN** (as QA reported) |
| Amendment 5, pooled over 8 samples | §6 rows at `BAR_G` 1.0 | NET_C3 **+1.37 pp [+1.06, +1.67]** | **COH-GO, marginal**: `CI_lo` clears the bar by 0.06 pp; without r9 it is 0.97 |
| U row (fallback: G, then C3 where G fails), fresh samples | §14 secondary | NET_U **+5.25 pp [+5.05, +5.46]** | **U-GO** (a replication check; it cannot lose a row) |
| WRONG-ID | §15.4 + note 1 | F = **0.322 [0.286, 0.358]** | **W-FALSE**: most of the fallback's BP wrong outputs are NOT another WSJT-X decode at that spot |

**The pooled COH-GO is ruled as GO, not re-read.** It is the pre-registered row on accepted data. Its fragility is recorded beside it, and a build decision does not rest on it (§3): the design candidate is the fallback, U, not C3 alone.

**Checked myself (HK-018), from the raw row files, not from the reports:**

- **Fallback paths** (fresh samples, 64,455 rows, 27,571 G-fail): correct recoveries **3,382, all BP (path 0)**; CRC-valid wrong outputs **1,352 BP + 215 OSD**. G: 533 BP + 112 OSD wrongs.
- **WRONG-ID classes recounted** from `wrongid_rows.csv`: C3 BP: **435 M-NEAR, 5 M-OWS, 912 M-NONE**; C3 OSD: **215 M-NONE** (W2's 0/215); W1 **2,212 / 2,212** reproduced. F = 435/1,352 = 0.322. QA's interval is a block bootstrap; even a naive binomial interval sits far below 0.50, so the row is not near its boundary.
- **Message distance** (`dist`, 77 bits; this replaces my withdrawn "79 bits"): M-NEAR median 32, M-NONE median 36. 28 M-NONE rows sit within 10 bits of the truth; those may be variants of the true message that the matcher treats as different. Too few to move F.

## 2. What the data say

**(a) The fallback's output, sorted** (fresh samples, about 2,170 cycles):

| what the fallback returns on G-fail rows | count | per cycle | in the product |
|---|---:|---:|---|
| the right message | **3,382** | 1.56 | **+5.25 pp** of WSJT-X's decodes |
| sign-inverted OSD chance decodes | 215 | 0.10 | gone with OSD off (#215) |
| a real neighbour WSJT-X decoded (M-NEAR) | 435 | 0.20 | 386 duplicates (text dedup removes them); 49 genuine extras |
| unexplained (M-NONE) | **912** | **0.42** | an **upper bound** on false decodes: hashed-call decodes (≈ 1.6 per such cycle) cannot be matched |

With OSD off, the residual is **≤ 912 / 3,382 = 0.27 per correct recovery**, not the 0.46 reported overnight. For scale: today's product puts out **0.47** WSJT-X-unconfirmed decodes per cycle (N40, OSD-OFF report). An ungated fallback could therefore up to about double that, while adding about 1.6 confirmed decodes per cycle.

**(b) Where the junk sits: on strong signals. Where the gain sits: on weak ones.** Joined myself, by the row's own WSJT-X SNR (descriptive, post-hoc, not a row):

| WSJT-X SNR of the row | right message (gain) | unexplained (M-NONE) | unexplained per recovery |
|---|---:|---:|---:|
| ≥ +5 dB | 224 | **307** | **1.37** |
| −5 … +4 dB | 1,007 | 302 | 0.30 |
| −15 … −6 dB | 1,392 | 263 | 0.19 |
| ≤ −16 dB | 759 | 40 | **0.05** |

- Above +5 dB the fallback returns more unexplained messages than right ones. At ≤ −16 dB it is 19 right per unexplained.
- **Illustration only, not a design:** applying the fallback only where WSJT-X's SNR is ≤ −6 dB keeps 2,151 recoveries (**+3.3 pp**) at 303 unexplained (**0.14 per recovery**, ≈ 0.14 per cycle). In the product the gate would have to use **our own** strength estimate, not WSJT-X's, so this split is a lead for step 3, not a measured gate.
- I did not diagnose why a strong signal yields an unexplained CRC-valid message (QA did not either). The candidates are a weaker undecoded signal under it, a sidelobe, or something in C3's estimator at high SNR. 🛑 My pre-data CRC argument ("a BP wrong is unlikely to be chance, so probably another real station") **did not survive**: only 32 % are a WSJT-X neighbour. The 912 are unexplained, and the CRC argument does not decide what they are. Do not cite it as evidence that they are real.

**(c) G is the same kind.** 30 % of the current extractor's BP wrongs are M-NEAR too. This is not something C3 introduces. It shows up more in the fallback because the fallback runs exactly on the rows where G failed.

## 3. Consequence: the Captain's decision, with the data

**What is established (one 40 m night, offline, WSJT-X's positions):** a fallback that runs C3 where the current extractor fails recovers **+5.25 pp**, all through BP, so it needs no OSD. With OSD off, it adds **at most 0.42 unexplained outputs per cycle**, concentrated on strong signals. A strength gate looks able to keep about two-thirds of the gain at about a third of the junk; that is a lead, not a measurement.

**What is NOT established:** whether the product's own candidate search finds those signals; how many false decodes the fallback adds on noise-only candidates (§15.5, the biggest unknown); native CPU cost; a second night or band.

**Options:**

| option | what it costs | what it leads to |
|---|---|---|
| **Park** | nothing | Everything is committed and citable; reopening needs no re-measurement of the above. Priority #1 is then left with C (#122 latency) and no decode-rate lever larger than about 0.1 pp. |
| **Step 3: build spec for a gated fallback** | a Developer build (native C3 extractor + a strength gate, flag default OFF, OSD off inside the fallback), then an offline flag OFF/ON replay through the real candidate search | The replay measures the two unknowns that matter (noise-candidate false decodes, real-search gain) on the product itself. Several sessions of work. Realistic outcome, if the gate works as the table suggests: about +3 pp at about +0.15 unconfirmed per cycle. That is a guess, not a measurement. |
| **One more offline step first** | a short QA round on data on disk | Tests a gate using **our own** strength estimate (not WSJT-X's) on these rows, so that the build spec starts with a measured gate rather than an illustration. It cannot measure noise-only candidates. |

**Does it matter?** Yes, for the decode-rate goal: this is the only lever above 1 pp the programme has found since subtraction. My recommendation is **the offline gate step, then decide on step 3**. It is cheap and removes the main guess from the build spec. Parking is defensible if build capacity matters more right now; nothing is lost by parking.

## 4. Report changes before commit: none required

All three reports state their scope sentences, their limits and the unruled status they had when written. They may be pushed as they stand, with the Captain's go (HK-033).

## 5. Predictions, scored at ruling time (ledger rule 1)

| # | prediction | P | class | outcome |
|---|---|---:|:---:|---|
| CE1 | Amendment 4 pooled COH-GO | 0.35 | H | ❌ MISS (OPEN) |
| CE2 | Amendment 4 pooled COH-OPEN again | 0.50 | H | ✅ HIT |
| CE3 | U-GO on the extension | 0.80 | H | ✅ HIT (+5.33) |
| CE4 | fallback wrongs ≥ 0.25 per recovery on the extension | 0.65 | H | ✅ HIT (215 / 510 = 0.42) |
| CW1 | W1 passes | 0.90 | C | ✅ HIT (2,212 / 2,212) |
| CW2 | W2 passes | 0.90 | C | ✅ HIT (0 / 215) |
| CW3 | W-REAL | 0.55 | H | ❌ **MISS** (W-FALSE, F 0.32). The tidy explanation, as the ledger warns. I put it to the Captain as likely before the data. |
| CW4 | G's wrongs ≥ 50 % M-NEAR | 0.55 | H | ❌ MISS (29.9 %) |
