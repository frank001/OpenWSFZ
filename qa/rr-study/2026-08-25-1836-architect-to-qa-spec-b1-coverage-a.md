# B1-COVERAGE-A — when we render `<...>`, had our own stream ever learnt that callsign?

**Architect → QA.** Drafted 2026-08-25 18:36Z (`date -u`, HK-017). Repo `main` at `1b8265f`.

**Answers:** `2026-08-25-1735-architect-WITHDRAWAL-...` §4.3 (the owed spec) and QA's
`2026-08-25-1756-qa-to-architect-corrected-predicate-rederivation.md` §5 item 3.

**Status: pre-registration.** No `src/` change, no `native/` change, no rebuild, no replay, no
capture run. **Pure re-analysis of dumps already on disk.** Expected runtime: minutes.

---

## §0. Why this exists, and what I already touched

`GAP-CENSUS-A` bucket **B1** is *"the reference decoded it, we decoded something in the same place,
and our text carries an unresolved `<...>` hash."* On the corrected predicate QA re-sized it to
**470 decodes / 1.08 pp of D-001** on L2 (current `main`), 95 % CI [1.05, 1.11].

**That number is a size, not a cause.** Nobody has asked the only question that decides whether any
hash-table change can ever recover it:

> **When we rendered `<...>`, had our own decode stream already emitted that callsign in plaintext —
> and if so, was the table still accepting entries at the time?**

If the answer is mostly *"we never heard the callsign at all"*, B1 collapses into bucket C, the
hash table is irrelevant to it, and **eviction (F-001 D3) is closed as a D-001 route.** If the
answer is mostly *"we had heard it, and the table was already frozen"*, then B1 is a real
capacity population and F-001 D3 earns its own pre-registration.

### 0.1 🔴 DISCLOSURE — I ran a feasibility probe before drafting, and it changed the design

Per the X1/X2 and WITHDRAWAL §7 precedent, and because HK-021(q) *requires* me to demonstrate the
predicate moves before the gate runs, I probed `L2_run1_decodes.json` directly while drafting.
Scratch scripts live under the gitignored `artefacts/2026-08-25-b1-coverage-probe/`. **Counts and
sha256-truncated tokens only; no callsign text printed, written, or retained (NFR-021).**

**What I measured, and therefore what QA's run is NOT blind to:**

1. **B1 reproduces at 470** from an independent code path — QA's population is sound.
2. **The B1 ↔ reference message correspondence** (§2.2 below) — the numbers in the §2.2 table.
3. **The concentration of B1 over callsigns** (§2.3) — the decodes-per-callsign histogram.
4. **ROW 0d's calibration constant** (§3), `D / 4096 = 0.965`, measured so the bar is set against a
   real distribution rather than guessed (HK-021(b)).

**What I did NOT compute, and where predictions in §8 are genuinely blind:** the `B1-cov` /
`B1-ord` / `B1-cap` split itself, and the `cap-frozen` / `cap-resident` split. I stopped
deliberately at the classifier's inputs.

🔴 **QA's numbers are the citable ones. Where QA disagrees with anything in §2.2/§2.3, QA is the
result and I am the error.**

---

## §1. Three facts read out of the source, which the design rests on

Read directly from `src/OpenWSFZ.Ft8/Native/ft8_shim.c` and
`native/ft8_lib_vendor/ft8/message.c` this session — cited so QA can check them rather than take
them on my word.

1. **An insert fails ONLY when the table is full.** `hash_table_add` (`ft8_shim.c:666-701`) probes
   linearly with wraparound; it increments `g_hash_table_reject_count` and returns *only* after a
   full probe pass finds no empty slot **and** `tbl->count >= HASH_TABLE_SIZE` (`:694`). A repeat
   announcement of a known callsign returns early and is explicitly **not** a reject (`:685`).
2. **Nothing is ever evicted or re-initialised** (`:705-711`). ⇒ **Once an entry is resident, it is
   resident for the life of the process, and a lookup of a resident entry cannot miss** unless the
   decoded hash bits themselves differ. This is what makes §6's split decisive rather than a guess.
3. **The table is populated at UNPACK time, not at emit time.** `unpack28` calls
   `save_callsign()` (`message.c:838`), which calls `hash_if->save_hash(callsign, n22)`
   (`message.c:589`), once per callsign with the 22-bit hash. **This happens for every candidate
   that survives LDPC, including ones the shim later filters out and never emits.**

Fact 3 is the design's one real weakness and §3 ROW 0d is built to bound it — see §7.1.

---

## §2. The population and how a callsign gets NAMED

### 2.1 Inputs — pinned, no rebuild, no replay

| input | path | pinned value |
|---|---|---|
| ours (L2, current `main`) | `artefacts/2026-08-25-g2a-remeasure-a/L2_run1_decodes.json` | `dll_sha256` = `bc8efcf148046f199c057b62c7987c4b69f2dc62d72509458a671305ab051d7f`, `shim_version` = 20260046, `n_decodes` = 71,600 |
| ours (determinism replicate) | `.../L2_run2_decodes.json` | same SHA, same count |
| reference | `artefacts/20260803_live_run_1713/wsjt-x/ALL.TXT` | `n_theirs` = 43,423 |
| freeze boundary | `.../L2_freeze_cycle.json` | `freeze_cycle_ts` = **`260803_202600`**, index 767 / 4,971 |
| table capacity | `ft8_shim.c:631` | `HASH_TABLE_SIZE` = **4096** |

Pinned constants, **never re-derived**: `F_MIN_HZ` = 200.0, `FREQ_TOLERANCE_HZ` = 4.0,
D-001 normalisation basis = `n_theirs` = 43,423.

🛑 **L1 does not appear in this arm at all.** This is a description of the population *as it exists
on current `main`*, not a contrast between binaries. Nothing here re-opens `ΔB1`, which stays
uncitable for the reasons already on record.

### 2.2 🔴 B1 as published is not textually corroborated, and ~28 % of it is a coincidence

`partition.py:classify_key` assigns B1 on **frequency co-location alone** — same cycle, ±4 Hz — and
never checks that our unresolved decode is *the same message* as the reference decode it is paired
with. Template-matching our text against the reference's resolved text over the 470:

| | count | share of B1 |
|---|---:|---:|
| token-aligned, exactly one `<...>` slot, **all other tokens identical** → callsign NAMEABLE | **339** | 72.1 % |
| token-aligned, **2** non-hash tokens differ → a different QSO that happens to sit within 4 Hz | 71 | 15.1 % |
| **token count differs** → a different message entirely | 58 | 12.3 % |
| token-aligned, 1 non-hash token differs → ambiguous | 2 | 0.4 % |

Every token-aligned case carries **exactly one** hash slot (412/412) — there is no two-slot
complication to design around.

⇒ **The partition below needs a fourth bucket, `B1-amb`, evaluated FIRST**, or a quarter of the
population is silently mis-attributed. It also means the textually-corroborated B1 is **339 decodes
≈ 0.78 pp** of D-001, not 470 / 1.08 pp. **QA must re-derive that figure; I am not issuing it.**

⚠️ **This test is a strictly sharper instrument than the circular-shift null.** The null estimates
the chance-co-location rate *in aggregate*; the template test identifies it *case by case*. Where
they disagree, the template test wins, and the null is not required for this arm.

### 2.3 🔴 B1 is 47 callsigns and one of them is half of it — this decides the whole readout

Decodes per named callsign, sorted descending:

```
178, 19, 17, 16, 15, 13, 10, 7, 5, 5, 4, 4, 3, 2x10, 1x25      (k = 47, n = 339)
```

Top-1 = **52.5 %** of named B1. Top-5 = **72.3 %**. **Effective sample size on a decode-weighted
proportion is ≈ 3.5.**

🛑 **Therefore: NO gated statistic in this arm is decode-weighted, and no decode-weighted quantity
gets a confidence interval.** The unit of independence is the **callsign** (HK-021(i)). A
cycle-clustered CI over 433 cycles here would read as though it had hundreds of independent
observations while actually describing one station's behaviour — the same class of error as the
withdrawn Part A, dressed differently. Decode counts are reported as **exact point counts of this
corpus**, always beside the concentration table, never with a CI.

*(Captain/PO decision, 2026-08-25: gate at callsign level; decode counts descriptive only.)*

### 2.4 The naming rule — pinned to the exact predicate that computes it (HK-021(q))

For each B1 key `(ts, R)` where `R` is the reference's normalised text:

1. Candidate set = every ours-decode in cycle `ts` with `|freq_hz − rep_freq| <= 4.0` that satisfies
   `has_unresolved_hash_marker()` (i.e. `re.compile(r"<\.*>")`, `common_g2a.py:63`). **Sort the
   candidate set at construction** by `(freq_hz, message_norm)` — hash-randomised iteration
   silently breaks seeded determinism.
2. A candidate `O` is **template-consistent** with `R` iff: `len(O.split()) == len(R.split())`,
   **exactly one** token of `O` fullmatches `^<\.*>$`, and every other position is byte-equal.
3. The **named callsign** is `R`'s token at the hash position, and it must pass the callsign-shape
   test in §2.5. Otherwise the candidate is not template-consistent.
4. If the template-consistent candidates name **more than one distinct callsign**, the key is
   `B1-amb`. If none is template-consistent, the key is `B1-amb`.

### 2.5 The callsign-shape test and the plaintext-emission predicate — both pinned

```python
CS_RE   = re.compile(r"^[A-Z0-9/]{3,11}$")
GRID_RE = re.compile(r"^[A-R]{2}[0-9]{2}$")
NONCALL = {"CQ","DE","QRZ","RRR","RR73","73","TU","NA","SA","EU","AS","AF","OC","AN","DX"}

def is_callsign_token(t):          # all five conditions, in this order
    return (CS_RE.fullmatch(t) and t not in NONCALL and not GRID_RE.fullmatch(t)
            and any(c.isdigit() for c in t) and any(c.isalpha() for c in t))
```

**Our stream emits callsign `X` in plaintext at cycle `t`** iff some ours-decode at cycle `t`
contains `X` as a whole whitespace-delimited token **that does not begin with `<`**.

🔴 **A bracketed `<CALL>` does NOT count as a plaintext emission.** A resolved `<CALL>` render came
*out of* the table; it does not put anything *into* it (§1 fact 3 — only `unpack28` on a plaintext
callsign calls `save_hash`). Counting it would make the proxy circular.

`T_plain(X)` = the earliest cycle `ts` at which our stream emits `X` in plaintext, or `∅`.

---

## §3. ROW 0 — preconditions, strict order, every bar bounded (HK-021(p))

Evaluate in order. Stop at the scope each row names.

| row | check | hard bar | consequence |
|---|---|---|---|
| **0a** | Dump identity | `dll_sha256` == `bc8efcf1…`, `shim_version` == 20260046, `n_decodes` == 71,600, `n_theirs` == 43,423 | **VOID.** A different input is a different arm. |
| **0b** | Population reproduction against QA's own 17:56Z re-derivation | `n_theirs_only` == **18,508** AND corrected B1 count == **470**, both exactly | **VOID.** If this harness and QA's own disagree on the population, nothing below is interpretable. |
| **0c** | **Predicate-movement exhibit (HK-021(q))** | The report must paste **one** B1 key the naming rule NAMES, **one** it declines as `B1-amb`, and **one** session-wide plaintext emission of a named callsign — callsigns redacted as `"CS-" + sha256(tok)[:6]` | **VOID.** A classifier that cannot be shown to return more than one value is decorative regardless of its CI. This row exists because the last arm's gate could not move and nothing we owned caught it. |
| **0d** | **Proxy calibration.** The table holds exactly **4096** entries at `260803_202600` (§1 fact 1 + the measured freeze). Let `D` = distinct plaintext callsign-shaped tokens (§2.5) our stream emits in cycles `<= 260803_202600` | **`0.75 <= D / 4096 <= 1.25`** | **Below 0.75:** the emitted-decode proxy misses >25 % of real inserts ⇒ **Part A (§5) is VOID**; Part B (§6) proceeds and every `B1-cap` figure is reported as a **LOWER BOUND** with `D/4096` stated. **Above 1.25:** the token extractor is picking up non-callsign free-text at scale ⇒ the plaintext predicate is contaminated ⇒ **same consequence.** |
| **0e** | Determinism, mechanically diffed | Classifier run twice from `L2_run1`: result JSON **byte-identical** | **VOID.** Diffed, never asserted. |
| **0f** | Independent-input replicate | Classify from `L2_run2_decodes.json`; **bucket assignment identical key-for-key**, not merely equal in count | **VOID.** |

### 3.1 ROW 0d is the load-bearing row, and I measured it while drafting

`D` = **3,954**, `D / 4096` = **0.965** (`probe4.py`). The proxy recovers 96.5 % of a quantity
known exactly and independently. The looser variant without the digit requirement gives 0.993.
**The bar is set against a measured distribution, not a guess, and 0.965 sits comfortably inside
it** — but QA must re-measure and evaluate the row rather than inherit my number.

### 3.2 ⚠️ What ROW 0d cannot detect (HK-022)

It calibrates the proxy **at the freeze cycle only**, on the busiest, best-populated stretch of the
session. It does not certify the proxy in the frozen tail, where by construction no further inserts
happen and the calibration has nothing to compare against. State that; do not upgrade 0d into a
general claim that the proxy is validated.

### 3.3 🔴 HK-025 stands

QA may refuse any row here without my agreement. If a row cannot change a verdict, name it,
evaluate both branches, and stop — no partial run.

---

## §4. The partition — exhaustive, mutually exclusive, strict order

Applied per **B1 key**. Evaluate top to bottom; the first matching row wins.

| # | bucket | condition | meaning | lever? |
|---|---|---|---|---|
| 1 | **`B1-amb`** | No unique template-consistent candidate (§2.4) | Our co-located decode is **not the same message**. Chance co-location. | **No** — and it should never have been in B1. |
| 2 | **`B1-cov`** | Named `X`, `T_plain(X) = ∅` | We never decoded `X` in plaintext anywhere in the session. The entry could not have existed. | **No.** Collapses into bucket C. |
| 3 | **`B1-ord`** | Named `X`, `T_plain(X)` exists, `T_plain(X) >= ts` | We learnt `X` only at or after this cycle. Ordering. | **No** — causally impossible in a streaming decoder. A re-render pass is a product feature, not DSP. |
| 4 | **`B1-cap`** | Named `X`, `T_plain(X) < ts` | We had already emitted `X` in plaintext before this decode, and still rendered `<...>`. | **YES, and only here.** |

🔴 **Same-cycle emission (`T_plain(X) == ts`) falls in `B1-ord`, deliberately.** Within one
`ft8_decode_all()` call the intra-cycle unpack order is not recoverable from the dump, so a
same-cycle plaintext emission does **not** demonstrate the entry existed first. This is
conservative in the direction that *shrinks* `B1-cap`.

⇒ **Report `|B1-ord ∩ same-cycle|` separately**, so the addressable population is bracketed
two-sidedly: **`B1-cap` is the floor, `B1-cap + same-cycle` is the ceiling.** Both, always, in the
same sentence.

---

## §5. Part A (PRIMARY, GATED) — how much of B1 is addressable at all

**Unit of analysis: the named callsign.** Expected `k ≈ 47`.

Each named callsign `X` is classified by the strongest bucket any of its B1 decodes reaches, in
strict order:

1. **`CS-cov`** — `T_plain(X) = ∅`.
2. **`CS-cap`** — `T_plain(X)` exists **and** at least one B1 decode of `X` sits at a cycle strictly
   after `T_plain(X)`.
3. **`CS-ord`** — otherwise.

**Statistic:** `p_cap = |CS-cap| / k`. 95 % CI by **callsign-level** bootstrap (resample the `k`
callsigns with replacement, `n_boot = 2000`, seeded, sorted at construction).

| row | condition | consequence |
|---|---|---|
| **A0** | `k < 20` | **UNRESOLVED — insufficient units.** Report `k` and the raw bucket counts. Do not evaluate A1–A3. Propose nothing. |
| **A1** | `CI_lo(p_cap) > 0.50` | **A majority of B1's callsign population had already been learnt and still rendered `<...>`.** B1 is a real, addressable population. ⇒ Proceed to Part B, which decides *which* mechanism. |
| **A2** | `CI_hi(p_cap) < 0.20` | 🔴 **B1 is overwhelmingly coverage and ordering.** It collapses into bucket C, **no hash-table change of any size or policy can recover it, and F-001 D3 (eviction) is CLOSED as a D-001 route.** Part B is then not run — say so and stop. |
| **A3** | neither | **INDETERMINATE at this `k`.** Report the point estimate and CI, state the `k` that would be required, propose nothing. **This is a likely and honest outcome, not a failure.** |

### 5.1 Resolution, computed while drafting (HK-021(m))

At `k = 47`, a proportion's normal-approximation 95 % half-width is `1.96·sqrt(p(1−p)/47)` —
**±14.3 pp at p = 0.5**, ±11.6 pp at p = 0.2.

⇒ **A1 fires only if `p_cap` ≳ 0.64 (≈ 30 of 47). A2 fires only if `p_cap` ≲ 0.11 (≈ 5 of 47).
Anything from 6 to 29 of 47 is A3.** That indeterminate band is 49 % of the range, and I am
stating it before the run rather than discovering it after: **this arm can separate the extremes
and nothing else.** It is still worth running, because both extremes are decisive and the arm costs
minutes.

**Readout quantum (HK-021(o)):** `p_cap` moves in steps of `1/47 = 2.13 pp`, seven times finer than
the half-width. Sampling-limited, not readout-limited.

**Absence power (HK-021(j)):** A2 is an absence-shaped claim. At `k = 47`, `p = 0.11` gives an
expected count of `5.2 >= 5`. The λ ≥ 5 floor is met exactly at the bar and nowhere below it —
which is why A2's bar is 0.20 and not 0.10.

---

## §6. Part B (GATED) — capacity, or bit error? The freeze cycle settles it

Runs **only if A1 fires.** By §1 facts 1–2, an entry inserted before the table froze is resident for
the rest of the process and cannot be missed by a lookup. So every `CS-cap` callsign splits
mechanically, with no judgement:

| sub-bucket | condition | mechanism | is a table change the lever? |
|---|---|---|---|
| **`cap-frozen`** | `T_plain(X) >= 260803_202600` | The table was already full when we learnt `X`. The insert was **rejected**; the entry never existed. | 🔴 **YES** — this is precisely what eviction or more capacity would serve. |
| **`cap-resident`** | `T_plain(X) < 260803_202600` | The entry was inserted **and is still resident**. A lookup nonetheless failed. | 🛑 **NO.** The decoded hash bits differ from the stored ones. This is a **bit-error** population; no table size or eviction policy touches it. |

**Statistic:** `p_frozen = |cap-frozen| / |CS-cap|`, callsign-level bootstrap, same construction as
Part A.

| row | condition | consequence |
|---|---|---|
| **B0** | `\|CS-cap\| < 10` | **UNRESOLVED — insufficient units.** Report exact counts. Do not evaluate B1–B3. |
| **B1** | `CI_lo(p_frozen) > 0.50` | **Capacity is the binding constraint on the addressable population.** ⇒ **F-001 D3 (eviction) earns its own pre-registration** — sizing, policy, and a recall-primary gate. It is *still not authorised by this arm*; this row authorises writing the spec, nothing more. |
| **B2** | `CI_hi(p_frozen) < 0.50` | 🔴 **The addressable population is a HASH-BIT-ERROR population, not a capacity one.** The entries were there. **F-001 D3 is closed as a D-001 route** and the question moves upstream to demodulation. |
| **B3** | neither | **INDETERMINATE.** Report exact counts and CI; propose nothing. |

### 6.1 Resolution (HK-021(m))

`|CS-cap|` is unknown at drafting time. At `|CS-cap| = 20` the 95 % half-width at p = 0.5 is
**±22 pp**, so B1/B2 need `p_frozen` ≳ 0.72 or ≲ 0.28. At `|CS-cap| = 10` the half-width is
±31 pp and only a near-unanimous split reads. **B0's bar of 10 is the point below which even a
unanimous split cannot clear 0.50, which is why it is a VOID row and not a warning.**

⚠️ **The point counts are an exact enumeration of this corpus's `CS-cap` population** — the CI is
there to generalise beyond this session, not to describe it. Report both and say which is which.

---

## §7. Part C (DESCRIPTIVE — NOT GATED, NO CIs)

1. **The four-way B1 partition in decode counts**, beside the §2.3 concentration histogram, with
   `B1-amb` first. Exact counts only.
2. **The corrected, textually-corroborated B1 size** as a pp of D-001 (`n_theirs` = 43,423), stated
   as replacing neither QA's 470/1.08 pp nor the withdrawn 1.55 pp until the Architect rules.
3. **`|B1-ord ∩ same-cycle|`**, so the floor/ceiling bracket of §4 can be quoted.
4. **The dominant callsign as a named case study** (redacted `CS-xxxxxx`): its 178 decodes, its
   `T_plain`, its bucket, and its position relative to the freeze cycle. One station carries half of
   decode-weighted B1; the report should say what it did rather than average it away.
5. **Distinct plaintext callsign-shaped tokens across the whole session vs. `HASH_TABLE_SIZE`.**
   My probe reads **16,320 vs 4,096**. If QA confirms the order of magnitude, state it plainly:
   *the session presents roughly four times more distinct callsigns than the current table can
   hold, so even another 4× of capacity does not reach the end of a 20-hour session.* Descriptive,
   ungated, and **authorises nothing** — but it is the number F-001 D3's eventual spec has to start
   from.

🛑 **No stratification by frequency separation to a neighbouring decode, in any form, under any
name.** That is the retired spectral-locality metric. Refuse under HK-025 if a leg drifts there.

### 7.1 The one limitation that must be stated in the report, not buried

By §1 fact 3, the table is populated at **unpack**, before the shim's emission filter. Our emitted
stream is therefore a **subset** of what actually populated the table. Every consequence points the
same way:

- a callsign we never emitted may still have been inserted ⇒ **`B1-cov` is a CEILING**;
- `T_plain(X)` is no earlier than the true first insert ⇒ **`B1-ord` is a CEILING**, and
  **`B1-cap` is a FLOOR**;
- combined with the same-cycle convention of §4, **both conservatisms push the same direction.**

⇒ **Every `B1-cap` and `cap-frozen` figure is reported as a lower bound.** ROW 0d bounds the size
of the leak (0.965 when I measured it), it does not eliminate it.

🔴 **HK-026 check, performed and recorded:** the instrument here is our own decode stream, and the
question is about our own table. That is not an instrument bounding its own blind spot — the table
*is* populated by that stream, so the stream is the correct instrument, not a proxy for the world.
The residual gap is the emit filter, which ROW 0d measures against an externally known constant
(4,096). **If `ft8_get_hash_table_count()` were exported the gap would close entirely; it is not,
and this arm does not authorise adding it.**

---

## §8. Architect predictions — blind on both gates, on the record

I have not computed either split (§0.1).

| gate | prediction | reasoning | confidence |
|---|---|---|---|
| **A** | **A1**, `p_cap` ≈ 0.65–0.85 | The table freezes at cycle 767 of 4,971 — 83.5 % of the session runs frozen. A compound callsign is sent in full in its own transmission and hashed in the replies, so we usually see the plaintext at some point; after freeze that plaintext buys nothing. | moderate |
| **B** | **B1**, `p_frozen` ≈ 0.70–0.90 | Same argument: most first-plaintext-emissions land in the 83.5 % of the session that is post-freeze, so most addressable cases should be never-inserted rather than resident-and-missed. | moderate |
| **C** | `B1-amb` will be QA's largest surprise, not mine — I expect QA to reproduce ~28 % | already measured, **not a prediction** | — |

⚠️ **If A2 fires I am wrong twice over and the eviction question dies with it.** That is the useful
outcome to be alert for, and it is the one I am least motivated to see, which is exactly why it is
written down here first.

---

## §9. Scope

- 🛑 No capture run. No `src/` change. No `native/` change. No rebuild. No replay. No push, no
  merge, no `pre_merge_check.py` (HK-011, HK-014, HK-010, HK-006).
- 🛑 **Does not authorise F-001 D3 (eviction).** Row B1 authorises *writing a spec*; it does not
  authorise a table change, a policy, or a Developer session.
- 🛑 Does not re-open `ΔB1`, which stays uncitable. Does not touch the `140 Hz` `BASE`+`WIDE`
  Developer session, which proceeds as the Captain authorised.
- 🛑 No spectral-locality metric under any name.
- Does not subsume `OSD-FA-A`, which remains independently runnable and unchanged.
- NFR-021: counts, cycle timestamps, frequencies and `sha256[:6]`-redacted callsign tokens only.
  No message text and no real callsign in any results JSON, report, log line, or commit.

---

## §10. Reporting and stopping

1. ROW 0 first, strict order, stop at the scope each row names.
2. **Cluster counts throughout** — callsign counts where the statistic is about callsigns, decode
   counts where it is about decodes, never conflated (HK-021(i)).
3. **Never print a decode-weighted proportion with a confidence interval** (§2.3).
4. **Never quote `B1-cap` without its floor/ceiling bracket** (§4) and its lower-bound caveat
   (§7.1), in the same sentence.
5. Report `B1-amb` first in every table. It is the finding, not a footnote.
6. Disclose every correction in full, including any disagreement with §2.2/§2.3 — **where QA
   disagrees with my probe, QA is right and I am the error** (§0.1).
7. Stop at the gate. Update the board in the same edit as the result (HK-024).
