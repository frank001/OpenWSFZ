# Defect: The 12-Bit Hashed-Callsign Lookup Names the WRONG Station, at a Rate the Corpus Can See

**Raised by:** QA, 2026-08-26 (14:52 UTC, `date -u`, per HK-017), per `F-001 D3` ARM 1B, ROW A1.
**Severity:** High, **product-facing, not a D-001 finding.** A wrong callsign is worse than an
unresolved one -- `<...>` is honest; a wrong name is **loggable**, spottable in QSO records and any
downstream reporting (PSK Reporter-style relay included).
**Affects:** any Type-4 FT8 message whose *second* callsign is nonstandard, decoded via the
12-bit hash path. Locus: `src/OpenWSFZ.Ft8/Native/ft8_shim.c:637-655` (`hash_table_lookup`,
`sh=10` / `FTX_CALLSIGN_HASH_12_BITS` branch) and `message.c:431` (`decode_nonstd`, the only call
site that reaches it).
**No fix proposed here.** Per HK-011/HK-015 this is QA-authored; a remedy earns its own
pre-registration, per the parent spec's Sec.1. **This document authorises no `src/` change.**

---

## 1. The measurement

Spec: `qa/rr-study/2026-08-26-1352-architect-to-qa-spec-f001-d3-arm1b-twelve-bit-correctness.md`.
Harness (new): `qa/rr-study/f001-d3-arm1b/{common_arm1b.py,run_arm1b.py}`. Result:
`qa/rr-study/f001-d3-arm1b/results/2026-08-26-<sha>/{result.json,run.log}`. Full write-up:
`qa/rr-study/2026-08-26-1452-qa-to-architect-f001-d3-arm1b-result.md`.

Against the independent WSJT-X reference decode of the same off-air audio (`20260803_live_run_1713`,
20m, ~19h), on the population of Type-4 messages where **both** decoders independently resolved the
hashed slot (unit = the callsign **this build** named, k = 243 paired decodes / n = 115 distinct
callsigns):

| quantity | value |
|---|---:|
| callsigns where at least one paired decode disagreed with the reference (`cs-disagree`) | **59 / 115** |
| point estimate `p_dis` | **51.3%** |
| Clopper-Pearson one-sided 95% **lower** bound | **43.2%** |
| pre-registered ROW A1 bar | lower bound > 5% |

**ROW A1 fires, and not narrowly** -- the pre-registered resolution bands (Sec.5 of the spec)
separated "under ~3%" from "over ~9%" with nothing in between; the measured rate is **more than 5x**
the ROW A1 threshold. `k`=243 comfortably clears the `k>=60` power floor. ROW 0d (the free validity
test -- every disagreeing pair must share the query hash `n12` with the reference, or be dropped as a
matching failure) passed at **100%**: zero of the 92 disagreeing decode-pairs were dropped, meaning
every single disagreement is confirmed to be the SAME physical query, not a pairing artefact.

## 2. Why this reads as OUR error specifically, not merely "one of the two is wrong"

⚠️ **Attribution is formally not claimed** -- WSJT-X carries the same protocol-level 12-bit hash
ambiguity, so by the spec's own discipline (Sec.3.3, HK-026) the measured rate is a **lower bound on
the joint error rate**, quoted that way throughout. That said, one descriptive (ungated, Sec.6)
cross-check points squarely at this build:

- **The reference's name, for every single one of the 92 disagreeing decode-pairs (92/92, 100%),
  appears somewhere else in OUR OWN corpus as a directly plaintext-decoded callsign.** This build did,
  at some point in the session, correctly decode that exact station in plaintext -- so the correct
  entry is very likely already sitting in our own hash table. The 12-bit lookup is not failing to
  *learn* the right callsign; it is returning a **different, earlier-inserted entry that happens to
  share the same 12-bit truncated code**, ahead of the correct one on the probe chain.
- By contrast, only 30/92 (32.6%) of *our own* wrong names appear anywhere in the reference's
  plaintext corpus -- consistent with those being decoys the reference never had reason to name.
- The 92 disagreeing decode-pairs collapse to exactly 59 distinct (ours, theirs) name pairs -- i.e.
  every disagreeing callsign returns the **same wrong name every time** it recurs, not a noisy
  mismatch. That is what a stable chain-order collision looks like, not decode noise.

This is descriptive corroboration, not a re-run of the gate, and is reported as such (Sec.6:
"descriptive tiebreaker ONLY... not used to attribute").

## 3. Mechanism (already on the record, now confirmed to bite in practice)

The parent ruling (`qa/rr-study/2026-08-26-1307-architect-to-qa-ruling-f001-d3-arm1.md`, Sec.3) had
already flagged the arithmetic: 12 bits is 4,096 codes, and this session alone emits **16,320**
distinct plaintext-shaped callsign tokens -- roughly 4 real, distinct callsigns per 12-bit code on
average. `hash_table_lookup` (`ft8_shim.c:649-651`) walks the probe chain and **returns the first
match, never checking for a second.** With ~4x oversubscription on the 12-bit path already, at
today's `HASH_TABLE_SIZE = 4096` (independent of the enlargement `#define` under discussion for
`F-001 D3` arm 2 -- **enlargement does not change this defect's rate**, per the parent ruling's Sec.7
withdrawal), a first-match-wins scan over a chain with several genuinely distinct callsigns is exactly
what a >40% wrong-name rate looks like.

## 4. What is NOT established

- **The true joint error rate**, separated from WSJT-X's own share of it. Not measured; would need an
  instrument with no shared blind spot (HK-026) -- none is available offline from this corpus.
- **Severity by message content.** Whether any misresolved slot in this corpus specifically named
  PD2FZ (the severe case named in the parent ruling) was **not** re-checked here; the parent ruling
  already measured that exposure at exactly zero in this receive-only corpus.
- **Whether the rate is corpus-dependent** (session length, distinct-callsign density, table
  occupancy at query time). This arm measured one ~19h 20m session.
- **The correction shape.** Ideas floated in the parent ruling's Sec.4 arm-2 scoping (a unique-match
  rule on the truncated paths: return a name only if exactly one entry matches, else `<...>`) trade
  resolution for correctness and would need their own measurement. **Not evaluated here.**

## 5. Recommended next step (not a fix)

Per HK-011/HK-015: this defect and its rate belong in front of the Captain/Architect alongside the
still-open `F-001 D3` arm 2 (enlargement) decision -- the two are related (both touch
`HASH_TABLE_SIZE`/hash-path behaviour) but **independent findings**: enlargement does not worsen this
defect's rate (parent ruling Sec.7), and this defect does not block enlargement. A remedy (unique-match
rule, table redesign, or accepting the rate) is a product decision requiring its own pre-registration
and a Developer session (HK-011).

## 6. Process

Per HK-015 this is QA-authored. Per HK-011 nothing here touches `src/` -- no fix is proposed. Per
HK-014/HK-010 committed locally only; no push, no merge implied. Per HK-006 no `pre_merge_check.py`
run implied. Per NFR-021 only aggregate figures and sha256[:6] redactions appear here and in the
harness's result.json/report; no real callsign and no raw message text is written to disk outside
`artefacts/` (gitignored).

## 7. Cross-references

- `qa/rr-study/2026-08-26-1352-architect-to-qa-spec-f001-d3-arm1b-twelve-bit-correctness.md` -- the
  spec this arm executed.
- `qa/rr-study/2026-08-26-1307-architect-to-qa-ruling-f001-d3-arm1.md` Sec.3/Sec.7 -- the mechanism
  and the enlargement-withdrawal that motivated this arm.
- `qa/rr-study/2026-08-26-1452-qa-to-architect-f001-d3-arm1b-result.md` -- the full QA result.
- `qa/rr-study/f001-d3-arm1b/{common_arm1b.py,run_arm1b.py}` -- harness.
- `src/OpenWSFZ.Ft8/Native/ft8_shim.c:610-719` -- the hash table, `hash_table_lookup`/`hash_table_add`.
