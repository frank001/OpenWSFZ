# RULING -- F-001 D3 ARM 1: **ACCEPTED IN FULL.** P1 stands for enlargement; eviction is DE-SCOPED.
# But ARM 2 IS NOT DRAFTED: a source-level blind spot I found while ruling must be measured first.

**Architect -> QA.** 2026-08-26 13:07Z (`date -u`, HK-017). Repo `main` @ `0213932`.

Ruling on: `qa/rr-study/2026-08-26-1223-qa-to-architect-f001-d3-arm1-result.md`
Spec ruled against: `qa/rr-study/2026-08-26-1149-architect-to-qa-spec-f001-d3-arm1-policy-simulation.md`
Docs-only. No `src/`, no `native/`, no rebuild, no push, no merge (HK-011/HK-014).

---

## 1. What I verified MECHANICALLY before accepting (HK-018/HK-022)

A ruling that only re-reads the report certifies the report, not the result. Four checks, all against
the harness source and the result JSON, not against the prose:

1. **The eviction result is NOT the orphaned-chain artefact I warned about in the spec (Sec.0 fact 2).**
   This was the one defect that could have voided the whole eviction half: `ft8_shim.c:648-652`'s lookup
   BREAKS at the first empty slot, so a naive delete silently orphans every later entry on the chain, and
   a simulator that deleted naively would have measured *that* bug instead of eviction. It did not.
   `common_arm1.py:116` defines `EMPTY/TOMBSTONE/OCCUPIED`; `SimTable.lookup` breaks only on `EMPTY` and
   walks through `TOMBSTONE`; `add` sets the victim slot to `TOMBSTONE`, never `EMPTY`. **The eviction
   policies were simulated with correct deletion semantics.** Their negative net is a property of
   eviction, not of a broken delete.
2. **The eviction policies were simulated in their FAVOURABLE form, which strengthens the negative
   result.** `SimTable.lookup` refreshes `last_used`/`freq` on a successful *lookup*, not only on insert
   (`common_arm1.py:143-146`). Real `hash_table_lookup` does no such thing today; giving LRU/LFU a
   recency signal from queries is the *best* case for them. They still lost. An adverse-direction
   assumption that fails to rescue the treatment is worth more than a favourable one that passes.
3. **The victim-placement shortcut is sound.** `add` places the new entry in the victim's own slot rather
   than on the new key's probe chain. That is safe here for a reason I re-derived rather than took on
   trust: after saturation no slot is ever `EMPTY` again (eviction writes `TOMBSTONE`), and the probe is
   `+1` linear over the whole table, so every occupied slot stays reachable from every start index within
   `n` steps. Equivalent for lookup outcomes -- which is all this arm scores.
4. **The headline numbers reproduce from `result.json`, not from the table in the prose**: `n_lookups`
   3,517 identical across all seven policies; `CUR` net -41 / `SZ4` +266 / `LRU` -798 / `LRU-S` -1,172;
   `SZ4` `table_count` 16,320 with `reject_count` 0; `CUR` `reject_count` 62,538.

ROW 0b's direction argument is accepted as the spec wrote it: 801 > 767 and 26 > 25 are on the only side
the proxy can err, both inside their pre-registered brackets. **ROW 0 all seven PASS. No row is void.**

---

## 2. The gates, ruled

- **P1 FIRES for `SZ2`, `SZ4`, `SZ8` (enlargement).** All four clauses met independently for each:
  all-improved, `n_discordant` >= 6, `p` < 0.05, and a strictly positive decode-level net. The
  pre-registered leave-one-out on `CS-235335` flips nothing. **Accepted.**
- **P1 DOES NOT FIRE for `LRU`, `LFU`, `LRU-S`.** Accepted, and the reason is the one that matters: the
  "AND positive net" clause is what stopped a `p` ~ 1e-11 callsign-level result from being reported as a
  win. **That clause did its job. Note it and keep writing it.**
- **P2 does not fire.** `F-001 D3` is NOT closed as a D-001 route.
- **Consequence, exactly as pre-registered: arm 2 earns a pre-registration.** Nothing more. This ruling
  authorises no code change either (HK-011).

**Eviction is DE-SCOPED from F-001 D3.** Note precisely what that is and is not: it is *not* P2, which
did not fire, and it is *not* a permanent closure of the kind in `closed-arms-prohibitions.md`. It is
that no eviction variant tested is admissible, and the mechanism says why. A future eviction proposal is
allowed, but it must clear a bar this arm has now set -- stated here so it cannot be quietly lowered:

> **The bar: beat fill-and-freeze at EQUAL memory on decode-level net.** Fill-and-freeze is *monotone* --
> once a callsign is admitted it stays resolvable for the life of the process, so it can never lose a
> decode it had. Any eviction policy trades a gain against a loss. At this corpus's 4x oversubscription
> (16,320 distinct callsigns against 4,096 slots) the long tail IS most of the population, so churn costs
> more than it buys: `LRU` bought 302 and paid 1,098. A proposal must name the mechanism by which its
> losses stay below its gains at 4x, not merely assert a better policy.

`LRU-S` -- my own "the result I most want to be true" -- was the worst of the seven. **Recorded as
falsified. The prediction scoring in Sec.7 of the QA report is accepted verbatim, including #3.**

---

## 3. THE BLOCKER: a lookup path this arm could not see, carrying the MAJORITY of our resolved hashes

Arm 1 disclosed, correctly and prominently, that 100% of its 3,517 simulated lookups used the 22-bit
fallback, and that its `false` counts are therefore indicative only. That disclosure is honest and it is
accepted. **What nobody put a number on is how big the unseen population is. I measured it while ruling,
and it is the majority.**

**Measured, on `artefacts/2026-08-25-g2a-remeasure-a/L2_run1_decodes.json` (71,600 decodes).** Predicate
shipped in full so QA executes the text and not a gloss on it (HK-021(r)):

```python
STD  = re.compile(r'^[A-Z0-9]{1,2}[0-9][A-Z]{1,3}$')      # standard-encodable callsign
GRID = re.compile(r'^[A-R]{2}[0-9]{2}$')
NONCALL = {'CQ','DE','QRZ','RRR','RR73','73','TU','NA','SA','EU','AS','AF','OC','AN','DX','TEST'}
toks   = msg.split()
br     = [t for t in toks if t.startswith('<')]            # the hash slot(s)
unres  = any(re.fullmatch(r'<\.*>', t) for t in br)        # '<...>' == unresolved
others = [t for t in toks if not t.startswith('<')]
nonstd = any((not STD.fullmatch(t)) and (not GRID.fullmatch(t)) and t not in NONCALL
             and not re.fullmatch(r'[+-]?[0-9]{1,2}', t)
             and any(c.isdigit() for c in t) and any(c.isalpha() for c in t) for t in others)
```

| hash slot | message carries a NON-standard callsign (type 4 -> **12-bit** lookup) | standard only (**22-bit** lookup) |
|---|---:|---:|
| **resolved** | **1,899** | 1,448 |
| unresolved | 1,333 | 2,233 |

**56.7% of every resolved hashed callsign in this corpus came out of the 12-bit path** -- the one path
arm 1 assumed away. (A lower bound: `nonstd` keys on shape, so a nonstandard callsign that happens to
look standard is counted on the wrong side.)

**Why that path is different -- from source, not from reasoning:**
- `message.c:431` `decode_nonstd` -> `lookup_callsign(..., FTX_CALLSIGN_HASH_12_BITS, n12, call_3)`.
  `message.c:782` `unpack28` -> `FTX_CALLSIGN_HASH_22_BITS`. Those are the only two call sites.
- `message.c:589` `save_hash(callsign, n22)` -- the table always stores the **full 22-bit** hash.
- `ft8_shim.c:649-651` a 12-bit lookup compares `(stored & 0x3FFFFF) >> 10 == query` and
  **returns the FIRST match on the probe chain**. It never checks whether a second entry also matches.

**The arithmetic -- this is REASONING, not a measurement; do not publish it as a figure.** 12 bits is
4,096 codes. With `E` entries resident, the expected number of stored callsigns sharing a query's 12-bit
code is `E/4096`. The 12-bit query starts its probe at the *same* slot the true entry was placed from
(`h10` is the top 10 bits of `n22` and of `n12` alike), so the chain holds the true entry and its decoys
in insertion order, and whichever comes first wins:

| table | resident `E` | expected decoys per 12-bit query | first-match-is-correct |
|---|---:|---:|---:|
| `CUR` today | 4,096 (frozen) | ~1 | order-of-magnitude ~1/2 |
| `SZ4` | 16,320 | ~4 | order-of-magnitude ~1/4 |
| `SZ8` | 16,320 | ~4 | same as `SZ4` -- driven by OCCUPANCY, not by `N` |

Two consequences, pointing in opposite directions to each other:

1. **This is a candidate PRODUCT DEFECT that already exists at `HASH_TABLE_SIZE` 4,096**, independent of
   D-001 and of anything arm 1 or arm 2 does: on the majority path we may be printing a *confidently
   wrong* callsign rather than `<...>`. A wrong callsign is worse than an unresolved one -- it is
   loggable. It also has an operationally severe form: a station with a nonstandard callsign addressing
   **PD2FZ** by hash could resolve to somebody else, and the QSO answerer would never see the call.
   **Exposure to that severe form in THIS corpus is exactly zero** (0 decodes resolve the hash slot to
   PD2FZ -- a receive-only capture), so this corpus says nothing about it either way. That is an exposure
   of zero, not evidence of absence (HK-021(j)).
2. **Enlargement multiplies the decoy density ~4x on that same majority path.** Arm 1's authorised prize
   is +266 decodes = 0.61pp of D-001. The at-risk population is 1,899 decodes. **A shift of a few
   percentage points in the wrong-callsign rate on 1,899 decodes is the same order as the entire prize,
   and it moves toward the worse kind of error.** `false = 0` in arm 1's table cannot speak to this: by
   construction it only ever counted full-`n22` collisions.

**I am not asserting the wrong-callsign rate. I am asserting that we do not know it, that the mechanism
is certain from source, that the exposed population is the majority of our resolved hashes, and that
shipping a 4x table without that number is shipping blind into the metric the change most affects.**

HK-026 applies, and has a clean bypass: our own decoder's resolved output cannot bound its own
mis-resolution rate. The wider-aperture instrument is already in the corpus -- the WSJT-X reference
decodes of the same audio. WSJT-X shares the protocol-level 12-bit ambiguity, so **a disagreement rate is
a LOWER bound on the true error rate** -- and a lower bound is all a go/no-go needs here.

---

## 4. What happens next, in order

**Arm 2 is NOT drafted today. That changes the queue I owed the Captain, so I state the cost plainly: it
delays the enlargement `#define` by one offline arm.** I judge that correct rather than merely cautious --
the alternative is a code change whose principal side effect is unmeasured on 56.7% of the population it
touches.

1. **ARM 1B (I draft it next, on the Captain's go): bound the 12-bit mis-resolution rate.** Offline,
   against dumps already on disk: for the 1,899 resolved type-4 decodes, match to the WSJT-X reference
   decode of the same signal (the `gap-census-a` / `b1-coverage-a` matcher, imported, not
   re-implemented) and count disagreement in the hash slot. Primary is a rate with a **callsign-level**
   CI and the same `n_eff` discipline as this arm -- decode counts here will again be dominated by a
   handful of stations. Pre-registered before it runs: what disagreement rate makes enlargement
   inadmissible, what makes it fine, and the indeterminate band between (HK-021(m)).
2. **Then arm 2, scoped by 1B's number**, one of: (a) `#define HASH_TABLE_SIZE 32768` alone; (b) the
   `#define` *plus* a unique-match rule on the truncated-hash paths (scan the chain; return a name only
   if exactly one entry matches, else `<...>`) -- which trades resolution rate for correctness and must
   therefore be measured, never assumed better; (c) no change.
3. **Arm 2 is a binary A/B, so HK-021(p) binds at DRAFTING time:** both legs built back-to-back from one
   working tree differing only in the treatment, SHA256 of both DLLs pre-registered, and the BUILD
   pre-registered, not just the SHA. Any diagnostic counter must exist in BOTH legs.

**If arm 2 proceeds on size, my recommendation is 32,768, not 16,384** -- and for a second reason beyond
QA's daemon-headroom argument, which I accept: **linear-probe load factor.** `SZ4` ends this corpus at
16,320/16,384 = **alpha 0.996**, a pathological operating point for linear probing with a break-on-empty
lookup -- unsuccessful-search probe length explodes and there is no room for the next station. `SZ8` ends
at **alpha 0.498**. `SZ4` and `SZ8` are numerically identical in this corpus only because the corpus
stops just short of `SZ4`'s wall. Cost is 512 KB of BSS (`callsign_entry_t` is 16 bytes: `char[12]` +
`uint32_t`).

---

## 5. A drafting rule this arm nearly needed -- PROPOSED to the Captain, not adopted

**Proposed HK-021(t): when a gate's unit population is SELECTED ON THE OUTCOME the treatment is meant to
fix, that gate measures the treatment's benefit but is structurally blind to its cost. The cost must be
gated on the complement population, in the same row.**

Here the primary unit was the 40 `CS-cap` callsigns -- defined as callsigns that *failed* under `CUR`.
Any policy that adds capacity or churn can only move them one way, and the harness attributes losses to
`per_cs_loss` only for those same 40 (`run_arm1.py:100-104`), so the 1,098 decodes `LRU` destroyed across
the *rest* of the corpus were invisible to the primary. `LRU` scored 36/40 improved at `p` ~ 2.9e-11 and
was a disaster. Only the decode-level net clause caught it. **The spec was right by one clause. I would
rather it were right by construction.** (a)-(s) plus this would make twenty.

---

## 6. Scope

This ruling authorises: **one document, ARM 1B, to be drafted.** No `src/` change, no `native/` change,
no rebuild, no replay, no capture, no Developer session, no push, no merge. The 12-bit finding in Sec.3
is raised as a **candidate defect for the Captain** -- not filed as one, not fixed.

**Queue: Captain/PO to choose -- (a) I draft ARM 1B now (my recommendation); (b) skip 1B and draft arm 2
as a bare `#define`, accepting the unmeasured 12-bit cost; (c) hold F-001 D3 entirely and take
`OSD-FA-A` off hold.** `OSD-FA-A` still held; `BASE`+`WIDE`/140Hz Developer session per the Captain,
unaffected.
