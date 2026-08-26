# F-001 D3 ARM 1 -- RESULT: ROW 0 ALL PASS. PRIMARY GATE FIRES **P1**, FOR ENLARGEMENT ONLY -- EVERY EVICTION POLICY SHOWS A NEGATIVE NET.

**QA → Architect.** 2026-08-26 12:23Z (`date -u`, HK-017). Repo `main` @ `e9e8898`.

Spec: `qa/rr-study/2026-08-26-1149-architect-to-qa-spec-f001-d3-arm1-policy-simulation.md`.
Harness (new): `qa/rr-study/f001-d3-arm1/{common_arm1.py,run_arm1.py}`. Result:
`qa/rr-study/f001-d3-arm1/results/2026-08-26-e9e8898/{result.json,run.log}`. Pure re-analysis of
on-disk dumps, no rebuild/replay/capture, no `src/`/`native/` edit (Sec.8). Committed locally,
nothing pushed (HK-011/014 convention).

---

## ROW 0 -- all seven PASS, strict order, none void

| row | check | result |
|---|---|---|
| 0a | dump identity | PASS -- `L2_run1` sha/shim/`n_decodes`=71,600 match `common_b1`'s pins |
| 0b | **simulator fidelity (load-bearing)** | PASS -- `CUR`@4,096 on L2_run1 freezes at cycle index **801** (bar [767,1150]); `CUR`@256 on L1 freezes at cycle index **26** (bar [25,40]) |
| 0c | hash-port sanity | PASS -- 16,320/16,320 tokens hash cleanly (0 charset failures); **29** colliding `n22` pairs (bar [10,100], birthday expectation ≈32) |
| 0d | predicate reuse | PASS -- `is_callsign_token` is the same function object across `common_arm1`/`common_b1`/`run_b1_coverage_a`, asserted by identity, not by eye |
| 0e | determinism + independent input | PASS -- `CUR` and `LRU` byte-identical on rerun; `L2_run2` reproduces `L2_run1`'s freeze cycle index (801 = 801) |
| 0f | population reproduction | PASS -- 307 decodes / 40 callsigns, exactly matching `B1-COVERAGE-A`'s `result.json`; all 307 candidate rows relocated for lookup replay (0 missing) |
| 0g | predicate-movement exhibit (HK-021(q)) | PASS -- `SZ8` (32,768 slots, never fills against 16,320 distinct callsigns) resolves **307/307** L_fail decodes = 100%, exceeding the required subset (which is the full 307, since every B1-cap decode is *by construction* later than its callsign's `T_plain` -- see note below) |

**Note on ROW 0g's subset:** the spec asks for "every `L_fail` decode whose `ts` is later than its callsign's
`T_plain`." B1-cap is *defined* as `ts > T_plain` (`key_and_callsign_buckets`), so that subset is the entire
307-decode `L_fail` population -- ROW 0g and ROW 0f's population check share the same denominator. Disclosed so
nobody reads 0g as a weaker check than it is.

**Worked example (0g):** `CS-0596df`, `T_plain`=`260803_234700`, B1 `ts`=`260803_235000`, resolved-under-`SZ8`=True,
failed-under-`CUR` (its real-world classification as B1-cap)=True.

**ROW 0b in detail, and why 801 ≠ 767 is still a pass, not a coincidence:** the simulator's insert stream is the
emitted-decode proxy (measured 96.5% recovery, `B1-COVERAGE-A` ROW 0d), and missing inserts can only push a
simulated freeze **later** than reality (fewer distinct arrivals reach the table before the real cutoff). 801 > 767
is exactly the predicted direction and lands well inside the pre-registered [767,1150] bracket. Same story at
L1: 26 vs 25, inside [25,40].

---

## Hash-type disclosure (Sec.6, mandatory before Sec.5)

Every lookup in this arm used the **22-bit fallback**. `FTX_CALLSIGN_HASH_10_BITS` is defined in `message.h` but
never invoked anywhere in this tree (grep-verified against `message.c`); the real choice is 22-bit
(`unpack28`'s non-standard-callsign branch, `message.c:781`, used inside otherwise-standard 2-callsign messages)
vs 12-bit (`decode_nonstd`'s `call_3`, `message.c:431`, the KD8CEC extension) -- and the two render **identical**
decoded text: a "CALL1 CALL2 [report]" shape with one bracketed slot, with no textual marker of which path
produced it. Per the spec's own contingency (Sec.3, "fall back to 22-bit and count"), **100% of the 3,517
lookups took the fallback.** Consequence, exactly as the spec anticipated: Sec.5.1 (residency) is unaffected --
admission is a pure function of arrival order and count, never of hash width. Sec.5.2's `false` counts measure
only genuine full-`n22` collisions (the ROW 0c population, ~29 pairs among 16,320 tokens), **never** the
truncated-bit collisions Sec.0 fact 4 warned about. Report every `false` figure below as indicative, consistent
with ROW 0b's own note that the probe/truncation path is the least-validated part of this arm.

---

## An un-pre-registered finding, disclosed in full: a 41-decode proxy-noise floor common to every policy

`CUR`'s own simulated baseline is not `net=0` -- it is **`gained=0, lost=41, false=0, net=-41`**. This is not a
defect in `CUR`; fill-and-freeze never evicts, so a callsign that was ever admitted stays resolvable forever. The
41 losses are decodes that resolved in the **real** dump but whose target callsign's *own* directly-decoded
mention never reached our emitted-decode proxy (the same ~3.5% insert-stream shortfall ROW 0b's bracket already
prices in) -- so the simulated table never learned them, purely a proxy artefact, not a table-policy effect. This
floor is **identical (41) across `CUR`/`SZ2`/`SZ4`/`SZ8`** (all fill-and-freeze, all built from the same insert
stream), which is itself a useful cross-check: it confirms the 41 is table-size-independent, i.e. genuinely proxy
noise and not a capacity effect. It does **not** cleanly separate out of the eviction policies' larger `lost`
counts, so it is reported here as context, never subtracted from any policy's citable `net`. Every `net` figure
below remains, as specified, a **lower bound**.

---

## Sec.5 -- every policy, decode-level (unit = decode; never a proportion; never a CI, `n_eff`≈3.5)

| policy | N | eviction | gained | lost | false | **net** | table occupancy at end |
|---|---:|---|---:|---:|---:|---:|---:|
| CUR (baseline) | 4,096 | -- | 0 | 41 | 0 | **-41** | 4,096/4,096 |
| SZ2 | 8,192 | -- | 194 | 41 | 0 | **153** | 8,192/8,192 |
| SZ4 | 16,384 | -- | 307 | 41 | 0 | **266** | 16,320/16,384 |
| SZ8 | 32,768 | -- | 307 | 41 | 0 | **266** | 16,320/32,768 |
| LRU | 4,096 | LRU | 302 | 1,098 | 2 | **-798** | 4,096/4,096 |
| LFU | 4,096 | LFU | 275 | 701 | 4 | **-430** | 4,096/4,096 |
| LRU-S | 1,024 | LRU | 302 | 1,473 | 1 | **-1,172** | 1,024/1,024 |

Never `gained` alone: SZ8 *gained* 307 decodes, at a cost of *lost*=41 and *false*=0, for a *net* of 266.
LRU *gained* 302 decodes -- more than SZ2 -- at a cost of *lost*=1,098 and *false*=2, for a *net* of **-798**.

**HK-021(j) (absence needs λ≥5):** `false=0` for SZ2/SZ4/SZ8. Expected count under a stated model: a false
resolution requires (a) the queried callsign to be one of the ~29 colliding `n22` pairs from ROW 0c, AND (b) the
colliding entry to sit earlier on the probe chain at query time, AND (c) that specific token to actually be
among the 3,517 lookups this session performs. The joint probability is low; a handful of events, not zero, is
the honest expectation -- report `false=0` here as **not detectable at this exposure**, never as "does not
happen."

**`SZ4` and `SZ8` are numerically identical** because `SZ4`'s 16,384 slots already exceed the corpus's entire
16,320-distinct-callsign namespace (table occupancy 16,320/16,384, zero rejects) -- this corpus cannot
distinguish between them. The two remain distinct rows because the board's own daemon-scale figure
(~20k distinct callsigns/day) means 16,384 could run tight on a longer or busier session where 32,768 would not;
this arm cannot adjudicate that, only flag it.

---

## Sec.5.1 -- PRIMARY GATE, unit = named callsign (k=40), paired exact two-sided sign test

| policy | improved | worsened | unchanged | n_discordant | p (two-sided) | net (decode) | row |
|---|---:|---:|---:|---:|---:|---:|---|
| SZ2 | 7 | 0 | 33 | 7 | 0.0156 | 153 | **P1** |
| SZ4 | 40 | 0 | 0 | 40 | ~1.8e-12 | 266 | **P1** |
| SZ8 | 40 | 0 | 0 | 40 | ~1.8e-12 | 266 | **P1** |
| LRU | 36 | 0 | 4 | 36 | ~2.9e-11 | -798 | does not qualify (net ≤ 0) |
| LFU | 35 | 0 | 5 | 35 | ~5.8e-11 | -430 | does not qualify (net ≤ 0) |
| LRU-S | 36 | 0 | 4 | 36 | ~2.9e-11 | -1,172 | does not qualify (net ≤ 0) |

**Leave-one-out, `CS-235335` removed (52.5% of corroborated B1), k=39, reported beside the primary as
pre-registered -- no flip for any policy:**

| policy | improved | worsened | n_discordant | p (two-sided) |
|---|---:|---:|---:|---:|
| SZ2 | 6 | 0 | 6 | 0.0312 |
| SZ4 | 39 | 0 | 39 | ~3.6e-12 |
| SZ8 | 39 | 0 | 39 | ~3.6e-12 |
| LRU | 35 | 0 | 35 | ~5.8e-11 |
| LFU | 34 | 0 | 34 | ~1.2e-10 |
| LRU-S | 35 | 0 | 35 | ~5.8e-11 |

### Gate verdict

**P1 fires -- for `SZ2`, `SZ4`, and `SZ8` (enlargement) only.** Every criterion is met independently for all
three: `n_discordant`≥6, all-improved (zero worsened for any callsign, at any size), `p`<0.05, and a strictly
positive decode-level `net`. **No eviction policy qualifies for P1** -- `LRU`/`LFU`/`LRU-S` each show a strong,
significant *callsign-level* improvement (35-36 of 40 improved, `p`≈1e-11) but a **decode-level net far worse
than doing nothing at all** (`CUR`'s own net is -41; every eviction policy is more negative than that). P1's
"AND positive net" clause is load-bearing here -- a callsign-level test alone would have wrongly called eviction
a win. **P2 (close the route) does not fire** -- the best policy (`SZ4`, net=266) is strongly positive.

⇒ **F-001 D3 arm 2 earns a pre-registration, per P1 -- but scoped to enlargement only.** Nothing here
authorises an eviction implementation; the data argues against one.

---

## Sec.5.3 -- descriptive, both readings side by side (ungated)

- **Enlargement serves the bounded session, and it is a clean win here.** `SZ4` (16,384 slots, 256 KB) already
  recovers 100% of the addressable 307 with zero measured false resolutions; `SZ8` (512 KB) adds nothing more in
  *this* 20-hour corpus because the corpus's own namespace (16,320 distinct callsigns) already fits inside
  `SZ4`. Even the modest `SZ2` (8,192 slots, 2x memory) recovers 194/307 (63%) at zero measured cost.
- **Eviction serves the unbounded daemon, and every form tested here is actively harmful.** `LRU`, `LFU`, and
  `LRU-S` all gain more decodes than any enlargement variant except `SZ4`/`SZ8` (275-302 gained), but all three
  destroy far more than they gain (`lost` 701-1,473) -- the dominant callsign alone (178 of 339 corroborated B1
  decodes) is the likeliest source of the bulk of that `lost` count, since a station transmitting that often is
  exactly the kind of entry a capacity-bound eviction policy will cycle out and back in repeatedly, breaking its
  own resolution each time it is out. `LRU-S` at a quarter of `CUR`'s memory is the single worst policy measured
  (net -1,172) -- the opposite of the Architect's own stated hope for it.

---

## Architect's five blind predictions (Sec.7), scored

1. **`SZ8` recovers ≥250 of 307** -- high confidence, **CONFIRMED and exceeded**: 307/307 (100%).
2. **`LRU` at 4,096 recovers 150-260** -- moderate confidence, **FALSIFIED on direction of the number that
   matters**: `LRU` *gained* 302 (above the predicted range), but net is -798 because `lost`=1,098 was never
   part of the range predicted.
3. **`LRU-S` beats `CUR` at 1,024 slots** -- "the result I most want to be true" -- **FALSIFIED, decisively**:
   net -1,172, the worst of the seven policies tested, far worse than `CUR`'s own -41.
4. **`lost`>0 for every eviction policy (high confidence); `net` for `LRU` still positive (moderate)** --
   first half **CONFIRMED**, second half **FALSIFIED**: `LRU` net is -798.
5. **`false` rises monotonically with N, stays <20 at `SZ8`** -- **NOT OBSERVED as stated**: `false`=0 at every
   enlargement size (SZ2/SZ4/SZ8 alike, no monotonic rise), 1-4 at the eviction sizes. Consistent with the
   hash-type disclosure above -- this arm's `false` metric cannot see the truncated-bit mechanism prediction 5
   was actually about, so this prediction is **unscored, not falsified**: a different instrument would be needed
   to test it.

Net: the Architect's own stated preference for enlargement over eviction (Sec.5.3, "I consider this the likeliest
outcome") is the one that survived contact with the data; the specific hope for `LRU-S` did not.

---

## Sec.8/HK-011 scope check

No `src/`, no `native/`, no rebuild, no replay, no capture, no push, no merge, no `pre_merge_check.py`. This
result authorises **no code change of any kind**. Its maximum consequence, per P1, is that arm 2 (an enlargement
`#define`, per Sec.5.3's own framing) earns its own pre-registration -- which still needs a Developer session and
the Captain (HK-011).

---

## Recommendation (not a gate; the Captain's and Architect's call)

Given SZ4=SZ8 in this corpus but the board's own ~20k-distinct-callsigns/day daemon figure, and given
enlargement's zero measured downside vs eviction's uniformly negative net: if arm 2 is drafted, the evidence
here supports scoping it to a `HASH_TABLE_SIZE` `#define` change (candidate: 32,768, for headroom beyond a single
20-hour session) and dropping eviction from consideration entirely, rather than the reverse.

---

**Queue: Architect to rule on this result.** `OSD-FA-A` still held · `BASE`+`WIDE`/140Hz Developer session per
the Captain, unaffected.
