# QA Review & Hand-back (Round 2) — Synthesiser L7 (packing) & L8 (LDPC)

**Reviewer:** QA · **For:** Developer · **Date:** 2026-06-06
**Branch:** `feat/rr-study-synth` · **Reviewed commit:** `5ebcd09` (fixes for F-101…F-105)
**Parent docs:** [`QA-REVIEW-L7-L8.md`](./QA-REVIEW-L7-L8.md) (round 1) · [`DEV-BRIEFING-L7-L8.md`](./DEV-BRIEFING-L7-L8.md) · [`BUILD-PLAN.md`](./BUILD-PLAN.md) · [`../STUDY-SPEC.md`](../STUDY-SPEC.md) (§5)

---

## Verdict: **CHANGES REQUIRED — returned, not approved** (narrow scope)

Automated baseline is healthy: `pytest tests/` → **85 passed, exit 0** (two independent runs).
Three of the five round-1 findings are cleared cleanly. The two original blockers (F-101, F-102)
are *improved* but not fully discharged — and both fail for the same root cause: **WSJT-X reference
programs were substituted for `ft8_lib`, rather than the algorithm being re-grounded in the paper.**

The Captain has ruled on the scope of the remaining work (2026-06-06): **pragmatic**. The constant
tables are protocol facts with exactly one correct value and may remain; the §5 WSJT-X decode gate
is accepted as the independence proof. The required rework is therefore confined to **provenance
honesty in the logic** and **one inaccurate test claim**. This is close — clear the two items below
and hand back; I will run the §5 gate.

> Note for the record: QA independently hand-verified the numerics —
> `Q1ABC → n_base 3 957 069 → n28 10 214 965`, `FN42 → igrid4 10 342`, full 77-bit word
> `1 136 611 074 065 201` — and confirmed the LDPC generator/`Nm` tables are the authentic protocol
> matrices. **The engineering is correct.** The objections below are about provenance and method,
> not demonstrated defects.

---

## Cleared in round 2 ✓

- **F-103** — `encoder.py` docstrings now state all layers implemented, §5 gate pending. Accurate.
- **F-104** — BUILD-PLAN L9 corrected to "🔶 implemented, §5 gate pending."
- **F-105** — Unreachable `"CQ NNN"` branch removed from `_pack_callsign`.
- **F-101 (crib removal)** — `native/ft8_lib` submodule removed from the tree. Confirmed the
  remaining `native/ft8_lib_build/patched/` holds only `decode.c`/`monitor.c` (the decoder side,
  pre-existing on `main`) — **none** of the packing/encode/`constants` source that would crib L7/L8.
  This part of F-101 §4 is satisfied.

---

## Still open — clear before resubmission

### F-101R — Logic provenance still cites WSJT-X implementation source *(Blocking — Captain's ruling)*

`packing.py` removed all `ft8_lib` strings but replaced them with **WSJT-X Fortran reference
programs** — `std_call_to_c28.f90`, `grid4_to_g15.f90` — described as *"the published algorithm"* /
*"the standard callsign packing algorithm."* DEV-BRIEFING §1 forbids porting from **WSJT-X by name**;
WSJT-X is the common ancestor of both `ft8_lib` and OpenWSFZ, so this re-creates the shared-ancestor
risk the clean-room mandate exists to prevent.

**Per the pragmatic ruling, required:**
1. **Constant tables may stay** (LDPC generator & `Nm`, the `_CHAR0–3` alphabets, `NTOKENS`,
   `MAX22`, `MAXGRID4`, special-token values) — they are protocol facts, one correct value. Cite
   them honestly as the published FT8 protocol constant tables; do **not** frame a `.f90` program as
   their algorithmic source.
2. **The packing logic is the clean-room deliverable** — `_normalize_to_c6`, `_pack_basecall`,
   `_pack_grid_field`, `_pack_callsign`, `pack_message`. Re-cite these to the **QEX 2020 paper's
   field definitions** (§III-A/§III-B, Tables I/II) and strike every reference describing a WSJT-X
   `.f90` program as the source of the algorithm/logic.
3. Add a one-line attestation in each of `packing.py` / `ldpc.py` that the encoding logic is original
   code derived from the paper's field definitions (tables transcribed as protocol facts).

### F-102R — Correct the inaccurate "independently-derived" claim *(Required, non-blocking)*

Hardcoding `_CQ_Q1ABC_FN42_EXPECTED_INT` is a genuine improvement — it now catches future drift in
`packing.py`'s constants, and QA has independently confirmed the value is correct. **Keep it.**
However, the docstring calling it an *"independently-derived worked example"* is inaccurate: it was
hand-traced from the same WSJT-X `.f90` programs the implementation uses — oracle and instrument
share a source.

**Per the pragmatic ruling** (the §5 WSJT-X gate is the accepted independence proof), required:
- Reword the `test_packing.py` provenance comment to state plainly that the vector is derived from
  the **same protocol field definitions** as the implementation (a regression guard against constant
  drift), and that **true independence is established by the §5 WSJT-X decode gate** — not by this
  unit test. Remove the "independently-derived/independently-sourced" language.
- A separately-published external vector remains welcome if you have one, but is no longer required.

---

## Carries over, still sound

- LDPC test design (1000-word generator↔H self-consistency, all-zeros/all-ones, exhaustive
  single-bit-flip detection) — the high point; unchanged.
- Consistent MSB-first `msg | CRC | parity` transmit ordering; Gray coding correctly left to L3.
- Length validation, determinism, case-insensitivity, supported/unsupported coverage.

---

## Definition of done for resubmission

1. F-101R cleared: logic re-cited to the QEX paper; all WSJT-X-`.f90`-as-algorithm language struck;
   constant tables cited honestly as protocol facts; original-logic attestation added.
2. F-102R cleared: `test_packing.py` provenance reworded; hardcoded literal retained.
3. `pytest tests/` green.
4. Hand back to QA. The **§5 WSJT-X self-validation gate is QA's to execute** and is the accepted
   proof of correctness/independence under the Captain's pragmatic ruling.

— QA
