# D-001 B.1 — jt9 ablation, QA task spec

**Author:** QA, 2026-07-26. **Operationalises:** `2026-07-26-2330-architect-capability-pricing-
plan.md` §3 (design) against §2 (due diligence already done by the Architect — verified again
below rather than re-derived). QA-runnable directly: no `src/` or native change, HK-011 does not
apply.

This is QA's own execution record, not a Developer handoff — no `dev-tasks/` entry, per this
thread's established split (compare `2026-07-26-2110-...md`, which ran directly off an Architect
ruling with no separate work-order doc).

---

## 1. Instrument and corpus, confirmed this session

- `D:\WSJT\wsjtx\bin\jt9.exe` exists (2,986,219 bytes, 2025-02-04). Same installation referenced
  at plan §2; version not separately queried (no `-v`/`--version` flag in `jt9 --help`; the
  binary's mtime and the fact it is the only WSJT-X install on this machine stand as the
  identification).
- Corpus: the 68 filename-matched cycles, taken from WSJT-X's own recordings
  (`artefacts/20260725_live_run_1806/wsjt-x/wav/*.wav`, 75 files present, all 68 matched names
  confirmed present by set difference). This is the arm A0/A1/A2 input — WSJT-X's own capture of
  WSJT-X's own decode reference, so the A0-vs-2028 comparison (plan §3.4 row 1) is not
  confounded by the capture-chain question `cycle-audio-archive` already closed separately.
  `owsfz/wav68` (our byte-compatible capture of the same 68 cycles) is reserved for optional arm
  A4.
- Live GUI reference: `artefacts/20260725_live_run_1806/wsjt-x/ALL.TXT`, ts field format
  `YYMMDD_HHMMSS` (full date-time), 2,684 raw lines total, restricted to the 68 matched cycles by
  ts membership.

## 2. Smoke test result (plan §3.1) — parses cleanly, proceed

`jt9.exe -8 -d 3 -p 15 -a <scratch> -t <scratch> 260725_180615.wav`, run from a scratch cwd:

- **Exit 0. Runtime 2.34 s for one 15 s WAV** (at depth 3 — the most expensive arm). 68 files at
  this rate is ~2.5 min worst case per arm; not a resource concern.
- **Output on stdout**, one line per decode, format:
  `HHMMSS  SNR  DT  FREQ  MARKER  MESSAGE...` (space-separated, `MARKER` is `~` for a
  non-AP FT8 decode; no `-c`/`-x` supplied in any arm so no `a1`-`a6` markers are expected —
  flagged as an assumption to verify against the full arm run, not asserted blind).
- `decoded.txt` also written under `-a`'s scratch dir, in a **different, wider column format**
  (extra sync-amplitude and pass-count fields, trailing `FT8` mode tag) — stdout is the cleaner
  parse target per the plan's own "whichever parses cleanly" instruction; `decoded.txt` is not
  used.
- **28 decodes for this one cycle at depth 3** — plausible against the live reference (which
  averages ~2028/68 ≈ 30/cycle across the corpus; single-cycle counts vary).
- `-p 15` accepted without error (FT8's T/R period); not testing `-p 60` (FT8-wrong default) as a
  negative control — not needed, the plan only asked whether `-p 15` is required or harmful, and
  it plainly is the correct value and does not error.
- **`~` hashed-callsign token confirmed present** (`<...>`) in this cycle's output, in the same
  bracket convention as our own ALL.TXT and the live WSJT-X ALL.TXT — `normalize_hash_tokens`
  (reused verbatim from `c4_matched_decode_verification.py`) applies unmodified.

## 3. Scoring — reused, not reinvented

Reusing `c4_matched_decode_verification.py`'s `normalize_hash_tokens` (the
`<[^>]*>` -> `<HASH>` bracket normalisation) and its dedup-by-`(ts, normalized message)` /
set-intersection matching approach verbatim. The one new piece is a **jt9-stdout line parser**
(the existing `parse_all_txt` targets this repo's own `ALL.TXT` writer format, which jt9 does not
produce — five fields before the message vs. jt9's four-plus-marker layout, confirmed in §2). This
is an unavoidable adapter, not a new matching algorithm: it produces the same
`{ts: set(normalized_message)}` shape the existing matcher consumes.

Driver: `qa/cycleframer-alignment-replay/b1_jt9_ablation.py` (this session). Runs arms A0/A1/A2
(A3/A4 optional, scoped per plan §3.2), scores each against the 68-cycle live reference using the
reused matcher, and prints the plan §3.3 table (total decodes, miss coverage of the ~740 gap,
overlap with our 1288-decode set) plus the plan §3.4 reading-rule table.

## 4. What this does not authorise

Same guardrails as the plan itself (§6 there): no native/`src/` change, no push/merge, no
`pre_merge_check.py` (Captain's trigger, HK-006), NFR-021 — raw jt9 output (real callsigns) stays
under git-ignored `artefacts/`, only aggregates go in the findings doc.

## 5. Cross-references

- `2026-07-26-2330-architect-capability-pricing-plan.md` §2, §3 — the design this operationalises.
- `c4_matched_decode_verification.py` — `normalize_hash_tokens`, matcher shape reused.
- `artefacts/20260725_live_run_1806/` — corpus and live reference (git-ignored).
