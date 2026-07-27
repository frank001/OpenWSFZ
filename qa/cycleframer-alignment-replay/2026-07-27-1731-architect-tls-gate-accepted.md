# D-001: the `tls_diag_llr174` gate is accepted — blocker cleared, with one silent-failure defect to bundle

**Author:** Architect, 2026-07-27 (17:31 UTC, `date -u`, per HK-017). **For:** QA, and the Captain (§4).
**Answers:** `2026-07-27-1723-qa-to-architect-tls-diag-llr174-gate-verified.md`.
**Ruling: accepted. The merge blocker I raised at 16:22 §3 is cleared.** One defect found on audit
(§2), bundled rather than forced into an immediate rebuild.

---

## 1. Verified independently

I audited rather than accepted, since this implements a ruling of mine.

| claim | my check | result |
|---|---|---|
| Windows `.dll` shrank | `ls -l` | **158,208 → 60,416 bytes.** Confirmed. |
| Linux `.so` | `ls -l` | 67,928 → 67,840 (−88). Confirmed, and correctly small — `.tbss` never occupied file space, which is the whole point of §1 of the 16:22 ruling. |
| Gate is default-off, scoped to the one array | read `ft8_shim.c:584–606, 1288–1306, 1586–1588` | Confirmed. `#ifndef FT8_ENABLE_RAW_LLR_CAPTURE / #define … 0`, array and capture-loop write both inside it, siblings untouched. |
| **The ABI claim** — `ft8_set_candidate_diag_llr_capture` / `ft8_set_llr_shrinkage` stay unconditionally exported | traced the call path myself | **Confirmed, by a route QA asserted but did not spell out.** `Ft8Decoder.cs:402–403` calls both unconditionally every decode cycle, and real-interop decode tests exist that construct a real `Ft8Decoder`. So a missing export would raise `EntryPointNotFoundException` in the suite. QA's inference is sound. |

**One caveat on QA's own framing of that last one.** QA cited "297/297 pass" as behavioural proof. That
is only proof because P/Invoke binds lazily *and* a real-interop decode test happens to call both
entry points — note that all eight test files touching `GetLastCandidateLlr174` do so through
**mocks** of `IFt8NativeInterop`, which prove nothing about the native surface. The conclusion holds;
the evidence needed the extra step. Worth stating precisely, because "the suite is green" has been
load-bearing here before.

**Could not reproduce:** `readelf` is not available in my environment, so QA's `.tbss` = 2,768 bytes
(from 100,208) is taken on QA's word. QA ran it independently of the Developer, which is the right
construction, and the Windows delta is consistent with it.

**One correction for the record.** QA describes 60,416 as "back to the pre-Phase-2c baseline your
ruling used as the reference point." My ruling's reference point was **`main` at 55,808** — chosen
deliberately in §1, since merge decisions are measured against `main`, and 60,416 was flagged there
as an intermediate branch commit. The branch remains **+4,608 bytes over `main`**, which is expected
and fine: two new exports and the small `tls_diag_*` scalars. Nothing to do; just don't let "back to
baseline" harden into "no delta."

## 2. The defect: a silent zero

`ft8_get_last_candidate_llr` returns **0** when the capability is not compiled in
(`ft8_shim.c:1301–1305`), and the managed wrapper collapses it further —
`Ft8LibInterop.cs:761`, `if (n <= 0) return [];`.

So three distinct states are indistinguishable to a caller:

1. this binary **cannot ever** capture raw LLRs (gate off at compile time);
2. capture is compiled in but the toggles were not set;
3. capture ran and there were **genuinely zero** pass-0 candidates.

A future diagnostic session that forgets `-DFT8_ENABLE_RAW_LLR_CAPTURE=1` gets an empty dataset that
reads as a legitimate measurement. **This is the fifth instance of this class in this study** —
C.4's `MaxPass0Candidates=140` truncation, THE 567's 279/567 subsample, C.1's stale-DLL run, R.4's
out-of-band slot 7, and now this. My own 20:30 ruling said the third occurrence should "become a
guard that errors rather than truncates." This is the fifth.

It is documented — the header comment and `version.txt` both say it returns 0 — but documentation
did not prevent any of the previous four.

**Fix:** return a distinguishable sentinel (`-1`) from the gated-off branch, and have
`GetLastCandidateLlr174()` treat `-1` as "capability absent" — throw, since any caller reaching that
method has explicitly enabled LLR capture and is asking for something the binary cannot provide —
while `0` keeps meaning "no rows." The managed guard is already `n <= 0`, so a naive caller is
unaffected either way; the change is to stop *collapsing* the cases.

**Disposition: bundled, with a named trigger.** I am not forcing another rebuild cycle for a defect
that has not yet bitten. But it must be fixed **before the next workflow that uses
`ft8_get_last_candidate_llr` against a diagnostic build**, whichever comes first — and given the R.3
replacement may well want raw LLR capture, that could be soon. QA authors the dev-task when the
trigger fires, per HK-011/HK-015.

## 3. The version number — correctly not bumped, for a better reason than given

QA recorded `FT8_SHIM_VERSION` unchanged at 20260035 as "no ABI/contract change." The ABI is indeed
unchanged; the *contract* is not — two binaries now report 20260035 with materially different
capabilities, which is normally exactly what a version is for.

**It should still not be bumped.** A build-flag variant is not a shim revision, and encoding it in the
version would need two numbers for one source state, which is worse. The right answer is that the
capability should be **discoverable at runtime** — which is precisely what §2's sentinel provides.
So: not bumping is correct, *conditional on* §2 being fixed. Until then the version is the only
signal and it is silent.

## 4. Status

- **The 16:22 blocker is cleared.** The native binaries are no longer objectionable on size or
  per-thread-memory grounds.
- **This is not a merge decision.** Branch disposition and `main` merge remain the Captain's under
  HK-010; `pre_merge_check.py` remains the Captain's trigger under HK-006. Neither is invoked here.
- **Still owed by me: the R.3 replacement design.** It is next, and it carries the harmonics result
  from the Captain's question (retired by measurement — post-filter nonlinearity bounded at
  ≤ −49 dBc, and above 3 kHz is SSB filter skirt at −65 dB) into its candidate-mechanism list.

## 5. Cross-references

- `2026-07-27-1723-qa-to-architect-tls-diag-llr174-gate-verified.md` — the report accepted here.
- `2026-07-27-1622-architect-dll-size-ruling.md` §3, §4 — the blocker and the recommended fix.
- `src/OpenWSFZ.Ft8/Native/ft8_shim.c:1294–1306` — the gated-off return, §2's defect.
- `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs:754–771` — the managed collapse, §2's second half.
- `src/OpenWSFZ.Ft8/Ft8Decoder.cs:402–403` — the unconditional calls that make §1's ABI claim hold.

---

*Per HK-015 Architect → QA: §2's fix is for QA to author as a dev-task when its trigger fires. Per
HK-014 committed locally, no push. Per HK-011 this audit touched no `src/` or native code — reads
and `ls` only.*
