# QA code review (HK-039), final: issue #262, opt-in PSK Reporter upload, Developer head `6ef0b33b`

Reviewer: QA. Written 2026-10-25 (`date -u` read 12:59:50Z before this file was written). Branch `feat/psk-reporter-262`, local, not pushed, cut from `origin/main` `d20059c3`. This record closes the review chain: first review `4ca20699` (`275b9cbd`, RETURNED R-1), re-review `57eacac6` (`bbedb5a5`, RETURNED R-2), and this record for the increment `bbedb5a5..6ef0b33b` and the whole branch.

Reviewed-commit: 6ef0b33ba7426c6c1d295ea27fbaa17e4d4debc9

Verdict: **APPROVED.** No required changes remain. R-1 (first-send offset test), R-2 (shutdown order), N-2 (the 4-token R-grid form) and N-3 (out-of-band dial) are met; N-1 (the NFR-021(3) exception wording) was approved by the Captain (Architect spec §12). Approval is of the code; it does not replace what is still owed before any push: `pre_merge_check.py` on this commit, live test L1, the Captain's push go and his merge sign-off.

## What QA verified in this increment

1. **R-2 is met** (`6ef0b33b`). `Dispose` is idempotent (an interlocked `_disposed` flag), cancels before it disposes and catches `ObjectDisposedException`; `StopAsync` returns at once on a disposed service and guards its own cancel. QA read it: no path can throw into the host, and an in-flight send after disposal can at most log a Warning. The Developer wrote the tests first (they failed against `bbedb5a5`): `R2_StopAfterDispose_DoesNotThrow` and `R2_StopTwice_DisposeTwice_DoNotThrow`, each a theory over `enabled` false and true.
2. **QA's own reproduction now passes.** The scratch tests `StopAfterDispose_DoesNotThrow` and `DoubleStopAndDispose_DoNotThrow` (the first failed with the exact exception of the Web failure on `bbedb5a5`): **2 of 2 pass** on `6ef0b33b`.
3. **The reverted fix is caught by the Developer's own tests.** QA mutation Q40 (the early return and the `try`/`catch` removed from `StopAsync`): the Developer's `R2_StopAfterDispose` fails in both its cases, as does QA's scratch test; restored afterwards. The service-level mutations Q21, Q22 (equivalent, as before), Q31 and Q35 give the same results as on the previous commit.
4. **Full unfiltered suite, run alone** (nothing else running on the machine; the earlier third run was lost to QA's own parallel-build collision), `dotnet test OpenWSFZ.slnx` on a clean detached tree at exactly `6ef0b33b` (`git status` empty): all ten test projects, **0 failed in every one**: TraceabilityCheck 34, LicenseInventoryCheck 24, Rig 41, TestSupport.Tests 12, Audio 40, Config 179, E2E 9, **Web 410**, **Daemon 882**, **Ft8 605**. These equal the Developer's.
5. **The intermittent failure, retested:** the whole Web project **ten times in a row, 0 failing runs** (410 of 410 each), on top of the clean full run. Ten clean runs are evidence, not proof of absence of an intermittent failure; the cause, not the symptom, is what was fixed and what the two new tests pin.
6. **Gates on the final tree:** `check_version_bump.py origin/main` OK (0.63 to 0.64, `User-facing = yes`); `check_version_docs.py` OK (v0.64); `openspec validate --all --strict` 74 of 74; **G3 traceability** PASS (Debug assemblies with the debt file; the Release form runs in `pre_merge_check.py`); `git diff --stat origin/main..6ef0b33b -- native` empty: no native change, no shim bump, so no binary refresh is needed.

## The whole branch, in one place (cumulative evidence of this review chain)

- **Wire format:** QA's three hand-built fixtures and builder are byte-identical to the Developer's embedded copies; the product encoder equals QA's independent builder on **300 random cases, 0 differences**; the encoder was not changed after the first review.
- **Behaviour:** 40 mutations run against the branch (Q01 to Q40): **36 killed**, **3 equivalent survivors** (Q22, Q26, Q27, each proven equivalent by a two-guard variant that is killed), **0 genuine survivors**.
- **Settings control:** QA's own Playwright run, 18 of 18 on an isolated daemon, screenshot reviewed, the station daemon untouched; the page carries the stated opt-in text and no `host` or `port`.
- **NFR-021(3):** the Developer's exception clause (opt-in only, default off, counts never calls) was approved by the Captain on 2026-10-25 (Architect spec §12).
- **Privacy in the code:** nothing written to disk, no message text or callsign in any log line (a mutation that logs one is killed), the queue is discarded unread while the feature is disabled, nothing is uploaded under the placeholder identity.

## Limits, stated

- **Not answered by any unit test (QA's L1, on the Captain's go):** whether the real test listener (`pskreporter.info:14739`) parses the 8-field and the 7-field sender blocks in one datagram, and that the receiver record, templates and sequence behave as the page says. The product sends two blocks whenever one cycle holds a with-grid and a without-grid sender. A rejection stops the work and goes back to the Architect.
- `pre_merge_check.py` has NOT yet been run on this commit (HK-006); nothing is pushed; L2 and L3 (production and the outside count) follow L1 on the Captain's go.
- Advisory items from the first review stand as recorded there (no pump test for early preview rows; the unguarded `ApplyConfig` call in `StartAsync` is the project's pattern; an invalid file-only `port` logs one Warning per window).
