# F-001 `SUP-B` — SIZE THE UNIQUE-MATCH REMEDY BY INSTRUMENTING THE REAL TABLE

**Architect → QA.** 2026-08-30 11:49Z (`date -u`, HK-017). Branch: see Sec.9.1 — **this spec should
not stay on `qa/nbr-a-2026-08-29`.**

Supersedes: `2026-08-30-1031-architect-to-qa-spec-f001-sup-a-unique-match-suppression-sizing.md`
(as amended). **`SUP-A` is not re-run, not re-bracketed, and not rescued.** Its ROW 0b failure
stands as reported.

Ordered by the PO 2026-08-30, choosing "instrument the real table" over three cheaper routes after
the escalation below.

---

## Sec.0 — What this is, and what it authorises

🔴 **THE QUESTION IS UNCHANGED FROM `SUP-A`:** of the 12-bit-path lookups that **today display a
name**, what fraction would display `<...>` under a unique-match (suppress-if-ambiguous) rule, **in
a 1–8 h single-band session** — normal operation, not an instrument run.

🔴 **WHAT CHANGES IS THE INSTRUMENT: we stop simulating the hash table from a text proxy and count
the real one.** No `ALL.TXT` proxy, no `SimTable`, no arrival-stream reconstruction, no positive
control of the `SUP-A` kind — **because there is no simulator left to validate.**

🛑 **AUTHORISES: one `src/` + `native/` instrumentation change, counters only, and replays of
corpora already on disk.** Nothing else. Specifically it authorises **NO** enablement of the
unique-match rule itself (Sec.3.4), **NO** table resize, **NO** eviction work, **NO** capture
campaign, **NO** Route B2 work, and no build claim beyond the pinned binaries of Sec.4
(HK-021(p) — **no unique-match binary exists and this arm does not create one**).

🛑 **Does not revise `ARM 1B`'s 51.3%/37.9%, `ARM 1C`'s VOID, `ARM 1D`'s C3/D3 INDETERMINATE, the
accepted defect, GH #132/#60, or the PO's "no name beats a wrong name" ruling.**

---

## Sec.1 — Why `SUP-A` could not answer it, corrected

QA's ROW 0b result (`2026-08-30-1129-qa-to-architect-f001-sup-a-result.md`) is accepted in full: the
row failed on all three primary corpora (1.46x / 1.48x / 2.67x against `0.85–1.30`), QA correctly
refused to move the frozen bar, correctly refused to downgrade the row to a diagnostic under
HK-021(k), and correctly escalated rather than reporting one of Sec.5.5's four outcomes. **The
handling was right.**

🔴 **BUT THE DIAGNOSIS IN THAT REPORT IS PROBABLY WRONG, AND THE FAULT IS IN MY SPEC, NOT IN QA'S
RUN.** Two findings, both checked at drafting time
(`artefacts/2026-08-30-supa-escalation/`, gitignored, **not a pre-registered gate**):

**1.1 — "Early freeze" is not a special regime; it is the only regime the estate contains.**
A repo-wide scan of every `openswfz-*.log` for the first non-zero `hashTableRejectCount`
(`freeze_scan.py`): 93 logs carry the counter, **59 show a freeze, and every one lands between
cycle 20 and 117.** Nothing freezes near cycle ~800. The three `SUP-A` primaries (25 / 50 / 57) are
unremarkable members of that population. **The regime-transfer argument therefore does not explain
the failure** — there is no late-freeze regime to have transferred from.

**1.2 — `ARM 1` already had the matching calibration point, at 1.04x, and neither my spec nor the
QA report cites it.** `ARM 1`'s ROW 0b ran **two** legs, not one
(`2026-08-26-1149-…-arm1-policy-simulation.md` §2 / ROW 0b, and its result at
`2026-08-26-1223-…-arm1-result.md`):

| leg | table | measured freeze | simulated | bracket as written |
|---|---|---|---|---|
| `L2` | **4,096** | 767 | 801 (+4.4%) | `[767, 1150]` |
| `L1` | **256** | **25** | **26 (+4.0%)** | `[25, 40]` |

🔴 **The `L1` leg is a 256-slot, cycle-25 early freeze — exactly `SUP-A` ROW 0b's configuration —
and the proxy tracked it to 1.04x.** I derived `SUP-A`'s `0.85–1.30` bracket from the **4,096** leg
and applied it to a **256-slot** control, when `ARM 1`'s own 256-slot control had used a far wider
bracket (effectively `1.00x–1.60x`) whose **lower bound sat at reality, never below it** — because
the proxy's error is known to be one-sided and late. **My bracket was both too tight in the
direction that matters and loosened in the direction that cannot happen.** That is a drafting
defect in `SUP-A` Sec.2.3, mine, and it was visible in a committed document before `SUP-A` was
written (HK-018 fired on my own spec).

**1.3 — The likely real cause, stated as a hypothesis and NOT measured here.** `ARM 1` built both
of its streams from the `L*_decodes.json` **decode dumps**
(`artefacts/2026-08-25-g2a-remeasure-a/`); `SUP-A` builds its arrival stream from **`ALL.TXT` text
rows**. Same predicate chain (`is_callsign_token` → `n22_of` → `tbl.add`), **different source
artefact.** That fits QA's own directly measured gap (206 distinct vs a real 256 by cycle 50) far
better than a regime argument does. 🛑 **Unverified. It is not load-bearing for anything in this
spec, and QA must not treat it as established.**

### 1.4 — Why this kills the cheap routes, and why I am not re-bracketing

🛑 **I am NOT citing 1.2 to rescue `SUP-A`.** Two of the three primaries happen to sit inside
`ARM 1`'s 256-slot bracket. **Re-bracketing a gate after seeing where the answers landed is the
prohibited re-read, and it stays prohibited when the author of the bad bracket is me.**

That is the whole argument for this arm: **ROW 0b exists only because we simulate a table from a
proxy. Every route that keeps the simulator needs a validity bracket, and every bracket available
to us now is written with the answers in view.** The way out is to stop simulating.

For the record, the routes rejected by the PO on 2026-08-30, with the reason each failed:

| route | why not |
|---|---|
| re-derive ROW 0b's bracket for an early-freeze regime | mis-targeted (1.1) and a re-read (1.4) |
| use the exploratory `S` values one-sidedly | **empty** — the bias only licenses "too expensive", but all three readings (23.6/21.6/20.8%) sit *below* the 40% bar, in the direction the bias forbids. It cannot produce a verdict. |
| find/replay a genuinely 256-slot instrumented capture | the 256-slot build is retired; you would have to build one. Dominated by instrumenting the current table. |

---

## Sec.2 — Inputs and preconditions

### 2.1 Corpora — this is a REPLAY arm, not a capture arm

🔴 **No new capture is required or authorised.** The instrument reads the real table under replay of
audio already on disk, in a fresh process, in cycle order — which reproduces the same table
evolution the live session had (`g_session_hash_table` is process-static and never re-initialised).

**Candidate corpora — the same 1–8 h, single-band, normal-operation population `SUP-A` targeted:**

| id | band | span | role |
|---|---|---|---|
| `S-17M` | 17m | 7.73 h | primary |
| `S-80M` | 80m | 8.27 h | primary |
| `S-20M` | 20m | 11.48 h, **1–8 h prefix only** | primary |
| `L-20M` | 20m | 43.79 h | **contrast only, never a product number** |

🔴 **PRECONDITION, AND IT MAY KILL A CORPUS: replay needs archived WAVs.** QA runs
`python qa/artefact_inventory.py --check` **first** (the inventory was last scanned 2026-08-10 and
is **STALE**), and reads `qa/ARTEFACT_INVENTORY.md` before concluding anything about what exists —
this rule has been violated 4x. **A corpus without replayable audio is dropped and said so; it is
not substituted for silently, and an empty `notes` cell is itself a risk.**

⚠️ **If fewer than two bands survive, STOP and escalate rather than running.** A single-band reading
cannot be generalised: band drives a **3.3x residency spread at matched session length**
(17m 7.73 h → 3,784 residents · 80m 8.27 h → 1,143 · 20m 11.48 h → 5,736).

🛑 **POOLING ACROSS BANDS IS FORBIDDEN** (carried unchanged from `SUP-A` Sec.5). Pooling **sessions
within one band** is permitted and expected — see Sec.6.3.

### 2.2 The bar — `S_max` = 40%, CARRIED OVER, STILL FROZEN

🔴 **`S > 40%` ⇒ the unconditional unique-match rule is too expensive and must be NARROWED.
`S ≤ 40%` ⇒ affordable.** Set by the PO on 2026-08-30 **before any `S` existed**, anchored to the
measured 37.9% decode-level misresolution rate on this same path (`ARM 1B`), rounded up.

🛑 **THE BAR IS UNCHANGED AND MAY NOT BE MOVED — by anyone, in either direction, for any reason.**
Carrying it forward untouched is the conservative act; **re-deriving it now, after `SUP-A`'s
exploratory numbers have been seen, would be the violation.**

🛑 **`SUP-A`'s exploratory `S`/`D` values (23.6% / 21.6% / 20.8% / 45.2% / 33.8%) are VOID and
MAY NOT BE CITED ANYWHERE IN `SUP-B`'s reading, comparison, or prediction scoring.** They are
biased low by an unquantified amount and their only remaining use is the historical record.

### 2.3 Code facts, verified at drafting, not inherited from the board

| fact | source | value |
|---|---|---|
| table size | `ft8_shim.c:631` | `HASH_TABLE_SIZE 4096`, open-addressed, linear probe, **no eviction**, reject-when-full (`:694`) |
| lookup | `ft8_shim.c:637-655` | `sh` = 12 / **10** / 0 for 10-bit / **12-bit** / 22-bit; keyed on a 10-bit bucket; **breaks on the first EMPTY (`:649`)**; **returns the FIRST match (`:650-651`)** |
| 12-bit code space | `message.c:577` | `n12 = n22 >> 10` ⇒ **4,096 codes, PROTOCOL-FIXED**. No table size changes this. |
| **the only 12-bit lookup call site** | **`message.c:431`** | **`lookup_callsign(hash_if, FTX_CALLSIGN_HASH_12_BITS, n12, call_3)` inside `ftx_message_decode_nonstd` — ONE call site, once per decoded nonstd message.** |
| render | `message.c:594-613` | a resolved 12-bit slot and a resolved 22-bit slot render **identically** |
| precedent for a read-only counter | `ft8_shim.c:657-665`, `:1071-1084` | `g_hash_table_reject_count` + `ft8_get_hash_table_reject_count()`, surfaced at `Ft8LibInterop.cs:570`, logged per cycle at `Ft8Decoder.cs:447` |
| current shim | `ft8_shim.h:626` | `FT8_SHIM_VERSION 20260046`; managed expectation `Ft8LibInterop.cs:371` |

✅ **The single call site at `message.c:431` is what makes this arm clean:** the 12-bit path is
identified **exactly, by `hash_type`, in C** — which **retires the `nonstd` heuristic entirely.**
`SUP-A` had to infer the 12-bit population from plaintext with `ARM 1B`'s `slot()` heuristic (a
disclosed lower bound) because no artefact carries `i3`/hash-type. **The instrument does not need to
infer it. That spec gap QA filled is closed by construction, not by a better heuristic.**

---

## Sec.3 — The instrument

🛑 **QA PROPOSES THIS CHANGE AND STOPS (HK-011).** QA does not edit `src/` or `native/`. A separate
Developer session applies it (`opsx:apply`, build and tests only, **never** `pre_merge_check.py`),
and the Captain reviews the diff. Sec.9 carries the full handoff.

### 3.1 Three counters, and what each one is

Per decoded-and-**EMITTED** message whose display came through the 12-bit path:

| counter | meaning |
|---|---|
| `h12Displaying` | the message displayed a **name** via a 12-bit lookup that returned a match. **This is the denominator — the exact population in Sec.0's question.** |
| `h12Ambiguous` | of those, the probe chain held **≥ 2 entries matching the same `n12`**. **`S = h12Ambiguous / h12Displaying`.** |
| `h12Divergent` | of those, the **most-recently-announced** matching entry differs from the **first** chain match. **`D = h12Divergent / h12Displaying`** — Amendment 1's divergence ceiling, carried over. |

Lookups that return **no** match already display `<...>` today and are **outside** the population —
they are not in the denominator, and the remedy cannot change them.

### 3.2 Where the counts come from, and the two traps that would corrupt them silently

🔴 **TRAP 1 — THE LOOKUP MUST NOT CHANGE ITS ANSWER.** `hash_table_lookup` returns the **first**
match today and must **still** return the first match, byte-for-byte, after instrumentation. The
multiplicity walk continues the probe chain past the first match **only to count**, and terminates
on the same EMPTY that terminates the real scan (`:649`). **The returned `callsign` must be
unaffected.** ROW 0b (Sec.5) is the mechanical proof of this and it is the load-bearing row of this
arm.

🔴 **TRAP 2 — RECENCY MUST BE STAMPED ON ANNOUNCEMENT, NEVER ON LOOKUP.** `D` needs a per-entry
recency stamp, which the table does not have today. Add a monotonic `uint32_t` stamped **in
`hash_table_add`** — on a genuinely new insert **and on a repeat announcement of an already-known
callsign** (`ft8_shim.c:685`, the `already known — no-op` branch: a repeat announcement **is** a
re-announcement and must refresh recency). 🛑 **`hash_table_lookup` must NEVER write the stamp.**
This is the exact defect `SUP-A` Amendment 1 named in `SimTable.lookup()`'s `last_used` refresh —
in C it would contaminate **announcement** recency with **lookup** recency and inflate `D` toward
whatever was last displayed.

🔴 **TRAP 3 — THE DENOMINATOR MUST BE DISPLAYS, NOT LOOKUP CALLS (HK-022).** A decode pass may
invoke `ftx_message_decode_nonstd` for messages that are later deduplicated or discarded and never
shown to the operator. **Counting at the lookup site would make the denominator "decode attempts",
which is NOT the PO's question.** Required design: the lookup records its multiplicity and
divergence into **thread-local scratch** for the message currently being decoded; the **emission**
path — the same place that decides a decode is real and reports it — is what accumulates the three
process-global counters. **ROW 0d is the mechanical check that this actually worked.**

⚠️ **Thread-safety follows the existing precedent, deliberately:** these are best-effort diagnostic
counters, not used for any decode-affecting decision, so an occasional missed increment under
concurrent decode is acceptable rather than adding synchronisation to the hot path — the same
trade-off `g_hash_table_reject_count` documents at `ft8_shim.c:662-664`. **State it in the comment;
do not silently inherit it.**

### 3.3 Exposure

Three read-only getters mirroring `ft8_get_hash_table_reject_count()` exactly — never reset, never
touch the table, process-lifetime cumulative, zero on daemon restart. Surfaced through
`Ft8LibInterop.cs` and logged **per cycle, cumulative**, on the existing `Ft8Decoder.cs:447` line
or one beside it:

`Cycle {Time}: h12Displaying=… h12Ambiguous=… h12Divergent=… (process-lifetime cumulative).`

✅ **Per-cycle cumulative, not per-run totals, is deliberate: it gives `S` as a function of elapsed
session time**, which is the product question the PO actually asked ("what does this cost in a
normal 1–8 h session?") and which no single end-of-run number can answer.

### 3.4 🛑 What the instrument must NOT do

**MEASURE-ONLY. The unique-match rule is NOT implemented, NOT enabled, and NOT behind a flag.** The
shipped behaviour after this change is **identical** to before — same names displayed, same decodes,
same output — plus three counters. **A build that suppresses anything fails ROW 0b by
construction.**

---

## Sec.4 — The build, pre-registered before it is built (HK-021(p))

🔴 **`FT8_SHIM_VERSION` IDENTIFIES NOTHING. Pin the SHA256.**

Before any leg runs, QA writes a manifest naming, for **both** legs:

| leg | build | identity |
|---|---|---|
| `BASE` | current `main` | shim **20260046**, DLL SHA256 **`bc8efcf1…`** (the `main` pin) |
| `INST` | instrumented | shim **20260047**, DLL SHA256 **`<recorded at build time, before any replay>`** |

**Every leg asserts its DLL's SHA256 against that manifest at run time.** Never infer a binary's
identity from a version label or a `git merge-base`. The manifest is committed **before** the first
replay, and `git diff --stat` against that commit must be **empty** when the run starts — the
pre-registration hygiene `NBR-A` Amendment 2 used, which worked.

---

## Sec.5 — ROW 0: the gates, in strict order, evaluated mechanically

🔴 **HK-025 is undiminished. QA may refuse any row on HK-021(k) grounds, naming the row and its
evaluation, and stop — no partial run, no Architect agreement needed.** QA may also reject Sec.3's
design against the shipped source: **if this spec diverges from `ft8_shim.c:637-655` or
`message.c:431`, the shipped code wins and the spec is the defect.**

| row | check | predicate | consequence if it fires |
|---|---|---|---|
| **0a** | binary identity | each leg's DLL SHA256 **==** Sec.4's manifest entry | **VOID** — the run is not of the pinned build |
| **0b** | 🔴 **NON-PERTURBATION — the load-bearing row** | replay **one** pinned corpus through `BASE` and through `INST`; the emitted decode sets are **byte-identical**, proven by a **mechanical `diff` (exit 0)**, run twice by two independent means | **VOID THE ARM** — the instrument changed the thing it measures |
| **0c** | counter arithmetic | `h12Divergent ≤ h12Ambiguous ≤ h12Displaying` at every logged cycle | **VOID** — an identity cannot fail; a violation is an implementation defect |
| **0d** | denominator identification (Trap 3) | per cycle, Δ`h12Displaying` **==** the number of **emitted** decodes in that cycle whose display came through a resolved 12-bit lookup | **VOID** — the denominator is decode attempts, not displays, and `S` is not the PO's quantity |
| **0e** | determinism | the same corpus replayed twice through `INST` yields **identical** counter series, mechanically diffed | **VOID** — a non-deterministic instrument cannot be read |
| **0f** | NFR-021 | every emitted artefact scanned for callsign-shaped tokens; **counts, cycle timestamps and integers only** | **STOP** — redact before anything is committed |
| **0g** | readability *(per band, see Sec.6.3)* | `h12Displaying ≥ 100` **and** distinct contributing `n12` codes **≥ 30** | **that band is UNINFORMATIVE, reported without a verdict** — not void, not a failure |

✅ **ROW 0b needs no bracket, and that is the entire point of this arm.** It is an **identity**
(same audio, same build family, same output), not a calibration against a proxy. `SUP-A`'s ROW 0b
needed a number I had to derive and derived wrongly; this one needs `diff` to exit 0.

📌 **Deliberately NOT a gate, per HK-025's classify-then-evaluate-both-branches:** "do the counters
move?" **Zero ambiguity is a legitimate, highly decision-relevant reading — `S` = 0, the remedy is
free — not an instrument failure.** It is reported as a diagnostic, exactly as `SUP-A`'s ROW 0d was.

---

## Sec.6 — The reading

### 6.1 The statistic

**`S` = `h12Ambiguous / h12Displaying`, lookup-weighted.** That is the operator-facing quantity —
the fraction of names on screen today that would become `<...>` — and it is what the 40% bar ranges
over.

### 6.2 The interval — clustered, because lookups are not independent (HK-021(i))

🔴 **Observation ≠ independence. One ambiguous `n12` code generates many lookups**, so a
lookup-level binomial CI would be far too narrow. **Report CLUSTER counts, never row counts.**

- point estimate: **lookup-weighted `S`** (Sec.6.1)
- interval: **95% cluster bootstrap resampling distinct `n12` codes with replacement**, 10,000
  draws, **seed pinned in the harness before the run**
- always reported beside it: **`h12Displaying`, the distinct-`n12` cluster count, and per-cycle
  `S` at 1 h, 2 h, 4 h, 6 h, 8 h elapsed**

⚠️ **Sort at construction.** Any set/dict iteration feeding the bootstrap must be **sorted**, or a
pinned seed still draws different indices per process — the hash-randomisation defect already found
in `x4`/`x3`, with `p23_common.py`'s fix still uncommitted. **"Byte-identical" is proven by a
mechanical diff, never asserted.**

### 6.3 Per band, pooled across sessions within a band

Verdict is stated **per band**, never pooled across bands (Sec.2.1). Within a band, sessions are
pooled to reach ROW 0g's minimum, **and each session's own `S` is reported alongside the pooled
figure** so heterogeneity is visible rather than averaged away.

### 6.4 The verdict table — MARGINAL is evaluated FIRST and governs

| order | condition | outcome |
|---|---|---|
| 1 | the 95% CI **spans 40%** | 🔴 **`MARGINAL`** — not resolved either way. **ESCALATES to the PO. Does NOT auto-trigger the narrowed rule.** |
| 2 | CI entirely **above** 40% | **TOO EXPENSIVE** — the unconditional rule must be narrowed |
| 3 | CI entirely **below** 40% | **AFFORDABLE** — the unconditional rule is within the PO's stated tolerance |

🛑 **`MARGINAL` is a real outcome with a real consequence, not a failure, and may NOT be settled by
re-reading the point estimate against the bar.**

⚠️ **`S_max` bounds TOTAL suppression, NOT loss of CORRECT names.** That split stays deliberately
unmeasured — it needs a truth source, which is `ARM 1C`'s hazard. What makes 40% defensible is
structural: suppression targets ambiguous lookups, and ambiguity **causes** misresolution, so the
suppressed set is **enriched** for wrong names by construction. 🛑 **Enriched is not "mostly wrong",
and this spec does not claim it is.**

### 6.5 `D` — the three prohibitions travel with it every time it is quoted

1. 🛑 `D` is a ceiling on **CHANGE, never a benefit.** An unknown share of any change is in the
   **wrong** direction. It may never be called "the misresolution a recency policy would fix".
2. 🛑 `D` is **NOT** our disagreement rate with WSJT-X — different table, different structure,
   different decode stream — and may never be cited beside `ARM 1B`'s 51.3% as the same kind of
   thing.
3. 🛑 `D` **authorises no build.** No prefer-most-recent binary exists (HK-021(p)).

---

## Sec.7 — Predictions, recorded before the run, and the power disclosure (HK-021(v))

Model disclosed: `S_null = 1 − λ/(e^λ − 1)`, `λ = R/4096`, `R` = residents at end of window —
the same model `SUP-A` Sec.7 used. Real `S` should land **at or below** null, because two entries
sharing an `n12` are both **found** only if the probe chain reaches both.

| band | window | `R` | `S_null` | **my prediction** | confidence |
|---|---|---:|---:|---|---|
| 80m | 1–8 h | 1,143 | 13.3% | **8–20%** | moderate |
| 17m | 1–8 h | 3,784 | 39.2% | **25–45%** | moderate |
| 20m | 1–8 h | ~4,096 | 41.8% | **28–48%** | moderate |
| — | `D/S` vs its null | — | — | **below null**, carried from Amendment 1 | 🔴 **low, self-flagged** |

🔴 **`D/S` below null CUTS AGAINST MY OWN WSJT-X RECENCY READING of 2026-08-30. Both can hold only
if the recency prior is real but rarely binding — which is exactly what `D` measures. One of my two
positions loses whatever this run returns; both are on the record.**

### 7.1 🔴 The power disclosure, and it is uncomfortable — quoted from my own predictions above

**Two of my three predicted ranges straddle 40%.** At my own stated expectation (17m centred ~35%),
with a per-band `n` in `SUP-A`'s range (37–93 lookups, few clusters) and a clustering design effect
around 2, the 95% CI half-width is **roughly 10–14 pp** ⇒ 🔴 **`MARGINAL` is the MODAL outcome on
both busy bands, not a tail.** This is the N4 fault (a cut placed where the answer lands), disclosed
at drafting rather than discovered at ruling.

🔴 **CONSEQUENCE, AND IT SIZES THE RUN — this is why Sec.6.3 pools sessions within a band:** to
resolve 40% with a ±5 pp half-width at `p ≈ 0.35` under that design effect needs roughly
**`n ≈ 700` displaying lookups per band**, i.e. **several 1–8 h sessions per band**, not one.
🛑 **ROW 0g's minimum (100 lookups / 30 clusters) is the floor for reporting a band at all, NOT the
`n` at which a verdict is likely to resolve.** If a band reaches the floor but not resolution, the
honest outcome is `MARGINAL`, escalated — **not a verdict read off a point estimate.**

⚠️ **(v) mandates DISCLOSURE, never a veto.** This arm is worth running at whatever `n` the corpora
carry, because a `MARGINAL` with a known interval is a strictly better input than `SUP-A`'s VOID.

---

## Sec.8 — Standing prohibitions restated, because each has bitten this programme

- 🛑 **`351,533` rejects is a 256-slot-era figure** (`openswfz-20260731T200428Z.log`, pre-`9500e03`,
  2026-08-12). **Never quote it as a current-build number.**
- 🛑 **The board's `50.9%` is an AT-SATURATION, INSTRUMENT-RUN figure** and must be cited as such.
  It is **not** the product-facing cost in a 1–8 h session — establishing that is this arm's job.
- 🛑 **`SUP-A`'s exploratory `S`/`D` values are VOID** and may not be cited (Sec.2.2).
- 🛑 **No pooling across bands** (Sec.2.1).
- 🛑 **Never re-read a closed gate with a better metric — it earns a NEW pre-registration.**
- ⚠️ **`compute_matched_hit_control(cycles, limit=N)` TRUNCATES IN FILE ORDER, it does not sample.**
  Check what `limit=` does before reusing any population helper.
- ⚠️ **An uncleared `ALL.TXT` contaminates `*_matched.csv` with full `message_text`.** Grep every
  file individually before committing anything (NFR-021).

---

## Sec.9 — Process and ownership

### 9.1 Branch — flagged, not restructured (HK-014)

⚠️ **`SUP-A` was filed on `qa/nbr-a-2026-08-29`, a CLOSED `NBR-A` QA branch — I flagged that as
arguably wrong at the time and did not move it.** `SUP-B` involves `src/` and `native/`, so the
mismatch now matters. **Recommended: a fresh branch off `main`.** Moving or creating it is the
Captain's call or QA's, not mine.

### 9.2 The handoff chain

1. **QA** proposes the `src/`/`native/` diff and **STOPS** (HK-011). QA does not build it.
2. **Developer session** applies it — build and tests only, **never** `pre_merge_check.py` (HK-006:
   that runs on the Captain's initiative only).
3. **Captain** reviews the diff. Merge to `main` needs explicit sign-off; **green CI is necessary,
   never sufficient** (HK-010).
4. **QA** pins the `INST` SHA256 into Sec.4's manifest, commits it, verifies `git diff --stat` is
   empty, then replays.
5. **Architect** commits locally and stops — **never pushes, never merges, does not even ask**
   (HK-014).

⚠️ **CI runs twice per PR commit — ACCEPTED.** 🛑 **BLACKLISTED: SHA-keyed `concurrency` +
`cancel-in-progress`** — it kills the PR run so G9 never runs while CI stays green.

### 9.3 What QA owes

A report in the house form: ROW 0 table in strict order, per-band `S` with cluster counts and CIs,
the per-cycle `S` curve, `D` with its three prohibitions attached, prediction scoring against
Sec.7, and — if it applies — a plain `MARGINAL, escalated` rather than a verdict.

### 9.4 What the Architect owes

Nothing further on `SUP-B` before the result. **The `SUP-A` bracket defect (Sec.1.2) is mine and is
recorded as mine.**

---

## Cross-references

- `qa/rr-study/2026-08-30-1031-architect-to-qa-spec-f001-sup-a-unique-match-suppression-sizing.md` —
  superseded spec (as amended).
- `qa/rr-study/2026-08-30-1129-qa-to-architect-f001-sup-a-result.md` — the ROW 0b failure and
  escalation this spec answers.
- `qa/rr-study/2026-08-26-1149-architect-to-qa-spec-f001-d3-arm1-policy-simulation.md` §2 / ROW 0b —
  the **two-leg** calibration, including the 256-slot `L1` leg neither `SUP-A` nor its result cites.
- `qa/rr-study/2026-08-26-1223-qa-to-architect-f001-d3-arm1-result.md` — `L1` 26 vs measured 25.
- `qa/rr-study/2026-08-26-1352-architect-to-qa-spec-f001-d3-arm1b-twelve-bit-correctness.md` —
  origin of the `nonstd` heuristic **that this arm retires**.
- `artefacts/2026-08-30-supa-escalation/` — drafting-time scans (gitignored, **not a gate**).
