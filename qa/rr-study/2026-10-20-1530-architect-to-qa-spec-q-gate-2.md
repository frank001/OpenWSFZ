# SPEC — `Q-GATE-2`: does the frozen strength gate keep the coherent fallback's gain on a NEW night, scored with a corrected truth, against today's product? To: QA

- **To:** QA (cc Captain)  **From:** Architect  **Date:** 2026-10-20 15:30Z (`date -u`, HK-017)
- **Branch:** `arch/coherent-limb2`, the A′ workstream branch (HK-003 addendum: one branch per workstream). Docs only:
  `git diff --stat -- src/ native/` empty.
- **Licence:** the Captain, Architect's window, 2026-10-20 ~15:2xZ: "spec it for a" (option (a): re-run the
  wrong-decode check on today's `main` before any step-3 build).
- **Programme:** priority #1, A′ (D-001 limb 2), step 3 gate. Prior: COH-GAIN spec `2026-10-06-1625-…-coh-gain-step1.md`
  §§14–18; rulings `2026-10-07-1043` (WRONG-ID), `-1115` (Q-GATE), `-1254` (FIELD-ID), `-1330` (ENC-ID); build spec
  `2026-10-07-1330-…-coh-fallback-step3-build.md` (never reviewed; not touched by this spec).
- **Status:** PRE-REGISTERED once committed. One question for the Captain (§9, `U_max`) must be answered **before any
  label of the main run is joined**. QA's prep, validity rows and the pilot may run before that.

## 0. Why this is a new test and not a re-read

- **Q-GATE's GATE-OPEN stands as ruled** and is not re-read (standing prohibition).
- The FIELD-ID ruling §2 said explicitly: "A corrected truth applies to the **next** measurement." This is that next
  measurement:
  - a **new night**;
  - a **new population** (today's product misses);
  - the **frozen** threshold;
  - a scoring rule fixed **before** the data.
- 🔴 **Correction to what the Architect told the Captain on 2026-10-20 (chat, not a ruling).** I said the OSD defect was
  part of the 0.178 unexplained rate. **It wasn't.** Q-GATE counted the fallback's BP outputs only; the 215 OSD outputs
  were already excluded (§16.1, "a path-1 output counts as no output").
- The real reasons a re-test can read differently:
  1. **The truth was mis-scored on type-4 messages:** 795 of 917 unexplained outputs were `i3` = 4 against a standard
     re-encoded truth (FIELD-ID). The mechanism is verified from source (ENC-ID §2).
  2. **The product the fallback would sit on has changed:** OSD fixed, `nhard` 24, Deep third pass, B2.

## 1. Question

On a 40 m night recorded with today's decoder, take the rows the live product missed. Does the coherent fallback (C3,
BP only), gated by the frozen GA threshold, keep **≥ `BAR_G`** of gain at **≤ `U_max`** unexplained outputs per cycle?
Truth for non-standard-call messages is scored correctly this time.

## 2. What changed since Q-GATE, and how each change is handled

| item | Q-GATE (2026-10-07) | Q-GATE-2 |
|---|---|---|
| night | `20261004_1634` (TRAIN and TEST) | **`20261019_1905`** (never used by COH-GAIN; same chain: FT-991A → Voicemeeter B1 → both decoders) |
| live product on that night | `040613d9`, `nhard` 40, inverted OSD, no Deep | **`87beed94`** (= `main` `5229beec` + #225), `nhard` 24, OSD fixed, **Deep read back**, B2, late batches |
| population | G-fail rows (oracle position) | **live-miss AND G-fail** rows (§4) |
| G arm decoder | DLL `2fa6d993` (shim 20260058), `nhard` 40, inverted OSD | the pinned DLL of §3, `nhard` 24, sign fix ON |
| truth | vendored re-encode of WSJT-X text, payload match | the same **plus the type-4 rule** (§5) |
| gate | GA threshold chosen on TRAIN | **GA, T1 = 17.552446 dB, frozen** (`gate_thresholds.json` on `main`); **no re-tuning, no TRAIN split** |
| `U_max` | 0.15 (Captain, 2026-10-07) | **Captain to confirm or reset before the data (§9)** |
| `BAR_G` | 1.0 pp | 1.0 pp (unchanged; §9) |

## 3. The DLL, and how this combines with the #225 amendment validation (Captain, 2026-10-20: "can it be combined…")

**Combined where it is safe, kept separate where it is not:**

- **One pinned DLL:** the Developer's `8b2f7c82` (`feat/dxpedition-decode-225`, shim 20260065, the #225 phase-2
  amendment).
  - Its diff from `main` is the #225 work: the type-0.1 unpacker, the 10-bit lookup and C# display/suppression.
  - **None of it is on the path this arm uses:** `ft8_extract_llrs_at`, `ft8_ldpc_decode_llrs`, BP, OSD.
- **#225's V1 doubles as this arm's equivalence check.** V1 is the amended build against old `main` on the 455 cycles:
  every non-0.1 decode identical.
  - **V0** of this arm (§6) = "#225 V1 PASS on `8b2f7c82`, quoted with its DLL SHA".
  - If #225 V1 **fails**, this arm pins `main`'s own DLL instead (`9d5ba635` publish, SHA recorded), and V0 becomes
    V-G1 alone.
- **One QA job, one scratch folder** (`D:\Projects\claude\_qa-scratch\q-gate-2\`), one pin record. The DLL is copied
  into the run folder, its SHA-256 checked at load and at the end (`pins.jsonl`, the COH-GAIN discipline).
- **Order on the PC, never concurrently:**
  1. #225 validation (V1, V2/V2b, then R4b reporting-ON replay).
  2. Then this arm.
  - **Why:** the #225 replay runs Replay81 with the production budgets, and its V1 also requires 0 abandoned third
    passes. CPU contention from this harness could abandon a pass and produce a spurious V1 FAIL. That would stop a PR
    for a reason that has nothing to do with it.
  - **sol's V3 (S5 0/480) is a different machine and may run in parallel.**
- **Separate verdicts, separate reports.** The #225 PR never waits on this arm's outcome, and this arm's verdict never
  depends on #225's V2/V2b/R4b.

## 4. Population

- **Corpus:** `artefacts\20261019_1905_endurance_run-gathered\` (`owsfz\wav\`, 4,663 WAVs; `owsfz\ALL.TXT`;
  `wsjt-x\ALL.TXT`).
- **C0, before choosing (standing rule, 2026-10-03):** QA lists **every** `artefacts\` folder with WAVs. It confirms
  in the report that no other night has all four of:
  - a live product row on a build with the OSD fix;
  - `nhard` 24;
  - Deep;
  - the B1 chain.
  - `20261009_1752` has the fix and `nhard` 24 but not Deep (it was DI sync 5). If it qualifies after all, say so; the
    choice stays `20261019_1905`.
- **Cycles:** a systematic sample, positions `i mod 4 == 1` of the frozen ordered cycle list, ≈ 1,165 cycles.
  - The 6 zero-row outage cycles of the run's outage ledger are excluded **by their stamps**, before selection.
  - **If the pilot (§8 step 3) projects more than 6 h of CPU:** take `i mod 8 == 1` instead, and record which before
    any main-run row.
- **Rows:** every WSJT-X decode in a sampled cycle. Encodable / unencodable exactly as COH-GAIN §4, counted by reason;
  type 0.1 rows are expected among the unencodable.
- **`live_hit`:** the endurance ANOVA's own matcher (the one that produced 97,480 matched of 135,563), run on the corpus
  `ALL.TXT` pair. No new matcher.
- **Fallback population `P`:** rows with `live_hit` = 0 **AND** G failing at every one of the 9 lattice cells (G as
  COH-GAIN §2, today's DLL).
  - **Why both conditions:**
    - **Live miss:** a row the product already decodes, in any batch, can never be a gain. This also removes Q-GATE's
      V4 problem (residual-pass hits G cannot see).
    - **G fail:** a row G decodes at the oracle position is a candidate-search miss, not an extraction miss. The
      fallback's mechanism doesn't address it.
- **Descriptive bridge (no row):** the same figures on Q-GATE's population definition (G-fail only, `live_hit`
  ignored). This shows how much of the change comes from the population. **Never difference it against Q-GATE's
  TEST.**

## 5. Truth and labels (fixed now; the type-4 rule is the correction)

- **RIGHT:** `out_crc_ok` AND either:
  - (i) `comparator.payload_match` with `v_star` (as before); or
  - (ii) the output's `i3` = 4 AND ENC-ID's `enc_match` against the row's own WSJT-X text. That is `call_eq` AND
    (`hash_eq` OR `t_has_placeholder`), with §18.1's tokenisation, as code in `cg_encid.py`.
- **The same rule scores G.** A G type-4 decode is G-RIGHT, so its row leaves `P`. Without this, the fallback would be
  credited with rows G already gets.
- **Fallback output** = C3 through `ft8_ldpc_decode_llrs` with **BP only** (OSD depth −1), CRC-valid. Anything else
  is no output.
- **Wrong-output classes** (first match wins, same windows as WRONG-ID §15.4), each tested with rule (i) or (ii)
  against every WSJT-X row of the cycle:
  - **M-NEAR:** equals a WSJT-X decode within ±12.5 Hz and ±0.32 s → **not** unexplained;
  - **M-FAR:** equals a WSJT-X decode elsewhere in the cycle → **not** unexplained (reported);
  - **M-OWS:** equals a live OWS decode of that cycle → **counted as unexplained** (as Q-GATE);
  - **M-NONE** → unexplained.
- 🔒 **HK-037 / NFR-021:** text, bits, calls and hashes live only inside the function that reads `ALL.TXT`. Per-message
  working files are allowed only under `_qa-scratch\q-gate-2\` and are deleted at job close. Persisted: numbers and
  flags only.

## 6. Validity (any FAIL ⇒ no reading; the report names the row and stops)

| row | predicate | basis (HK-038) |
|---|---|---|
| **V0** DLL equivalence | #225 V1 PASS on the pinned DLL (quoted with SHA), or the fallback in §3 | #225's own gate; exact |
| **V-G1** G arm reproduces | on COH-GAIN sample `ext` (`rows_ext.json`), every row persisted as G-RIGHT on **path 0 (BP)** is G-RIGHT on path 0 with today's DLL: **≥ 99.9 %** | BP is not touched by the OSD fix or #225 (read from the diffs); 0.1 % allows for float order only. A miss means the harness or the DLL load changed |
| **V-C1** C3 reproduces | on the same sample, C3's persisted `C3_ok` / `C3_crc` / `C3_path` / `C3_nbe` on path 0 reproduce on **100 %** of the first 300 rows | Q1 reproduced 4,949 / 4,949 on 10-07 with the same Python; C3 BP doesn't depend on the OSD |
| **V-L** live matcher | the matcher reproduces the ANOVA's **97,480** matched over the whole night: exact | the gathered ANOVA, this night, today's tooling |
| **V-T1** type-4 rule | on the 795 FIELD-ID X rows, the new scorer's `enc_match` equals ENC-ID's persisted `enc_match`: **795 / 795** | ENC-ID's Y1 passed 814 / 814 with the same code |
| **V-T2** type-4 control (ENC-ID's failed Y4, redesigned) | each of this night's `i3` = 4 fallback and G outputs is matched against the text of a **different row in the SAME cycle** (seeded derangement within cycle, seed 20261020); match rate **≤ 2 %** | **checked on the pilot first:** if the pilot rate is > 1 %, STOP and come back before the main run. Reason: ENC-ID's control failed because a CQ station recurs across cycles; within a cycle a station transmits once, so recurrence can't occur (ENC-ID ruling §1). The 2 % is ENC-ID's own tolerance |
| **V-K** gate non-vacuity (HK-025(k)) | on `P`, GA keeps > 0 and < all fallback outputs | mechanical |

## 7. Rows (exclusive, first match wins; on the main-run cycles)

- **`KG`** = 100 × kept RIGHT / Σ encodable WSJT-X rows of the sampled cycles, in pp of WSJT-X decodes (Q-GATE's unit).
- **`UPC`** = kept unexplained / sampled cycles.
- **Kept** = a fallback output on a `P` row with **F1b ≤ 17.552446 dB** (F1b exactly as `cg_gate_features.py`).
- **CIs:** blocks of 8 sampled cycles, non-overlapping, numerator and denominator together, B 10,000, seed 20261020,
  95 % percentile.

| row | predicate |
|---|---|
| **G2-OK** | `CI_lo(KG)` ≥ 1.0 pp **AND** `CI_hi(UPC)` ≤ `U_max` |
| **G2-FAIL** | `CI_hi(KG)` < 1.0 pp **OR** `CI_lo(UPC)` > `U_max` |
| **G2-OPEN** | otherwise |

- **What each row leads to:**
  - **G2-OK** ⇒ the step-3 build spec is revised and goes to QA's (k) review. It has never had one.
  - **G2-FAIL** ⇒ the fallback can't ship as designed. The lead is recorded and the A′ line parks.
  - **G2-OPEN** ⇒ the Captain chooses, with the data.
- **Reported with it (descriptive, no row):**
  - the ungated fallback on `P` (KG, UPC);
  - KG and UPC by WSJT-X SNR band (≤ −16, −15…−6, −5…+4, ≥ +5);
  - the share of unexplained outputs that rule (ii) moved out of M-NONE (the forward measurement of FIELD-ID's 795 /
    917 pointer, on a new night);
  - the §4 bridge;
  - distinct cycles carrying kept RIGHT, and the share of KG in the top 5 blocks (say so in the first paragraph if
    > ½);
  - **today's live OWS-only per cycle on the sampled cycles**, so `UPC` can be read against it.

## 8. Run order

1. **C0** inventory; freeze the cycle list (committed with its SHA) **before** any extraction.
2. **V0** (from #225), V-G1, V-C1, V-L, V-T1.
3. **Pilot:** 50 rows from `i mod 4 == 3` cycles, **discarded**. It projects CPU hours (`cg_run.py` pilot mode) and
   gives the V-T2 pilot rate.
4. **The Captain's `U_max` answer (§9) recorded in the harness constant and committed.** Nothing joins a label before
   this.
5. Main extraction → features → labels → V-T2, V-K → rows.
6. Report; Architect ruling.

## 9. For the Captain (via QA, or here): `U_max`. A real choice, not housekeeping

**The data:**
- The 0.15 was set on 2026-10-07 as "about +30 % on the 0.47 WSJT-X-unconfirmed decodes per cycle" of the then-shipped
  decoder. That 0.47 came from the offline replay of `20261004_1634`: `nhard` 40, inverted OSD.
- **Today's product makes far fewer unconfirmed decodes.** Last night, live: 819 OWS-only in ~4,660 cycles ≈
  **0.18 per cycle** (the ANOVA, `87beed94`, Deep).
  - The same night's offline figure isn't measured.
  - The two numbers come from different instruments, so they aren't strictly comparable.
- **What the fallback figure doesn't include:** `UPC` counts false outputs at real-signal positions only. False
  decodes on noise-only candidates come **on top**, in the step-3 replay.

| option | what it means today | leads to |
|---|---|---|
| **Keep 0.15** | up to about **+85 %** on today's live unconfirmed rate, before the noise-only share | easier to pass; a passing build could visibly raise unconfirmed rows |
| **0.05** (the same +30 % rule on today's 0.18) | the same relative cost the Captain accepted on 10-07 | harder: `UPC` is an upper bound, so OPEN becomes likelier |
| **0.10** | about +55 % | in between |

**Architect's view: 0.05.** It applies the Captain's own 10-07 rule to today's decoder, and step 3 will add the
noise-only share on top. The cost is a higher chance of OPEN. The Captain decides.

**`BAR_G` stays 1.0 pp.** It was set as "a build-worthy gain", not derived from a build's numbers, so the build change
doesn't move it (HK-038).

## 10. What this arm does NOT do

- No build, no `src/` or `native/` change, no step-3 work.
- No noise-only candidates (step 3).
- No product candidate search: the positions are still WSJT-X's (step 3).
- No second band.
- Not run concurrently with the #225 replay on the PC (§3).

## 11. Predictions (blind; scored at ruling time)

| # | prediction | P | class |
|---|---|---:|:---:|
| QG1 | every validity row passes | 0.80 | C |
| QG2a | G2-OK, if `U_max` = 0.15 | 0.60 | H |
| QG2b | G2-OK, if `U_max` = 0.05 | 0.35 | H |
| QG3 | point `KG` in [2.0, 4.5] pp | 0.55 | H |
| QG4 | rule (ii) moves ≥ 70 % of the old-rule unexplained outputs out of M-NONE | 0.60 | H |

⚠️ QG4 is the tidy "findable localised defect" story the ledger warns about. It sits barely above even on purpose.
Only the QG2 line matching the Captain's `U_max` is scored; the other is void.

## 12. Amendment 1 — 2026-10-20 15:32Z (`date -u`): QA's HK-025(k) review, adopted in full. Before any cycle list, extraction or datum. Supersedes §§3, 4, 6, 7, 8 where they differ

QA accepted the spec with no row refused, and asked for three changes. All three are right.

**A1.1 Sampling must cover both slot parities (QA required 1).** An FT8 cycle is 15 s and parity alternates cycle by
cycle. So any even stride (`mod 4`, `mod 8`) takes **one parity only**: half the band's stations, and the same slot
of the minute every time. That was my design error.
- **Index:** `i` is the position in the frozen ordered list of **every** 15 s slot of the corpus window, **gaps
  included**. The 6 outage cycles are dropped **after** selection, by stamp. That way a gap can't shift the parity
  alignment.
- **Main run:** `i mod 5 == 1` (≈ 930 cycles). 5 is coprime to 2 and 4, so the sample cycles through all four slots of
  the minute.
  - **If the pilot projects more than 6 h of CPU:** `i mod 7 == 1` (≈ 665 cycles). Record which before any main-run row.
- **Pilot:** a disjoint residue, `i mod 5 == 3`. See A1.2 for its size.
- **Parity check (validity row V-P):** the main sample's even/odd cycle counts differ by **≤ 2 %** of the sample.
  Mechanical. A coprime stride should give near-equal counts; a gross imbalance means the index isn't the slot list.
- **About COH-GAIN's own samples (QA's question), checked:** they used `i mod 10 == r` (spec §4, §14). **Each sample was
  single-parity.** Q-GATE's TRAIN {5, 1, 2, 4} and TEST {6, 8, 9} each mix both parities, as do the pooled figures.
  - Whether `i` there was a gap-free slot list I have not checked. The residues alone don't guarantee a 50/50 split.
  - 🛑 **No closed COH-GAIN or Q-GATE figure is re-read for this.** It is recorded as a limit of those figures: per
    sample they describe one parity, and the pools mix them in whatever proportion the residues gave.

**A1.2 The type-4 control needs a minimum n (QA required 2).** At 50 rows a single chance match reads 12–30 %, so the
pilot STOP rule was meaningless.
- **Control population:** every CRC-valid `i3` = 4 output, **from G and from the fallback**, in cycles with **≥ 2
  encodable WSJT-X rows**. A within-cycle derangement needs a second row. Cycles with fewer rows are excluded from the
  control and counted.
- **Pilot control:** drawn from `i mod 5 == 3` cycles, taken in order, **until n ≥ 200 type-4 outputs**. These cycles
  are discarded from every row.
  - The CPU-projection pilot stays at 50 rows from the first of those cycles.
  - **STOP rule:** pilot match rate **> 1 %**, i.e. ≥ 3 matches at n = 200. If the residue runs out before n = 200, STOP
    and report n.
- **Main-run V-T2:** match rate **≤ 2 %**, on the main run's own control population (expected n ≫ 200). It reports n
  and the Wilson interval.
- Both rates keep ENC-ID's tolerance (2 %). The pilot's 1 % is half of it, to leave room for sampling noise at n = 200.

**A1.3 V0 is a pin selector, not a validity row (QA required 3).** Both branches continue the run, so it can't stop
anything.
- **Renamed: S0 "pin selector".**
  - #225 V1 PASS on `8b2f7c82` (quoted with its DLL SHA) ⇒ pin `8b2f7c82`.
  - Not available or FAIL ⇒ pin `main`'s DLL (SHA recorded).
- **The equivalence evidence is V-G1 and V-C1, run on whichever DLL is pinned.**
  - #225's V1 runs on the 455 cycles of `20261009_1752`, not on this night. That is enough for code equivalence: the
    question is whether this DLL's extraction and BP path behave as before, and that doesn't depend on the night.
  - **V-G1 / V-C1 on COH-GAIN sample `ext` are what cover the extraction path.** V1 only chooses the pin.
- The §6 table now reads **S0** (selector), then the validity rows **V-G1, V-C1, V-L, V-T1, V-T2, V-K, V-P**. Any FAIL
  of a validity row ⇒ no reading.

**A1.4 QA's notes, adopted:**
- **G2-OK wording.** The report's G2-OK sentence must include: "**necessary, not sufficient**, for the step-3 build:
  UPC counts false outputs at real-signal positions only; it does not establish the step-3 false-decode rate."
- **Precision before the run.** From the pilot's per-cycle rates, the pilot reports projected 95 % CI half-widths for
  KG and UPC at the chosen stride. The Captain then sees, before the main run and alongside his `U_max` choice, how
  likely G2-OPEN is.
  - **Descriptive.** It changes no row, no stride and no bar.
  - The one exception is the pre-set `mod 7` CPU fallback above.
- **Scheduling.** The #225 replays are paused by the Captain.
  - **No DLL needed, so these can run now:** C0, the cycle list, V-P, V-L and V-T1. V-L and V-T1 use the matcher and
    the scorer only.
  - **Wait for S0:** V-G1 and V-C1 run on the pinned DLL.
  - **If the Captain wants this arm first:** pin `main`'s DLL now (S0's second branch). Then nothing waits on #225.
  - **That is his call.** The cheaper #225 V1 (455 cycles, ≈ 2 h) and this arm (≤ 6 h) together book the PC for most
    of a day, run one after the other.

**Predictions (§11):** unchanged. They were made blind to the population size, and the parity fix doesn't move them.
