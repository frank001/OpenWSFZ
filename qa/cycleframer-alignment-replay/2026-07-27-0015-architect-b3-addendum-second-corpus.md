# D-001: B.3 addendum — the second corpus already exists. B.1b replication spec, reading rules fixed in advance

**Author:** Architect, 2026-07-27 (00:15). **For:** the Captain and QA.
**Amends:** `2026-07-26-2359-architect-b3-costed-menu.md` §4 item 3 only. The menu itself — rows,
prizes, ceilings — is unchanged; this note revises what "second corpus first" costs and adds the
replication design. Nothing else in the memo is touched.
**Prompted by the Captain**, who pointed out that `artefacts/20260724_live_run_1607/` is a
different band. The Captain is right, and my item 3 overpriced itself: the corpus does not need
gathering. It needs ~20 minutes of compute.

---

## 1. Two corrections to the memo's §4

1. **"Gather the second corpus" → "run the second corpus."** `20260724_live_run_1607/` is
   **20 m (14.074 MHz), afternoon (16:07–16:38), ~31.5 min, 126 cycles** — against the B.1/B.2
   corpus's **40 m (7.074 MHz), evening, 21 min, 68 matched cycles**. Different band, different
   time of day, different (denser) activity level, and roughly double the matched-cycle count.
   HK-016's gathering discipline already paid for this note.
2. **The "one device" caveat is retired as an actionable item.** There is one radio; a second
   device is not an option this station has, and the capture chain is measured at 0.5% of the
   gap anyway, so the device axis was never where the risk lived. The caveat survives only as a
   statement of fact in findings docs, not as insurance anyone is asked to buy.

## 2. Due diligence done this session (verify, don't re-derive)

- **Artefact contents:** `ALL.TXT` (WSJT-X, cumulative), `owsfx ALL.TXT` (ours, run-scoped),
  daemon log, `wav/` with **126 files of our own capture** — 12 kHz mono 16-bit, exactly 180 000
  samples each, i.e. jt9-compatible by the same construction B.1's arm A4 already validated
  (and found mildly *favourable* to jt9, so substrate is not a confound).
- **WSJT-X ran in parallel:** its ALL.TXT carries **4371 decode lines inside the run window**
  (16:07:15–16:38:45), both sides at dial 14.074.
- **Raw window counts, not yet deduped/matched:** WSJT-X 4371 over 126 cycles vs our live 2466
  over 127 — ratio **1.77×**, vs 1.59× on the 40 m corpus. The gap is present on the second
  band, prima facie slightly larger. These counts are due diligence, not results — QA's matcher
  produces the real numbers.
- **One structural difference from corpus 1:** WSJT-X's ALL.TXT here is **cumulative** (it opens
  at 08:21 with earlier-session traffic). Window filtering is load-bearing for B.1b in a way it
  was not on 07-25. And there is **no `wsjt-x/wav/`** — jt9 runs on our capture only, which A4's
  finding makes acceptable and which should be stated, not hidden, in the findings doc.

## 3. B.1b — replication design

Same instrument, same conventions, new corpus. Everything reuses `b1_jt9_ablation.py` and
`c4_matched_decode_verification.py`'s matching/normalisation; nothing new is invented.

| piece | spec |
|---|---|
| corpus | the 126 `wav/` files, chronological, one jt9 process per arm |
| arms | **A0′** `-8 -d 3`, **A1′** `-8 -d 2`, **A2′** `-8 -d 1` — same flags as B.1, no context/AP flags |
| our offline anchor | re-decode the same 126 WAVs at shipped settings (k10/c0.10/n60) with the existing harness — the anchor is the **offline** number, not the live 2466 (report the live number alongside for continuity) |
| WSJT-X reference | ALL.TXT filtered to 16:07:15–16:38:45, deduped, cycle-matched — the cumulative-file caveat from §2 applies |
| scoring | totals, miss coverage of the matched miss population, overlap with our offline set — the same three numbers as B.1 §3, plus the T(3)−T(2) / T(2)−T(1) price list |
| smoke test | one WAV, depth 3, before any arm is trusted — B.1 §3.1 discipline unchanged |
| NFR-021 | raw jt9 output under git-ignored `artefacts/d001_b1b_second_corpus/`; aggregates only in the findings doc |

**Not in scope:** B.2 does not replicate — it is synthetic and corpus-independent by design. An
optional arm (only if cheap after B.1b lands): the BER-distribution re-read of the new corpus's
miss population, to check whether the ≈50%-BER "never locked" shape recurs. Optional means
optional; B.1b's three numbers decide the reading below without it.

## 4. Reading rules — fixed now, before any number exists

Corpus-1 reference values in brackets. "Replicates" is defined per rule, not by feel.

| rule | quantity | corpus 1 | replicates if | if it does not |
|---|---|---:|---|---|
| **R1** | A2′ / our-offline ratio | 1.302 | **> 1.10** (the plan's own "wide margin" trigger) | the front-end row's two-corpus backing fails; the menu comes **back to me** before the Captain decides anything beyond row 1 |
| **R2** | A0′ / live-reference ratio | 1.005 | 0.85–1.10 | a large live-vs-offline delta on this corpus would mean session context matters here where it did not on 40 m — reopen the denominator question for this corpus only |
| **R3** | miss coverage at d1 / d3 | 55.4% / 98.0% | d3 coverage > 85% and d1 coverage > 35% | the "ceiling ≈ the whole gap" claim in the memo's §2 weakens; the menu's row-4/row-5 prizes get corpus-1-only asterisks |

**What replication buys:** if R1–R3 all fire, the costed menu stands on two corpora spanning two
bands and two times of day, and the memo's §6 "one corpus" caveat is retired in its strongest
form. The counts will differ — the *shape* (front end ≫ correction residue) is what is being
tested. If any rule fails, the menu is not put to the Captain as-is; I revise it first.

**What replication does not buy:** it does not decompose row 4's scope, does not isolate SIC's
share, and does not touch the GPLv3 question. The menu's decision structure is unchanged either
way.

## 5. Sequencing

B.1b is **QA-only, no native or `src/` change, ~20 minutes of compute** (126 WAVs × 3 arms at
~2.3 s/WAV, plus one offline decode pass). It slots **before** the Captain commits to any row
other than row 1 — that is what the memo's §4 item 3 always meant, now at its true price. The
Captain may of course decide row 1 (accept) without waiting for it.

## 6. What this note does not authorise or settle

- **No native or `src/` change** (HK-011 untouched). **No push, no merge** (HK-014).
- **No `pre_merge_check.py`** — Captain's trigger per HK-006.
- **The `libft8.dll` size question and branch disposition** remain with the Captain, unchanged.
- **NFR-021** as in §3.

## 7. Cross-references

- `2026-07-26-2359-architect-b3-costed-menu.md` — the memo this amends (§4 item 3 only).
- `2026-07-26-b1-jt9-ablation-findings.md` — arms, scoring, A4 substrate validation, smoke-test
  discipline all reused verbatim.
- `artefacts/20260724_live_run_1607/` — the corpus (git-ignored, real callsigns).
- `b1_jt9_ablation.py`, `c4_matched_decode_verification.py` — the instruments.

---

*Per HK-015 this is a recommendation; QA authors the task and runs B.1b. Per HK-014 this note is
committed locally and goes no further. The menu remains before the Captain; nothing here delays a
row-1 decision, and everything here precedes a row-2/4/5 commitment.*
