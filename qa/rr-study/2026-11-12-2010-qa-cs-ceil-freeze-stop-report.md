# CS-CEIL freeze: STOPPED at the slot rule. The spec's quiet-tail floor match does not exist on this night. V-REPRO passes. No relocated output exists.

**Written:** 2026-11-12, `date -u` read 20:09:35Z. **To:** Architect, then the Captain. **Spec:** `arch/cs-model-ceiling` `6d911263` with Amendment 1 (`fc82317a`). **Code:** `qa/cs-ceil/cc_lib.py`, `cc_prep.py`, `cc_repro.py` (committed with this record; nothing past the freeze has been written: no fit, no copy, no relocated forced decode).

## 1. What ran (no relocated output)

| step | result |
|---|---|
| **V-CAT** (my check, not a spec row) | `nrtax_defs.categorise` on the rebuilt neighbours reproduces **all 11,960** NR-TAX tags; CS-NR 700, IW-NR 73, CS mixed 169 of 700 (matches `result_nrtax.json`, 24 %), so **CS-pure = 531** |
| groups | CTRL-HIT 300 drawn (seed 20261112, band-matched A/B/C/D = 4/50/86/160 against CS-NR 9/116/201/374 scaled), from 474 eligible CS hits decodable in place; CTRL-WEAK 73 (bands C 27, D 46: **no band A or B**, see 3) |
| **V-REPRO** (spec 3, A1.4) | forced legs in place on the stored R3 (R2 in 18 cycles), `gr_forced.force_cycle` unchanged: CS-NR **700 of 700** not decodable, CTRL-HIT **300 of 300** decodable, CTRL-WEAK **73 of 73** not decodable; identical to NR-TAX's stored record in all 1,073. **PASS** (28 s, PC quiet) |

## 2. The finding: no quiet tail exists on `20260925_2010`

The spec (section 1) takes the floor from "the quiet tail 13.2 to 14.8 s, after the FT8 transmissions end". My F1 check measured it:

- WSJT-X dt runs from -2.5 to +2.4 s (1st to 99th percentile -1.3 to +1.7). With the product's offset (start = dt + 0.6 s, end = start + 12.64 s) the **latest signal end in a cycle has a median of 14.94 s (25th to 75th percentile 14.34 to 15.04, maximum 15.64): in all 400 cycles at least one signal is still on after 13.2 s.**
- The same dt spread puts the **next period's early signals** inside the last seconds of this buffer. The stored buffers confirm it: R3's RMS is 0.07 to 0.10 across the window but **0.14 to 0.20 in the last second**, and O is flat at about 0.20 throughout.
- In the no-copy pilot, the slot's in-window PSD minus its own tail PSD has a **median of -13.9 dB** (5th to 95th percentile -22.6 to +1.1 dB). A noise-only slot cannot be 14 dB *quieter* during the transmissions than after them; the tail is polluted by other periods' signals, not quiet. So A1.3's X (median + 1.0 = **-12.9 dB**) is computed on a floor that is not a floor.
- With F1's fix (tail window starts after the latest END of any n_ref signal overlapping the row's band, minimum 0.4 s) **96 of 700 CS-NR rows have no tail window at all**; for the rest the tail still contains next-period starts.

## 3. What the rule as written does to V-SLOT (a validity row, VOID if it fails)

| group | rows | blocker rule only (no signal within 60 Hz) | + tail match, no X | + tail match + A1.3 X (frozen as specified) |
|---|---:|---:|---:|---:|
| CS-NR | 700 | **93.7 %** | 38.4 % | 27.6 % |
| CS-pure | 531 | 93.8 % | 39.4 % | 27.3 % |
| CTRL-HIT | 300 | 93.7 % | 40.0 % | 23.7 % |
| CTRL-WEAK | 73 | 94.5 % | 42.5 % | 21.9 % |

V-SLOT needs 90 % per group. **The spec as written VOIDs at the freeze.** The blocker rule alone passes (about 20 free 60 Hz slots per cycle at the median; 17 of 355 cycles with none). Also: CTRL-WEAK has no band A or B rows (the IW rows are all at or below -10 dB), so it measures the optimism of the weak bands only, which strengthens the A1.4 caveat.

## 4. What I did not do, and the options

I did not change the slot rule: it is the Architect's frozen design and the floor match is its safeguard against an over-clean slot. **No fit, copy or relocated decode was run.** Options, QA's order of preference:

1. **Replace the tail by an in-window floor, same buffer, same window, no tail.** The slot must be clean *during* the transmissions: its in-window PSD (0.5 to 13.1 s) must be no more than **X dB above the cycle's median in-window PSD of the blocker-free slots**, with X = 1.0 dB (a fixed bar that matches the spec's own ±1.0 dB tolerance, HK-038: that number is the spec's, not a fit to the data). The pilot reports the distribution; a cycle with no blocker-free slot gives no slot. The floor match to the row's own band disappears; **its job (calibrating the optimism of a cleaner-than-real slot) is already done by CTRL-WEAK and CTRL-HIT, which relocate under the same rule.** V-SLOT then sits near the 93.7 % blocker-only level and I report it per group before the run.
2. **A floor reference from gaps beside the row** (in-window PSD in the nearest blocker-free windows within about 200 Hz): closer to the spec's intent, more code, and it needs its own bar from data on file.
3. **Do not run CS-CEIL** on this night (its stack is old, spec 5) and take the lever as closed on SM-2 grounds without the ceiling: not recommended, the question remains useful.

## 5. State

Nothing is frozen beyond V-REPRO and the group lists (`_qa-scratch\cs-ceil\frozen\cc_groups.json`, v_repro.json; numbers only). The slot table in `cc_groups.json` was produced with the spec's rule and is **not** a frozen input; it is overwritten when the rule is ruled. The PC window is not yet needed; once the rule is ruled I need about 1 to 1.5 h for the freeze (slot code, fit and run code, self-test with mutation kills, group lists) and then the window (a few minutes to 45 min).
