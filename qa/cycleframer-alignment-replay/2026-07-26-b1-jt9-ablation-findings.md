# D-001 B.1 — jt9 ablation: findings

**Author:** QA, 2026-07-26. **Executes:** `2026-07-26-2330-architect-capability-pricing-plan.md`
§3, per `2026-07-26-b1-jt9-ablation-task-spec.md`. QA-run directly, no `src/`/native change.

---

## 0. Verdict

**The gap is dominated by front-end/sync quality, not by the subtraction/effort stack alone.**
`jt9` at **minimum** effort (depth 1, no context, no AP) already decodes **30% more** messages
than our decoder does offline on the identical WAVs, and recovers **55%** of the specific
messages we miss. At **full** offline effort (depth 3) it recovers **98%** of our miss
population and, on this corpus, **slightly exceeds** the live GUI's own real-time decode count.
Plan §3.4's row 3 (front-end/sync) fires; row 2 (SIC) is confirmed real but bounded to a smaller
share than the investigation's prior working assumption.

## 1. Anchors, self-checked

Reproducing the existing `c4_matched_decode_verification.py`'s own "k10 (shipped)" row before
trusting anything new (this thread's established discipline):

| anchor | value |
|---|---:|
| live WSJT-X GUI, deduped, restricted to the 68 matched cycles | **2028** |
| our decoder, offline, on WSJT-X's own 68 WAVs, shipped settings (k10/c0.10/n60) | **1300** (dedup **1300**, `matched`=**1239**) |
| the miss population (WSJT-X-live minus our-offline, per cycle) | **789** |

This reproduces `c4_matched_decode_verification.py`'s printed numbers exactly (1300 rows, 1300
dedup, 1239 matched). **Note for the record:** the plan and several prior findings docs in this
thread cite this anchor as "1288" / "793 missed" / "1235 shared" — close but not identical to the
self-checked 1300/789/1239 here (differences of ~1%, order 10-12 messages). Not investigated
further; flagged as a minor, non-material drift between an earlier approximate citation and the
canonical script's own output, not a new discrepancy this session introduces. All B.1 numbers
below are computed against the self-checked 1300/789/1239, not the plan's citation.

## 2. Method

Single `jt9.exe` process per arm, all 68 of WSJT-X's own WAVs (`wsjt-x/wav/`, the audio that
produced the 2028 live reference — not our own capture, so this measurement is not confounded
with the `cycle-audio-archive` capture-chain question, already closed separately), file order
chronological (alphabetical = chronological, confirmed by naming convention), `-8 -p 15 -a
<scratch> -t <scratch>`, no `-c`/`-x`/AP flags in any arm. Depth is the only swept axis (`-d 3` /
`-d 2` / `-d 1`).

**Smoke test** (§3.1 of the spec) parsed cleanly: one WAV, depth 3, exit 0, 2.34 s, 28 decodes,
plausible against the ~30/cycle average. jt9's stdout decode-line format
(`HHMMSS SNR DT FREQ ~ MESSAGE`) parses reliably; `decoded.txt` (the file-based alternative) was
not used, per the "whichever parses cleanly" instruction.

**Marker check:** across all 68×3 = 204 cycle-arm decodes, **every marker was `~`** — zero `a1`–
`a6` and zero `?` suffixes anywhere in this offline-CLI, no-context condition. This corroborates
(does not independently confirm — CLI-without-context is a different condition from the live GUI)
the plan §2 AP-marker probe's reading that the live 2028 reference likely also ran without AP.

**Scoring:** `c4_matched_decode_verification.py`'s `normalize_hash_tokens`
(`<[^>]*>` → `<HASH>`) reused verbatim; jt9's own stdout format needed a new line parser (jt9
does not emit this repo's `ALL.TXT` writer format) but feeds the same `{ts: set(message)}`
matching shape. Driver: `b1_jt9_ablation.py`.

## 3. Results

| arm | depth | total | miss coverage (of 789) | overlap w/ our-1300 |
|---|---:|---:|---:|---:|
| A0 | 3 | **2039** | 773 (98.0%) | 1236 (95.1%) |
| A1 | 2 | 1947 | 683 (86.6%) | 1235 (95.0%) |
| A2 | 1 | **1693** | 437 (55.4%) | 1226 (94.3%) |

Per-capability price list: **T(3)−T(2) = 92, T(2)−T(1) = 254.** Of the 346 messages gained going
from minimum to full offline effort, 254 (73%) come from the depth-1→2 step and only 92 (27%)
from depth-2→3.

**Optional arm A4** (jt9 on **our own** byte-compatible capture of the same 68 cycles, depth 3):
**2113** total — *exceeds* both A0 (2039, jt9 on WSJT-X's own audio) and the live anchor (2028).
Symmetric to the `cycle-audio-archive` parity result: our capture chain is, if anything, mildly
*favourable* to jt9, not a source of loss. Miss-coverage/overlap not computed for A4 (not required
to answer its question — the totals alone confirm ≈A0, in fact slightly above).

## 4. Reading against the plan's fixed-in-advance rules (§3.4)

| observation | plan's row | fires? | reading |
|---|---|---|---|
| A0 (2039) vs 2028 | "A0 ≪ 2028 (>15%)" | **No** — A0 is 0.5% *above* 2028, not below | Offline replay at depth 3 needs no session/GUI-context correction; the menu's denominator can stay at 2028 (or A0, they agree). A secondary, unplanned observation: the live GUI does *not* out-decode a context-free offline batch replay on this corpus — real-time session state buys nothing measurable here, and may cost slightly (real-time deadline pressure vs. unhurried batch replay is the most likely mechanism, not investigated further). |
| A2 (1693) vs our-1300 | "A2 ≫ 1288, wide margin" | **Yes** — ratio 1.302, a 30% margin | **A large share of the gap sits in front-end/sync quality itself**, not in subtraction passes. Per the plan's own consequence: the menu must carry a front-end/sync row distinct from SIC. This also coheres with Phase 2c's ≈50% BER "never locked" reading — minimum-effort jt9 finding 30% more than our full-effort decoder is consistent with a front-end/sync gap, not a correction-power gap. |
| T(3)−T(2), T(2)−T(1) | price list | — | 92 / 254 — goes into the §6.3 menu verbatim (Sec.3). |

The miss-coverage numbers sharpen this further, beyond what §3.4 asked for: **55.4% of our
specific 789-message miss population is recoverable by jt9 at *minimum* effort**, climbing to
**98.0%** at full offline effort. Almost the entire 789-message gap is something WSJT-X's own
decoder recovers without live session context — the ceiling for *any* engineering investment
along this axis (SIC, front-end, or effort constants) is close to the full 789, not a fraction of
it.

## 5. Honest caveats (plan §3.5, carried forward)

- **Depth is a bundle.** The 92/254 price list is *effort including subtraction*, not subtraction
  isolated. Do not read T(3)−T(1)=346 as "SIC's ceiling" in §6.3 — it is the whole depth-axis
  ceiling, of which SIC is an unknown share.
- **Offline jt9 ≠ live GUI**, in principle — though this session's own A0-vs-2028 result (§4) found
  the practical difference to be negligible in this corpus's favour, not a source of unmeasured
  loss.
- **One corpus, one band, one device, 21 minutes.** Unchanged from every note in this thread.
- **A2 ≫ our-anchor is a strong signal but not yet a decomposition.** It says *how much* sits
  outside the effort/subtraction axis, not *what specifically* in the front end differs (sync
  detection, candidate scoring, symbol demodulation are all still folded together inside "depth
  1 jt9"). Scoping that further is B.3's row 4, not this session's job.

## 6. Cross-references

- `2026-07-26-2330-architect-capability-pricing-plan.md` §2, §3 — design executed here.
- `2026-07-26-b1-jt9-ablation-task-spec.md` — smoke-test detail, instrument/corpus confirmation.
- `b1_jt9_ablation.py` — driver; raw jt9 output under git-ignored
  `artefacts/d001_b1_jt9_ablation/` (NFR-021).
- `c4_matched_decode_verification.py` — anchor self-check, `normalize_hash_tokens` reused.
- `2026-07-25-2030-cycle-audio-archive-parity-result.md` — the capture-chain-parity finding A4 is
  symmetric to.
