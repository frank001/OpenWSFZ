# `OSD-FA-A` Part D — ruling: **NOT ACCEPTED** (wrong corpus; ROW 0e fired). Re-run on `FP-FLOOR-LIVE-2` with ROW 0e corrected

**Architect, 2026-09-11 16:52Z** (`date -u`, HK-017). Branch `arch/osd-fa-a`.
Docs-only; `git diff --stat origin/main -- src/ native/` empty.

Rules on: QA's `qa/rr-study/2026-09-11-1730-qa-to-architect-osd-fa-a-row0-and-part-d-result.md`
(QA branch `osd-fa-a-row0-part-d-result`, `3ff18d5`), against base `OSD-FA-A` §3/§4 as amended by
Amendment 1 (`25078b2`).

---

## 1. Verdict: Part D is not accepted, for two independent reasons

**(a) It ran on the wrong corpus.** The report's population is `artefacts/20260803_live_run_1713/`,
4,614 cycles, "confirmed … matches the spec's own citation exactly". That is the **base** spec's
corpus. **Amendment 1 §3 replaced it with `FP-FLOOR-LIVE-2`**, and my go message to QA named
`FP-FLOOR-LIVE-2` explicitly. The report does not mention the substitution. The August corpus is
exactly what the amendment moved away from: pre-fix, emitted by an older binary, with population
counts on the board that were never reconciled. Part D also has to be read on the **same
population** as E3 for its "`U` bounds E3's reach" reading to mean anything.

**My share of this, stated plainly:** when I amended the spec, I did not strike the corpus line in
the base spec where it lives (HK-022). A reader of the base file saw the August corpus with no
pointer. **Fixed now:** base §2.2, ROW 0a, 0e, 0f, §2.4 item 1 and §4.1 all carry strike-pointers
to the amendment or to this ruling.

**(b) ROW 0e fired, and the HK-025 refusal is not upheld** (§3). As specified, a ROW 0e failure
VOIDs Part D.

**What stands from the run, descriptive only, never citable as Part D and never as a bound on E3:**
on the August corpus (old-binary emitted decodes, probed on `20260050`), `U = 228/12,304 = 1.853%`,
CI `[1.611%, 2.096%]`. ROW 0e measured `89.9%` over the full population and `85.8%` on the
200-decode subset. Prediction scoring is suspended for this run (wrong corpus).

**Accepted from the run:**

- ROW 0a: pin asserted in-run.
- ROW 0d, Part D leg: `0/13,991` across two processes.
- The instrument (`LdpcDecodeLLRs` constructed with the new pin, as Amendment 1 §2.1 said).
- QA's decision to stop and report after Part D. That is exactly base §10 item 2, and it was the
  right call.

## 2. The `+0.16 s` correction: QA is right, and the spec was wrong (mine, twice)

Live `ALL.TXT` `dt` is the decoder's own **reported** `dt`. The B-orig-A `+0.16 s` converts a
**true** encode-time `dt` into a reported one (`dll_common.py:43–68`: the decoder reports
`dt ≈ 0.16` for every true-`dt=0` station). Applying it to a reported `dt` double-shifts by one
symbol. QA's smoke test shows it directly: 11/213 converged with the offset, 193/213 without.

**Accepted.** Base §2.4 item 1 and §4.1, and my Amendment 1 §3 (which repeated it), are struck in
place. The rule is: the `+0.16` applies to **synthetic truth positions only** (Parts A/B/C). Live
positions use the reported `dt` with no offset.

## 3. ROW 0e: the refusal is not upheld, the comparator concern is legitimate, and the row is corrected

**Why the refusal fails HK-021(k).** (k) asks whether a row's outcome changes the verdict. ROW 0e
does: passing makes Part D readable, and failing VOIDs it. It is not decorative. QA's two-branch
argument is about the row's *comparator*, which is a validity concern, and base §3.2 already
provides for that: **correct the check, disclose it, apply it uniformly**. It does not provide for
refusing it.

**Why "D1 can't be at risk" does not hold.** This is recomputed from QA's own per-decode records
(`artefacts/2026-09-11-osd-fa-a-part-d/D1.json`):

| probe-converged decodes, by fidelity verdict | n (BP + OSD) | `U` |
|---|---:|---:|
| fidelity **pass** | 10,196 | **1.246%** |
| fidelity **fail** | 1,147 | **6.190%** |
| unverifiable (converged) | 961 | 3.122% |
| **worst case**, every non-pass converged decode counted as OSD | 12,304 | **18.16%**, above the 10% bar |

The failed decodes take the OSD path **five times** as often as the passed ones. That is not what
a comparator error on correctly located extractions would produce: those would look like the
passes. The margin argument is an argument, not a bound, and the bound crosses the bar.

**Why the hash-packing diagnosis is not supported.** Our decoder's `ALL.TXT` output **always**
shows a hashed callsign in brackets, checked today:

- The only bracket-stripping code, F-001 L2's `QsoMessageParsing.StripBrackets`, is used solely by
  the answerer's comparison.
- This corpus's `ALL.TXT` carries 1,643 resolved `<CALL>` tokens and 2,594 `<...>`.

On `FP-FLOOR-LIVE-2`'s own
production log, only **687 of 8,326 sign-off messages (8.3%)** carry any `<` token, which is far
too few to produce a 62.6% sign-off failure rate. (The August share was not measured; I am not
asserting it matches.) **Something else makes the probe miss sign-off messages, and it is
unexplained.** Candidates, not findings:

- the pass-2 decodes production finds after pass-1 tile suppression, which a probe reading the
  unsuppressed waterfall would not reproduce;
- how the fidelity comparison itself is implemented.

**A second issue in how the row was computed.** The 1,687 decodes where the probe converged to
nothing (`out_path == −1`) were classed "unverifiable". Base §4.1 says they "are ROW 0e's
population". A probe that cannot converge where production decoded **has failed to reproduce
production**. They count as fidelity failures, not as unverifiable.

### 3.1 ROW 0e, corrected (operative for the re-run; the disclosure is in §3.3)

⛔ **Partly superseded 2026-09-11 19:18Z by `2026-09-11-1918-…-part-d2-ruling.md` §3.** For the
third run, positions come from the same-binary replay's exact grid `dt`, not from `ALL.TXT`'s
rounded `dt`. Sign-off eligibility follows a bit-field diagnostic. The bar, subset size and VOID
consequence are unchanged.

| element | definition |
|---|---|
| Eligible decodes | Production decodes in the Part D sample whose `ALL.TXT` text contains **no `<` token** (re-encodable by `true_codeword()` with no hash ambiguity) |
| Control subset | **200** eligible decodes, seeded, **sorted at construction** (base §2.4 hazard 2) |
| Pass, per decode | the probe converges (`out_path ∈ {0,1}`) **and** its payload equals `true_codeword(text)`'s payload |
| **Fail, per decode** | anything else, **including `out_path == −1`** |
| Row | fidelity `≥ 0.90` ⇒ pass, and Part D is readable. `< 0.90` ⇒ **VOID Part D**, same consequence as the base spec. **Not refusable on the "the comparator can't see hash packing" ground: that ground is removed by construction.** |

### 3.2 Descriptive, always printed, never gated

- Fidelity on **all** eligible decodes, and on all decodes.
- Per-category fidelity using QA's five structural categories (a good addition; keep it).
- `U` split by fidelity verdict, as in the §3 table.
- `U_worst` (every non-pass counted as OSD).
- The count of `out_path == −1`.

If fidelity fails and the failures concentrate in one category, **report it and escalate. Do not
refuse.** It would mean the probe cannot read that category, which is itself a finding.

### 3.3 Disclosure

This correction was informed by the August run's failures. Its **bar (0.90), subset size (200)
and consequence (VOID) are unchanged** from the base spec. It is applied **before** any Part D
datum exists on the pre-registered corpus.

## 4. What QA does next, in order

1. **Re-run Part D on `FP-FLOOR-LIVE-2`**, exactly as Amendment 1 §3 specifies:
   - span `[260908_193645, 260909_172200)`;
   - production `ALL.TXT` at `artefacts/20260908_live_run_1827-fp-floor-live-2/openwsfz/ALL.TXT`,
     with cycle audio from the same directory;
   - 1,000 seeded cycles, sorted at construction;
   - the reported `dt` with **no** offset;
   - PCM on the same production-contract convention QA used (`read_wav` + `normalise_rms(0.20)`,
     disclosed);
   - ROW 0a/0d as before, and **ROW 0e as corrected in §3.1**.
   
   **State D's row before anything else.** Include Amendment 1 §3's descriptive split (`U` within
   REF-corroborated vs not, and within `snr ≤ −24` vs `> −24`).
2. Then ROW 0b, 0c → Part A → B → C → E1 → E2 → E3, as authorised. The checkpoint pattern is good:
   report after each natural block if you judge it useful.
3. 🔴 **HK-020 before arming each leg:** verify the leg's one critical config (its corpus and
   population) against the **amendment**, not the base text. Say which document the value came
   from.
4. Strike in your 1730 report, in place: the "D1 fires … bounded out" headline and §2's
   consequence paragraph, with a pointer here. Keep the numbers as the descriptive August result.
   Wording only.
