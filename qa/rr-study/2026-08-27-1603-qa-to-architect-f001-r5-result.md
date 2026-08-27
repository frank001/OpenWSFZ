# QA -> Architect — RESULT: `F-001 R5` — own-callsign direct hash match on the answerer path

**From:** QA · **To:** Architect · **Date:** 2026-08-27 16:03Z (`date -u`, HK-017) · Repo `main` @ `49470d4`

Spec: `qa/rr-study/2026-08-27-1531-architect-to-qa-spec-f001-r5-own-callsign-direct-hash-match.md`
Harness (new): `qa/rr-study/f001-r5/{common_r5.py,run_r5.py}`
Result: `qa/rr-study/f001-r5/results/2026-08-27-49470d4/{result.json,run.log}`

Pure offline re-analysis of the two `ALL.TXT` logs already on disk. No capture, no replay, no rebuild,
no `src/`/`native/` edit. Committed locally, nothing pushed (HK-011/014).

---

## 1. Headline

**ROW 0 clears in full (0a-0h, plus 0f/0g run after). G1 HOLDS under the reading that tests the
spec's actual claim. G3 lands firmly G3-2 UNFAVOURABLE — not a squeaker, and the opposite of the
Architect's own blind prediction.** One genuine, independently-confirmed arithmetic discrepancy in
Sec.0.2's drafting narrative is reported (does not gate ROW 0c, per Sec.4's own wording). One drafting
imprecision in G1a's population wording is disclosed and resolved by reading, not silently assumed.

---

## 2. ROW 0 — instrument checks

All PASS, nothing skipped, run in the order Sec.4 specifies:

- **0a** input identity — SHA-256 recorded for both files; Rx/Tx counts reproduce **64,417/0** (ours)
  and **43,423/0** (theirs) EXACTLY. Zero `Tx` lines confirmed on both, independently of Sec.0.2 —
  the zero-exposure premise holds.
- **0b** population reproduction — the Sec.0.2 six-row shape table reproduces on **our** log EXACTLY:
  177 / 18 / 293 / 2,640 / 1,206 / 9, total **4,343**. Reference side: total **2,867**, dest **1,805**,
  of which resolved **626** — EXACT.
- **0c** hash reproduction — `n22_of`/`n12_of` confirmed as the imported `common_arm1` functions by
  object identity (not re-typed). **11,233** distinct calls, **3,848** occupied codes, and the full
  occupancy histogram (`{1:714, 2:1009, 3:914, 4:645, 5:339, 6:153, 7:40, 8:22, 9:10, 10:2}`) all
  reproduce EXACTLY — this is everything Sec.4's ROW 0c text actually names. See §3 below for a
  discrepancy found in the surrounding Sec.0.2 prose, which Sec.4 does not gate on.
- **0d** predicate-movement exhibit (HK-021(q)) — exhibited a real corpus decode where, for its own
  resolved hash content taken as the hypothetical own-call, `to_us_current` is `False` and
  `to_us_l1l2` is `True`; and a decode/own-call pair where both are `False`.
- **0e** transcription check — `try_parse_message` returns `None` for exactly the **195** two-token
  bracket-bearing decodes and a 3-tuple for exactly the **4,146** three-token ones, zero exceptions.
- **0f** determinism — full run twice, out of process, under two different `PYTHONHASHSEED`s
  (`24601`/`271828`); `result.json` byte-identical.
- **0g** NFR-021 scan — `result.json` + `run.log` scanned for callsign-shaped tokens outside the
  single pre-registered `PD2FZ` (OWNCALL) exception. Zero hits. Independently re-confirmed by hand
  with a second regex outside the harness — clean.
- **0h** reference-coverage exposure, stated not gated — of our 2,933 hashed-dest decodes, **1,043
  (35.6%)** have any reference row at all (matched by `(ts, others, ntok)` within 4 Hz), and **347
  (11.8%)** have a reference row that itself resolved the slot. Carried alongside every G3 figure per
  Sec.4: reference pairing covers a minority of our hashed-dest decodes, and nothing licenses
  extrapolating past it.

---

## 3. A genuine discrepancy in Sec.0.2 — does NOT VOID the arm

**Sec.0.2 said "8 other callsigns... share our call's 12-bit code." The measured figure is 9, and the
reason is mechanical: `PD2FZ` never appears as a plain token in either corpus at all (independently
confirmed with `grep -w PD2FZ` on both `ALL.TXT` files — zero hits, before touching the harness).**
The drafting probe's `by12.get(n12_of(h), 0) - 1` subtracted one assuming OWNCALL's own presence in
the bucket without checking it. Since `PD2FZ` is receive-only in this corpus (Tx=0) and, it turns out,
was never spoken about in plaintext by anyone else either, the bucket holds 9 real OTHER stations, not
8. Off by one, in the direction that **understates** the collision exposure Sec.0.2 was trying to
convey — every one of those 9 is a station this corpus's own-hash rule cannot distinguish from us.

**This does not VOID ROW 0c.** Read literally, Sec.4's ROW 0c text names three reproduction targets —
module identity, 11,233 distinct calls, and the occupancy histogram (implying 3,848 occupied codes) —
and does not name "8 other colliding" as one of them; that figure lives only in Sec.0.2's prose. Per
HK-025 discipline, QA does not self-impose a stricter bar than the one actually pre-registered, so this
is reported here as a disclosed finding rather than used to stop the arm. The 1,553/0 refs figures
from the same Sec.0.2 paragraph DID reproduce exactly, for what that is worth.

---

## 4. G1 — the reframing itself

**Disclosed reading, stated up front (not silently resolved):** Sec.5's own G1a formula reads "over
all 11,233 hypothetical own-calls x **4,343** single-bracket decodes" — literally, the whole
population. But Sec.1's outcome #2 says the falsifying event is "**a hashed-dest decode** IS
recognised," and Sec.0.1's own reasoning is specifically about the bracket sitting in the `dest` slot.
Both readings were computed:

- **LITERAL** (all 4,343 decodes): **G1a = 1,211**.
- **RESTRICTED** (hashed-dest only, 2,933 decodes — the population Sec.0.1(a) and outcome #2 actually
  describe): **G1a = 0**.

Every one of the 1,211 literal hits comes from the **1,206** `3tok_src` and **9** `other` shapes —
messages where the bracket sits at `src`, so `dest` (`parts[0]`) is an ordinary PLAIN callsign token.
For those, `to_us_current` correctly recognising "own-call == plain dest" is existing, correct,
non-hash behaviour (a station literally addressing that plain call), not a counter-example to
Sec.0.1(a)/L2's claim about what happens when the hash sits at `dest`. **G1 HOLDS** under the
restricted reading, which is the one that actually tests the spec's claim; the literal-reading mismatch
is flagged here as a Sec.5 drafting-precision issue, not resolved unilaterally.

- **G1b (to_us_l1l2 fires) = 1,599** — comfortably `> 0`.
- Standard-form-only subset (own call is standard, 6,904 of 11,233 own-calls): G1a_literal=930,
  G1a_restricted=0, G1b=1,042 — same pattern, both readings consistent with the whole population.

**G1 verdict: HOLDS.** Sec.0.1's reframing is correct: today's predicate recognises zero of the
hashed-dest population as "to us," under any hypothetical own-call, and the L1+L2 predicate recovers
some. Proceeding to G2/G3 per outcome #3/#4/#5's branch.

---

## 5. G2 — layer worth (descriptive, not gated)

Pairs newly recovered vs. `to_us_current`, for the same hypothetical own-call each time:

| layer | recovered (own-call, decode) pairs |
|---|---:|
| L1 alone (2-token accept, no bracket strip) | 18 |
| L2 alone (bracket strip, still 3-token only) | 292 |
| L1+L2 together | 388 |

L2 does most of the work here (292 of 388, 75.3%), consistent with the population sizes (2,933
hashed-dest vs. 195 two-token) and confirming blind prediction #4's direction (L2 alone > L1 alone),
though the *(own-call, decode)*-pair weighting narrowed the margin somewhat vs. the raw 293-vs-195
decode counts.

---

## 6. G3 — the false-positive cost of the own-hash rule

**This is the load-bearing result, and it inverts the Architect's own blind prediction.**

Population: (hypothetical own-call, hashed-dest decode) pairs where the reference resolved the slot —
**347 KNOWN pairs**. The remaining **2,586 UNKNOWN** pairs (reference never resolved, so the TRUE
12-bit target is unobservable in either log — no residual bits survive a printed `<...>`) were
assigned adversarially, disclosed in `common_r5.py`'s docstring: MIN pass treats every UNKNOWN as
contributing zero fires; MAX pass treats every UNKNOWN as firing for, and being a false positive
against, the single largest occupancy bucket (10).

| pass | fp | n_fires | p | CP one-sided 95% |
|---|---:|---:|---:|---:|
| MIN (favours G3-2) | 944 | 1,291 | 73.1% | **lower = 0.7102** |
| MAX (favours G3-1) | 26,804 | 27,151 | 98.7% | upper = 0.9883 |

**-> G3-2 UNFAVOURABLE.** The MIN-pass CP lower bound (0.7102) clears the 0.0500 bar by **14.2x**, and
it does so using ONLY the 347 KNOWN pairs — this verdict does not depend on the disclosed UNKNOWN
adversarial convention at all; UNKNOWN pairs contribute nothing to the MIN pass by construction, and
the KNOWN-only figure alone already blows past 0.05. Neither CP interval straddles either threshold
(both lie entirely above 0.05, let alone 0.01) — this is not a squeaker in either direction.
Standard-form-only subset (6,904 own-calls): fp_min=518, n_fires_min=547, CP lower=0.9284 — the same
verdict, more starkly.

**Why this contradicts the Architect's own power note, and where the note's reasoning breaks down.**
Sec.5's power paragraph computed an *unconditional* rate — expected false fires across the *entire*
11,233 x 1,553 cross-product, landing near the 1/4,096 a-priori rate (~0.000244) — and predicted G3-1
FAVOURABLE with the CP bound "far inside" 0.0100. **But G3's own formula, as written ("fp counts pairs
where it fires; n_fires counts every pair where it fires"), is a *conditional* rate: of the pairs that
fire at all, what fraction are wrong.** Firing requires landing in an *occupied* 12-bit bucket, and
conditioning on that already selects for collision — the corpus's own occupancy histogram (already in
hand at drafting: mean bucket size 11,233/3,848 ~ 2.92 among occupied codes) predicts a conditional
wrong-fraction near `(2.92-1)/2.92 ~ 65.7%`, which is the same order of magnitude as the 73.1%
measured. **The 12-bit code space (4,096) is roughly a third of the 11,233 real callsigns this corpus
already contains — this is the identical arithmetic mechanism behind the whole F-001 defect, not a
new one:** route 5's own-hash comparison does not escape the collision problem the hash table has, it
just moves where the same collision math lands. This was computable from Sec.0.2's own histogram at
drafting time (HK-021(m) applies with the opposite sign from ARM 1D's finding: here the power note
*understated* the arm's ability to move, in the direction the Architect's own rationale did not
expect).

**What G3-2 UNFAVOURABLE authorises, and what it does not (Sec.6, unchanged by this result):** no
`src/` change, no claim about a fixed build, no benefit claim in either direction (efficacy is still
structurally unmeasured — zero Tx exposure, Sec.0.2/0.3). What it DOES do, per outcome #4's own text:
it moves Sec.8.4's containment (the `fromPartner && toUs` conjunction, live only in the
partner-bound states) from *optional* to *load-bearing* for any future implementation of an
unconditional own-hash rule in the *unengaged* state — an own-hash comparison fired with no partner
context would be wrong roughly 3 times out of 4 in this corpus, not roughly 1 time in 4,096.

---

## 7. G4 — containment by partner binding

**Reported NOT COMPUTABLE**, per the spec's own explicit permission (Sec.5/G4, and blind prediction
#5). This corpus is receive-only and carries no QSO state machine; "the hypothetical own-call's actual
QSO partner" has no operational referent here. `QsoAnswererService.cs:1081`/`:1163`'s `fromPartner` is
bound to explicit protocol state (`WaitReport`/`WaitRr73` with a specific partner call already
latched) — any text-proximity proxy invented after the fact would measure something shaped like that
conjunction, not the conjunction itself. Matches blind prediction #5 exactly.

---

## 8. Blind predictions scored (Sec.7)

1. **G1a == 0 — HIGH.** **HELD** under the restricted reading (the one that tests the claim); **MISSED**
   under the literal reading (1,211), for the reason given in §4 — a drafting-wording gap, not a defect
   in the L2 reasoning.
2. **G1b > 0 — HIGH.** **HELD** (1,599).
3. **G3 lands G3-1 (FAVOURABLE) — MODERATE-HIGH.** **MISSED, decisively.** G3-2 UNFAVOURABLE, CP lower
   bound 14.2x past the bar. The stated mechanism that "could sink it" (hash clustering by prefix) was
   not needed — the occupancy histogram alone, already measured at drafting, predicted this.
4. **L2 alone > L1 alone — MODERATE.** **HELD** (292 vs 18).
5. **G4 comes back NOT COMPUTABLE — MODERATE.** **HELD.**

---

## 9. What this result does NOT do (Sec.6, reproduced)

No `src/`/`native/` change, no Developer session authorised by this result. No claim about a fixed
build — no binary carrying L1/L2/L3 exists (HK-021(p)). No benefit claim in either direction — the
efficacy side stays structurally unmeasured (zero `Tx` lines, confirmed independently at ROW 0a).
Nothing about harm 1 (wrong names displayed/logged) — ARM 1B's A1/51.3%, ARM 1C's VOID, and ARM 1D's
C3+D3 all stand untouched. This is a new pre-registration with its own ROW 0, not a re-read of any
closed gate with a better metric.

---

## 10. Queue

- Architect to review/rule on this result, in particular: (a) the G1a disclosed-reading resolution
  (§4), (b) the Sec.0.2 "8 vs 9" discrepancy (§3) — informational only, does not itself require a
  ruling to close, but the underlying probe script is the Architect's and may warrant its own note,
  (c) whether G3-2 UNFAVOURABLE changes anything about how Sec.8 (the design brief) should be framed
  before any future Developer session, given containment (8.4) is now load-bearing rather than
  optional for the unengaged-state case specifically.
- PO/Captain still owe the two coupled ARM 2 / remedy-pre-registration decisions from the 15:04Z ARM 1B
  ruling (unaffected by this result — different mechanism, different route).
- QA has now filed the 12-bit MISRESOLUTION GitHub issue (#132, cross-linked with #60) — that queue
  item from the 2026-08-26 19:13Z task is closed.
- `OSD-FA-A` held. `BASE`+`WIDE`/140Hz Developer session per the Captain, unaffected by any of this.
