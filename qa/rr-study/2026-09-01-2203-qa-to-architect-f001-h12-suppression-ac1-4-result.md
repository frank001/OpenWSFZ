# QA result: `f001-h12-unique-match-suppression` — AC-1..AC-4 replay, `S-17M` full corpus

**Author:** QA, 2026-09-01 22:03Z (`date -u`, per HK-017).
**Scope:** `openspec/changes/f001-h12-unique-match-suppression/tasks.md` §7–§8 — the replay-based
acceptance criteria, run against the Developer session's diff (commit `b616b6d` on
`feat/f001-h12-unique-match-suppression`, shim `20260049`, binaries SHA256-verified against
`libft8.version.txt`'s own record before use).
**Verdict: AC-1 PASS, AC-2 FAIL (explained, not a suppression defect), AC-3 PASS, AC-4 PASS.**
Per HK-011/tasks.md §8.5, QA reports and stops here — the Captain rules on the merge.

---

## 1. What ran

- **BASE**: `artefacts/2026-08-30-sup-b-row0-amend2/s17m_inst_run1.json` — shim `20260048`, SHA256
  `e22524e8fb4964496e34a2c3f08d6e10d8f6f48eaadb0626fe6a8799fa84e33e` (== `main`@`68a014d`'s pin).
  Reused, not re-run — but first **validated for harness parity**: a fresh 100-cycle BASE leg,
  generated with the same script family used for the candidate, produced byte-identical decode
  text and identical `h12Displaying/Ambiguous/Divergent` totals to the reused artefact before I
  trusted it (HK-022 — don't reuse an artefact from a different script generation without
  checking it actually matches).
- **CANDIDATE**: freshly replayed this session, shim `20260049`, SHA256
  `ce02c7ba10e216349c3cc6d2460a6106379a4593bb730c807dbe8128ecca153e` (matches the binary's own
  hash, independently verified, and `libft8.version.txt`'s recorded value). New harness script
  `qa/cycleframer-alignment-replay/g4_h12_suppression_replay.py` (adds the one new
  `ft8_get_h12_suppressed_count` binding to `g3_h12_replay.py`'s pattern; deliberately not an
  edit to `g3` itself, same reasoning `g3`'s own docstring gives for not editing `g2`).
  Output: `artefacts/2026-09-01-f001-h12-suppression-replay/s17m_candidate_20260049.json`
  (1,856 cycles, `S-17M`, window `260808_115445`-`260808_193830`, wall 1,124 s).
- **Evaluator**: `qa/cycleframer-alignment-replay/g4_ac_evaluate.py` (new). Positional per-cycle
  decode-line diff (valid once AC-1 confirms equal decode counts per cycle — the decoder is
  deterministic and this diff changes render text only, never candidate count/order); AC-3's
  token comparison is bracket-aware (see §3). Redacts every differing callsign token to
  `CS-<sha256[:6]>` before it can reach stdout or a report file, per this codebase's existing
  NFR-021 convention.

Both scripts and their outputs are committed/kept under `artefacts/` (gitignored, NFR-021) except
the two `.py` harness files themselves, which are ordinary `qa/` tooling.

## 2. Result, mechanically

```
AC-1  decode count identical:        base=29,696  candidate=29,696   PASS
AC-2  differing lines == ambiguous:  250 differing lines vs 847 ambiguous   FAIL
AC-3  every differing line scope-compliant (numeric fields identical,
      exactly one bracketed token -> "<...>"):                         250/250  PASS
AC-4  suppressed count == ambiguous count:  847 == 847                 PASS
```

`h12Displaying=1582 h12Ambiguous=847 h12Divergent=652 h12Suppressed=847` (candidate run, final).

## 3. AC-3's own false-positive, found and fixed before trusting the number

First pass flagged 20/250 differing lines as scope violations (token count changed, not just one
token). Traced to my own evaluator, not the diff: the native hash table can store a resolved
callsign with an embedded space (a pre-existing padding/storage quirk, present in BASE
independent of this change — confirmed by re-deriving BASE fresh and seeing the same shape), so
a single bracketed field like `<AB1 CQRS>` splits into two tokens under naive `str.split()`.
Rewrote the tokenizer to treat a `<...>`-delimited span as one token regardless of internal
whitespace (`bracket_aware_tokens` in `g4_ac_evaluate.py`); re-run: 250/250 clean. Recorded here
so the false alarm isn't rediscovered.

## 4. Why AC-2 fails, and why it is not evidence against the change

Traced to source, not inferred: `ftx_message_decode_nonstd` (`message.c:431-454`) calls the
12-bit hash lookup **unconditionally**, before it decides whether the result will be used:

```c
lookup_callsign(hash_if, FTX_CALLSIGN_HASH_12_BITS, n12, call_3);
char* call_1 = (iflip) ? call_decoded : call_3;
...
if (icq == 0) strcpy(call_to, call_1);
else          strcpy(call_to, "CQ");   // discards call_1/call_3 when iflip==0
strcpy(call_de, call_2);
```

For a CQ-shaped Type-4 message (`icq=1`, `iflip=0`) — the shape `TestFt8Encoder.cs`'s own
`PackType4CqAnnounce` doc comment already names as real WSJT-X's actual CQ encoding — the 12-bit
slot is computed, counted by the (SUP-B-inherited, unchanged-by-design) instrumentation as a
"display", and then unconditionally discarded before rendering. The suppression rule fires
exactly where it should; the **counter it is checked against never distinguished "resolved" from
"rendered"** — a gap `SUP-B` shipped and this change was designed to keep unchanged (D3), for
good reason (comparability of every prior ROW-0 reading) — but it means AC-2's literal
"differing lines == ambiguous count" cannot hold on real traffic where CQ calls are common,
independent of whether the suppression logic is correct.

**847 ambiguous, 250 visibly differ ⇒ 597 (70.5%) are the discarded-CQ-slot case.** Consistent
with the corpus: CQ-first-token messages are ~20% of all decodes in a 100-cycle pilot slice
(includes standard-type CQ too, an upper-bound sanity check, not a precise attribution — I do
not have per-message `icq`/`iflip` instrumentation to attribute the 597 exactly, and building
that would be a `src/` change, HK-011, not QA's to add unbidden).

**What the other three ACs still establish, independent of AC-2:** AC-1 (no decode lost or
gained, 29,696 both legs) and AC-3 (all 250 visible changes are clean single-token swaps to
`<...>`, nothing else moves) are direct behavioural evidence the shipped mechanism does only what
the design says. AC-4 confirms the wiring invariant design D4 predicted. The failure is
localised entirely to AC-2's own measurement premise, not to anything AC-2 was trying to detect
(a predicate firing somewhere other than where it's counted, or scope creep) — verified because
AC-3 found zero scope violations across all 250 real differences.

## 5. Recommendation, not a ruling

AC-2 as pre-registered cannot be satisfied on real data for a reason unrelated to correctness. I
see two ways forward and take neither unilaterally (HK-011/HK-025 — a pre-registered mechanical
criterion that fails is escalated, not silently reinterpreted by QA):

- Treat AC-2 as **VOID by explained mechanism** (HK-025-style: the predicate cannot distinguish
  "predicate fires in the wrong place" from "predicate fires in the right place on a slot that
  was never going to render") and let the merge decision rest on AC-1/AC-3/AC-4 plus this
  explanation.
- Or: re-derive AC-2 against a *rendered*-ambiguous count, which does not exist as instrumentation
  today and would need a new counter (a `src/` change, Developer session, its own scoping).

Captain's/Architect's call. I have not touched `src/`/`native/`, not pushed, not run
`pre_merge_check.py` (HK-006/HK-011).

## 6. Cross-references

- `openspec/changes/f001-h12-unique-match-suppression/{design,tasks}.md` — AC-1..AC-4's origin
  (design.md's Migration Plan section, tasks.md §8).
- `dev-tasks/2026-09-01-f001-h12-unique-match-suppression.md` — the Developer handoff this replay
  validates.
- `qa/cycleframer-alignment-replay/g4_h12_suppression_replay.py`,
  `qa/cycleframer-alignment-replay/g4_ac_evaluate.py` — new harness, this session.
- `artefacts/2026-09-01-f001-h12-suppression-replay/` — candidate JSON, AC report, pilot
  artefacts (all gitignored, NFR-021).
