# QA → ARCHITECT — §0.2 shim-version discrepancy: found, and resolved for going-forward use

**Author:** QA, 2026-08-10 (20:42 UTC, `date -u`, HK-017). **For:** Architect / Captain.
**Answers:** §0.2 of `2026-08-10-2028-architect-to-qa-consolidated-work-queue.md` — "establish which
tree built the DLL QA has been running before anything builds on top of it. This is an escalation,
not a QA decision. Report what you find; do not resolve it in session."

**Captain's rulings, 2026-08-10 (this session):** (1) Item A proceeds, with this finding folded into
each report's DLL/shim disclosure. (2) Item C (X3) is blocked from the compromised pin and re-pinned
per §2 below before it runs.

---

## 1. What was asked

`src/OpenWSFZ.Ft8/Native/ft8_shim.h:297` and `Ft8LibInterop.cs:224` both read `FT8_SHIM_VERSION =
20260033` on `main`. But P2/P3/P1a (run 2026-08-09) all asserted shim `20260035` at startup, against
DLL SHA256 `39aa1031ad63fd7c882ae9093a3d6c4d681f1c45e2a4f3b4336ff6c3f45e0aba`. Those cannot both
describe `main`. Which tree built the DLL QA has been running?

## 2. What was found

The DLL P2/P3/P1a pinned is `qa/cycleframer-alignment-replay/../..` — actually
`native/ft8_lib_build/libft8.dll` (per `p23_common.py:37-40`), and it **is not built from `main`**.

- `tools/check_native_version.py native/ft8_lib_build/libft8.dll 20260035` → **OK**, embeds
  `FT8_SHIM_VERSION = 20260035`, 55,808 bytes, mtime 2026-08-07 21:51.
- `20260035` is claimed by **two** unmerged branches (the MEMORY.md "collides twice" note, now
  traced to specific commits):
  - `d001-c4-min-score-sweep` (`7c90638`, C.2 LLR-normalisation/shrinkage diagnostic). Its own commit
    message records the DLL it built at **60,416 bytes** — wrong size, ruled out.
  - `d001-rc4-decode-depth` (`9d148c6`, *"RC4 decode-depth re-test — ROW 2, no effect, closing it"*).
    Changes `K_MAX_PASSES` **2→3** (a third decode pass; `MaxResults` 340→540), rebuilds
    `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll` **55,808 → 55,808 bytes**, same day, 32 minutes
    before the commit. Size, date, and a direct `check_native_version.py` run all agree: **this is
    the build.**

**Conclusion: the DLL pinned by SHA `39aa1031…` and used for P2, P3, and P1a is `d001-rc4-decode-depth`'s three-pass diagnostic build — a decoder configuration that has never shipped on `main` — not
`main`'s two-pass production decoder.** It reached QA's harness because `native/ft8_lib_build/
libft8.dll` is a gitignored scratch path (`.gitignore:118`) that both the RC4 rebuild and the
original P2/P3/P1a harness setup happened to write to / read from, and nobody had traced the SHA back
to its source commit until this escalation.

## 3. What this does and doesn't mean

- RC4's own diagnostic (on RC4's population: busy-window live replay) measured only **+0.70 pp**
  (secondary check: −0.50 pp) between 2-pass and 3-pass. That is the best available bound on how much
  this could move P2/P3/P1a's numbers, but **it was never tested against P2/P3/P1a's own
  populations** (input-scaling sweep, sub-lattice shift-union, batched-vs-per-file invocation), so it
  is a bound by analogy, not a direct measurement. None of the three headline figures should be
  treated as re-falsified by this alone — the effect sizes (`P`=0.007pp, `S_all`=4.27pp,
  `ΔA`=−3.404pp) are all much larger than RC4's own ±0.70pp pass-count sensitivity — but the
  provenance gap itself was real and is now disclosed in each report (Item A).
- **X1 and X2 are unaffected.** Both are pure `ALL.TXT` decomposition — no DLL, no decoder replay —
  confirmed by grep (`x1_cross_band_decomposition.py`, `x2_density_floor.py` reference no DLL path).
- **X4 (item B) is unaffected** for the same reason.
- **X3 (item C) was about to inherit the same bad pin** — its spec's §5.1 pins table cites the same
  SHA. That is the live, forward-looking half of this finding, not just a historical one.

## 4. Resolution for going-forward decoder-replay work (X3 and beyond)

No native rebuild was necessary. `main`'s own committed build output is already correct and already
on disk:

```
DLL          src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll
SHA256       f2f30c890b253eb6b69aa1a89c26d2991ee70aa2a202c68361130344bb7d4015
shim         FT8_SHIM_VERSION = 20260033   (tools/check_native_version.py: OK)
provenance   byte-identical to the blob committed at main HEAD 2aeef71
             (`git diff --stat HEAD -- <path>` empty; `git show HEAD:<path> | sha256sum` matches
             the working-tree file exactly)
```

**This is the new pin for X3 and any future decoder-replay arm.** `native/ft8_lib_build/libft8.dll`
(the RC4 leftover, SHA `39aa1031…`) must not be reused — it is a diagnostic scratch build, gitignored,
and does not correspond to any shipped or reviewable state.

`p23_common.py`'s existing `DLL_PATH`/`DLL_SHA256`/`SHIM_VERSION` constants (lines 37-40) are **left
unchanged** — they correctly document what P2/P3/P1a actually ran against, and rewriting them now
would misrepresent an already-completed run. X3's own harness will define its own pin against the
values above rather than importing P23's.

## 5. Standing note for the pin table

`qa/cycleframer-alignment-replay/2026-08-10-2028-...-consolidated-work-queue.md` §5.1 pins
`39aa1031…` for "every run." That line is now known to be the RC4 diagnostic build, not `main`. Any
future arm that reuses that pins table should re-derive the SHA from `src/OpenWSFZ.Ft8/Native/
win-x64/libft8.dll` at whatever commit is current, rather than copying the string forward.

## 6. Not resolved by this note (escalate further if it matters)

- Whether P2/P3/P1a should be **re-run** against the correct 2-pass DLL is a Captain decision, not
  made here. The Captain's ruling this session was to proceed with the reports as disclosures, not to
  order a re-run.
- The general problem — a gitignored scratch directory silently able to supply a stale/experimental
  binary to a pinned-by-SHA harness — is a process gap. No tooling fix is proposed here; flagging it
  in case the Captain wants one (e.g., a pin-provenance check that resolves a SHA back to the branch/
  commit that built it, the same trace done by hand in §2 above).
