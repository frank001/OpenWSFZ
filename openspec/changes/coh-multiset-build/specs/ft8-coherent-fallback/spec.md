## ADDED Requirements

### Requirement: The coherent fallback tries four further bit-metric sets where V3 gives no CRC-valid output

When `decoder.coherentFallbackMultiSet` is true and the coherent fallback is on, for each candidate on which the fallback's V3 ran and its BP returned no CRC-valid output, the fallback SHALL try the following sets in this fixed order and stop at the first CRC-valid output: C1 (order 1 on power), J2 (joint pairs), J3 (joint triples), N1 (order 1 on magnitudes, each bit divided by the larger of its two maxima, 0 if both are 0). Each set SHALL be formed from the per-symbol correlations already computed for the candidate at the same fine-sync estimate, SHALL be decoded by belief propagation only (no OSD) with the production normalisation, and SHALL be followed by the CRC-14 check. The grouping, magnitude score, Gray map, bit order and sign (positive = bit 1) SHALL be those of the reference `qa/rr-study/coh-multiset/ms_metrics.py` at commit `96aa80d4`. The first CRC-valid output SHALL take the existing fallback path unchanged (known-payload check, SNR, the F1b gate at `CF_T1_DB`, dedup, plausibility, publication). A known or gated-out payload SHALL NOT be retried with a later set.

#### Scenario: V3 gives no CRC-valid output and a set does

- **WHEN** the flag is on and a candidate's V3 + BP gives no CRC-valid output and J2 (after C1 failed) gives one
- **THEN** the walk SHALL stop at J2, the payload SHALL follow the existing path (F1b gate included), and the result's provenance SHALL be 2

#### Scenario: V3 gives a CRC-valid output

- **WHEN** the flag is on and a candidate's V3 + BP gives a CRC-valid output, whether its payload is known, new, gated or gated out
- **THEN** no further set SHALL be computed for that candidate, and the output SHALL be exactly the output the build without the flag produces

#### Scenario: A candidate the fallback did not attempt

- **WHEN** the flag is on and the fallback did not attempt a candidate
- **THEN** the multi-set walk SHALL NOT run for it

#### Scenario: A set's payload is gated out

- **WHEN** a set gives a new CRC-valid payload whose F1b exceeds `CF_T1_DB`
- **THEN** the payload SHALL NOT be published and the walk SHALL NOT continue with a later set

### Requirement: The multi-set walk is behind a default-off flag

The configuration SHALL provide `decoder.coherentFallbackMultiSet` (boolean, default `false`), read once per decode cycle as `decoder.coherentFallbackEnabled` is, and acting only when `decoder.coherentFallbackEnabled` is true. It SHALL have no Settings-page control. A configuration update that does not mention it SHALL leave it unchanged. With the flag false the decoder SHALL make the same native calls and produce the same outputs, counters (apart from added zeros) and order as the build without this change, both with the fallback on and with it off. The flag SHALL reach native as a per-call parameter, not as a process-global setting.

#### Scenario: Flag off changes nothing

- **WHEN** `decoder.coherentFallbackMultiSet` is false and a fixed set of recorded cycles is decoded with the fallback on, then with it off
- **THEN** the `ALL.TXT` lines, UDP datagrams, panel events and QSO-channel batches SHALL be identical (outcome fields) to those of the build before this change

#### Scenario: A partial configuration update leaves the flag as it was

- **WHEN** a configuration update that does not mention `decoder.coherentFallbackMultiSet` is saved while the flag is true
- **THEN** the flag SHALL still be true afterwards

### Requirement: Every fallback result records which set produced its payload

Each fallback result SHALL carry a provenance value: 0 for V3, 1 for C1, 2 for J2, 3 for J3, 4 for N1 and -1 for none. It SHALL be available in the harness outputs and the per-cycle counters. `ALL.TXT`, UDP and panel formats SHALL be unchanged, and the existing native struct layouts SHALL keep their sizes.

#### Scenario: Serial and parallel runs agree on provenance

- **WHEN** the same cycle is run through the serial and the parallel fallback paths with the flag on
- **THEN** the outcome and the provenance SHALL be equal row by row

### Requirement: A diagnostic export returns every set for one position

A diagnostic-only native export SHALL take `(pcm, freq, time offset)` as `ft8_coherent_fallback_at` does and return the fine-sync estimate, V3's BP outcome and, for each of C1, J2, J3 and N1, its 174 raw values, BP result, CRC flag and payload, computed for every set whether or not the walk would have reached it, and the walk's result. Existing exports SHALL keep their contracts.

#### Scenario: All four sets are returned

- **WHEN** the export is called at a position where V3 gives a CRC-valid output
- **THEN** it SHALL still return the raw values and BP results of all four sets, and the walk's result SHALL report that the walk did not run
