# Architect recommendation: `f001-h12-unique-match-suppression` — AC-2 is void by construction

**Author:** Architect, 2026-09-02 13:40Z (`date -u`, HK-017).
**Branch:** `feat/f001-h12-unique-match-suppression` @ `27d9c6a`. Docs + one read-only probe
script. Nothing pushed, nothing merged, no `src/`/`native/` touched (HK-011/HK-014).
**Asked by the PO:** "what do you recommend for the AC-2 fail?"

**Recommendation: VOID AC-2 as unsatisfiable by construction, let the merge decision rest on
AC-1/AC-3/AC-4, and open the replacement gate as a separate follow-up change.**
The merge ruling itself is the Captain's (HK-010); this is a recommendation, not a ruling.

---

## 1. Summary

QA's replay (`2026-09-01-2203-qa-to-architect-f001-h12-suppression-ac1-4-result.md`) returned
AC-1 PASS, **AC-2 FAIL** (250 differing lines vs 847 ambiguous), AC-3 PASS, AC-4 PASS.

QA's *mechanism* for the failure is correct. Its *magnitude* ("597, 70.5%") was obtained by
subtraction and should not be cited. This document does three things:

1. Establishes, from the **encoder**, that AC-2's equality could never have held for any correct
   implementation — which is the only legitimate ground for voiding a pre-registered gate after
   seeing the result.
2. Replaces the 597 residual with a **measured, containment-tested** population.
3. Records that the drafting defect in AC-2 is **mine**, and what it cost.

## 2. The decisive fact is in the encoder, not the decoder

QA traced the discard to `decode_nonstd`. The stronger fact sits one function earlier, in
`ftx_message_encode_nonstd` (`native/ft8_lib_vendor/ft8/message.c:256-261`):

```c
else            /* icq != 0  -- i.e. call_to == "CQ" */
{
    iflip = 0;
    n12   = 0;          /* hard-wired: NOT a hash of any callsign */
    call58 = call_de;
}
```

The 12-bit field of a CQ-shaped Type-4 message is **padding**. The decoder nonetheless looks it
up unconditionally (`:431` — grep-verified as the **only** `FTX_CALLSIGN_HASH_12_BITS` call site
in the vendored tree) and then discards the result whenever `icq == 1 && iflip == 0` (`:434`,
`:451`).

Consequence: **every nonstandard CQ performs a lookup of hash slot 0.** Once slot 0 holds two or
more entries, those lookups are counted `ambiguous` by SUP-B's instrument while being incapable of
altering a single rendered character.

## 3. Why this makes AC-2 void, and why "we found an explanation" would not

Voiding a pre-registered gate because a post-hoc story explains its failure is precisely the move
pre-registration exists to prevent. That is **not** the argument here.

The argument is that AC-2 was **unsatisfiable by construction**, provable from source *before* the
run, for **any** correct implementation, on any corpus containing nonstandard CQs:

> `ambiguous_count` counts lookups. Differing lines count renderings. The encoder guarantees a
> population of lookups that are never rendered. Therefore `ambiguous_count > differing_lines`
> strictly, whenever that population is non-empty and slot 0 is occupied.

AC-2 was never a test of this change. It was a test of an identity that the vendored decoder
violates by design. That is the ground for voiding it.

## 4. The drafting defect is mine

AC-2 originates in my brief
(`2026-09-01-1949-architect-to-qa-brief-f001-option-a-unique-match-suppression.md`, §6):

| | as drafted |
|---|---|
| **AC-2** | "The number of decode lines whose text differs from the pre-change run **equals** `ft8_get_h12_ambiguous_count()` read from the same run." |
| consequence | "Any mismatch ⇒ the predicate is firing somewhere other than where the instrument counted." |

Two faults, both mine:

- **HK-021(x)** — I scoped a falsification gate to the population "ambiguous *resolutions*" while
  the claim it was meant to falsify ranges over "ambiguous *renderings*". The gate's population was
  strictly larger than its claim's.
- **False dichotomy in the consequence clause.** A mismatch also follows from a predicate firing in
  exactly the right place on a slot that was never going to render. The clause named one cause and
  excluded the true one.

I also over-claimed AC-2 in the brief as "far better than 'the suite is green'". It was worse than
that: it was a gate that could only ever fail. QA was right to escalate rather than reinterpret
(HK-025).

## 5. The residual, replaced by a measurement

A residual assigned wholesale to one named mechanism hides any second cause. Instead of
subtracting, the discard population can be **counted** from artefacts already on disk, because a
Type-4 nonstandard CQ renders as exactly `CQ` + one nonstandard call (2 bracket-aware tokens,
`extra` empty), whereas a standard Type-1 CQ renders `CQ CALL GRID` (3-4 tokens).

Reproduced by `qa/rr-study/architect_ac2_padding_probe.py` (read-only; exit 0):

| Quantity | Value | Source |
|---|---:|---|
| `h12_ambiguous_count_final` | 847 | candidate run |
| Differing lines (rendered) | 250 | positional diff |
| Residual to explain | **597** | 847 − 250 |
| Nonstd-CQ decodes (`icq=1, iflip=0`), one `n12=0` lookup each | **925** | **measured**, BASE leg |
| Implied slot-0 ambiguity rate | 64.5% | 597 / 925 |
| `CQ` + standard call, no grid (contamination guard) | **0** | measured |

**Containment test — could have failed, and did not:** the residual must fit inside the measured
population. `597 <= 925` **PASS**. Had the nonstd-CQ population come back at, say, 300, the
padding mechanism would have been dead as an explanation and AC-2's failure would have had to be
re-opened as a possible defect.

This also tightens QA's own upper bound. QA offered "CQ-first-token messages are ~20% of all
decodes" (~5,900) as a sanity check; the relevant population is 925 (3.1% of decodes) — roughly a
6× tighter bound.

**Citable form.** *250 rendered, 597 discarded, discard population measured at 925, implied slot-0
ambiguity rate 64.5%.*
🛑 **Do not cite "70.5%".** It is a subtraction expressed as a proportion of a number it was
derived from.

## 6. Corrections, including to my own reasoning

- 🔴 **My own prediction failed.** I predicted zero CQ-shaped lines could differ. **41 did**, all
  `CQ <HASH>` → `CQ <...>`. These are `icq=1, iflip=1` — a shape ft8_lib's encoder never produces
  (it forces `iflip=0` for CQ) but which the decoder honours, so `call_3` lands in `call_de` and
  **is** rendered. The discard population is `icq==1 && iflip==0` **only**, not "CQ-shaped".
  QA's write-up said `icq=1, iflip=0` precisely; my own board summary generalised it loosely to
  "CQ-shaped Type-4 messages". **QA was right; my summary was loose. The board entry is corrected.**
- ⚠️ **QA's supporting correlation is vacuous (HK-021(u)).** 1,823 of 1,856 cycles (98.2%) contain
  a CQ decode, so "the ambiguous-without-diff cycles all contain CQ traffic" is true of essentially
  every cycle and corroborates nothing. Not cited here; recorded so it is not cited later.
- ✅ **AC-3 re-derived independently, not inherited.** With a separately written bracket-aware
  tokenizer, all **250/250** differing lines are exactly one `<HASH>` → `<...>` swap across 10
  distinct line shapes, with `f`/`dt`/`snr` byte-identical (0 numeric violations). QA's evaluator
  and this probe agree while sharing no code — the check QA's own false positive (naive
  `str.split()` on an embedded-space callsign) makes worth repeating (HK-022).

## 7. What voiding AC-2 costs, stated plainly

Voiding removes the only gate aimed at **under-suppression on the rendered population**: a
rendered, ambiguous 12-bit token that kept its name. That hole is real but small, for a
**structural** reason rather than a statistical one:

`cb_lookup_hash` ends in a single boolean expression on the single 12-bit path
(`src/OpenWSFZ.Ft8/Native/ft8_shim.c:826`):

```c
return found && !tls_h12_suppressed;
```

There is no per-case dispatch, so suppression **cannot be partial** — if it works once it works
always. "Did the *right* 250 get suppressed?" therefore reduces to "does the flag track
`multiplicity >= 2`?", which **AC-4 measures at 847/847**, and the flag's per-message lifecycle is
pinned by the reset at `:1635-1636`. AC-1 (29,696 decodes both legs, none gained or lost) and AC-3
(250/250 clean swaps) supply the direct behavioural evidence.

That is what carries the change. It is an argument from structure corroborated by measurement —
not "the suite is green".

## 8. Options, and the recommendation

| | Option | Assessment |
|---|---|---|
| **A** | **Merge on AC-1/AC-3/AC-4; AC-2 formally recorded VOID BY CONSTRUCTION; replacement gate opened as a separate follow-up** | ✅ **Recommended** |
| B | Block the merge until a rendered-ambiguous counter exists, then re-replay and re-rule | Delays a correct change behind a defective ruler. The instrument fix has no bearing on whether the shipped behaviour is right. |
| C | Merge and drop AC-2 altogether | Loses the coverage question rather than answering it, and leaves the same defective gate shape available for reuse. |

**Rationale for A in outcome terms:** the change does what the PO asked — a wrong name is replaced
by no name, and no decode is lost. Three of four acceptance criteria pass, and the fourth turns out
to measure the vendored decoder's internal bookkeeping rather than this change's behaviour.
Shipping should not wait on re-graduating a ruler that was mis-drawn.

## 9. The replacement gate (follow-up, not now)

Cheaper than expected: `cb_lookup_hash` **already** stores the hash value
(`tls_h12_code = h`, `ft8_shim.c:810`, from SUP-B Amendment 2), so the discriminator is already
plumbed to the decision site.

- **Discriminator:** a 12-bit lookup with `hash == 0` is CQ padding.
- **New counter:** ambiguous-and-padding, incremented at the **emission point** beside its
  siblings — never inside the callback (SUP-B TRAP 3, the same trap that design D4 exists to avoid).
- **New getter:** `ft8_get_h12_ambiguous_padding_count()`.
- **Restated criterion:**

```
AC-2'  differing lines == ambiguous_count - ambiguous_padding_count
```

- **Exactness:** ~1/4096 contamination, since a real callsign may legitimately hash to 0. Bounded
  and quantifiable; state it rather than ignore it.
- **Preserves design D3:** existing counters keep their meaning, so every prior ROW-0 reading stays
  comparable. The new counter is additive.
- **No vendor change.** `native/ft8_lib_vendor/` stays untouched, as in this change.
- **Costs:** shim `20260049` → `20260050`; the Windows-only `/EXPORT:` list in
  `rebuild_shim.bat:155-158` (design trap D5 — a getter omitted there builds and links clean on
  Linux and fails only on Windows, only at runtime, on P/Invoke resolution); four C# interop files;
  one re-replay (~1,124 s wall on `S-17M`).

Per HK-025's own test this is a legitimate gate rather than a diagnostic: both branches change the
verdict (pass ⇒ the wiring is proven end-to-end; fail ⇒ the predicate is misfiring and the change
is wrong). It is worth doing — just not worth blocking on.

## 10. The larger finding, which outranks the AC-2 question

🔴 **`g_h12_ambiguous` is contaminated as a *sizing* statistic.**

Roughly 70% of its 847 are slot-0 padding lookups that were never user-visible. **The user-facing
12-bit ambiguity in this corpus is 250, not 847** — any sizing claim resting on that counter
overstates the user-visible problem by ~3.4×.

This does not change the merge decision (Option A stands on AC-1/AC-3/AC-4), and it does not
invalidate SUP-B's *instrumentation*, which counts exactly what it says it counts. What it
invalidates is the **interpretation** of that count as "how big is the ambiguity problem the user
sees".

The existing R1/R3 prohibition on citing a bare `1,582/847` limits the blast radius, but this is a
**new and independent reason** that number misleads, and it should be on the record before anyone
reaches for it again. Any future sizing work needs the padding counter from §9 first.

## 11. The two review findings from the Developer diff, folded in

Neither blocks the merge; both should be carried rather than dropped.

1. 🔴 **`qa/rr-study/nfr021_pre_merge_scan.py`'s `TEXT_SUFFIXES` is missing more than the review
   note said, and the gap is now measured.** The list is
   `{".csv", ".md", ".html", ".txt", ".log", ".json", ".py", ".c", ""}` (`:112`) — so it omits
   `.cs`, `.h`, **`.yaml` and `.bat`** as well. Measured against `main` on this branch **right
   now**: 37 files changed, **14 scanned** (9 `.md` + 3 `.py` + 1 `.txt` + 1 `.c`), **21
   text-bearing files silently skipped** — 18 `.cs`, 1 `.h`, 1 `.yaml`, 1 `.bat` — plus the `.so`
   and `.dll` correctly reported as binary. Every `.cs` file carrying a new literal callsign is in
   the skipped set. The review note's "9 of 22" understated it and named only `.cs`/`.h`.
   **The tool's CLEAN verdict must not be trusted on any diff that is not purely
   `.md`/`.py`/`.c`/`.txt` until those four suffixes are added.** This is a live tooling defect,
   independent of the AC-2 decision, and the more urgent of the two.
   ⚠️ It bites this document too, in the honest direction: the CLEAN reported for *this* commit
   covers both of its files (`.md` + `.py`, both in the list) — trustworthy here, and only here.
2. ⚠️ **`ft8_shim.c:826`'s `return found && !tls_h12_suppressed;` sits outside the 12-bit
   `if`-block**, so it also governs the 22-bit branch. Verified safe today: `ftx_message_decode`
   dispatches to exactly one decoder, `decode_nonstd` is the only 12-bit issuer, and the flag is
   reset per message at `:1635-1636` — so no message decode can issue both hash types with the flag
   set. It is a latent fragility, not a live defect. Worth one comment so a future maintainer does
   not have to re-derive it. Note the direction: the risk is **over**-suppression of 22-bit calls,
   which AC-1 and AC-3 both bear on.

## 12. Honest limits

- **The 597 is bounded and rate-checked, not directly measured.** This probe shows a sufficient
  population exists (925) and that the implied rate (64.5%) is unremarkable. It cannot attribute
  individual lookups. Only the §9 padding counter would.
- **Source paths were read, not executed**, except where §5's probe over recorded artefacts is the
  execution. §7's structural argument is what carries the change; the replay corroborates it.
- **N green runs cannot prove an absence.** Nothing here should be reported as "replay green ⇒
  correct".
- **This is a recommendation.** Voiding a pre-registered criterion and ruling on the merge are the
  Captain's under HK-010/HK-025.

## 13. Authorises nothing

No push, no merge, no `pre_merge_check.py` (HK-006). No `src/`/`native/` change — including the
§9 counter and the §11 comment, both of which need their own scoping and a Developer session
(HK-011). `S_max` = 40% stays FROZEN. No capture run. No re-opening of the accepted risk
(unmeasured correct-name loss at `S-17M`'s CI upper bound). No work on `F-001` L3 / site-6 /
`ARM 2`. The archive-ordering hazard stands unchanged: **`SUP-B` must be spec-synced and archived
before this change**, or this change's `MODIFIED` block overwrites version history that was never
recorded.

## 14. Cross-references

- `qa/rr-study/2026-09-01-2203-qa-to-architect-f001-h12-suppression-ac1-4-result.md` — QA's replay.
- `qa/rr-study/2026-09-01-1949-architect-to-qa-brief-f001-option-a-unique-match-suppression.md` §6 —
  AC-1..AC-4 as drafted, including the defective AC-2.
- `qa/rr-study/architect_ac2_padding_probe.py` — this document's numbers, reproducible, read-only.
- `native/ft8_lib_vendor/ft8/message.c:256-261` (encoder padding), `:431` (sole 12-bit call site),
  `:434-451` (discard condition).
- `src/OpenWSFZ.Ft8/Native/ft8_shim.c:802-828` (`cb_lookup_hash`), `:1635-1636` (per-message reset),
  `:1650-1654` (emission-point counters).
- `openspec/changes/f001-h12-unique-match-suppression/{design,tasks}.md` — where a voided AC-2 and
  the §9 follow-up need recording if Option A is taken.
