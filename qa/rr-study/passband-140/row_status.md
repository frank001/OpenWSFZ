# `PASSBAND-140` — ROW status (running record, QA)

Spec: `qa/rr-study/2026-09-14-1542-architect-to-qa-spec-g2b-140-passband-rearm.md`
(as amended by Amendment 1, `arch/g2b-passband-140` `4b7b9044`: `WIDE`'s `f_max` also
moves 3000→3075, not just `f_min`).

Updated as each row is checked. Not the final report — that comes after §3.2's full
sequence and §3.5/§3.6.

| row | check | result | detail |
|---|---|---|---|
| **0a** build | **PASS** | 2026-09-14 | Developer's diff (exactly two hunks, `.f_min`+`.f_max` per Amendment 1) independently cross-checked against `origin/main`'s live content — exact match. Both SHA-256s in manifest before any leg ran. `WIDE` independently re-loaded by QA (`p23_common.Decoder verify=True`): SHA and shim version (`20260050`, unchanged) both confirmed. |
| **0b** BASE is what ships | **PASS (fallback)** | 2026-09-14 | `SHA(BASE)`=`db31d351...` ≠ pin `6b2e16a6...` (non-reproducible link, independently re-verified both hashes). Fallback: K60 (committed) vs B60 (this BASE), C2 first 500 cycles, `(10,0.10,60)` — 8782/8782 tuples, **0 differing**. Architect-confirmed: record `db31d351...` as `BASE`, not the pin. See `dll_manifest.json` `_row0b`. |
| **0c** chain fidelity | **PASS** | 2026-09-14 | `PassbandChain row0c`, C2 window (`ts>=260908_193645`, dial `14.074`): `total_rows=57969` (matches spec's own drafted-in count exactly), `rejected=3` (0.0052%), threshold ≤58 (0.1%). `callsign-grammar.json` sha256=`7b581f31b7f0f65191da247eda6568e2f919d96c1414f9b268c39f4943bba37e`. |
| **0d** seam | pending | — | needs B60 through the chain vs C2 live `ALL.TXT` (`seam_fidelity()`) |
| **0e** determinism | pending | — | needs B40r leg |
| **0f** treatment moves | pending | — | needs W40 vs B40 |
| **0g** truncation | pending | — | checked per-leg during decode |
| **0h** C1′ cut | **PASS** | 2026-09-14 | 251st sorted `wsjt-x/wav/*.wav` = `260808_011045.wav`, exact match to spec. |

## Build status

- `BASE`: built, `db31d351484046e9f2430e2536d68850c13adba9c7e74f6c911f96345a85627a`, validated via ROW 0b fallback.
- `WIDE`: built, `ae0c7c213da7c80d47a01b38f3a538ba279cb52bd48c150153b66c33918c00aa`, shim `20260050` (unchanged), independently re-verified by QA. Both DLLs sitting in `artefacts/passband-140/bin/`.

## Tooling built so far

- `qa/rr-study/passband-140/PassbandChain/` — C# managed-chain tool (§3.1), modes `row0c` and `chain`.
- `qa/rr-study/passband-140/row0b_fallback.py` — K60/B60 tuple-identity check (§3.2 ROW 0b fallback).
- `qa/rr-study/passband-140/dll_manifest.json` — binary identity record (§2.1 item 4).

## Not yet built

- Leg runner for §2.2 (B40/W40/B60/B40r/K60 on C2 and C1′, one process per (leg, corpus), params
  asserted per leg — LIVE-GAP-NOW's `decode_leg.py`/`dll_pin.py` pattern, adapted).
- `seam.py` application for ROW 0d.
- Bootstrap/CI machinery for §3.1 (two cluster schemes, wider governs) — reuse
  `live-gap-now/bootstrap.py`, extend for the cycle-cluster scheme per spec.
- §3.5/§3.6 descriptive + gate computation.
