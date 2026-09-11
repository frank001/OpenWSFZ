# `OSD-FA-A` Part D, third run — acceptance ruling: **D1 ACCEPTED**; the sign-off comparator mechanism identified to the bit

**Architect, 2026-09-11 19:32Z** (`date -u`, HK-017). Branch `arch/osd-fa-a`.
Docs-only; `git diff --stat origin/main -- src/ native/` empty.

Accepts QA's work on branch `osd-fa-a-row0-part-d-result`, `0338eed`, against the Part D rulings
`2026-09-11-1652-…` and `2026-09-11-1918-…` §3:

- `qa/rr-study/2026-09-11-1935-qa-to-architect-osd-fa-a-mechanism-2-diagnostic.md`
- `qa/rr-study/2026-09-11-2000-qa-to-architect-osd-fa-a-part-d3-result.md`

---

## 1. Mechanism 2 is identified: other stations send "RR73" as a grid square

QA's diagnostic took its field boundaries from `message.c:354–376`, not from my prose. I had the
field order wrong: `i3` is at bits [74, 77). The result:

- **All 578** sign-off mismatches are confined to `g15`, and nothing else is touched.
- **2,890 differing bits = exactly 5.0 per decode.**

**The mechanism, checked to the bit.** "RR73" is a valid Maidenhead locator (field RR, square 73),
so it has two encodings that display identically:

- the grid-square value **32373**, unpacked by `unpackgrid` as a locator (`igrid4 ≤ MAXGRID4`);
- the special token **32403** (`MAXGRID4 + 3`), which is what `packgrid` always writes
  (`message.c:908–909`).

`popcount(32373 XOR 32403) = 5`. **Every sign-off mismatch carries exactly that 5-bit
signature.** These are stations transmitting RR73 as the grid square. They decode and display
correctly, but `true_codeword(text)` re-packs them as the special value.

**The comparator is invalid for this category on a demonstrated mechanism.** QA's exclusion of
sign-offs from ROW 0e eligibility under the `…1918` ruling §3.3 is **accepted**. The mismatch
pattern of every other category (all fields at once, e.g. 68/68 CQ mismatches hit `c28_1`, `c28_2`
and `g15`) is what a genuine different decode looks like, so those categories stay in.

It is **not a product defect**: both encodings decode to the same text, and nothing in the product
re-encodes received messages.

## 2. Part D: D1 fires, and I accept it

Recomputed independently from `artefacts/2026-09-11-osd-fa-a-part-d3/D3a.json` / `D3b.json`:

| check | QA | recomputed |
|---|---|---|
| Binary | `6b2e16a6…` shim `20260050`, both legs | as recorded |
| Sample | 1,000 cycles, seed `compute_seed("OSD-FA-A-PART-D3", 0, 0)`, derived from a label, not the data | as coded, `part_d3.py:53` |
| Reproduction share (live decodes matched to replay) | 11,551 / 11,615 = **99.45%** | same; ≥ 0.90, readable |
| ROW 0e (no `<`, not sign-off; `−1` = fail) | **93.51%** full, 93.5% subset | 8,745 / 9,352 = **93.51%** |
| ROW 0d, two processes | 0 / 11,615 | **0 / 11,615** |
| `U` | 183 / 11,132 = **1.644%** | same |
| 95% CI, cycle-clustered | [1.414%, 1.876%] | [1.408%, 1.881%] (independent bootstrap) |

**D1:** `CI_hi < 0.10`, about 5× inside the bar, with every precondition genuinely met.

**Consequence (base §4.2 D1, unchanged):** OSD false accepts are **bounded out as an explanation of
D-001** on live data. ~~Junk arriving via the OSD path cannot exceed ~1.9% of live output.~~ Parts A
and B become characterisation of a minor path and may not be cited as explaining D-001.

~~**What D1 means for the FP question, in the same breath:** Option B only touches OSD-path
accepts, so **its reach is bounded by `U`**: at most ~1.9% of live output (CI upper bound).~~

> ⛔ **STRUCK 2026-09-11 22:10Z (Architect), HK-026:** `U` counts only the decodes the probe could
> classify, and it undercounts OSD. E3 measured Option B's live reach directly: **2.59%** [2.46, 2.72],
> above this "ceiling". The OSD share is between ~2.6% (E3) and ~5.7% (worst case here). The D1
> **row** and "bounded out of D-001" stand (both are under 10%). See
> `2026-09-11-2210-architect-osd-fa-a-e3-acceptance.md` §4.

**Prediction scoring:** suspended. My Part D prediction was de-blinded by the `…1918` ruling §4.

## 3. Descriptive, from the now-valid leg: where our unconfirmed decodes come from

Amendment 1 §3's descriptive split, recomputed. **No row, not a gate, and "unconfirmed" is not
"false"**: corroboration bounds genuine loss from below.

| | count | share |
|---|---:|---:|
| Live decodes in the sample | 11,615 | — |
| **Not confirmed by WSJT-X #1** | **481** | **4.14%** of live output |
| OSD-path decodes (all) | 183 | 1.58% of live output |
| … of which unconfirmed | **173** | **94.5%** of OSD-path decodes |
| Confirmed decodes taking the OSD path | 10 of 10,890 converged | 0.09% |
| Unconfirmed decodes: OSD-path / BP-path / probe finds nothing / not matched to replay | 173 / 69 / 197 / 42 | 36% / 14% / 41% / 9% |

**Reading, as a lead only:** OSD-path decodes are almost all unconfirmed, and they make up about a
third of our unconfirmed output. Another ~41% of unconfirmed decodes are ones the probe cannot
reproduce at all, and their decode path is unknown.

**Part E is what turns this into a decision:** E1 measures the FP change, E2 genuine cost under
oracle truth, and E3 live harm. The bars are frozen.

## 4. Next

QA continues: **ROW 0b / 0c → Part A → B → C → E1 → E2 → E3**, as authorised, with checkpoints at
natural blocks and HK-020 per leg, naming the source document for each config value.

Two reminders:

- **The `+0.16 s` rule, stated once for every remaining leg** (base §2.4 item 1 as corrected):
  - Apply it **only** when extracting LLRs at a synthetic **true** (encode-time) `dt`.
  - Parts A/B run the full decoder and extract nothing.
  - Part C's `nhard`/`corr` recomputation extracts at the decoder's **reported** `dt`, so **no
    offset** there, the same as Part D.
  - If any leg extracts at a true `dt`, say so and apply it uniformly.
- **Match on payload, not displayed text** (base §5.1). The RR73 finding is a concrete instance of
  why.
