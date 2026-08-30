# ARCHITECT — HK-018 pass over the D-001 ledger: **P2 is not a new target. It is Route B2's sharpest acceptance test.**

**Author:** Architect (Captain: *"start the pass"*)
**Date (UTC, `date -u`, HK-017):** 2026-08-29 20:00:28Z
**Sources read:** the D-001 investigation ledger (`2026-08-18-1902`, 336 lines), the `NBR-FIX`/`NBR-A`
spec (`2026-08-27-2100`), the F-NBR-A spec and results (`2026-08-23`), `closed-arms-prohibitions.md`,
`ftx_find_candidates` in `patched/ft8/decode.c`, and the per-part matched CSVs.
**Type:** Evidence review. 🛑 **No arm proposed. No spec. No `src/` change. Direction requested.**

---

## 0. The conclusion, first

🔴 **There should be no `P2-*` arm.** Every mechanism that could target P2 directly is already
closed by standing prohibition, and the one live route that would fix it is **already specced and
already ranked highest on the board**.

✅ **P2's real value is as an acceptance test, not a target.** It is the cleanest, cheapest,
zero-variance demonstration of D-001's root cause that exists anywhere in the programme — and it is
exactly the thing Route B2 is supposed to fix.

---

## 1. 🔴 First, a correction I owe: I re-discovered a known finding

My 19:40Z report presented the S8 co-channel observation — two signals at 1500 Hz, 0 dB and −6 dB,
both decoding — as an **unsought finding**. **It was already on the board.** It is the
2026-08-27 sweep review §6.2's central mechanism lead, and it is written into the `NBR-A` spec as
**ROW 0e**, whose stated purpose is to test whether it generalises off the S8 scene.

🔴 **That is HK-018 firing on my own work for the third time this session**, and it is the rule's
canonical shape: a file that already existed, unread before I wrote.

⚠️ **What I did add is real but smaller than I made it sound.** The `NBR-A` spec explicitly flags
that this lead *"rests on a single scenario with N = 5"* — which is precisely why ROW 0e exists. My
measurement extends it to **30/35 across four independent runs** (`7d36038` 5/10, `f5dec23` 10/10,
`22b749c` 10/10, `872ba65` 5/5) and contrasts it directly against P12's 0/5. **That is corroboration
of a known lead, not a discovery**, and it should be cited as strengthening §6.2 — not as new.

---

## 2. The mechanism space for P2 is already exhausted

Every plausible direct remedy, checked against the prohibitions rather than reasoned about:

| candidate remedy for P2 | status | source |
|---|---|---|
| Subtract the strong signal, re-decode (successive interference cancellation) | 🛑 **BARRED** — three builds, three reverts, −17 pp at worst | prohibitions; ledger §8 |
| Add a decode pass / raise the candidate budget | 🛑 **CLOSED TWICE** — RC1's ROW 2 plus C.1; caps saturate but *saturation is not loss* | prohibitions; ledger §4 |
| Normalise / AGC / equalise the input | 🛑 **CLOSED PERMANENTLY** (arm "P2", unrelated name) over ±18 dB | prohibitions; ledger §8 |
| Candidate **selection** rather than budget | ✅ checked in code — `ftx_find_candidates` (`decode.c:275`) is a plain score-ranked heap with **no dedup radius and no near-neighbour suppression**. Nothing to tune. | read this session |
| `K_FREQ_OSR`/`K_TIME_OSR` 2→4 | ⚠️ not closed, but lands at 1.5625 Hz / 0.04 s — nowhere near WSJT-X's ≈0.5 Hz / 5 ms; earns its own pre-reg with **FP primary** | prohibitions; ledger §5 |
| Coherent multi-symbol extractor (limb 2), as built | ⚠️ **built but NOT shippable** — ROW 0g-2 still fires, `d_real = −3.000`, CI95 `[−5.000, −2.000]`, still *worse* than production | `NBR-A` §3 |
| Error correction / OSD depth | 🛑 closed on the strongest evidence in the programme — the misses are **not near-misses** (missed-population BER median 44.0% vs `B50` = 11.3%) | ledger §7 |

⇒ **A P2-targeted arm would have to re-open a closed family.** There is nothing left to try that has
not been tried, except the one thing in §3.

✅ **One useful negative result from this pass:** I checked `ftx_find_candidates` specifically because
a near-neighbour *suppression radius* would have explained P2 exactly. **There isn't one** — it is a
score-ranked heap, nothing more. That hypothesis is dead before it cost anything.

---

## 3. What P2 actually is, in the programme's own terms

The ledger's §1.1(3) names the architectural divergence: for each candidate WSJT-X builds a
**private, per-candidate complex-baseband front end** — downconversion with phase retained, fine
frequency (±5 × 0.5 Hz), fine time (±4 × 5 ms), coherent Costas correlation, coherent 1/2/3-symbol
bit metrics. **We have no equivalent stage at all**; every candidate reads the *same* shared,
magnitude-only, `uint8_t` waterfall.

🔴 **P2 is that divergence made visible in a single test part.** Three equal-power signals inside
19 Hz put energy into each other's tone bins. A per-candidate complex baseband separates them by
phase and fine frequency. A shared magnitude waterfall cannot — every candidate sees the same
contaminated bins, so **all three fail together.** That is exactly the observed signature:

- **0 of 3, never 1 or 2** — a shared-front-end failure mode, not a budget or capacity ceiling
  (which would leak one or two through)
- **135 observations, zero variance** across nine runs — deterministic, as a structural limitation
  should be
- **Pairwise spacings all solved 10/10 with two signals** — one contaminator is survivable, two are
  not, which is a threshold effect in how many of the 8 tone bins get polluted
- **WSJT-X: 12–15/15** — the reference decoder, using precisely that machinery, does it routinely

⚠️ **This is a reading consistent with the ledger's §1.1(3) and §6.1, not a measured result.** No arm
has tested it, and the ledger's own citation limits apply. I am not upgrading it.

---

## 4. The route that already exists, and its sizing changes

**`NBR-A` (spec `2026-08-27-2100`, commit `427a5cf`) is specced, bounded, offline, uses an existing
harness (`qa/rr-study/f-nbr-a/`), touches no `src/`, and has been awaiting a Captain decision at its
§5 since 2026-08-27.** It has never been run.

It is a **mechanism discriminator**, not a fix: does the near-neighbour exclusion come from **M1**
tone-set contention in extraction (⇒ same work item as D-001 limb 2 ⇒ priority becomes clearing
ROW 0g) or **M2** a pass-1/tile artefact (⇒ needs a fresh pre-reg, FP primary)?

🔴 **Two things in that spec are now out of date because of today's decisions, and both make the case
stronger:**

1. Its §1 says *"the remaining S7 residual is dominated by P2's 3-stack co-channel case (15 misses),
   which is structural and was Captain-waived."* **The waiver is retracted, and "co-channel" is the
   wrong description.** P2's 12 net observations now sit **inside** the accountable gap.
2. Its ROW 0e precondition — does the ΔF = 0 survival generalise? — is **substantially de-risked** by
   §1's four-run corroboration. The spec priced ROW 0e as *"the most likely of those"* to fire on an
   N = 5 basis; it now rests on 30/35.

**Sizing, with the waiver gone.** `NBR-A`'s §1 claimed the near-neighbour family is 26 of 46 S7
misses and all 5 of S8's. If P2 shares the mechanism — §3's reading, untested — the family is **41 of
46 S7 misses**, and closing it would take S7 from 78.60% to ≈97.7% and S8 to 100%. ⚠️ **That is an
upper bound on the prize, explicitly not a forecast**, and it assumes one mechanism and one fix,
which is exactly what `NBR-A` exists to test and what has never been established.

---

## 5. Where the probability actually sits (ledger §9, restated — not re-derived)

| route | credence | note |
|---|---:|---|
| **Route B2** — per-candidate complex baseband | **45%** | the only route with real probability; **weeks**, native C, Developer session, HK-011 |
| Anchor-offset question | 20% | cheap, re-analysis only, could *re-route* the programme |
| Route A — live framing phase | 12% | cheap-first, not likely-first; settle power before arming |
| X1 + X2 — channel and crowding | 8% | 🔴 largest measured effect (17.22 pp), **no available treatment** (§8.1's trap) |
| B1 / Route C / D-009 Option B | 8% combined | **none recommended** — all feed the extractor N1 showed is position-insensitive |

🛑 **These are Architect credences with a stated calibration of 6/11 categorical. No
pre-registration may cite or gate on them** (ledger §11). Quoted here only to show P2 does not
create a new route — it strengthens the case for one already ranked first.

⚠️ **Ledger delta since 2026-08-18:** it predates `WIN-A` entirely. Add: **the analysis-window family
is now CLOSED** (Hamming and Blackman, on a failed ROW 0e), and the capture cliff it was built on is
**not** a decoder property in the way §1.2 of that spec claimed. Nothing else in the ledger moves.

---

## 6. Recommendation, and the decision I need

**Do not open a P2 arm.** Instead:

1. ✅ **Authorise `NBR-A`** (its §5 option 1 — my recommendation then and now). Offline, existing
   harness, no `src/`, no capture, **hours not days**. It is the only thing that says whether the
   near-neighbour family — now including P2 — is limb 2's business case or a separate defect.
   ⚠️ It needs a short amendment first to fix the two stale items in §4 above.
2. ✅ **Adopt P2 as Route B2's acceptance test, whenever B2 is considered.** It is deterministic,
   synthetic, zero-variance over 135 observations, needs no live capture, and carries a reference
   existence proof. **A candidate fix that does not move P2 off 0/15 has not addressed the
   architectural gap** — that is a far sharper acceptance bar than a percentage on a live corpus.
3. 🛑 **Do not read this as authorising Route B2.** It is weeks of native C, and the honest position
   is unchanged: 45%, and nothing in our own build predicts the gain.

⚠️ **The standing question from earlier this session is still the real one.** S7 is an adversarial
battery; the realistic scenario sits at **55/60 vs 58/60**. Route B2 is a multi-week bet against a
three-decode realistic gap. **That trade is the Captain's to make, and `NBR-A` is the cheapest thing
that informs it.**

🛑 Nothing here authorises a `src/`/`native/` change, an arm, a Developer session, a merge, or a
push. Per HK-014 committed locally, not pushed.
