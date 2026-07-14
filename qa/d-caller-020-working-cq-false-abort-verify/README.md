# D-CALLER-020 working-CQ false-abort — live verification

`Program.cs` is the live verification required by
`dev-tasks/2026-07-14-working-cq-false-abort.md` §5 — the "synthetic-decode harness" alternative
to a full real-hardware reproduction (no CAT/audio hardware or virtual audio cable needed, unlike
`qa/d-caller-018-abort-hard-stop-live-verify/` or `qa/decode-filter-synth-verify/live_verify_9_axes.py`).

It goes beyond the dev-task's stated minimum (replaying a static log excerpt through some harness)
by genuinely re-synthesising the partner's CQ signal fresh every run
(`qa/rr-study/synth_wav.py`) and decoding it with the real, unmocked `Ft8Decoder` — an actual
P/Invoke call into `libft8`, the same native decoder the daemon ships with — then feeding the
decoded batches into the real, unmodified `QsoAnswererService`/`QsoCallerService` production
classes. This is stronger evidence than the unit tests added alongside the fix
(`QsoAnswererServiceTests.WaitReport_PartnerStillCallingCq_DoesNotAbort_RetriesInstead`,
`QsoCallerServiceTests.WaitRr73_PartnerStillCallingCq_DoesNotAbort_RetriesInstead`), which inject
hand-authored `DecodeResult` message strings rather than a genuine encode→synthesise→decode
round-trip.

Run it after `dotnet build OpenWSFZ.slnx -c Release`:

```
dotnet run -c Release --project qa/d-caller-020-working-cq-false-abort-verify
```

Requires the R&R study's Python venv (`qa/rr-study/.venv`) to already exist — see
`docs/rr-synth-cli-guide.md` if it doesn't. No audio hardware, PTT, or virtual audio cable is
needed: everything from "FT8 signal exists" through "the service reaches the right state" runs
in-process against real production code. Exit 0 = PASS, non-zero = FAIL.

## What it does

1. Synthesises four FT8 signals fresh every run: the partner's CQ (`CQ Q1TST JO22`) rendered
   *twice* with different seeds — standing in for "partner calls CQ", then "partner calls CQ
   again a cycle later" (the field sequence from `logs/openswfz-20260714T171230Z.log`) — a
   response to our own CQ (`Q1OFZ Q1TST JO22`, used to drive the caller side into `WaitRr73`),
   and a genuine third-party message (`Q2OTR Q1TST +03`, the control case that must still abort).
2. Decodes all four with the real `Ft8Decoder`.
3. Drives a real `QsoAnswererService` through: engage on the partner's CQ → feed the partner's
   second CQ render → assert **no abort** (D-CALLER-020) → feed the third-party message →
   assert **abort to `Idle`** (AC-2, unaffected).
4. Drives a real `QsoCallerService` through the symmetric sequence in `WaitRr73`: prime →
   partner responds → feed the partner's CQ re-transmission → assert **no abort**
   (D-CALLER-020) → feed the third-party message → assert **abort to `Idle`** (AC-4, unaffected).

## Callsign note

`Q2OTR` (not `Q2OTHER`, as the unit tests use) — the synthesiser's callsign packer requires a
digit at index 1 with length ≤ 5 (or digit at index 2 with length ≤ 6) to compress into the
standard 28-bit callsign field; `Q2OTHER` (7 chars) doesn't fit either form and would decode back
as a hashed `<...>` placeholder instead of literal text. The unit tests don't hit this because
they inject `DecodeResult` strings directly, bypassing real FT8 packing entirely.

## `live-reports/` — what's in here

- **`2026-07-14T183903Z-7b330e1.md` — PASS.** Includes the deliberate control run (fix reverted
  via `git apply -R` on just the two production files, tool rebuilt and re-run) that reproduces
  the exact regression on both services before the fix was restored — proving this tool actually
  catches the defect rather than false-passing regardless of the fix.
