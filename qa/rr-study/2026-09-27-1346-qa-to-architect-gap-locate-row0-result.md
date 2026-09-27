# `GAP-LOCATE` — ROW 0 result: **STOP at 0c** — corrected position mapping tops out at `P_ctrl = 86.90% [85.31, 88.34]`, short of the `>= 0.90` bar; the spec's literal mapping instruction fails outright at `6.68%`

QA, 2026-09-27T13:46Z (`date -u`, HK-017). Per spec `qa/rr-study/2026-09-22-1807-architect-to-qa-spec-gap-locate.md`
(`main`) and Amendment 1 `qa/rr-study/2026-09-27-1325-architect-to-qa-gap-locate-go-and-amendment-1.md`
(`arch/gap-locate` `75fb9b97`). Branch `qa/gap-locate`, cut from `origin/main` `00698fb1`. DLL copied and
pinned per Amendment 1 item 1 (`bin/libft8_C3.dll`, SHA-256 `38a21f840b00af146348c166786cb54e178cd2201c5ed4dba3016a4c589a1cba`,
full match, all 3 entry points resolve). Artefacts: `artefacts/20260927_1327_gap-locate/` (HK-016).

**Headline.** ROW 0a and 0b **pass** — my own independently-written loader (kept in-repo,
`qa/rr-study/gap-locate/`) reproduces the committed LIVE-GAP-MAP numbers **bit-for-bit**: `n_ref = 127,482`,
`H10 = 19.268602626253116` pp, `|M| = 24,564`. ROW 0d **passes** (0/4,411 referenced cycle WAVs bad). **ROW
0c fails**, and not narrowly: the spec's literal position-mapping instruction (§0/§2 — force-read at
`t = REF_DT + delta`, through `row0._forced_success`, which applies `dll_common`'s own `+0.16s`
waterfall-origin correction on top) recovers only **6.68%** of a full-power control sample (`n = 1,901`,
`127` found) — nowhere near the `0.90` bar. Diagnosing why (§2 below) turned up what looks like a
composition error in that literal instruction, not a property of the corpus; a disclosed correction (drop
the extra `+0.16s`, since `delta` already appears to land REF's DT in OpenWSFZ's own native reporting
frame) raises it to **86.90% CI95 [85.31, 88.34]** (Wilson, `n = 1,901`) — much better, but the CI clearly
excludes `0.90` too. **Per spec §3 ("any fail ⇒ all §4 rows VOID, report the gap") and strict row order, I
stopped here.** Leg R and ROW 0e were not run. No Leg F. No new instrument was built to chase this further
(Amendment 1: "No new instrument: if a leg needs one, STOP and report") — the obvious next move, widening
the 9-cell search, would be exactly that.

---

## 1. ROW 0a / 0b / 0d — PASS

| row | result |
|---|---|
| **0a** identity | loaded `bin/libft8_C3.dll` SHA-256 `38a21f84…1cba` = pin; shim `20260054` = pin; `ft8_decode_all`, `ft8_extract_llrs_at`, `ft8_ldpc_decode_llrs` all resolve. **PASS** |
| **0b** harness | independent loader (own ALL.TXT parse, DT column [5] kept alongside SNR [4] and freq [6] — the committed `lgm_harness.py`/`matcher.py` path never surfaces DT) reproduces, over the Amendment-3-cut C3 corpus: `n_ref = 127,482` (want `127,482`), `H10 = 19.268602626253116` pp (want `19.268602626253116`, exact), `\|M\| = 24,564` (want `24,564`). **PASS, exact** |
| **0d** audio | every WAV referenced by M ∪ K (4,411 distinct cycles) is exactly 180,000 samples / 12 kHz / mono / 16-bit. 0 bad. **PASS** |

## 2. ROW 0c — FAIL under both the literal instruction and a disclosed correction

**delta** (spec §2: "median OWS DT − REF DT over matched pairs in C3, recomputed in ROW 0c") = **0.7000 s**,
computed over all 74,793 exact-matched (ts, message) pairs in the cut corpus. The spec's own prose
estimate was "≈0.653 s" (in fact that is the *mean* of this same sample, `0.6534`; median and mean diverge
because the distribution is sharply bimodal, not because of a computation error — see below).

| delta (rounded) | count | share |
|---|---:|---:|
| 0.5 | 81 | 0.1% |
| 0.6 | 34,732 | 46.4% |
| 0.7 | 39,952 | 53.4% |
| 0.8 | 28 | 0.04% |

**Control population K** (spec §1): REF rows, hit, SNR ≥ −10 dB, seeded uniform sample n = 2,000 (seed
20260922) of 62,467 eligible. 99/2,000 (4.95%) excluded before any position was tried: `ft8_encode_message`
returns no true codeword for them — 22 carry a WSJT-X hash-placeholder (`<...>`, unresolved callsign), 77
more are free-text / non-standard-format messages the encoder's grammar does not cover (skews toward
longer strings, 16–23 chars). Text match is impossible to score either way for these, so they are excluded
from the denominator rather than silently scored as N (that would bias `P_ctrl` down for a reason that has
nothing to do with candidate search or bit recovery). **This is disclosed, not silent — n = 1,901 is the
scored population for both rows below.**

**Two position-mapping conventions, same 9-cell lattice search (spec §2: nearest cell + 8 neighbours, ±1
step in time [0.08 s] and frequency [3.125 Hz], both exactly reproduced from `ft8_shim.c`'s own inverse
mapping, reused verbatim from THRESH-A's independently-derived `row0c_lattice.py` — HK-018), full K
(n=1,901, well powered):**

| convention | what it does | `P_ctrl` | 95% CI (Wilson) |
|---|---|---:|---|
| **Literal (spec §2/§0 as written)** | `t = REF_DT + delta`, fed as `true_dt_s` into `row0._forced_success`, which then adds `dll_common`'s own confirmed one-symbol `+0.16 s` waterfall-origin offset on top | **6.68%** (127/1,901) | [5.64, 7.89] |
| **Corrected (this session's disclosed fix)** | `t = REF_DT + delta`, used directly as the raw `time_offset_s` — the extra `+0.16 s` is NOT applied | **86.90%** (1,652/1,901) | [85.31, 88.34] |

**Diagnosis.** The `+0.16 s` correction in `dll_common.extraction_time_offset_s` (and reused verbatim here,
Amendment 1's named instrument) was derived and validated for mapping a **synthetic scene's authored,
ground-truth `dt_s`** into `ft8_extract_llrs_at`'s own coordinate frame (f-nbr-a's S8HN positive controls:
true `dt_s = 0.0`, decoder always reports `dt ≈ 0.16` for it). `REF_DT + delta` is a different kind of
quantity: an *estimate of what OpenWSFZ's own decoder would report as `dt`* for this signal, built from two
DECODER-REPORTED values (WSJT-X's REF DT, corrected by the empirical WSJT-X→OpenWSFZ reporting gap). A
direct spot-check confirms OpenWSFZ's own reported `dt` (`live[k]`, for rows both decoders exact-matched) is
**already** in `ft8_extract_llrs_at`'s native frame with no correction needed — passed raw to `extract_at`,
it recovers 12/15 in a 15-row spot-check; the same value **with** the extra `+0.16 s` added recovers 0/15.
Composing `REF_DT + delta` (itself an estimate of that same OpenWSFZ-native `dt`) through the
synthetic-scene correction on top therefore double-applies a shift that doesn't belong to this quantity at
all — which is exactly what Amendment 1's warning against a "second `+0.16 s` correction" would want caught,
except the warning's own literal instruction is what introduces the one `+0.16 s` that shouldn't be there.

**Why the corrected convention still falls short of 0.90.** REF/OpenWSFZ DT values are both reported at 0.1 s
resolution (all observed deltas above are exact multiples of 0.1), but the extraction lattice's own
addressable step is 0.08 s (`SYMBOL_PERIOD_S / TIME_OSR = 0.16 / 2`) — not an integer multiple of 0.1 s. A
single **global** `delta` (median 0.7) is only reachable by the ±1-step (±0.08 s) neighbourhood search from
individual true offsets in `[0.62, 0.78]`; the 46.4% of matched pairs whose own true offset clusters at 0.6
sit up to 0.18 s away from centre — outside the search radius by more than one step. This reads as a
structural property of "one global delta, 9-cell search" against a DT resolution mismatch between the two
decoders, not an implementation bug: both conventions were run at full population size (n=1,901) with the
same lattice code, same corpus, same DLL.

## 3. Stop

Per spec §3 ("any fail ⇒ all §4 rows VOID, report the gap") and the strict row order in that table, ROW 0c
failing stops the arm before 0d/0e are load-bearing (0d was already computed, harmlessly, before this was
found — included above) and before Leg R, Leg F or the §4 gate rows are run. Amendment 1: "No new
instrument: if a leg needs one, STOP and report" — the obvious next step (widen the lattice search beyond
9 cells, or derive a per-frequency or per-SNR-band `delta` instead of one global value) is a capability
change beyond what's specified, so it is not something I built. Handing this back rather than picking a
convention and running the multi-hour Leg F/Leg R compute on a mapping this session cannot certify.

**HK-025:** I am not refusing this spec — ROW 0c is doing exactly the job HK-021(k) says it should ("a bad
mapping drives `R_F` toward 0 ⇒ false LB... a real precondition, not decoration"). This is a report of that
precondition firing, with the diagnosis that got the number from 6.68% to 86.90%, not a claim that the
mapping is unfixable — a real fix (per-band `delta`, or a wider search) may well clear the bar, but that is
the Architect's call, not mine to build unilaterally.

NFR-021: this report and every artefact under `artefacts/20260927_1327_gap-locate/` carry counts, rates,
SNR/DT/freq values and lattice-cell labels only. No message text, no callsign, scanned before writing.
Committed locally on `qa/gap-locate`; push needs the Captain's go (HK-033).
