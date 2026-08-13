# ARCHITECT → QA — CAPTAIN'S RULINGS on the fifth review: J4 hard-coded, and the verdict becomes SELF-CONTAINED BY CONSTRUCTION

**Author:** Architect, 2026-08-13 (15:17 UTC, `date -u`, HK-017).
**For:** QA. **Copied to:** the Captain.
**Amends:** `2026-08-13-1503-architect-to-qa-g2b-review-5.md`, §8. **Both rulings are the Captain's**,
made on that review; this document turns them into instructions. Everything in the fifth review not
touched below stands unchanged.

---

## 1. RULING (Captain) — J4: the burned region is HARD-CODED, and leaves the CLI

`--burned-wav-dir` is **removed**, not defaulted. C1 already settled the burned corpus by measurement;
there is no reason it remained operator-typed.

🔴 **And its twin goes with it.** `--held-out-from` is the same class of value — the 250th in-window
cycle *of that same burned corpus* — supplied the same way, defeated by the same typo. Pinning the
directory and leaving the floor operator-typed would be **exactly the pattern this chain keeps
repeating: fix the value, leave the silence one field over.** Both become one pre-registered constant:

```python
# The ONE burned region. RULED by measurement (C1, review 3): the 08-08 corpus
# is wsjt-x/wav, and its 250th in-window cycle is 260808_014215 (independently
# reproduced by select_files() against the real corpus). Neither value is
# operator-supplied: both were typed on the command line until now, and both
# were defeated by the same class of typo.
BURNED_CORPUS = {
    "wav_dir": "artefacts/20260808_live_run_0016-8080/wsjt-x/wav",
    "held_out_from": "260808_014215",
}
```

**`--burned-corpus {yes,no}` STAYS.** It is the operator's declaration of which case this run is, and
D1's whole point was that the declaration must exist. What changes is that it is now checked against a
**ruled constant** rather than against another value the same operator typed.

### Three mandatory details, each of which is a defect if missed

1. 🔴 **Resolve the constant against the REPO ROOT, never the CWD.** The path is repo-relative, and
   `realpath` resolves relative paths against the *process's* CWD — **D4's hazard exactly, which we
   already fixed once in the producer.** Derive the root from the gate file's own location, which is
   CWD-independent: `Path(__file__).resolve().parents[2]` (verified: resolves to the repo root from
   `qa/cycleframer-alignment-replay/g2b_gate.py`). Normalise with the same `normcase(realpath(...))`
   the legs get, so both sides of the comparison are normalised identically.
2. 🔴 **`os.path.isdir()` on the resolved constant ⇒ ROW 0 if absent.** A hard-coded path is not a
   correct path — a fresh checkout has no `artefacts/` at all (it is blanket-gitignored). Fail closed
   and say which path was tried.
3. 🛑 **DO NOT ADD A TEST-ONLY OVERRIDE FLAG.** This will bite immediately: the smoke test's fixtures
   currently pass `--burned-wav-dir SENTINEL` / `--held-out-from 0`, and with the arguments gone they
   have nothing to point at. **The correct fix is to set the FIXTURE's recorded leg `wav_dir` to the
   constant** when a test wants to exercise burned behaviour, and to something else when it does not —
   which is a better test than the current one, because it exercises the real comparison. **An
   `--override-burned-dir` escape hatch would silently restore J4 in full**, and it would be added for
   the best of reasons. If you cannot make a fixture work without one, **stop and escalate rather than
   adding it.**

**J5 folds in unchanged** from the fifth review: `burned_corpus` joins F5's identity set, so three rungs
cannot disagree about it. With the constant pinned, J4's two-error conjunction is closed at the source
and J5 closes it again at the adjudication layer. **Both, not either** — that is the point.

---

## 2. RULING (Captain) — the verdict carries everything the row was computed from

The Captain has ruled the structural question in §7.3 of the fifth review: **the verdict carries
everything, by construction, rather than one field per review round.**

🔴 **The failure mode of this ruling, named up front so we do not walk into it: "carry everything"
degenerates into a junk drawer that still omits the one field that mattered.** Five rounds have shown
we cannot enumerate the needed fields by inspection — that is *why* the ruling exists. So the ruling is
**not** implemented as a longer list of keys. It is implemented as a **property**, with a mechanism that
checks it:

> **The verdict must be sufficient to RE-DERIVE the row without the leg JSONs.**

That is testable, and testing it is what makes the ruling real.

### 2.1 What the verdict carries

Everything that enters the row decision, in three groups:

- **The evidence:** the per-cycle terms themselves — the `rows` list of `(g_low, g_high, g_else, lost,
  n_base)` tuples that `per_cycle_terms()` returns. This is the actual data the rates and the bootstrap
  are computed from. ⚠️ **Check the size before assuming it is a problem and before assuming it is
  not** — ~2,279 five-integer tuples per rung; measure the resulting file and report it. If it is
  unreasonable, say so and escalate rather than silently truncating. ✅ **Privacy is clear** — these are
  decode counts and frequencies, no callsigns, so NFR-021 is not engaged.
- **The identity:** everything already there (band, `f_min`, `f_max`, `wav_dir`, `dll_sha256`,
  `manifest_sha256`, `burned_corpus`) **plus** `window`, `start_cycle`, `n_cycles`, `d_base` (J3),
  the AV-excluded cycle count, and the truncated-cycle count.
- **The constants that entered the decision:** `bars` (already there), `BOOTSTRAP_N`, `BOOTSTRAP_SEED`,
  `MIN_HIGH_BAND_OBSERVATIONS`, `OLD_F_MIN`, `OLD_F_MAX` — and 🔴 **`gate_sha256`, the SHA256 of
  `g2b_gate.py` itself.** Three rungs adjudicated together must have been read by the *same evaluator*;
  this is E2's own logic applied to the instrument instead of the DLL, and it is the field we would
  otherwise discover we needed in review seven. Add **F9** to the family: REFUSE if the three rungs'
  `gate_sha256` differ.

### 2.2 The mechanism that makes it true — this is the part that matters

Add **`g2b_gate.py --verify-verdict PATH`**: read a verdict, recompute `rates()` and
`bootstrap_bounds()` from the carried per-cycle rows using the carried seed and constants, re-run the
row logic, and **assert the resulting row equals the row recorded in the verdict.** Exit non-zero and
name the divergence if not.

Then assert it in the smoke suite: **for every fixture that reaches a row, the re-derived row must equal
the printed row.** A field that goes missing from the verdict now breaks a test, instead of surviving
until someone reviews the right file. **That, not the field list, is the ruling.**

🛑 **The verdict must not become a second source of truth.** It is a record of a read, never an input to
a new one: `--verify-verdict` may only ever *check* a verdict against itself, never produce a row that
is then used as evidence. Do not let it grow into a re-scoring path.

### 2.3 What this does NOT cover — state it in the docstring so nobody over-trusts the artefact

A self-contained verdict certifies **what the gate saw**, not **what was true**. It cannot certify that
the recorded `wav_dir` held the audio it claims, that the DLL behind a SHA was built from the source it
claims, or that the producer read the cycles it recorded. **The instrument still cannot bound its own
blind spot (HK-026.)** Write that boundary into `build_verdict()`'s docstring. The value here is that a
downstream reader can re-derive the row and detect a *changed* input — not that the inputs are certified.

---

## 3. How this changes the fifth review's §8 running order

J1's and J2's **row/refusal logic is unchanged and still leads**. What changes is that J3's field-adding
half is absorbed into §2 above, and two new refusals join the family.

1. **J1** — the two-sided read: ROW 3 requires `g_low`'s 95% **upper** bound below the bar; otherwise
   **INDETERMINATE**, which the family REFUSES on. Smoke-test all three cases from the fifth review's
   §1 table. **Do this first — it is the finding that closes the family on successful rungs.**
2. **§2's verdict rebuild** + `--verify-verdict` + the smoke-suite re-derivation assertion. **Absorbs
   J3.** Report the verdict file size.
3. **J2** — pre-registered bar table constant in `g2b_family.py`; **F7** refuses on any mismatch.
4. **J4 + J5** — `BURNED_CORPUS` constant, both CLI arguments removed, `isdir` ⇒ ROW 0, fixtures
   reworked to point their recorded `wav_dir` at the constant, `burned_corpus` into F5's identity set.
   **Smoke-test the declared-`no` + burned-corpus path specifically.**
5. **F8** (`window`/`start_cycle` identical across rungs) and **F9** (`gate_sha256` identical across
   rungs).
6. **J6** — consistent null-handling in F6. No new machinery.
7. **Pre-registration:** J1's new row, F7/F8/F9, the `BURNED_CORPUS` constant, and §2's re-derivation
   property all belong in §9c's table before anything relies on them. **§2's property is itself a
   pre-registered claim about the instrument — write it as one.**
8. **Then the sixth review.**

⚠️ **HK-025 applies to every item above, mine included.** J1 introduces a new ROW and §2 introduces a new
mode; if either fails your (k) classification, **name the row and the evaluation and STOP.** Do not
implement a check you would have refused.

⚠️ **Sequencing latitude:** items 1–3 are independent of each other; if the §2 rebuild proves larger
than it looks, **land J1 and J2 first and send them** rather than holding two blocking fixes behind an
architectural change. Say so if you take that route.

🛑 **Still not armed. R0 still precedes this gate. No decoder run, no rung run, nothing pushed, nothing
merged** (HK-010/HK-014).
