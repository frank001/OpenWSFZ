# `OSD-FA-A` E3 — acceptance ruling: **E3-N ACCEPTED**; 9 of the 11 "corroborated removals" are callsign-rendering artefacts; the Architect's "Option B's live reach ≤ ~1.9%" is WRONG and struck

**Architect, 2026-09-11 22:10Z** (`date -u`, HK-017). Branch `arch/osd-fa-a`.
Docs-only; `git diff --stat origin/main -- src/ native/` empty.

Accepts QA's work on branch `osd-fa-a-row0-part-d-result`, `37d6587`, against Amendment 1 §5.3:

- `qa/rr-study/2026-09-11-2204-qa-to-architect-osd-fa-a-e3-result.md`

All figures below are recomputed from QA's artefacts (`subject_20260050.json`, `replay40.json`,
production `ALL.TXT`, WSJT-X #1 `ALL.TXT`). I used QA's own loaders and matcher read-only, and wrote
my own counting. **Counts only; no message text was printed or written (NFR-021).**

---

## 1. Recomputed

| check | QA | recomputed |
|---|---|---|
| Live decodes in span | 57,947 | 57,947 |
| Reproduced by the 60-leg | 57,594 = **99.39%** | same; ≥ 0.90, not VOID |
| Removed (reproduced at 60, no wildcard match at 40) | 1,509 | 1,509 |
| … of those corroborated by WSJT-X #1 | 11, CP95 [0.364%, 1.301%] | same |
| Binary / window, both legs | `6b2e16a6…`, same window | as recorded |

**Row, by the pre-registered predicate:** `lo = 0.364% < BAR_H = 5%` ⇒ **E3-N.**

## 2. HK-020 "same harness": QA did not verify it; I did, and it holds

Amendment 1 §5.3 requires both legs to use the **same harness**. QA reused F-001 L3's 60-leg and
checked its **count** (65,798). That shows the file is the intended one. It does not show that the
new 40-leg harness behaves identically apart from `nhard`.

**The check, from the two replay files:** `nhard` gates only OSD accepts, so a harness identical
except for `nhard` should produce a 40-leg that is (nearly) a **subset** of the 60-leg:

- 40-leg decodes with **no 60-leg decode within 3 Hz** in the same cycle: **14 of 58,438**.
- Live decodes matched at 40 but **not** at 60: **20**.

⇒ **The 40-leg is a frequency-subset of the 60-leg to within 0.03%. No harness difference beyond
`nhard` is visible. Accepted.** QA should add this check to the report as a disclosure.
Exact-text comparison shows 1,666 "gains", but those are almost all rendering differences at the same
frequency (§3). That is why the Amendment requires wildcard matching.

## 3. What the 1,509 removals actually are

Each removal falls into exactly one category, by what the 40-leg shows within 3 Hz:

| category | n | corroborated |
|---|---:|---:|
| **No 40-leg decode within 3 Hz**: the decode vanished | 994 | 1 |
| **A different message** at the same frequency | 497 | 1 |
| **Same decode, different hashed-callsign rendering** (`<X>` vs `<Y>`) | **18** | **9** |
| total | 1,509 | 11 |

**The 18 are not removals.** The two legs build different callsign-table histories once the
40-leg drops decodes. Amendment 1 §5.3 named this confound. The wildcard covers only literal `<...>`,
so a hash resolved to a *different* bracketed call still reads as a mismatch. **They carry 9 of the
11 corroborated removals.**

**I evaluated both branches (HK-025).** Both give the same row:

| reading | k / n | CP95 | row |
|---|---|---|---|
| **Pre-registered** (wildcard) | 11 / 1,509 | [0.364%, 1.301%] | **E3-N** |
| True removals (drop the 18) | 2 / 1,491 | [0.016%, 0.484%] | E3-N |
| Frequency-only (decode vanished) | 1 / 994 | [0.003%, 0.559%] | E3-N |

**E3-N is ACCEPTED on the pre-registered figure.** The "true removals" figure is **descriptive,
not a re-read of the gate**. Its direction is instructive: the pre-registered k **overstates**
corroborated removals about 5×, and that bias ran **toward** E3-H, so E3-N is conservative.

**How to cite it:** *"E3-N: of 1,509 live decodes the 40-leg failed to reproduce, 11 were
corroborated by WSJT-X #1 (CP95 [0.36%, 1.30%]). Descriptive: 18 of the 1,509, and 9 of the 11,
are callsign-rendering differences. True removals are 1,491, and 2 of them are corroborated (≈ 0.09
per hour against ≈ 68.6 removed per hour)."*

- 🛑 **Never "safe", "no cost" or "negligible".** Corroboration bounds genuine loss **from below**
  (the `FP-FLOOR-LIVE-2` principle). WSJT-X misses weak genuine signals too.

## 4. 🔴 CORRECTION: "Option B's live reach ≤ ~1.9%" is wrong, and it is mine

The Part D3 acceptance (`…1932…` §2) and the E1 acceptance (`…2048…` §4) both said Option B's live
reach is **bounded by D1's `U`**, at most ~1.9% of live output, and I made that pairing
**mandatory**. **E3 measures the reach directly:**

- True removals: **1,491 / 57,594 = 2.59%** of reproduced live output, CP95 [2.46%, 2.72%].
- That is **above D1's `CI_hi` of 1.88%**. Even the frequency-only floor, 1.73% [1.62%, 1.84%], sits
  inside the band I claimed as a ceiling.

**Cause (HK-026):** `U` is the OSD share among decodes the **Part D probe could classify**. OSD
accepts are exactly the decodes the probe struggles to reproduce. D3's "probe finds nothing"
category was 41% of unconfirmed decodes. E3 removes **~62% of our WSJT-X-unconfirmed output**
(2.59% of 4.14%), where D3 attributed only 36% of it to OSD. `U` therefore **undercounts** the OSD
share. An instrument cannot bound its own blind spot, and I used it as a bound.

**What survives:** D1's **row** (`CI_hi < 10%`) and its consequence ("OSD bounded out as a D-001
explanation") stand. E3's 2.59% is a **lower bound** on the OSD share, because 40 removes only part
of it. Counting **every** decode D3 could not classify (483 of 11,615) as OSD gives ≈ **5.7%** at
worst. Both are under 10%.

**The replacement citation:** *"OSD-path decodes are between ~2.6% (E3, direct) and ~5.7% (Part D3,
worst case) of live output. D1's `U = 1.64%` undercounts them. Option B removes ~2.6% of live
output."*

**Struck where they live (HK-022):** `…1932…-part-d3-acceptance.md` §2, `…2048…-e1-acceptance.md` §4,
the `BOARD.md` 19:32Z and 20:48Z entries, and the `MEMORY.md` FP-workstream line. QA's E3 report §5
and E1 report §4 repeat the figure because I told QA to. **QA owes a strike with a pointer here in
both.** No fault attaches to QA.

## 5. The arm's consequence (Amendment 1 §5.4, strict order)

1. `E2-B2 or E3-H`: **neither.** Option B is not contraindicated on this evidence.
2. `E1-2`: no (E1-1 fired).
3. **`E1-1 ∧ E2-B1 ∧ E3-N`: HOLDS.** ⇒ **The Architect is cleared to DRAFT a separate
   pre-registration for changing the default 60 → 40** (a `src/` change, HK-011). This is not a
   licence to change anything. **Bound by the E2 ruling §2:** the draft must carry a
   **near-threshold oracle leg as its safety gate**, because no leg of this arm can show that weak
   real stations survive.

**What the whole arm says, in one place (read with each leg's caveats):**

| | at `nhard` 60 | at `nhard` 40 |
|---|---|---|
| Synthetic noise: slots with any false decode (E1) | 10.3% | 0.35% |
| Strong-signal synthetic scene: false share of output (A, E2) | 9.41% | 1.02% |
| … genuine decodes lost (E2) | — | 0 of 11,000 (this scene has no weak stations) |
| **Live: our output removed (E3)** | — | **~2.6%, ~68.6 per hour** |
| … of which WSJT-X confirms (E3, descriptive) | — | **2 of 1,491, ≈ 0.09 per hour** |
| Weak real stations survive? | — | **Not shown by any leg** |

**Operating note (Amendment 1 §5.4 clause 1 wording, applicable generally):** `OsdNhardMax` is
already an operator setting (`config.json` `Decoder.OsdNhardMax`, range [30, 100], applied on the
next cycle). The PO may set 40 on their own station with these figures in hand. That is an
**operating choice**, not a product change, and needs nothing from this arm.

## 6. Arm status

Part 0 → D → A → B → E1 → E2 → E3: **complete and accepted.** Part C: **deferred** (granted
20:21Z). Nothing is pushed. QA's branch `osd-fa-a-row0-part-d-result` and `arch/osd-fa-a` both wait
on the Captain: the push/PR go (HK-033 / HK-014) and merge sign-off (HK-010). **Next is the
Captain's call:** whether the Architect drafts the default-change pre-registration, including its
near-threshold oracle leg.
