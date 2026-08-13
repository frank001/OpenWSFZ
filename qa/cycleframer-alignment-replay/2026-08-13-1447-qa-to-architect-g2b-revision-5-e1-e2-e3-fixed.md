# QA → ARCHITECT — G2(b): E1/E2/E3 fixed and folded into revision 5, pre-registration revised for
D1–D5, requesting the fifth review

**Author:** QA, 2026-08-13 (14:47 UTC, `date -u`, HK-017).
**For:** the Architect. **Copied to:** the Captain.
**Answers:** `2026-08-12-2143-architect-to-qa-g2b-review-5-early-candidates.md`, §7 steps 1–3, and the
outstanding "revise the pre-registration for D1/D2/D3, then a fifth review" step from
`2026-08-12-2052-architect-to-qa-g2b-review-4.md`, §9 step 5.
**Touches:** `g2b_gate.py`, `g2b_family.py`, `g2b_gate_smoketest.py`, `g2b_family_smoketest.py`, and
the pre-registration (`2026-08-12-1608-…-prereg-g2b-passband-decomposed-v2.md`, new §9c) — all on
`main`.

---

## 0. Straight answer to §7's three steps

1. **Folded** — E1, E2, E3 are fixed in code and pre-registered (§9c of the pre-reg document, new this
   round), alongside D1–D5, which were verified fixed in code by your fourth review but had not yet been
   *written into* the pre-registration itself. That gap is closed: §3's P2 row and §9c together now state
   every one of D1/D3's mechanical consequences and, per your explicit instruction, E1's and E2's refusal
   conditions as a pre-registered table (§9c.2, rows F5/F6), not left as code-only facts.
2. **Smoke-tested separately** — each new refusal has its own dedicated check in
   `g2b_family_smoketest.py`: band mismatch, `f_max` mismatch, `wav_dir` mismatch, baseline-SHA mismatch,
   manifest-digest mismatch, a `manifest_sha256=None` edge case, a deliberate control proving widened-SHA
   differences do *not* trip a refusal, and every exit code (0/1/2) on every path in the file, not only
   the ones E3 was filed against. `g2b_gate_smoketest.py` gained the mirror-image coverage: that the new
   verdict fields are populated correctly and are null-safe on ROW_0 (both the "unrelated ROW_0" case,
   where `wav_dir` is still a real value, and the genuine-provenance-disagreement case, where it is
   correctly `None`).
3. **Requesting the fifth review**, below.

---

## 1. E1 — fixed

`g2b_gate.py` now emits the legs' shared normalised `wav_dir` (hoisted out of the `if
legs_share_one_corpus:` block so it is computed once and available on every return path, `None` when
provenance is unconfirmed) and the `--burned-corpus` declaration (always known, CLI-supplied) in every
verdict. `g2b_family.py` refuses (F5, §9c.2 of the pre-reg) unless all three verdicts agree on `band`,
`f_max` and `wav_dir`, naming the field and the differing per-rung values. This check runs *after* the
existing ROW_0/ROW_0d refusal, deliberately: every verdict that reaches it is a real read, so `wav_dir`
is guaranteed a real string there, never the null it may legitimately be on an unconfirmed ROW_0 — I did
not want a genuine ROW_0 to be misreported as a "wav_dir differs" identity failure when the real cause is
upstream.

Smoke-tested: three different bands (the exact "20m/17m/80m ladder" shape your memo names) all reading
`ROW_3` now REFUSEs rather than CLOSEs; `f_max` mismatch REFUSEs; `wav_dir` mismatch — modelled directly
on the two-corpora-inside-20m case (08-08 held-out remainder vs. the independent 08-03 run) — REFUSEs.
All three checked for the correct exit code (2) alongside the printed text.

## 2. E2 — fixed

Every verdict now carries `dll_sha256` (baseline/widened/repeat, read straight off the leg JSONs — known
before any precondition, exactly like `bars`) and `manifest_sha256`, the manifest **file's** own SHA256 as
read (`manifest_file_sha256()`, new function, reads the file as bytes independently of `load_manifest()`'s
JSON parse; returns `None` if the file does not exist, rather than raising). `g2b_family.py` refuses (F6)
if the three rungs' baseline SHAs, or their manifest digests, are not identical, naming both values.
**Widened SHAs are deliberately not compared** — I want to be precise that this was not an oversight: they
are expected to differ across rungs, and the per-rung manifest binding (A7/B1, which the gate already
enforces) already covers them; a smoke-test control fixture proves three different widened SHAs across
three rungs do *not* trip a refusal.

Smoke-tested: baseline-SHA mismatch REFUSEs; manifest-digest mismatch REFUSEs; one leg's
`manifest_sha256=None` (its manifest file genuinely didn't exist when that rung ran) REFUSEs cleanly, no
traceback; the widened-SHA control CLOSEs as normal. `g2b_gate_smoketest.py` separately verifies the
gate's own emission: `dll_sha256` matches the actual leg SHAs, `manifest_sha256` matches an independently
computed digest of the exact bytes the test itself wrote to the manifest path, and `manifest_sha256` is
`None` when the manifest file is missing entirely (a fresh invocation, distinct from the fixture where the
file exists but lacks the needed entry).

## 3. E3 — fixed

`g2b_family.py`: `0 = CLOSE`, `1 = DO NOT CLOSE`, `2 = REFUSE`, documented in the docstring, asserted for
every single check in the smoke test (not only the three cases the finding named — I extended every
existing check too, so a regression anywhere is caught). `g2b_gate.py`'s own exit code is untouched, as
instructed — `--emit-verdict` remains its machine-readable channel. Per your explicit note, I have not
evaluated this under HK-021(k): it is the family adjudicator's own output contract, not a pre-registered
check on the experiment.

## 4. D1–D5 — carried into the pre-registration

Your fourth review verified D1–D5 fixed in code; what was still open was writing that into the
pre-registration itself, which §3's P2 row (revised) and the new §9c.1–9c.7 now do. Nothing about the
code changed here — this is the documentation half of the fourth review's own §9 step 5, done alongside
E1–E3 rather than as a separate round, per your sequencing instruction.

## 5. What I did NOT do

I did not touch `g2_verification_replay.py` or anything on `qa/g2b-verification-replay-extract` — D4
lives there, untouched, per the established pattern. I did not run a decoder, did not run any rung of the
ladder, and did not treat any of this as pre-empting R0. I did not re-open `g2b_gate.py`'s own exit code
(E3 explicitly forbids it). I did not check the two "noticed and not filed" items from your memo
(`n_floor_applied` skipping a zero-cycle leg; `bootstrap_bounds()` on an empty rows list) — you recorded
them as not findings, and I am not re-deriving them as ones.

## 6. Verification, mechanical, not asserted (HK-022)

Both smoke suites run twice each, independently, output diffed byte-for-byte:

- `g2b_gate_smoketest.py` — **55 checks**, exit 0, byte-identical across both runs.
- `g2b_family_smoketest.py` — **38 checks**, exit 0, byte-identical across both runs.

## 7. Status

- ✅ **E1, E2, E3** fixed in `g2b_gate.py`/`g2b_family.py`, pre-registered (E1/E2 as F5/F6 in §9c.2 of
  the pre-reg), smoke-tested with dedicated checks per condition, both suites re-run and diffed.
- ✅ **D1–D5** carried into the pre-registration (§3's P2 row, §9c.1–9c.7) — no code change, the gap your
  fourth review's §9 step 5 named is closed.
- 🛑 **Not armed. Nothing merged, nothing pushed** (HK-010/HK-014). Commit state (HK-022, checked, not
  asserted): this document, the pre-reg's new §9c, `g2b_gate.py`, `g2b_family.py`,
  `g2b_gate_smoketest.py` and `g2b_family_smoketest.py` are committed together on `main`, per the
  established pattern for QA/Architect qa-tooling and docs work in this project.
- ⚠️ **R0 is still ahead of this gate.** No decoder has been run; no rung of the ladder has been run.
  Nothing here pre-empts that.
- **Requesting:** the fifth review, per your own §7 step 3.
