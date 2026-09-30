# SUB-FEAS speed redesign, Stage A: exact optimisations, hard deadline, thread count, lean hot path

**Date:** 2026-09-30
**Prepared by:** QA (HK-015: Architect → QA → Developer)
**Audience:** Developer (to execute); Captain (hand-over per HK-000, merge sign-off HK-010, push go-ahead HK-033)
**Status:** **DRAFT for hand-over (updated 2026-09-30 for the Architect's Amendment 1, `arch/subtraction-feasibility` `b653298e`).** The Captain's direction is on record in the Architect's ruling ("go for option 2. more threads, code speedup, remove redundant monitoring from hot decode path", 2026-09-30) and QA asked him directly about M1 the same day. QA has **not** had a separate direct go for this hand-over; the Captain hands this over.
**Branch:** create `feat/sub-feas-speed-redesign` **off** `feat/sub-feas-native-subtraction` (`ab95bea1`, code `2b39cf18`). Do not branch off `main`: the base change is not merged. Git will refuse if another worktree holds the base branch; that is the mechanism working.
**OpenSpec change:** `openspec/changes/sub-feas-speed-redesign/` (`proposal.md`, `design.md`, `specs/`, `tasks.md`). **`tasks.md` is the checklist; this file is the briefing.** `openspec validate --all --strict` is 62/62.

---

## 0. Why this exists

The base build's real-band replay failed: 765 of 905 busy real cycles exceeded the 13 s budget (max 16 309 ms), and the pass was deadline-abandoned in 87.8 % of heavy cycles (`qa/rr-study/results/2026-09-29-sub-feas-8-1-replay/report.md`). Two defects: the pass is too slow (about 377 FFTs of 262 144 points per signal, about a third of them pure repeats, on at most 4 threads), and the deadline is not a real bound (checked only between native phases). The Captain funded a redesign. **Stage A is exact-only: the fit's output must not change by a single byte.**

## 1. What you build (Stage A only)

| # | Change | Note |
|---|---|---|
| A1 | Compute the smoothed tone track once per signal; `r_fit_drift` applies only the ḟ-dependent drift term | `subfeas_fit.c:238-283`. Keep the track at the precision the old code held it. |
| A2 | FFT the Gaussian pulse and Hann window once per workspace; reuse the spectra | `:168-230`, `:449-500` |
| A3 | Reuse workspaces and FFT plans instead of rebuilding per signal: a **bounded, locked pool** of heap workspaces, size = effective thread count, leased per fit and returned in a `finally`, freed at decoder dispose, **no native thread-local state** (decided by the Architect, Amendment 1) | **The crash-history hotspot.** |
| A4 | Config `decoder.subtractionMaxThreads`: **`0` = auto = `max(1, ProcessorCount − 2)`, and `0` is the default**; other values clamp to `[1, ProcessorCount]` | replaces `Math.Min(ProcessorCount, 4)` at `Ft8Decoder.cs:63`; optional key, no UI |
| A5 | Hard deadline: cancel flag checked per Δt/ḟ/envelope iteration, new rc `-4`; C# sets it at `budget − 1 500 ms`; do not start the residual decode with less than 1 500 ms left | named constant `SubtractionResidualDecodeReserve` = **1 500 ms** (Amendment 1, raised from 1 000), no literal |
| M2 | Residual `DecodeAll` with diagnostics off | keep `compute_noise_floor` (feeds SNR fallback) |
| M3 | Guard the Debug-only per-pass log loops with `IsEnabled(Debug)` | `Ft8Decoder.cs:470-495` |

## 2. What you do NOT build

- 🛑 **M1 (removing the LDPC-fail LLR statistics) is DEFERRED by the Captain.** Four QA scripts parse that Debug line. Do not touch `ftx_compute_candidate_llr_stats`, `tls_llr_*`, `ft8_get_last_llr_stats` or `GetLastLlrStats`.
- **Stage B** (faster FFT, pruned frequency search, coarse-to-fine Δt) is not authorised unless Stage A fails acceptance.
- **No build-flag changes** (`/fp:fast`, `/arch:AVX2`, vectorised sin/cos): they change rounding and are Stage B.
- No decode-rate work, no change to what is decoded, no change with the flag OFF. The flag stays OFF by default.

## 3. Order of work (it matters)

1. **Measure first (tasks §2).** A test-only tool that times each fit phase, `ft8_subfeas_compute_analytic` and one residual `DecodeAll` on the base DLL, and reports the longest stretch a cancel flag would wait through. Nothing about the cost map is measured today; this makes it checkable and sizes the reserve.
2. **Build the E1 hash probe (tasks §3) and record golden hashes from the base DLL before optimising.** Then re-run after each of A1, A2, A3. A difference means revert that item.
3. A1 → A2 → A3, A5, A4, M2, M3, tests, shim version.

**Keep the base `libft8.dll` (SHA-256 `5a6a4dc04a2cf6fbd987c12ce7635a968f4c9b69f73cacebe422af62827e38c5`).** QA's acceptance compares your DLL against it byte for byte.

## 4. The pitfalls, in order of how much they will hurt

1. **Exactness is floating-point.** A stored value at a different precision, a reordered sum or a fused multiply-add breaks bit-identity quietly. E1 is the judge, not your reading of the code. First suspect on failure: the A1 hoist.
2. **Thread-pool threads are not yours.** Thread-local C storage has no destructor here, so a per-thread workspace leaks when the pool retires the thread and cannot be freed at shutdown from another thread. **The mechanism is decided** (Architect, Amendment 1; `design.md` D2): a bounded, locked pool of heap workspaces, leased per fit and returned in a `finally`. You record only the pool API and how a changed thread count resizes it (at the next cycle boundary, nothing in flight). A cancelled or failed fit must still return its lease; concurrent fits never share a workspace; dispose must not free a workspace that is leased out.
3. **The cancel flag's memory must outlive every in-flight native call.** Own it on the managed side for the whole of `RunCoreUnguarded` and free it only after `Parallel.For` returns. Native reads it `volatile`; managed writes it with a volatile write.
4. **`-4` is a deadline, not an error.** The interop currently throws on any code other than 0 and -3. If `-4` throws, every deadline is logged as a contained exception and the R3 and R4′ acceptance rows read the wrong thing.
5. **`FT8_SHIM_VERSION` literal:** verify against `main` (`20260051`), `decoding_improvement` (`20260054`), the base (`20260055`) and any live branch. Do not assume `20260056`.
6. **Config:** the Settings page sends neither `subtractionEnabled` nor `subtractionMaxThreads`, and the config POST is a full replace (HK-035), so until the Engineer's config-save fix (#193) lands a Settings save resets both: the flag to OFF and the thread key to `0` = auto. Both are safe. That is why `0` is auto. Confirm this, and re-confirm after that fix lands. Negative values clamp to 1 (QA's reading; the Architect did not state it).
7. **Reserve margin** is now 1 500 ms against an observed flag-OFF max of 830 ms (670 ms of margin; raised by the Architect from QA's 1 000 ms draft, `design.md` D5). R1′ stays at 13 000 ms and is still fairly tight; a near miss is expected to be about the reserve, not a surprise.
8. **Acceptance amendments (accepted, Amendment 1):** R5′ compares against the `2b39cf18` DLL re-measured in the same session, and E1 uses pooled `(run, stamp)` pairs sorted by `(run, stamp)`, indices 0, 9, 18, …, plus the 60 pilot cycles. **M1 stays deferred, so P4 is scored on M2 + M3 only.**

## 5. Tests (see `tasks.md` §8 for the full list)

Bit-identity against golden hashes; cancel preset and mid-fit returning `-4` promptly with a zeroed buffer; deadline → `deadlineAbandoned=true`, `containedException=false`; skip residual decode when less than the reserve remains; thread-count default/clamp table and next-cycle pickup; **many workers × many cycles with forced cancels, deterministic per-signal hashes** (this is the concurrency stress test); memory plateau and release at shutdown; diagnostics-off output equality and unchanged SNR fallback; Debug loops not run when Debug is off; existing flag-OFF/AV/`MaxPasses` tests still green. **Full `dotnet test`, no `--filter`; quote the exact command and the total.**

## 6. Hygiene

- 🔒 **NFR-021 / HK-037:** the E1 probe and every test write hashes, return codes, counts and stamps only. No message text, no callsigns, no exception message text.
- **HK-011:** you are the separate Developer session; QA and the Architect touch no `src/` or `native/`.
- **Stage by path, never `git add -A` / `git add .`.** Check `git branch --show-current` before committing.
- Not pushed and not merged without the Captain's explicit go (HK-033, HK-010).
- Licence policy: permissive only; no GPL.

## 7. Done means

`tasks.md` §1–§9 ticked; the E1 probe over the fixtures identical to the golden; full suite green (command quoted); new `libft8.dll` SHA-256 pinned (actual and pinned); report handed to QA. **QA then runs §10** (real-corpus E1 first; if it fails nothing else is read), the flag-OFF control re-run, and the timing rows on the frozen §8.1 instrument with WSJT-X closed. Stage A passes only if E1, R0, R1′, R2′, R3, R4′, R5′ and R6 all pass; the Architect's predictions (P1–P4) are scored by the Architect at that ruling.

**Blind spot, to keep in view:** no real cycle in the corpus has more than 32 pass-0 signals, and acceptance is one 16-thread machine. A PASS will mean "up to 32 real signals on this machine", not more.
