# `F-001` L3 — result: **ROW 3 FIRES, escalate — occupancy check fails hard; `U149 = 0`**

QA, 2026-09-10 18:14Z (`date -u`, HK-017). Spec:
`qa/rr-study/2026-09-02-1631-architect-to-qa-spec-f001-l3-own-hash-compare-sizing.md`, Amendment 1
(same file, 2026-09-03 16:16Z). Amendment 2 (board, 2026-09-08 20:31Z: corpus substitution to
`FP-FLOOR-LIVE-2`, ROW 0d withdrawn/replaced, ROW 0f/tooling authorised) — 🔴 **its own spec file
(`qa/rr-study/2026-09-08-2031-...-amendment-2-...md`) is NOT present in this worktree**, `arch/f001-l3`
being a different worktree/branch, local-only. Reconstructed here **only** from `BOARD.md`'s own
detailed paraphrase (2026-09-08 20:31Z entry) — flagged so this is read as second-hand, not as
having read the source document. Harness: `qa/cycleframer-alignment-replay/g3_h12_replay.py`
(extended, additive-only, `g4` untouched), `l3_gate.py` (new), both committed alongside this file.

**Headline, Sec.0.3/§8 verbatim: this arm sizes L3's COST ONLY. Efficacy remains structurally
unmeasurable (zero `Tx` lines in every corpus held) — a cost-only result is NEVER a verdict on
whether L3 should be built.** Within that constraint: ROW 0 clears in full (with two disclosed
deviations, §2 below). `U149 = 0` — **our own code drew zero unresolved 12-bit lookups** across the
entire corpus, consistent with the spec's own prediction (`U149 ∈ {0,1}`). But the **occupancy
check fails hard** (`z = −11.75`, nearly 4× outside the ±3σ band) — unresolved lookups are **not**
uniformly distributed across the 4,095 non-padding codes, so `U149 = 0`'s reading cannot be safely
derived from the base rate. Per spec: **ROW 3, escalate. Not averaged, not rounded to the nearer
row, threshold not re-cut, no re-run on another corpus for a cleaner occupancy** (Amendment 2's own
explicit bar).

---

## 1. Population

| quantity | value |
|---|---|
| Corpus | `FP-FLOOR-LIVE-2`, span `[2026-09-08T19:36:45Z, close)` — Amendment 3's frozen boundary to the corpus's own true close |
| Window | `260908_193645` .. `260909_172200` |
| Cycles replayed | **5,222** (the corpus's full natural population in-window — not `FP-FLOOR-LIVE-2` Part A/B's own `n=601`, a *different* arm's own stopping rule, not a corpus limit) |
| Subject binary | shim `20260050`, `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll` (current `main`), SHA256 `6b2e16a6…` — matches manifest pin exactly |
| Control binary | shim `20260049`, `artefacts/2026-09-03-f001-l3-shim-rebuild/libft8-20260049-prechange.dll` (`ac6150d`'s own parent, preserved by the Developer), SHA256 `ce02c7ba…` — matches manifest pin exactly |
| Decodes, both legs | 65,798 (byte-identical, see ROW 0e) |
| `hash_table_reject_count`, final | 65,034 (both legs) — this replay's own table saturates within the 22 h window, independent of the original live capture's own saturation horizon (a fresh in-process table, not shared with the daemon's) |

## 2. ROW 0 — every row evaluated, printed, in strict order (HK-021(r), code: `l3_gate.py`)

| row | predicate | result |
|---|---|---|
| 0a | binary identity, both legs | **clear** — both shim/SHA pairs match the manifest exactly |
| 0b | `U_total < <...> renderings` | 🔴 **REFUSED AS A STOP (HK-025)** — see §2.1 |
| 0c | `out_of_range ≠ 0` | **clear** — `0`, and equals the resolved-side `h12_code_out_of_range` (`0`) exactly, as design D3's counter reuse predicts |
| 0d′ | `sum(by_code.displaying) == h12_displaying_count_final` | **clear** — `3610 == 3610` |
| 0d″ | `sum(by_code.ambiguous) == h12_suppressed_count` (read via `h12_ambiguous_count_final`, source-verified identical, `ft8_shim.c:1220`) | **clear** — `1529 == 1529` |
| 0e | byte-identical decode lines, both binaries, same corpus | **clear** — `5,222/5,222` cycles compared, **0 diffs**, 0 control-only, 0 subject-only |
| 0f | re-derive `n12=149` a third time, from the DLL, in-run | 🔴 **NOT COMPLETED** — see §2.2 |
| 0g | `U_clean < 500` | **clear** — `U_clean = 1,561` |

**ROW 0 clear on every row this arm could mechanically evaluate.** Two disclosed deviations from the
letter of the spec, neither hidden:

### 2.1 ROW 0b — refused as a STOP, a genuine comparator defect found by the smoke test

"Count of `<...>` renderings parsed from the same leg's emitted lines" (spec §5) mixes two different
hash widths. `native/ft8_lib_vendor/ft8/message.c:782` (`unpack_callsign`, the plain **Type-1/2
standard-message** field unpacker used by ordinary QSO traffic) also renders the identical `<...>`
on a miss, via a **22-bit** hash lookup (`FTX_CALLSIGN_HASH_22_BITS`) — the same bracket convention
(`message.c:606`; widths listed `message.h:58-60`) shared across all three hash widths. This arm's
export counts **only** the 12-bit (Type-4/nonstandard-call) branch. On the full corpus: `U_total
(12-bit) = 1,585` vs `4,199` total `<...>` renderings (12-bit + 22-bit combined) — and ordinary
Type-1/2 traffic, the overwhelming majority of any real corpus, is exactly where 22-bit misses come
from. The decode JSON this arm collects carries no message-type (`i3`) field to separate the two
post-hoc. **This reflects a mismatched comparator, not a miswired 12-bit counter** — 0c/0d′/0d″/0e
all independently confirm the 12-bit table itself is internally consistent and non-perturbing.
Evaluated and printed every run; never allowed to stop the arm on its own (HK-025 — QA's authority
to refuse a non-mechanical row, not authority to rewrite it). **The spec's own ROW 0b wording likely
needs an amendment** (scope it to 12-bit renderings specifically) — flagged for the Architect, not
actioned unilaterally.

### 2.2 ROW 0f — attempted, not completed, disclosed rather than claimed

A genuine `ft8_encode_message` → synthesise (continuous-phase FSK, `b2_synthetic_calibration.py`'s
own established method) → `ft8_decode_all` → read-`h12_by_code` round trip was attempted for
`PD2FZ`, in a standalone throwaway process (no contamination of either corpus leg — separate OS
process, separate DLL load, separate global hash-table state). The message round-tripped and
rendered correctly (`PD2FZ <...> RR73` → resolved to plain `PD2FZ` on decode, confirming the
encode-side `save_callsign` → decode-side `lookup_callsign` path works for our own call), but the
resolution did **not** register in `h12_by_code`'s per-code table within the time this session judged
reasonable to spend tracing a message-type/dispatch detail in `ftx_message_decode_nonstd` that
wasn't fully resolved. **Not marked pass.** Resting instead on the spec's own two prior independent
from-scratch confirmations already on record — the spec's own derivation (Sec.2) and the project's
committed `qa/rr-study/f001-d3-arm1/common_arm1.py` (`n22_of`/`n12_of`), both agreeing at
`n22=153456`, `n12=149` — a real, disclosed reduction in this row's evidence relative to the letter
of the spec, not a silent skip. `OUR_CODE=149` is asserted in `l3_gate.py` itself, not left as a
prose reminder (standing project instruction).

## 3. The distributional reading, in full

```
U_total (12-bit unresolved lookups) = 1,585
U[0]    (padding, always code 0)    = 24
U_clean = U_total - U[0]            = 1,561
U149    (our own code)              = 0

E_uniform = U_clean / 4096          = 0.3811

Occupancy (codes 1..4095, padding code 0 excluded from both the observed count and
the expected/sd formulas -- a QA-side convention pre-registered in l3_gate.py's own
source before any of this run's data was read, since neither the spec nor Amendment 2
pins an exact formula under the U_clean redefinition):
  lambda   = U_clean / 4095 = 0.3812
  occ_obs  = 948   (distinct codes 1..4095 with >=1 unresolved lookup)
  occ_exp  = 1,297.9
  occ_sd   = 29.8
  z        = (948 - 1297.9) / 29.8 = -11.75
```

**Shape of the clustering, descriptive (not part of the gate):** 605 of the 948 occupied non-padding
codes were hit exactly once; the top code (excluding padding) drew 16 hits, with several more codes
at 9-13 — a heavy top against a long thin tail, not a uniformly-thin spread. `occ_obs` sits **349.9**
below `occ_exp`, i.e. probability mass is concentrating onto *fewer* distinct codes than uniform
predicts, repeatedly, rather than spreading across more.

**Two live, undetermined candidate mechanisms, neither investigated further — out of this arm's own
pre-registered scope, noted for whoever picks this up next:**
- The FP-FLOOR-LIVE-2 corpus's own known hash-table-saturation finding (`BOARD.md`, ~2026-09-09
  00:04Z entry): "some share of this corpus's `<...>` renderings from the saturation point on are
  table-CAPACITY artifacts... a different, non-stationary mechanism from L3's own-hash-collision
  question." This replay's *own* table also saturates within the window (`hash_table_reject_count`
  final `65,034`, both legs) — a capacity-eviction mechanism could plausibly produce exactly this
  "same few codes recur" signature. Its message to the Architect was queued twice and undelivered;
  no Architect session was reachable this session either (`ListAgents` checked before writing this
  report). Travelling via this report and the board entry instead.
- A mundane alternative: a small number of genuinely nonstandard-format stations (contest/portable
  suffixes) transmitting repeatedly over a 22-hour single-band span, each landing on the same code
  every time by construction (the hash is deterministic per callsign) — ordinary traffic, not an
  artifact.

Neither is distinguishable from the data this arm collected. Disentangling them is new work, not a
re-run of this one (Amendment 2's own bar against re-running for a cleaner occupancy applies with
equal force to re-running to attribute this one).

## 4. ROW 1/2/3

| row | predicate | result |
|---|---|---|
| 1 | `U149 ≥ 5 AND U149 ≥ 5·E_uniform` | clear — `U149 = 0` |
| 2 | `U149 ≤ 2 AND |occ_obs − occ_exp| ≤ 3·occ_sd` | clear on the first clause (`0 ≤ 2`), **fails the second** (`349.9 > 89.3`) |
| 3 | anything else | **FIRES** |

**Per spec: escalate. Do not average, do not pick the nearer row (ROW 2's first clause alone would
read as reassuring — resist that), do not re-cut the ±3σ threshold, do not re-run on another corpus
for a cleaner occupancy** (Amendment 2's own explicit instruction, restated because this is exactly
the situation it anticipated).

## 5. Recommendations

1. **No further reading of this arm is authorised or attempted** — ROW 3 hands the decision to the
   Architect/PO, not to a QA re-analysis.
2. **ROW 0b's spec wording (§5) needs an amendment** scoping "`<...>` renderings" to the 12-bit path
   specifically, or an accepted alternative comparator — Architect's call, not QA's to redraft
   unilaterally.
3. **ROW 0f remains genuinely unverified from the DLL.** If a future arm needs this row load-bearing
   (this one didn't — ROW 0 cleared regardless, since 0f's fire condition never gated the STOP path),
   the message-type dispatch in `ftx_message_decode_nonstd` this session didn't fully trace is the
   place to pick up.
4. **The hash-saturation finding from FP-FLOOR-LIVE-2 (§3 above) is still undelivered to the
   Architect** — re-flag at the next opportunity a session is reachable; it bears directly on how to
   read this arm's own occupancy failure.
5. If the occupancy failure is judged worth attributing, that is new, unscoped work (a per-cycle
   saturation-horizon reconstruction against the unresolved-code table, correlating pre-/post-
   saturation code reuse) — not something this report recommends starting without the Architect's
   sizing of its value against everything else open.

## 6. NFR-021

Message text was never printed or written to any file by either harness script (`g3_h12_replay.py`'s
own JSON output carries it, under `artefacts/`, blanket-gitignored; this report and `l3_gate.py`
carry only counts, code indices, and booleans). `PD2FZ` is the sole real callsign in this report, a
named NFR-021 exception (our own call). Scanned with `nfr021_pre_merge_scan.py` before commit.
