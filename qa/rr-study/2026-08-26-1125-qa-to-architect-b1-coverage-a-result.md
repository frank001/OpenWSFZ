# B1-COVERAGE-A -- result: ROW A1 fires (0.85), ROW B1 fires (1.00) -- F-001 D3 earns a pre-registration

**QA → Architect.** 2026-08-26 11:25Z (`date -u`, HK-017). Repo `main` @ `2ed5f7d`.

**Answers:** `qa/rr-study/2026-08-25-1836-architect-to-qa-spec-b1-coverage-a.md` in full.

**Status: complete, stopped at the gate.** Pure re-analysis of on-disk dumps, no rebuild, no
replay, no capture. Harness: `qa/rr-study/b1-coverage-a/{common_b1.py, run_b1_coverage_a.py}`
(new). Result: `qa/rr-study/b1-coverage-a/results/2026-08-26-2ed5f7d/{result.json, run.log}`.
Committed locally, nothing pushed (HK-011/014 convention).

---

## Headline

- **ROW A1 fires**: `p_cap` = **0.8511**, 95% CI **[0.7447, 0.9362]** (k=47 callsigns, callsign-level
  bootstrap). B1 is a real, addressable population -- 40 of 47 named callsigns had already been
  learnt in plaintext and still rendered `<...>`.
- **ROW B1 fires**: `p_frozen` = **1.0000**, 95% CI **[1.0000, 1.0000]** (40 CS-cap callsigns). Every
  single addressable callsign was first heard in plaintext *after* the table froze (cycle 767/4,971).
  **⇒ Capacity is the binding constraint. F-001 D3 (eviction) earns its own pre-registration** --
  this authorises *writing that spec*, nothing more (§6, B1's consequence row).
- **QA correction, disclosed in full below**: the spec's naming rule as written (§2.4 step 3 / §2.5)
  yields **k = 0** and VOIDs the whole arm at ROW 0c. Fixed; reproduces your disclosed 339/47/histogram
  exactly. See "QA correction" section.

---

## ROW 0 -- strict order, every row PASS

| row | check | result |
|---|---|---|
| 0a | Dump identity | `dll_sha256`, `shim_version`=20260046, `n_decodes`=71,600 all match; `n_theirs`=43,423 matches. **PASS** |
| 0b | Population reproduction | `n_theirs_only`=18,508, `\|B1\|`=470 -- both exact matches to my own 17:56Z re-derivation. **PASS** |
| 0c | Predicate-movement exhibit (HK-021(q)) | One NAMED key (`ts=260803_172015` → `CS-7d2fd5`, bucket `B1-ord`), one declined `B1-amb` key (`ts=260803_171615`, category `token_count_differs`), one session-wide plaintext emission (`CS-c3e2a1` first seen `ts=260803_171330`). The classifier demonstrably returns more than one value. **PASS** |
| 0d | Proxy calibration | `D` = 3,954, `D/4096` = **0.9653** (bar 0.75-1.25). **PASS** -- proxy recovers 96.5% of a quantity known exactly and independently, exactly matching your disclosed figure. |
| 0e | Determinism | Classifier run twice on `L2_run1`: B1 key set, per-key bucket, per-key named callsign all byte-identical. **PASS** |
| 0f | Independent-input replicate | Classified from `L2_run2_decodes.json` independently: `\|B1\|`=470=470, every key's bucket and named callsign identical key-for-key to `L2_run1`. **PASS** |

No VOID anywhere in ROW 0. Proceeding to the gated parts.

---

## §2.2 textual corroboration -- independent re-derivation, exact agreement

| category | count | share of B1 |
|---|---:|---:|
| **nameable** (all non-hash tokens identical) | **339** | 72.1% |
| two non-hash tokens differ (different QSO, chance co-location) | 71 | 15.1% |
| token count differs (different message entirely) | 58 | 12.3% |
| one non-hash token differs (ambiguous) | 2 | 0.4% |

**Exact match to your disclosed probe (339/71/58/2, 72.1%).** My harness is an independent
implementation (not a re-run of your scratch scripts), so this is real corroboration, not
self-agreement.

⇒ **The corrected, textually-corroborated B1 size is 339 decodes = 0.7807 pp of D-001**
(`n_theirs`=43,423). Per §7 item 2, this **replaces neither** the 470/1.08 pp figure nor the
withdrawn 1.55 pp figure until you rule on it -- stated as a fact QA measured, not a proposal.

---

## 🔴 QA correction to the naming rule (§2.4 step 3 / §2.5) -- disclosed in full

**As written, the naming rule VOIDs the arm.** §2.4 step 3 says the named callsign is "R's token
at the hash position, and it must pass the callsign-shape test in §2.5." Applied literally, this
fails on **all 339/339** nameable candidates, because the reference's token at the hash position is
itself bracket-wrapped -- e.g. a token shaped `<XX/XXXXXX>` -- and §2.5's `CS_RE` =
`^[A-Z0-9/]{3,11}$` has no `<`/`>` in its character class. Every hash-type message field is
displayed bracket-wrapped by `ft8_lib`'s `add_brackets()` **on resolution success too**
(`common_g2a.py`'s own Sec.1 note, which your spec cites at §1 fact 3) -- the bracket is not the
"unresolved" marker (that is the literal `<\.*>` form), it is the hash-type-field display
convention, and the reference is *by construction* always the hash-type message our decode failed
to resolve. Applied literally: `k = 0`, ROW 0c fails, VOID.

**Fix:** strip exactly one enclosing `<...>` layer from the reference's hash-position token before
applying the §2.5 shape test (implemented as `common_b1.strip_enclosing_brackets`, applied only at
the point a callsign is extracted for naming/`T_plain` lookup -- template matching and the §2.2
mismatch classifier both still compare tokens literally, unaffected).

**This is not a guess -- it reproduces your disclosed numbers exactly.** With the fix: `k = 47`,
and the decodes-per-callsign histogram is
`178, 19, 17, 16, 15, 13, 10, 7, 5, 5, 4, 4, 3, 2×10, 1×25`, **identical, entry for entry, to your
§2.3 disclosure.** Your own probe scripts (`probe.py`/`probe2.py`) never applied the §2.5 shape test
to the named token at all -- they took the reference token as-is -- which is why this defect wasn't
visible from your side; the spec as *written*, not as probed, is what fails. Per §0.1's own rule
("where QA disagrees with anything in §2.2/§2.3, QA is the result and I am the error") this is the
inverse case: QA agrees with your numbers and finds the *written* rule wouldn't have produced them.
Recommend folding this into the spec text if `B1-COVERAGE-A`-shaped arms recur.

---

## PART A (PRIMARY, GATED) -- addressability

Unit of analysis: **the named callsign** (k=47, per §2.3's ruling -- decode counts never gated).

| bucket | condition | count |
|---|---|---:|
| CS-cov | never emitted plaintext | 2 |
| CS-ord | learnt only at/after every B1 decode | 5 |
| **CS-cap** | learnt in plaintext, then still rendered `<...>` later | **40** |

**`p_cap` = 40/47 = 0.8511, 95% CI [0.7447, 0.9362]** (callsign-level bootstrap, n_boot=2000, seeded,
resampling the 47 callsigns with replacement).

**ROW A1 fires** (`CI_lo` = 0.7447 > 0.50, comfortably past the ≈0.64 (30/47) resolution threshold
computed while drafting): **a majority of B1's callsign population had already been learnt and still
rendered `<...>`. B1 is a real, addressable population.** Proceeding to Part B.

*(Prediction check: you called A1 at `p_cap` ≈ 0.65-0.85, moderate confidence. Point estimate 0.8511
sits at the top edge of your predicted band; correct in direction and magnitude.)*

---

## PART B (GATED) -- capacity, or bit error?

Runs because A1 fired. Unit: the 40 CS-cap named callsigns, split on the freeze cycle
(`260803_202600`).

| sub-bucket | condition | count |
|---|---|---:|
| **cap-frozen** | learnt after the table froze -- insert rejected, entry never existed | **40** |
| cap-resident | learnt before freeze, entry resident, lookup still failed (bit error) | 0 |

**`p_frozen` = 40/40 = 1.0000, 95% CI [1.0000, 1.0000]** (callsign-level bootstrap over the 40
CS-cap callsigns; a unanimous 40/40 sample cannot resample to anything but 1.0 -- **noting per
HK-021(o) that the readout quantum here is `1/40` = 2.5 pp, and the CI's collapse to a point is a
mechanical consequence of unanimity, not a claim of zero true variance in the underlying process**).

**ROW B1 fires** (`CI_lo` = 1.0000 > 0.50, an order of magnitude past the ≈0.72 resolution threshold
at n=40): **the addressable population is entirely a CAPACITY population, not a bit-error one.**
Every one of the 40 addressable callsigns was first heard in plaintext during the 84.6% of the
session that runs past the table's freeze point.

**⇒ Consequence, per §6's own row: F-001 D3 (eviction) earns its own pre-registration -- sizing,
policy, and a recall-primary gate. This result authorises writing that spec. It does NOT authorise a
table change, a policy, or a Developer session (§9).**

*(Prediction check: you called B1 at `p_frozen` ≈ 0.70-0.90, moderate confidence. Actual result is
more extreme than predicted -- unanimous rather than a majority -- but the direction and the fired
row are exactly as you called.)*

---

## PART C (DESCRIPTIVE, ungated, no CIs) -- `B1-amb` reported first

| bucket | decode count |
|---|---:|
| **B1-amb** | **131** |
| B1-cov | 2 |
| B1-ord | 30 |
| B1-cap | 307 |

(131 + 2 + 30 + 307 = 470, exhaustive.)

- **Decodes-per-callsign histogram** (k=47, descending):
  `178, 19, 17, 16, 15, 13, 10, 7, 5, 5, 4, 4, 3, 2×10, 1×25`. Top-1 = 52.5%, top-5 = 72.3% of named
  B1 -- exactly your §2.3 disclosure, independently reproduced. **No CI is placed on this
  distribution or on any of its counts** (decode-weighted, `n_eff`≈3.5, per the Captain/PO ruling).
- **Textually-corroborated B1 = 339 decodes = 0.7807 pp of D-001**, replacing neither 470/1.08 pp
  nor the withdrawn 1.55 pp until you rule (§7 item 2).
- **`|B1-ord ∩ same-cycle|` = 0.** ⇒ **`B1-cap`'s floor and ceiling coincide at 307 decodes / 40
  callsigns** in this corpus -- but per §7.1, **every `B1-cap` figure is still a LOWER BOUND on the
  true addressable population**, because the table is populated at `unpack`, before the emit filter,
  and ROW 0d's proxy recovers 96.5% (not 100%) of real inserts. Both statements belong in the same
  sentence: **B1-cap = 307 decodes / 40 callsigns, floor = ceiling in this corpus, and both are a
  lower bound on the true population by ROW 0d's ~3.5% measured gap.**
- **Dominant callsign case study**: `CS-235335`, 178 of 339 corroborated B1 decodes (52.5%),
  `T_plain` = `260804_000230` -- well after the freeze cycle `260803_202600` -- bucket `CS-cap`. One
  station accounts for over half of decode-weighted B1, and it is squarely in the frozen-capacity
  population, not a bit-error one.
- **Distinct plaintext callsign-shaped tokens, whole session: 16,320** vs `HASH_TABLE_SIZE`=4,096
  (**×4.0**) -- confirms your disclosed order of magnitude. Descriptive, ungated, authorises
  nothing, but this is the number F-001 D3's eventual spec has to start from: even another 4× of
  capacity would not reach the end of this 20-hour session.

*(Prediction check, `B1-amb`: you predicted QA would reproduce ~28%; actual 131/470 = 27.9%. Exact
match.)*

---

## Scope discipline confirmed

No `src/` change, no `native/` change, no rebuild, no replay, no capture run, no push, no merge, no
`pre_merge_check.py`. Does not authorise F-001 D3 as a change -- only as a spec. Does not re-open
`ΔB1`. Does not touch the `140 Hz` Developer session. No spectral-locality metric anywhere in this
arm. NFR-021 checked: `run.log`/`result.json` grepped for callsign-shaped tokens -- only
`sha256[:6]`-redacted `CS-xxxxxx` forms and counts/timestamps present, verified mechanically (no
match for a raw callsign pattern in the log).

---

## Board update (HK-024, same edit)

`BOARD.md` live line and `MEMORY.md` pointer updated to: **`B1-COVERAGE-A` COMPLETE -- ROW A1 and
ROW B1 both fire; F-001 D3 (eviction) earns a pre-registration, not yet authorised as a change.**
Queue: **Architect to rule on this result and either (a) draft the F-001 D3 pre-registration, or (b)
hold it** · `OSD-FA-A` unchanged, still held · `BASE`+`WIDE`/140 Hz Developer session status per the
Captain, unaffected by this arm.
