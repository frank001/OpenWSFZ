# `OSD-FA-A` Amendment 1, Part 0 — result: **P0-1 FIRES — the counter build does not perturb decoding, or its text, on noise-only input in this harness**

QA, 2026-09-11 16:14Z (`date -u`, HK-017). Spec:
`qa/rr-study/2026-09-11-1540-architect-to-qa-osd-fa-a-amendment-1-current-binary-and-fp-decision.md`
§1 (`arch/osd-fa-a`, `bb26778`, read via `git show`, local branch not present as a file in this
worktree — flagged as second-hand only in the sense that I read the committed blob, not that I
trust it unverified: every figure below is independently re-measured, not taken from the spec's
own prose). Harness: `qa/rr-study/osd-fa-a/part0_runner.py` (new), `part0_compare.py` (new), both
committed alongside this file.

**Headline: `P0-R1` clears (S1 == S2, byte-for-byte, message text included, on all 4,000 slots —
the harness is deterministic on one binary). `P0-1` FIRES: S1 == C in every field on every one of
4,000 slots, message text included — zero differences of any kind.** Citation guard (g) is
**resolved for this population and this harness** (HK-022 scope: nothing wider — this is one
noise-only corpus, one ctypes harness, one pair of binaries). `ROW 0r`'s 246 text-only differences
did not come from the `20260049` → `20260050` binary change; they came from the run (the
Architect's own candidate explanation in spec §1.1, now confirmed rather than merely plausible).

---

## 1. Method

| quantity | value |
|---|---|
| Population | 4,000 WAVs, `D:\Projects\claude\OpenWSFZ\qa\rr-study\awgn-fp-replay\_work\m1m4_s5\` (Architect worktree root, gitignored, read in place by absolute path, not copied) |
| Instrument | `extract_llrs_ctypes.ExtractLLRs`, extended additively with an `ft8_set_ap_bits` binding (Part 0's own new code). Reused, not reimplemented (HK-018) — `ExtractLLRs.__init__` binds `ft8_decode_all` but never *calls* `ft8_set_decode_params`, which **is** spec §1.2's "default decode params (`ft8_set_decode_params` not called)" |
| PCM convention | `int16 / 32768.0` → float `[-1, 1]`, **no further RMS-targeting rescale** — matches `tests/OpenWSFZ.Ft8.Tests/WavReader.cs` and `AwgnFpReplayTests.cs`'s own `SetApBits([],[])` → `DecodeAll(pcm)` path exactly (the harness behind `ROW 0r`'s "before" CSV). See §4 for a disclosed correction: this was **not** the first thing tried |
| AP bits | `ft8_set_ap_bits([], 0, [], 0)` called before **every** decode (spec §1.2 "cleared per slot") |
| File order | `sorted()` over filenames as strings — see §4, a disclosed correction from the literal spec reading |
| Legs | `S1`/`S2`: `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll`, shim `20260050`, SHA256 `6b2e16a6…4f85c`. `C`: `artefacts/2026-09-03-f001-l3-shim-rebuild/libft8-20260049-prechange.dll`, shim `20260049`, SHA256 `ce02c7ba…153e`. Each leg a **separate OS process** (`python part0_runner.py` invoked three times), run **sequentially** |
| Pin assertion | in-run, at construction (`ExtractLLRs(verify=True, expected_sha256=…, expected_shim_version=…)` raises before any WAV is touched — HK-021(p)) |

## 2. ROW 0 / Part 0 rows, strict order (HK-021(r), code: `part0_compare.py`)

| row | predicate | result |
|---|---|---|
| P0-0a | any leg's loaded DLL SHA ≠ its pin | **clear** — all three match (asserted twice: in-run at construction, and again by the compare script from each leg's own recorded `dll_sha256`/`shim_version`) |
| P0-0b | any leg decodes ≠ 4,000 slots | **clear** — `S1=4000 S2=4000 C=4000`, 0 AV-contained crashes on any leg |
| P0-R1 | `S1` vs `S2`: any field differs on any slot | **clear (does not fire)** — `0/4,000` slots differ, in every field, including message text. Independently re-verified by a second, simpler tuple-sort comparison outside `part0_compare.py`'s own pairing logic: `0/4,000` |
| P0-1 | `S1` vs `C`: zero differences in every field | **FIRES** — `0/4,000` slots differ. Same independent re-verification: `0/4,000` |
| P0-2 | `S1` vs `C`: any count/freq/dt/snr difference | not reached (P0-1 matched first) |
| P0-3 | `S1` vs `C`: counts/numerics identical, text differs | not reached |

**HK-021(k) check:** P0-R1 changes the verdict (had it fired, P0-1/2/3 would be unreadable and this
would STOP). It cleared, so P0-1/2/3 are readable — the precondition does the work the spec asked
of it.

**Per-slot classification method (disclosed, spec §1.2 "diff per slot, per field... never assert
byte-identity"):** decodes within a slot are paired across legs by `(freq_hz, dt_s)`, sorted
ascending, then `snr`/message compared on the paired records; a count mismatch is its own category,
never paired. This matters only for a multi-decode slot (population runs ~0.11 decodes/slot). Given
the result is **zero differences of any kind**, the pairing choice is moot here — it never had to
break a tie — but is disclosed because a different result would have made it load-bearing.

## 3. Descriptive (never gated, spec §1.3)

**`<...>` rendering counts**, this run vs. the two committed CSVs named in spec §1.3:

| source | decodes | `<...>` renderings |
|---|---:|---:|
| `awgn-fp-replay/results/m1m4_s5_decodes.csv` (`20260049`, `4a7fb3d`) | 454 | 118 |
| `fp-parity/results/m1m4_s5_20260050_decodes.csv` (`ROW 0r` "after") | 454 | 118 |
| S1 (this run) | 454 | 118 |
| S2 (this run) | 454 | 118 |
| C (this run) | 454 | 118 |

All five agree exactly on both totals. Redaction maps callsigns, not `<...>`, so this count is
readable per spec's own instruction; checked before relying on it (both files' `<...>` tokens are
literal decoder hash-miss renderings, not a redaction artefact — confirmed by inspecting the
committed CSVs' own header/format before counting).

**Wall-clock per leg, sequential (spec: "answers the Captain's 'does it only hit performance?' on
a like-for-like basis"):**

| leg | wall time |
|---|---:|
| S1 | 294.0 s |
| S2 | 291.5 s |
| C | 283.0 s |

No meaningful separation between `S1`/`S2` (same binary) and `C` — `C` is in fact the fastest of
the three, inside plausible run-to-run system noise. No performance signal, descriptively.

## 4. Two disclosed corrections, found and fixed before committing to the full run

Neither changes a row's verdict — both were caught by smoke-testing on small slices first, exactly
the discipline HK-018/HK-021 ask for, before spending ~4.9 minutes/leg on the full population.

1. **PCM convention.** The first attempt reused `p23_common.py`'s own `read_wav` (raw int16-scale
   magnitude, RMS ≈ 3,000 on a real signal slot) on the reasoning that "no PCM normalisation"
   meant "skip `normalise_rms` and stop." That produced **zero decodes across a 200-file smoke
   test** — a 15,000×-too-loud operating point relative to what the decoder expects (production's
   own `NormalisePcm` targets RMS 0.20). Read `tests/OpenWSFZ.Ft8.Tests/WavReader.cs` (the actual
   harness behind `ROW 0r`'s own "before" CSV) instead: it converts `int16 / 32768.0` to reach
   `[-1, 1]`, then calls `DecodeAll` directly with **no further rescale**. Switching to that
   convention immediately recovered a plausible event rate (22/200 in the corrected smoke test,
   11%, in the neighbourhood of `FP-PARITY` P3's normalised **10.325%** — not expected to match
   exactly, since P3's rate carries the additional RMS-targeting step this leg deliberately omits).
2. **Filename pattern.** Trial indices run `0..1999`, not zero-padded past 3 digits (`t999` →
   `t1000`, one character wider). A `\d{3}` filename pattern silently accepted only 2,000/4,000
   files (all of part 0's `t000`–`t999` plus none of `t1000`–`t1999`, and none of part 1 at all,
   by coincidence of how Python's glob ordering surfaced the first smoke test) — caught because the
   smoke test's own file count didn't match the expected 4,000, not because anything crashed.
   Fixed to `\d+`. **Consequence: "sorted file order" is `sorted()` over these variable-width
   filename strings**, e.g. `t1000` sorts before `t999`, not numeric `(part,trial)` order. Applied
   identically to all three legs (same function, same file set), so this affects only which
   callsign-table history each leg accumulates as it runs — a property of the *harness*, held
   constant across `S1`/`S2`/`C` alike, not a threat to either P0-R1 or the S1-vs-C reading.

## 5. NFR-021

Message text is real decoder output over synthetic AWGN scenes; per-leg JSON (raw text, all 4,000
slots) lives under `artefacts/2026-09-11-osd-fa-a-part0/` (blanket-gitignored), enforced by
`part0_runner.py` refusing any `out_json` path outside `artefacts/` before writing. This report,
`part0_runner.py` and `part0_compare.py` carry counts, code indices, SHAs and booleans only —
`part0_compare.py` never reads message text into anything it prints or writes beyond an in-memory
equality/pairing check. Scanned with `nfr021_pre_merge_scan.py` before commit (both new `.py`
files and this report).

## 6. Recommendation

**Part 0 is complete; no further reading of it is authorised.** Per the spec's own running-order
table (§6): the rest of `OSD-FA-A` (base ROW 0 → D → A → B → C → E1 → E2) needs the Captain's
separate go, and `E3` additionally needs `BAR_H` ratified by the PO before its `k` is computed.
Nothing in this result licenses either on its own — this was a same-harness A/B on one noise-only
corpus, settling one citation guard, not a statement about the live FP question Part 0 was carved
out ahead of.
