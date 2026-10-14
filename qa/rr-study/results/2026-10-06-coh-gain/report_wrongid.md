# COH-GAIN Amendment 6 — WRONG-ID: what are the fallback's "wrong payloads"?

**QA report to the Architect.** Run 2026-10-07 10:41Z (`date -u`), 45 s of CPU, no station. Spec §15 of `2026-10-06-1625-architect-to-qa-spec-coh-gain-step1.md` (branch `arch/coherent-limb2`) with note 1 (`5e728ee9`: F is WSJT-X-only). The Captain's go was given in QA's window. The row list was frozen and committed BEFORE any re-extraction (`791bae96`, list LF SHA-256 `24a81fc1dd8b8d061f52402a62dbf89ec5bef217fa3aba442249cc19fd4dfef7`).

**Scope (verbatim):** *Offline, Python, at WSJT-X's own positions on one 40 m night. Extraction and decode only; candidate search, the managed layer and the live path are not exercised. WSJT-X's AP is off on this station.* Rows: the FRESH samples only (the extension plus r1 / r2 / r4 / r6 / r8 / r9), positions where WSJT-X found a signal.

## Reading: **W-FALSE** — and it is clean

**F = M-NEAR / 1,352 = 0.322, 95 % CI [0.286, 0.358]** (435 of the 1,352 C3 BP wrongs; blocks of 8 over each sample's FULL cycle order, pooled, B 10 000, seed 20261006, 273 blocks). `CI_hi` 0.358 < 0.50 ⇒ **W-FALSE**: most (68 %) of the fallback's BP "wrong payloads" are **not** another WSJT-X decode at that position. The 0.50 bar is the decision value the question implies ("most of them"; HK-038), not a carried figure.

## Validity (all PASS, and each by a wide margin)

| row | result |
|---|---|
| **W1** reproduction | **PASS: 2,212 of 2,212 rows reproduced exactly** (C3 set: `C3_ok`, `C3_crc`, `C3_path`, `C3_nbe`; G set: the `G_*` fields). The harness reproduces every persisted field, including G's best-cell choice. |
| **W2** negative control | **PASS: 0 of 215** sign-inverted-OSD wrongs matched any WSJT-X decode (bar ≤ 5 %). The matcher is not loose; as predicted, an OSD wrong is a chance codeword. |
| **W3** geometry | **PASS: all 435 of the BP wrongs that match a WSJT-X decode are M-NEAR, 0 are M-FAR** (bar ≥ 80 %). No truth-comparison or indexing artefact (source (b)): the matches sit within one tone bin and one symbol step of the anchor, which is exactly where a different overlapping signal can be decoded. |

## What the 1,567 C3 wrongs and the 645 G wrongs are

| set (path) | rows | M-NEAR | M-FAR | M-OWS | M-NONE |
|---|---:|---:|---:|---:|---:|
| **C3, BP (path 0)** | 1,352 | **435** (32.2 %) | 0 | 5 | **912** (67.5 %) |
| C3, OSD (path 1, sign-inverted) | 215 | 0 | 0 | 0 | **215** (100 %) |
| G, BP | 533 | 193 | 0 | 5 | 335 |
| G, OSD | 112 | 0 | 0 | 10 | 102 |

- **The 435 M-NEAR are real signals, not false decodes**, and **all 435 are themselves rows of the sample; G already decodes 386 of them (89 %)** at their own row, so in the product they would be duplicates (text dedup) and neither harm nor gain; 49 are genuine extras the product could show. F with M-OWS added (descriptive): 0.325 [0.290, 0.362].
- **The residual is the false-decode upper bound for the fallback with OSD off: M-NONE = 912 against 3,382 correct recoveries = 0.27 per correct recovery** (not 0.40 and not 0.46: the 0.46 included 435 real signals and 215 OSD chance decodes). It is an UPPER bound for two reasons: unencodable decodes cannot be matched (a mean of 1.66 WSJT-X and 1.00 OWS decodes per such cycle could not be re-encoded, so a wrong payload equal to one of them lands in M-NONE), and positions here are all ones where WSJT-X found a signal.
- **G is not different in kind:** 29.9 % of G's wrongs are M-NEAR (C3: 32.2 %); G's OSD wrongs are 91 % M-NONE and 9 % M-OWS. The wrong-payload phenomenon is a property of any extractor in this band, with C3 producing more of them in absolute terms (it recovers more).
- **`dist` (payload Hamming distance to the truth, 77 bits; message distance, NOT `C3_nbe`):** M-NEAR median 32 (10th–90th 21–39); **M-NONE median 36 (26–42)**; the 5 M-OWS wrongs sit at 5 bits (a near-miss message). Most wrongs are far-different messages, so none of them is "the right message with a flipped bit".
- **M-NONE by WSJT-X SNR band of the row** (counts): ≥ +5 dB 307; −5…+4 dB 302; −15…−6 dB 263; ≤ −16 dB 40. 🔶 **An open observation, not explained:** 609 of the 912 unexplained wrongs sit on rows whose own WSJT-X SNR is ≥ −5 dB, i.e. positions with a strong real signal, where C3 returned a CRC-valid message that nobody else decoded and whose distance from the true message is large (median 36 bits). It is not weak-signal noise. I have not diagnosed it (candidate causes: a second, undecoded signal under the strong one; a sidelobe; a chance codeword). It is the first thing a step-3 false-decode gate should be pointed at.

## What this check does not answer (§15.5, unchanged)
Noise-only candidate positions (the step-3 offline flag OFF/ON replay through the real candidate search is the instrument); whether the product's candidate search finds the 3,382; a second night; native cost.

## Pins and instrument (HK-022)
DLL `2fa6d99302c6c602231c870c1e61755aeeddb7ad1b9ce392fb98a4bdbd94f365` (shim 20260058), verified before the run; same harness arms as the persisted rows (reproduction exact, W1). Commits (local `qa/coh-gain`, not pushed): harness, row list and 23 tests `791bae96` (15 of 15 mutants caught); this report's commit follows. Message text, bits and any text-derived hash never left the function that reads `ALL.TXT`; only numbers are persisted (`wrongid_rows.csv`, `analysis_wrongid.json`, never a `rows*.json` name).

## Predictions, facts for the ledger
CW1 (W1 passes, 0.90): **hit**. CW2 (W2 passes, 0.90): **hit**, 0 of 215. CW3 (W-REAL, 0.55): **miss**: W-FALSE. CW4 (G's wrongs M-NEAR ≥ 50 %, 0.55): **miss**: 29.9 %.

## Reading for the decision (QA's, not a ruling)
The fallback's "wrong payloads" are three different things: **215 are the sign bug** (gone with OSD off), **435 are real neighbouring signals** (mostly duplicates of decodes the product already shows), and **912 are unexplained**: 0.27 per correct recovery as an upper bound, concentrated where a strong signal is present. So the false-decode problem for a build is smaller than 0.46 but not dismissed: it is the 0.27 residual, and its cause on strong-signal rows is still open.
