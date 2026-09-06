# QA — NFR-021 incident: `AwgnFpReplayTests` clobbered 12 redacted committed CSVs; `pre_merge_check.py` fix applied

**2026-09-06 09:13Z**, QA (AI-assisted). Found while independently verifying the Developer's
`test/repin-shim-20260050` fix (`dev-tasks/2026-09-05-1931-awgnfpreplaytests-stale-shim-sha-pin.md`)
after running `tools/pre_merge_check.py` twice against it, per the Captain's request. Fix applied
directly (`tools/pre_merge_check.py`, not `src/`/`native/` — no HK-011 gate), on the Captain's
explicit instruction ("add the missing filter").

---

## 0. What happened

Running `pre_merge_check.py`'s full test suite (twice, this session — once against `main`, once
against `test/repin-shim-20260050`) silently overwrote **12 previously-reviewed, redaction-mapped**
result CSVs with raw, unredacted native-decoder output, in the working tree:

```
qa/rr-study/awgn-fp-replay/results/m3_s1_decodes.csv
qa/rr-study/awgn-fp-replay/results/m1m4_s5_decodes.csv
qa/rr-study/awgn-fp-replay/results/row0d_s1_complement_decodes.csv
qa/rr-study/awgn-fp-replay/results/row0b_baseline_decodes.csv
qa/rr-study/awgn-fp-replay/results/row0c_lp_baseline_decodes.csv
qa/rr-study/awgn-fp-replay/results/row0c_lp_minus10_decodes.csv
qa/rr-study/awgn-fp-replay/results/row0c_lp_plus10_decodes.csv
qa/rr-study/awgn-fp-replay/results/row0c_minus10_decodes.csv
qa/rr-study/awgn-fp-replay/results/row0c_plus10_decodes.csv
qa/rr-study/awgn-fp-replay/results/row0k_after_decodes.csv
qa/rr-study/awgn-fp-replay/results/row0k_before_decodes.csv
qa/rr-study/fp-parity/results/m1m4_s5_20260050_decodes.csv
```

Each of these had been reviewed and redacted at commit time (see `4a7fb3d`'s message and
`REDACTION-MAP-M1-M4.md` / `REDACTION-MAP-ROW0K.md` / `REDACTION-MAP.md`), with decoder-hallucinated
callsign-shaped tokens (RUNBOOK §7.5's documented CRC-14-coincidence-in-AWGN class — real personal
data under NFR-021 despite not being real transmissions) rewritten to `<RDCTMnn>`-style placeholders,
byte-level CRLF/BOM-preserving, and re-scanned to 0 before commit.

`AwgnFpReplayTests.DecodeDirectory` (`tests/OpenWSFZ.Ft8.Tests/AwgnFpReplayTests.cs`) writes a fresh
decode CSV to these exact committed paths on every run, from live decoder output, with no redaction
step. On this machine `qa/rr-study/awgn-fp-replay/_work/` (the gitignored WAV corpus the fixture
reads) happens to be populated from a prior manual arm run, so the fixture's precondition was
satisfied and it ran to completion instead of failing fast — clobbering all 12 files, on both the
native Windows leg and the WSL Debian leg (same repo checkout via `/mnt/d/`), each time.

**Exposure was contained throughout: never staged, never committed, never pushed.** A second,
independent near-miss occurred in parallel: the Architect's `git add -A` (while committing an
unrelated `G9b` fix) nearly swept these 12 files plus this session's unrelated dev-task note into an
`arch(...)` commit; caught via their own NFR-021 `scan()` before commit, reset, recommitted with only
their intended file. See their message to this session, 2026-09-06, for their own account of that
slip.

## 1. Verification — mechanical, not asserted

For every one of the 12 files, the committed (`HEAD`) version's redaction-placeholder count matched
its original redaction-commit record exactly; the working-tree version's count was **0** in every
case:

```
m3_s1_decodes.csv                    HEAD=311  WORKING=0
m1m4_s5_decodes.csv                  HEAD=250  WORKING=0
row0d_s1_complement_decodes.csv      HEAD=38   WORKING=0
row0b_baseline_decodes.csv           HEAD=4    WORKING=0
row0c_lp_baseline_decodes.csv        HEAD=3    WORKING=0
row0c_lp_minus10_decodes.csv         HEAD=4    WORKING=0
row0c_lp_plus10_decodes.csv          HEAD=3    WORKING=0
row0c_minus10_decodes.csv            HEAD=4    WORKING=0
row0c_plus10_decodes.csv             HEAD=4    WORKING=0
row0k_after_decodes.csv              HEAD=4    WORKING=0
row0k_before_decodes.csv             HEAD=4    WORKING=0
fp-parity/m1m4_s5_20260050_decodes.csv  HEAD=250  WORKING=0
```

`qa/rr-study/nfr021_pre_merge_scan.py --against origin/main` confirmed the pre-remediation state:
820 distinct non-compliant tokens across these 14 files (12 above + 2 unrelated, see §3), 1304
occurrences.

Before remediating, I characterised the S1 files specifically (`m3_s1_decodes.csv`,
`row0d_s1_complement_decodes.csv`) because S1 is a genuine-signal SNR ladder, not pure noise, and
the Architect flagged (correctly, without ruling on it) that NFR-021 requires the *injected* message
content itself to be Q-prefix synthetic — a different question from RUNBOOK §7.5's noise-floor
class. Token-repetition analysis on `m3_s1_decodes.csv` settles it:

- **4 distinct Q-prefix tokens, 2303 occurrences** — one token accounts for 2300 of them. This is
  the single deliberately-injected synthetic station, decoding correctly across the SNR ladder.
  Fully compliant.
- **645 distinct non-Q-prefix tokens, 656 occurrences — 634/645 (98.3%) occur exactly once.** This
  is the same non-repeating signature already on record for the noise-floor CRC-coincidence class
  (cf. the withdrawn `decode-implausibility-marking` proposal's own finding: "0 of 161 distinct FP
  callsign tokens ever repeat"). These are RUNBOOK §7.5's phenomenon extending into the S1 ladder's
  low-SNR rungs, not a corpus-generation defect — the actual injected content is clean.

## 2. Remediation

Restored all 12 files to their compliant committed state:

```
git checkout -- qa/rr-study/awgn-fp-replay/results/m3_s1_decodes.csv \
  qa/rr-study/awgn-fp-replay/results/m1m4_s5_decodes.csv \
  qa/rr-study/awgn-fp-replay/results/row0d_s1_complement_decodes.csv \
  qa/rr-study/awgn-fp-replay/results/row0b_baseline_decodes.csv \
  qa/rr-study/awgn-fp-replay/results/row0c_lp_baseline_decodes.csv \
  qa/rr-study/awgn-fp-replay/results/row0c_lp_minus10_decodes.csv \
  qa/rr-study/awgn-fp-replay/results/row0c_lp_plus10_decodes.csv \
  qa/rr-study/awgn-fp-replay/results/row0c_minus10_decodes.csv \
  qa/rr-study/awgn-fp-replay/results/row0c_plus10_decodes.csv \
  qa/rr-study/awgn-fp-replay/results/row0k_after_decodes.csv \
  qa/rr-study/awgn-fp-replay/results/row0k_before_decodes.csv \
  qa/rr-study/fp-parity/results/m1m4_s5_20260050_decodes.csv
```

Re-scan confirmed **0 non-compliant tokens** in this path afterward.

## 3. Two unrelated flags, left alone

The same scan flagged `.gitignore` (3 tokens) and `TESTING_STRATEGY.md` (1 token) in the wider
diff vs. `origin/main` — pre-existing committed content, not working-tree contamination, and no
callsign-shaped strings visible on inspection (`.gitignore`'s addition documents the `_work/`
exclusion referenced above; `TESTING_STRATEGY.md`'s addition is §4.7 itself, quoted below).
Likely scanner false-positives on prose; out of scope for this incident, not remediated here.

`row0_verdicts.txt` remained modified (aggregate slot/event counts and timestamps only, no
callsigns) — harmless, left as-is; a human commit decision, not a privacy matter.

## 4. Root cause and fix — `tools/pre_merge_check.py`

`TESTING_STRATEGY.md` §4.7 (already on file, predating this incident) states outright that any
measurement-arm test class such as `AwgnFpReplayTests` "must never run unfiltered" — it depends on
a gitignored, machine-local corpus and pins a specific native binary, so CI can never satisfy its
preconditions and a category filter is the documented convention:

> `AwgnFpReplayTests.cs` is the first instance: it asserts a pinned `libft8` SHA256 in every row
> and reads from `qa/rr-study/awgn-fp-replay/_work/`, which is `.gitignore`'d and holds no tracked
> files — no CI runner can ever satisfy its preconditions, so it must never run unfiltered.

`tools/pre_merge_check.py` violated this outright: `step_tests()` ran plain
`dotnet test OpenWSFZ.slnx -c Release --no-build`, and `_WSL_BASH_SCRIPT` ran the WSL-side
equivalent, neither with any `--filter`. On any machine where `_work/` happens to be populated
(true here), this runs the excluded class unfiltered on every single invocation — which is exactly
how this incident occurred, twice, today.

**Fix applied** (`tools/pre_merge_check.py`, Captain's explicit instruction, tools/-only diff, no
`src/`/`native/` touched):

- `step_tests()`: added `"--filter", "Category!=AwgnFpReplay"` to the `dotnet test` argv.
- `_WSL_BASH_SCRIPT`: added `--filter "Category!=AwgnFpReplay"` to its `dotnet test` line.
- Module docstring (step 3) updated to document the exclusion and point here.

Verified: `ast.parse` on the edited file, `--help` still exits clean, and the WSL bash template
still `.format()`s correctly with the new flag in place. Not yet re-run as a full
`pre_merge_check.py` pass (that stays HK-006, the Captain's initiative) — the next full run will be
the first to confirm `AwgnFpReplayTests` is actually excluded end-to-end and that the 12 files
survive it untouched.

## 5. Consequence for the pin-fix ticket

None. `AwgnFpReplayTests` is exactly the fixture the shim-SHA re-pin (`d2a99b8`,
`dev-tasks/2026-09-05-1931-awgnfpreplaytests-stale-shim-sha-pin.md`) touched and verified
(330/330 native, 330/330 WSL, both confirmed clean after this remediation). That verification
stands — this incident is about the CSV *artifacts* the test's `DecodeDirectory` helper writes as a
side effect, not about the test's own pass/fail signal, which was read and reported correctly
before the working tree was restored.

## 6. Recommendation, not adjudicated here

Consider gitignoring `qa/rr-study/{awgn-fp-replay,fp-parity}/results/*_decodes.csv` outright,
matching the precedent already in `.gitignore` for the raw `_work/` WAV corpus — manual
redact-then-commit is exactly the kind of manual discipline `TESTING_STRATEGY.md` §4.7 itself
warns is fragile ("risks being left on" / silent failure), and this incident is proof it already
failed silently at least once. That's a broader QA/Architect call on how these summary CSVs are
meant to be retained long-term, not something this incident report rules on.
