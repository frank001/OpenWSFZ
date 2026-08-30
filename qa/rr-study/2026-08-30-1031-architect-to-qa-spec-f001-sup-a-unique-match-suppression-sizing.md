# `F-001 SUP-A` — how many names does a unique-match rule remove in NORMAL operation?

**Architect → QA.** Written 2026-08-30 10:31Z (`date -u`, filename and byline agree — HK-017).

**Status: SPEC ONLY. Not authorised to run until Sec.2.4's PO bar is filled in.**
Offline re-analysis. **No capture, no rebuild, no replay, no `src/`, no `native/`, no Developer
session.** Runnable in minutes once armed.

---

## 🆕 AMENDMENT 1 — 2026-08-30 10:53Z, ordered by the Captain ("add SUP-A")

**Amended IN PLACE because this spec has never run and is not authorised.** The pre-amendment text
is preserved in git at commit **`71fb7d8`**; diff against it to see exactly what changed.

🛑 **AMENDMENT 1 ADDS ONLY. It moves no bar, changes no existing row, and narrows no population. If
any reading of it appears to loosen anything in Sec.1–Sec.9, THE ORIGINAL SPEC WINS AND THE
AMENDMENT IS THE DEFECT.**

**What it adds, and why now.** A read-for-method pass over WSJT-X's `lib/77bit/packjt77.f90`
(2026-08-30, Captain-ordered, licence-clean — read only, nothing copied or ported) established that
WSJT-X stores 12-bit hashes in a **direct-indexed** array, `calls12(0:4095)`, written as
`calls12(n12)=cw`. **Last write wins.** It has **no ambiguity detection whatsoever** — so it has *not*
solved misresolution — but its overwrite policy means a 12-bit lookup there returns the **most
recently announced** callsign for that code.

**Ours returns the OLDEST resident match on the probe chain.** The two designs resolve an identical
collision in **opposite directions**.

⇒ **A second candidate remedy exists that costs NO suppressed names: prefer the most-recently-
announced matching entry rather than the first.** It composes with unique-match rather than
replacing it.

🛑 **Its BENEFIT cannot be measured here** — that needs a truth source, which is `ARM 1C`'s hazard and
is excluded by Sec.0.2. **Its CEILING can**, from a pure table property costing one extra field on
the chain walk Sec.3 already performs. **Amendment 1 measures the ceiling and nothing else.**

Additions: **Sec.3.2** (predicate), **Sec.4 ROW 0g** (a consistency assertion), **Sec.5.6** (the
reading), **Sec.7.1** (prediction). Nothing else in this document changes.

---

## Sec.0 — Why this exists, and what it deliberately is NOT

### 0.1 The decision it serves

The PO ruled, 2026-08-30: **"no name beats a wrong name."** On the 12-bit hash path we sometimes
display a callsign that is wrong; a **unique-match rule** (display a name only when exactly one
resident table entry matches the queried 12-bit code, otherwise `<...>`) is therefore the wanted
direction.

That ruling settles the *direction*. It does not tell the PO **what it costs**, and the only figure
currently on the board — **50.9% of resolved 12-bit queries have ≥2 matching entries** — was measured
on a **saturated 4,096-entry table**, i.e. a long unattended capture.

🔴 **Normal operation is 1–8 h single-band sessions** (PO, 2026-08-30). The long runs are **QA
instrument runs**, not product usage. **So 50.9% is not the product-facing cost, and must stop being
quoted as one.** This arm measures the product-facing number.

### 0.2 What this arm is NOT — and this is the scoping decision that keeps it cheap

🛑 **It does NOT measure whether a suppressed name would have been RIGHT or WRONG.**

That is deliberate, and it is what keeps this arm clear of `ARM 1C`'s hazard. ARM 1C crossed a **real
outcome** (agree/disagree against the WSJT-X reference) with a **simulated stratifier** (multiplicity
from a replayed table) and **VOIDed on ROW 0d fidelity**. HK-021(w)-amended additionally forbids
handling the unverifiable units with a **filter**.

**This arm has no outcome variable at all.** Multiplicity is a pure property of the table state and
the query stream, computable without any reference decoder. There is nothing for a fidelity defect to
corrupt into a spurious contrast.

⚠️ **If the PO later wants the right/wrong split of the suppressed population, it earns its OWN
pre-registration.** It may not be bolted onto this arm, and this arm's output may not be read as
implying it.

### 0.3 Disclosure — what I computed while drafting (HK-018 pass, and a partial de-blinding)

**Measured while drafting (EXPOSURE ONLY, the outcome deliberately NOT computed — the `ARM 1C`
convention):** per-session distinct-callsign residency, via
`artefacts/2026-08-30-hashtable-horizon/saturation_horizon.py` (gitignored).

| corpus | band | span | distinct callsigns | reaches 4,096? |
|---|---|---|---|---|
| `20260808_live_run_1154-8080-17m` | 17m | 7.73 h | **3,784** | no |
| `20260809_live_run_0155-8080-80m` | 80m | 8.27 h | **1,143** | no |
| `20260808_live_run_0016-8080` | 20m | 11.48 h | **5,736** | yes, at 7.82 h |
| `20260731_live_run_2004-8080` | 20m | 43.79 h | **17,075** | yes, at 7.08 h |

🔴 **Band dominates: 3.3× between 80m and 17m at the same session length.** ⇒ **Sec.5 forbids pooling
across bands.**

⚠️ **I have NOT computed any multiplicity or suppression figure.** What I *have* done is state a
model-based expectation in Sec.7, which is a **prediction from an arithmetic model, not a
measurement**. Prediction scoring stands.

### 0.4 Source facts, read from the tree, not inherited from the board

All verified 2026-08-30 against the working tree:

- `#define HASH_TABLE_SIZE 4096` — `src/OpenWSFZ.Ft8/Native/ft8_shim.c:631`. Open-addressed, linear
  probe, **no eviction**, reject-when-full (`:694`).
- **The 12-bit code space is protocol-fixed:** `n12 = n22 >> 10` —
  `native/ft8_lib_vendor/ft8/message.c:577`. **4,096 codes. No table size changes this.**
- **The 12-bit lookup path:** `message.c:431` (`decode_nonstd` ⇒ `FTX_CALLSIGN_HASH_12_BITS`).
  The 22-bit path is `:782` (`unpack28`). These are the only two call sites.
- **`hash_table_lookup` (`ft8_shim.c:637-655`) returns the FIRST match on the probe chain and never
  checks for a second** — this is the misresolution mechanism, and the unique-match rule is precisely
  the change of "first" to "exactly one".
- **The 10-bit bucket is shared across hash types.** An entry is stored at
  `h10 = (n22 >> 12) & 0x3FF` (`:669`); a 12-bit query computes
  `h10 = (n12 >> 2) & 0x3FF ≡ (n22 >> 12) & 0x3FF` (`:643`). **Identical** ⇒ every entry sharing a
  12-bit code starts on the **same probe chain**. ROW 0c checks this rather than assuming it.
- **56.7% of resolved hashed callsigns come out of the 12-bit path** (1,899 vs 1,448 on 22-bit) —
  the majority population, and the one `ARM 1` was blind to.

🛑 **HK-021(p): this arm measures a RELABELLING of an existing build's data. No unique-match binary
exists. No row and no report line may say "the fixed build would…".**

---

## Sec.1 — The question, and the population it ranges over

> **Of the 12-bit-path lookups that TODAY display a callsign, what fraction would display `<...>`
> instead under a unique-match rule — in a 1–8 h single-band session?**

**Population (HK-021(x) — scoped to exactly what the claim ranges over):** 12-bit-path lookups that
**currently return a name**. Explicitly **excluded**: 22-bit-path lookups (different mechanism), and
12-bit lookups that already return nothing (unique-match cannot make those worse).

🔴 **HK-021(x) drafting question, answered: "name a unit that trips this gate and does not contradict
the claim."** A 22-bit lookup with a multiplicity-≥2 *12-bit* code would trip a naively-scoped
predicate while being entirely consistent with the claim, because the 22-bit path compares the full
hash and is unaffected. **That unit is why the population is restricted to `decode_nonstd`-path
lookups.** QA must confirm the implementation cannot admit it.

### 1.1 HK-021(t) — is the population selected on the treatment's target outcome?

**Yes, and I have checked the complement rather than waving at it.** The population is "lookups that
display a name", and the treatment removes displays. The complement is "lookups displaying nothing".

**Unique-match is strictly more restrictive than first-match: it can only ever turn a display into a
non-display, never the reverse.** ⇒ the complement **cannot be harmed by construction**, so there is
no cost hiding outside the gated population. **(t) does not bite here** — but the argument, not the
conclusion, is what QA should check.

---

## Sec.2 — Corpora, pins, and the one blocking input

### 2.1 Corpora (primary — the 1–8 h regime)

| id | path (under `artefacts/`) | band | span |
|---|---|---|---|
| `S-17M` | `20260808_live_run_1154-8080-17m/owsfz/ALL.TXT` | 17m | 7.73 h |
| `S-80M` | `20260809_live_run_0155-8080-80m/owsfz/ALL.TXT` | 80m | 8.27 h |
| `S-20M` | `20260808_live_run_0016-8080/owsfz/ALL.TXT` | 20m | 11.48 h |

### 2.2 Corpus (contrast — the figure the product must NOT use)

| id | path | band | span |
|---|---|---|---|
| `L-20M` | `20260731_live_run_2004-8080/owsfz/ALL.TXT` | 20m | 43.79 h |

⚠️ **`S-20M` runs to 11.48 h and saturates at 7.82 h.** It is included **because** it straddles the
horizon — it is the only corpus that shows the transition inside one session. Report its 1–8 h
prefix as primary and its full span as secondary; **do not let the saturated tail contaminate the
headline.**

⚠️ **`S-80M`: WSJT-X's leg ends early (`260809_072815`) and the deep tail has no reference.**
**Irrelevant here** — this arm uses no reference. Stated so it is not re-derived as a blocker.

⚠️ **`qa/ARTEFACT_INVENTORY.md` was last scanned 2026-08-10 and is STALE.** Run
`python qa/artefact_inventory.py --check` first; regenerate if it fails. Do not take the table above
on my word — it is transcribed from a stale inventory plus my own reads.

### 2.3 🔴 The pre-resize question, named and bounded

**All four corpora predate the `256 → 4096` resize** (`9500e03`, 2026-08-12). The real decoder that
produced them ran a **256-slot** table.

**Named assumption:** the callsign **arrival stream** is table-size-independent. Basis — the standing
prohibition *"hash-table saturation does NOT discard decodes — it costs message TEXT only"*: a
saturated table changes the rendering of hashed tokens, not which messages decode, and plaintext
callsigns (the arrival stream) are unaffected either way.

🛑 **This assumption is not taken on trust — ROW 0b tests it against the real instrument** (Sec.4).

### 2.4 🔴 BLOCKING INPUT — the PO's bar, to be filled in BEFORE the run

Per the programme's own precedent (`DEFECT-decode-panel-perceived-latency`: *"pre-commit the
acceptable number with the Product Owner BEFORE measuring"*), the acceptability bar is the PO's, not
mine, and it must be recorded here before QA arms the run:

> **Maximum acceptable suppression rate in normal (1–8 h) operation: `____ %`.**
> Above this, the unique-match remedy is too expensive to ship as an unconditional rule and must be
> narrowed (e.g. applied only where an unsolicited Tx could result).

🛑 **QA must not run this arm with that blank unfilled.** A number chosen after seeing the result is
not a bar.

---

## Sec.3 — The predicate, shipped as code (HK-021(r))

**The prose below is a gloss on this code, not the other way round.**

`SimTable` already exists at `qa/rr-study/f001-d3-arm1/common_arm1.py:119` and is a faithful
transcription of `hash_table_add`/`hash_table_lookup`. **Reuse it. Do not re-implement it.** Its
`lookup()` is 22-bit-only (`sh=0`); this arm adds the 12-bit form:

```python
def lookup12_multiplicity(tbl, n12: int):
    """ft8_shim.c:637-655 with hash_type == FTX_CALLSIGN_HASH_12_BITS (sh = 10).

    Returns (first_callsign_or_None, n_matches_on_chain).

    first_callsign  -- what the SHIPPED build displays today (first match wins).
    n_matches       -- how many resident entries on the SAME probe chain also
                       match the 12-bit code. Under a unique-match rule the
                       name is displayed iff n_matches == 1.

    Chain semantics are the shipped ones and are load-bearing: the scan BREAKS
    at the first EMPTY (ft8_shim.c:649); TOMBSTONE and non-matching OCCUPIED
    slots do NOT stop it. Matches beyond the first EMPTY are UNREACHABLE to the
    real decoder and MUST NOT be counted -- ROW 0c verifies none exist.
    """
    sh = 10
    h10 = (n12 >> (12 - sh)) & 0x3FF          # == (n22 >> 12) & 0x3FF, Sec.0.4
    idx = (h10 * 23) % tbl.n
    first, n_matches = None, 0
    for _ in range(tbl.n):
        st = tbl.state[idx]
        if st == EMPTY:
            break
        if st == OCCUPIED and ((tbl.hash[idx] & 0x3FFFFF) >> sh) == n12:
            n_matches += 1
            if first is None:
                first = tbl.callsign[idx]
        idx = (idx + 1) % tbl.n
    return first, n_matches


def suppressed(first, n_matches) -> bool:
    """The unique-match rule. A lookup that displays nothing today is NOT in
    the population at all (Sec.1) and must be filtered out BEFORE this call."""
    assert first is not None, "caller must exclude non-displaying lookups"
    return n_matches >= 2
```

**The primary statistic, per session:**

```
S = |{ 12-bit displaying lookups with n_matches >= 2 }|
    -----------------------------------------------------
    |{ 12-bit displaying lookups                       }|
```

### 3.1 The arrival-stream extractor, and its honest limitation

The simulator must be fed the ordered `(cycle, callsign)` stream that `save_callsign` would have
seen. QA reconstructs it from `ALL.TXT` plaintext callsign tokens in cycle order (`ALL.TXT` fields
are 0-based: `[0]` ts, `[4]` SNR, `[5]` DT, `[6]` freq Hz, `[7:]` message).

⚠️ **This is a PROXY.** It cannot see callsigns the real decoder packed but never rendered as a
plain token, and it may include tokens `save_callsign` never received. **ROW 0b is what bounds the
gap; nothing else in this spec does.**

⚠️ **Sort every set at construction** before any seeded or ordered use — hash-randomised set
iteration is a standing defect in this programme and it has already broken seeded determinism once.

### 3.2 🆕 (Amendment 1) The divergence predicate — first-match vs most-recent-match

**Replaces the Sec.3 chain walk with a strictly wider one. Same walk, one extra field. `first` and
`n_matches` are computed identically — if they change at all, that is a defect.**

```python
def lookup12_multiplicity(tbl, n12: int):
    """ft8_shim.c:637-655 at sh = 10, plus Amendment 1's recency field.

    Returns (first_callsign_or_None, n_matches, most_recent_callsign_or_None).

    first         -- what the SHIPPED build displays today (first match wins).
    n_matches     -- resident entries on the SAME chain matching the 12-bit code.
    most_recent   -- of those matches, the one with the HIGHEST last_used, i.e.
                     the most recently ANNOUNCED. This is the analogue of
                     WSJT-X's calls12(n12)=cw overwrite, which executes on every
                     announcement.

    Ties on last_used are broken toward the EARLIER chain position, so that
    most_recent == first whenever recency cannot distinguish them. That makes
    the divergence count CONSERVATIVE (it can only under-report D, never
    inflate it).
    """
    sh = 10
    h10 = (n12 >> (12 - sh)) & 0x3FF
    idx = (h10 * 23) % tbl.n
    first, n_matches = None, 0
    best_idx, best_used = None, None
    for _ in range(tbl.n):
        st = tbl.state[idx]
        if st == EMPTY:
            break
        if st == OCCUPIED and ((tbl.hash[idx] & 0x3FFFFF) >> sh) == n12:
            n_matches += 1
            if first is None:
                first = tbl.callsign[idx]
            if best_used is None or tbl.last_used[idx] > best_used:
                best_used, best_idx = tbl.last_used[idx], idx
        idx = (idx + 1) % tbl.n
    most_recent = tbl.callsign[best_idx] if best_idx is not None else None
    return first, n_matches, most_recent


def diverges(first, n_matches, most_recent) -> bool:
    """True iff a prefer-most-recent policy would display a DIFFERENT name."""
    assert first is not None, "caller must exclude non-displaying lookups"
    return most_recent != first
```

🔴 **IMPLEMENTATION TRAP, and it will silently corrupt the result if missed: `SimTable.lookup()`
(the 22-bit form, `common_arm1.py:136-151`) REFRESHES `last_used` on every hit.** That is `ARM 1`'s
disclosed "favourable form" and it is fine there — **here it would contaminate `last_used` with
LOOKUP recency when the metric requires ANNOUNCEMENT recency.**

⇒ **Either do not call the 22-bit `lookup()` on the same `SimTable` instance, or use a
non-refreshing copy of it.** `lookup12_multiplicity` above deliberately does **not** refresh.
`SimTable.add()` **must** keep refreshing — that is exactly the announcement recency being measured.

⚠️ **Chain order and insertion order:** entries sharing a 12-bit code necessarily share `h10`
(Sec.0.4), start at the same index, and take the first free slot scanning forward with no deletion
⇒ **within one code, chain position IS insertion order.** ROW 0g asserts a consequence of this
rather than trusting it.

**Evaluate in strict order. Stop at the first fire. Every row is mutually exclusive by construction.**

| row | check | class | both-branch | verdict |
|---|---|---|---|---|
| 0a | corpus identity | VALIDITY | n/a | ✅ gate |
| 0b | simulator positive control | VALIDITY | n/a | ✅ gate |
| 0c | chain reachability | VALIDITY | n/a | ✅ gate |
| 0d | predicate movement | **PRECISION** | **differs** | 🛑 **DIAGNOSTIC — REPORT, DO NOT GATE** |
| 0e | determinism | VALIDITY | n/a | ✅ gate |
| 0f | NFR-021 | compliance | n/a | ✅ gate |
| 0g 🆕 | `D ≤ S` consistency | VALIDITY | n/a | ✅ gate |

### ROW 0a — corpus identity — VALIDITY

Assert each corpus's decode-row count and first/last `ts` against Sec.2.1/2.2. Any mismatch ⇒
**VOID that corpus** (others unaffected). *Rationale: if the file is not the session named, every
figure describes a different session.*

### ROW 0b — 🔴 SIMULATOR POSITIVE CONTROL — VALIDITY — the load-bearing row

**This is the only row that tests the Sec.2.3 assumption, and it is the reason this arm can use
pre-resize corpora at all.**

Run `SimTable(size=256, policy=None)` over the corpus's own arrival stream and compare the
**simulated freeze cycle** (first cycle at which `count == 256`) against the **observed** freeze
cycle — the first cycle in that session's `openswfz-*.log` at which `hashTableRejectCount > 0`.

**Observed anchors, read from the logs 2026-08-30 (final cumulative values, for orientation):**

| corpus | log | cycles | final `hashTableRejectCount` |
|---|---|---|---|
| `S-20M` | `openswfz-20260808T001605Z.log` | 2,728 | 72,012 |
| `S-17M` | `openswfz-20260808T115445Z.log` | 1,856 | 40,214 |
| `S-80M` | not located under the expected name — **QA to locate; if absent, `S-80M` runs WITHOUT a positive control and must be reported as such** |

🛑 **Gate on the FREEZE CYCLE, not on `reject_count`.** `reject_count` is dominated by *repeat*
announcements of non-resident callsigns, which a text proxy reproduces poorly; the freeze cycle
depends only on *distinct* arrivals and is the statistic `ARM 1` validated on.

**Bar, hard:** `0.85 ≤ simulated_freeze_cycle / observed_freeze_cycle ≤ 1.30`. Outside ⇒ **VOID that
corpus.**

**Derivation of the bracket, not a choice:** `ARM 1`'s ROW 0b simulated a freeze at cycle **801**
against an independently measured real **767** — **+4.4%**, and *later* than reality, because a text
proxy sees fewer distinct callsigns than the packer does. The bracket admits ~7× that discrepancy on
the late side and a smaller allowance early. **Expected side: simulated ≥ observed.** A simulated
freeze *earlier* than observed means the proxy is inventing arrivals and is the more alarming
direction — which is why the low edge is tighter.

### ROW 0c — chain reachability — VALIDITY

For every 12-bit code with ≥2 resident entries, assert **all** such entries are reachable before the
first EMPTY from the chain's start index. Any unreachable entry ⇒ **VOID**: `n_matches` would
over-count what the real lookup can see, and the direction of the error is not bounded.

*Expected to hold universally under fill-and-freeze (no deletion ⇒ same-`h10` entries occupy a
contiguous run). It is checked rather than assumed because the whole statistic rests on it.*

### ROW 0d — predicate movement — 🛑 DIAGNOSTIC, NOT A GATE

Exhibit one lookup with `n_matches >= 2` (moves) and one with `n_matches == 1` (does not).

🔴 **HK-025 applied to my own draft, and it changed the row's status.** HK-021(q) would normally make
this a gate. But evaluating **both branches**: if *nothing* moves, the correct reading is
**"suppression = 0%, the remedy is free"** — a legitimate and highly decision-relevant answer, not an
instrument failure. **A precondition that cannot change the verdict is a DIAGNOSTIC (HK-021(k)).**
⇒ **Report the exhibits; never void on them.**

### ROW 0e — determinism — VALIDITY

Re-run **out of process** under two different `PYTHONHASHSEED` values; `result.json` byte-identical,
**mechanically diffed** (script *and* an independent `diff`, exit 0). Not byte-identical ⇒ **VOID.**

### ROW 0f — NFR-021 — compliance

Zero callsign-shaped tokens in any committed artefact. **Counts only, never callsigns.** Scan every
file individually before committing. Non-zero ⇒ **do not commit; escalate.**

### ROW 0g 🆕 (Amendment 1) — `D ≤ S` consistency — VALIDITY

**Assert, per session: `D ≤ S`, and every lookup counted in `D` has `n_matches ≥ 2`.**

This is not a finding, it is an **arithmetic identity**: divergence requires at least two matching
entries, so a diverging lookup is necessarily a suppressed one. **Violation is an implementation
defect in the chain walk — most likely `last_used` contaminated by the 22-bit `lookup()` refresh
(Sec.3.2's trap), or `first` not being taken from the earliest chain position. ⇒ VOID that session;
do not report `D` or `S` for it.**

*This row also indirectly tests the Sec.3.2 claim that chain position equals insertion order: if it
did not hold, `first` would not be the earliest-inserted entry and the identity could still pass —
so ROW 0g is necessary but NOT sufficient for that claim, and the claim is not otherwise gated.
Stated so nobody reads a 0g PASS as confirming it.*

---

## Sec.5 — Readings, pre-registered

### 5.1 Primary — per session, NEVER pooled

Report `S` for each of `S-17M`, `S-80M`, `S-20M`(1–8 h prefix), each with:

- numerator and denominator as **counts**;
- a **callsign-clustered bootstrap 95% CI** (2,000 draws, seed `20260830`, sets sorted at
  construction). 🛑 **Never a binomial SE** — a station is referenced many times, so the unit of
  observation is not the unit of independence (HK-021(i));
- **distinct 12-bit codes** and **distinct callsigns** exercised, beside the lookup count.

🛑 **Do not pool across bands.** Sec.0.3 measured a 3.3× residency spread between 80m and 17m at
matched session length; a pooled mean would describe no session that exists.

### 5.2 The base rate, in the same sentence (HK-021(u))

Beside every `S`, report residency `R` (entries resident at session end) and the **uniform-collision
expectation**:

```
lambda = R / 4096
S_null = 1 - lambda / (exp(lambda) - 1)      # P(>=2 entries | >=1), Poisson
```

🔴 **`S` is only informative to the extent it departs from `S_null`.** If `S ≈ S_null`, the finding
is *"suppression is the arithmetic of 4,096 codes and nothing more"* — which is still the number the
PO needs, but it is **not** evidence of any structure and must not be reported as such.

### 5.3 Secondary — the within-session curve

`S` evaluated at elapsed `t ∈ {1, 2, 4, 6, 8}` h within each session.

⚠️ **These are NESTED PREFIXES of one session, not independent samples.** Report as a trajectory;
**no CI across `t`**, no trend test, no slope. The `t = 8` point for `S-17M`/`S-80M` is the same data
as 5.1 and must not be double-counted as corroboration.

### 5.4 Contrast — the figure the product must not use

`S` on `L-20M` (43.79 h, saturated). **Reported explicitly as the instrument-run figure**, alongside
the board's existing 50.9%, so the gap between the capture regime and the product regime is on the
record in one place.

### 5.5 The consequence, pre-registered against the PO's Sec.2.4 bar

- **All three primary `S` below the bar** ⇒ the unconditional unique-match rule is affordable in
  normal operation. **This authorises a pre-registered Developer arm to be DRAFTED — nothing more.**
- **Any primary `S` above the bar** ⇒ the unconditional rule is too expensive; the remedy must be
  narrowed (e.g. to the unsolicited-Tx case, which is where `R5`'s G3-2 measured a 73.1% wrong rate).
  **No narrowing is designed here** — it earns its own spec.
- **Split verdict across bands** ⇒ report as such and **escalate**; do not average it away.

### 5.6 🆕 (Amendment 1) — the divergence ceiling `D`

```
D = |{ 12-bit displaying lookups where most_recent != first }|
    ---------------------------------------------------------
    |{ 12-bit displaying lookups                            }|
```

Report `D` **per session**, beside `S`, with the same callsign-clustered CI and the same
no-pooling rule. Also report the **conditional** form `D / S` — of the ambiguous lookups, the share
where recency actually disagrees with insertion order. That is the informative quantity; `D` alone
is bounded by `S` and will track it.

**Base rate, in the same sentence (HK-021(u)).** If announcement recency were independent of
insertion order, then among lookups with `m` matches the earliest-inserted entry is most-recently-
announced with probability `1/m`, giving

```
D_null = sum over displaying lookups of (1 - 1/n_matches) / (count of displaying lookups)
```

🔴 **`D / S` compared against its null is the whole reading.** `D` ≈ `D_null` ⇒ recency and insertion
order are unrelated, and a prefer-most-recent policy is a coin-flip relabelling. `D` ≪ `D_null` ⇒ the
oldest resident entry usually IS the most recently active station (long-lived regulars), and
**prefer-most-recent buys little.** `D` ≫ `D_null` is not expected and would need explaining before
being believed.

### 5.6.1 🛑 What `D` is NOT — three prohibitions, all binding

1. 🛑 **`D` is a CEILING ON CHANGE, never a benefit.** It counts lookups where the displayed name
   would *differ*, not where it would *improve*. **An unknown share of any change is in the wrong
   direction.** `D` may never be reported as "the misresolution rate a recency policy would fix",
   in any document, summary, or issue comment.
2. 🛑 **`D` is NOT our disagreement rate with WSJT-X.** It is computed on OUR table, from OUR decode
   stream. WSJT-X's `calls12` is direct-indexed, differently sized, and populated from a different
   (larger) decode stream. **Do not use `D` to predict agreement with WSJT-X, and do not cite it
   alongside `ARM 1B`'s 51.3% as though the two measured the same thing.**
3. 🛑 **`D` authorises no build.** HK-021(p) is unchanged: no prefer-most-recent binary exists either.

### 5.6.2 Consequence, pre-registered

- **`D` small (and `D/S` at or below its null)** ⇒ the prefer-most-recent option is **near-dead**;
  it can barely move a name. **Record it as closed on a number and stop** — this is the cheap
  outcome and it is the point of running it.
- **`D` material** ⇒ the option is **LIVE but UNMEASURED**. It then earns its own pre-registration
  with a truth source and a two-sided gate (a recency policy can make things WORSE), **which is a
  different and more expensive arm than this one.** Do not design it here.

---

## Sec.6 — What this authorises

🛑 **Nothing beyond the measurement.** No `src/` change, no `native/` change, no Developer session,
no capture, no rebuild, no build claim (HK-021(p) — **no unique-match binary exists**), no re-opening
of any closed family. **Eviction stays de-scoped** and this arm does not bear on it.

⚠️ **It does not revise** `ARM 1B` (51.3% / A1), `ARM 1C`'s VOID, `ARM 1D`'s C3+D3, the accepted
defect, or GH #132 / #60.

---

## Sec.7 — Predictions (HK-021(v)), and my calibration

**My running tally, so the reader discounts appropriately: categorical ROW calls ~6/11; range calls
better than categorical; both range misses were too PESSIMISTIC about how cleanly effects separate.**

**Model disclosed, because a prediction from an undisclosed model is not scoreable.** Using
`S_null = 1 - λ/(e^λ - 1)` with the Sec.0.3 residencies:

| corpus | `R` | `λ` | `S_null` | my prediction for `S` |
|---|---|---|---|---|
| `S-80M` | 1,143 | 0.279 | **13.3%** | 10–20% |
| `S-17M` | 3,784 | 0.924 | **39.2%** | 33–48% |
| `S-20M` (1–8 h) | ~4,096 | 1.000 | **41.8%** | 36–52% |
| `L-20M` (contrast) | saturated | — | — | 48–58% (board: 50.9%) |

**Categorical call: `S-80M` lands below the midpoint of any plausible PO bar and `S-17M` does not.**
Confidence **moderate**. 🔴 **The honest headline of this prediction is uncomfortable and I am
stating it before the run: on a busy band a 7–8 h session is already at ~90% table occupancy, so
"normal operation" does NOT automatically mean "cheap suppression". My earlier claim to the PO that
the cost is "lower than 50.9%" is true but may be much less reassuring than it sounded.**

### 7.1 🆕 (Amendment 1) — prediction for `D`

**I predict `D / S` lands BELOW its null — i.e. prefer-most-recent buys less than the arithmetic
would suggest. Confidence: LOW, and I am flagging it as low.**

**Reasoning, so it is scoreable:** an FT8 band is dominated by a persistent core of stations that
call repeatedly for hours. Where two callsigns share a 12-bit code, the earlier-inserted one is
disproportionately likely to be one of those regulars and therefore *also* recently announced ⇒
`first` and `most_recent` coincide more often than chance. **If that is right, the recency prior I
inferred from WSJT-X's structure is real but small, and the option dies cheaply.**

🔴 **The honest counterweight, recorded before the run: this reasoning cuts against the conclusion I
drew an hour ago from WSJT-X's design.** I argued its overwrite policy encodes a useful recency
prior; here I predict recency rarely differs from insertion order. **Both can be true only if the
prior is real but rarely binding — which is precisely what `D` measures.** If `D` comes back large,
my Sec.7.1 reasoning is wrong and the WSJT-X reading is stronger than I credited. **Either way one of
my two positions loses, and that is the point of writing both down.**

**Power (HK-021(v)):** this is a **sizing measurement, not a threshold gate** — there is no
hypothesis to be underpowered against. With thousands of lookups per session the clustered CI on `S`
should be a few points wide, which is ample against a bar stated to the nearest 5%. **If the CI on
any primary `S` exceeds ±10 pp, say so and report that corpus as underpowered rather than reading
it.**

---

## Sec.8 — Reporting and citation limits

- Report per HK-001's section standard; filename and byline from real `date -u`, in agreement
  (HK-017).
- **Every `S` travels with its session length, its band, and its residency `R`.** An `S` quoted bare
  is meaningless — it is a function of residency, and residency is a function of band × time.
- 🛑 **`S` may never be quoted as "the suppression rate".** It is *"the suppression rate for a
  <band>, <n>-hour session at residency R"*.
- 🛑 **Nothing in this arm licenses a statement about how often suppression removes a WRONG name.**
  That quantity is not measured here (Sec.0.2).
- 🛑 **The `L-20M` figure may never be quoted as a product cost**, and the existing **50.9%** must
  from now on be cited as *"at saturation, i.e. an instrument-run figure"*.
- 🆕 🛑 **`D` (Amendment 1) travels with all three prohibitions in Sec.5.6.1, every time it is
  quoted: it is a ceiling on CHANGE not on benefit; it is NOT our disagreement rate with WSJT-X; and
  it authorises no build.** A bare `D` in a summary is a misquotation of this spec.
- Commit harness, `result.json` and run log together; nothing pushed (HK-014 binds me, not QA;
  follow the branch's standing convention).

---

## Sec.9 — HK-025 notice

**QA may refuse any row of this spec on HK-021(k) grounds, without my agreement and without
escalating to the Captain.** I have run the two-step check on every ROW 0 above and it **changed one
row** — ROW 0d is published as a DIAGNOSTIC precisely because both branches yield a reading. If QA's
own pass reaches a different classification on any row, **the refusal is final for this draft** and I
re-draft.

**QA is also free to reject the Sec.3 predicate as drafted.** It is my transcription of
`ft8_shim.c:637-655` at `sh=10`; if it diverges from the shipped code in any respect, **the shipped
code wins and the spec is the defect.**
