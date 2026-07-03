# DEV TASK — D-011: False-positive guard silently discards genuine nonstandard-callsign decodes

**Date:** 2026-07-03
**QA defect ID:** D-011
**Severity:** Medium — no crash, no data corruption; but the operator never sees a real,
correctly-decoded message class, which directly undercuts the value of
`f-001-hashed-callsign-resolution`
**OpenSpec change (context, not modified by this task):** `f-001-hashed-callsign-resolution`
**Related defect:** D-009 (OSD false-positive guard, `Ft8Decoder.IsPlausibleMessage`)

---

## 1. Context

During a live 1-hour R&R session (2026-07-03, real off-air 40m FT8 traffic, WSJT-X and
OpenWSFZ decoding the same real antenna feed concurrently) validating
`f-001-hashed-callsign-resolution`, a real special-event station transmitted a nonstandard
(7-character) callsign for the full session. Per NFR-021, the real callsign is **not**
reproduced in this document — it is referred to below as `NONSTD1` (a fictional
placeholder). Any illustrative examples use the existing synthetic convention already
established in `tests/OpenWSFZ.Ft8.Tests/HashedCallsignResolutionTests.cs` (e.g.
`Q0X7ZFZ`-style fictional calls).

**What went right:** the core cross-cycle hash-resolution mechanism f-001 shipped works
correctly on live traffic. OpenWSFZ's session-scoped table correctly showed the unresolved
placeholder at the very first cycle of the session (before it had heard anything), then
correctly resolved `NONSTD1` for every subsequent correspondent reply for the rest of the
45+ minute session, matching WSJT-X's own decode text exactly.

**What's wrong:** WSJT-X decoded `NONSTD1`'s own transmissions directly — its repeated
`CQ NONSTD1` announcements and its own `RR73` confirmations — on almost every cycle, at
strong SNR (+5 to +17 dB). OpenWSFZ's `ALL.TXT` shows **none of these** anywhere in the
entire session log. Inspecting the Trace-level daemon log (`logs/openswfz-*.log`,
`fileLogLevel: Trace`) shows the native decoder caught every one of them correctly:

```
[DBG] Cycle 20:23:30: filtered implausible message 'CQ NONSTD1' (false-positive guard).
[DBG] Cycle 20:19:45: filtered implausible message 'NONSTD1 <Q0COR1> RR73' (false-positive guard).
[DBG] Cycle 20:21:00: filtered implausible message '<Q0COR2> NONSTD1 RR73' (false-positive guard).
```

(The two correspondent callsigns above were real off-air callsigns from the same session
in the original QA draft of this document; they have been redacted to fictional Q-prefix
placeholders — `Q0COR1`, `Q0COR2` — per NFR-021 before this file was committed to VCS.
Only the exact filtered *message shape* is evidentiary here, which the redaction
preserves.)

**Root cause** — `Ft8Decoder.cs`, `IsCallsignOversized` (line ~536), part of the
pre-existing D-009 false-positive guard (`IsPlausibleMessage`, D9-R3 rule):

```csharp
private static bool IsCallsignOversized(string token)
{
    if (token.StartsWith('<')) return false;   // hash reference — never oversized
    if (token.Length <= 3)    return false;    // CQ / DE / QRZ / very short call — exempt

    int    slashPos  = token.IndexOf('/');
    string baseCall  = slashPos >= 0 ? token[..slashPos] : token;

    // Base callsign from standard Type 1 packing: maximum 6 characters.
    // Rendered token with /suffix: maximum 10 characters.
    return baseCall.Length > 6 || token.Length > 10;
}
```

This correctly exempts **hash-resolved** tokens (anything wrapped in `<...>`, which is
why the correspondent-side replies like `Q0COR3 <NONSTD1> -05` survive and appear in
`ALL.TXT` — f-001's own new code path is unaffected). It has **no equivalent exemption
for a literal, directly-decoded nonstandard callsign** — the genuine 58-bit full-text
field a Type 4 message carries, which is legitimately up to 11 characters
(`design.md` §Context, `f-001-hashed-callsign-resolution`: "up to 11 chars"). The
`baseCall.Length > 6` assumption predates f-001 and was safe when nonstandard callsigns
never resolved to real text at all. It is stale now: this guard silently discards every
CQ and every direct confirmation from a nonstandard-callsign station, while only ever
showing the *other* party's view of the conversation.

**Why the existing test suite didn't catch this:** `HashedCallsignResolutionTests.cs`
(added by f-001) calls `Ft8LibInterop.DecodeAll` — the raw native P/Invoke layer —
directly. It never goes through `Ft8Decoder`'s managed wrapper, so it never exercises
`IsPlausibleMessage`/`IsCallsignOversized` at all. This defect is invisible to every
existing automated test and was only found by comparing OpenWSFZ's `ALL.TXT` against
WSJT-X's on real traffic.

---

## 2. Branch name

```
fix/d-011-nonstandard-callsign-fp-guard
```

---

## 3. Actions

### 3.1 — `src/OpenWSFZ.Ft8/Ft8Decoder.cs`: extend `IsCallsignOversized`

Add an exemption for literal (non-hash) nonstandard-callsign tokens up to the true Type 4
maximum of 11 characters, without reopening the original D-009 false-positive hole for
genuinely garbled OSD hits. Suggested approach — raise the base-callsign ceiling from 6 to
11 specifically, since the *rest* of D9-R3's structure (2-token / 3-token / 4-token shape
gating, the hex-dump rule D9-R2, the grid/report validation D9-R4, the 5+-token rule R5-B)
already does the discriminating work of rejecting genuinely malformed OSD noise; the
6-character ceiling was the only length-based signal and is the one now known to be wrong:

```csharp
private static bool IsCallsignOversized(string token)
{
    if (token.StartsWith('<')) return false;   // hash reference — never oversized
    if (token.Length <= 3)    return false;    // CQ / DE / QRZ / very short call — exempt

    int    slashPos  = token.IndexOf('/');
    string baseCall  = slashPos >= 0 ? token[..slashPos] : token;

    // Base callsign from standard Type 1 packing: maximum 6 characters.
    // f-001-hashed-callsign-resolution: a literal (non-hash) nonstandard callsign's
    // full text (Type 4 n58 field) can legitimately be up to 11 characters — raise
    // the base-call ceiling to 11 to match. Rendered token with /suffix: maximum
    // 10 characters remains a separate, still-enforced bound for standard calls.
    return baseCall.Length > 11 || token.Length > 11;
}
```

**Use judgement on the exact constants** — re-derive the correct limits from
`design.md`'s Context section (the `ihashcall`/`pack58` charset and width) rather than
copying the numbers above verbatim if they don't hold up under review. The risk to manage
explicitly: raising this ceiling must not measurably increase the false-positive decode
rate characterised by D-009 (`qa/rr-study/results/` — see 0.042/slot baseline, shim
20260029). If a straight ceiling raise reopens that risk, consider gating the relaxation
on message shape already validated elsewhere in `IsPlausibleMessage` (e.g. only relax for
tokens in a message shape that also passes D9-R4's report/grid check, or only for the
specific 2-token/3-token forms already gated here) rather than loosening the check
unconditionally.

### 3.2 — Add managed-layer regression coverage

`HashedCallsignResolutionTests.cs` bypasses `Ft8Decoder` entirely (see Context). Add a
test that goes through the actual managed decode path (`Ft8Decoder.DecodeAsync`, or at
minimum a direct unit test against `IsPlausibleMessage`/`IsCallsignOversized`) asserting
that a literal, non-hash Type 4 decode of an 7–11 character nonstandard callsign is
**not** filtered out. Use a fictional Q-prefix call for the test input, per NFR-021
(e.g. extend the existing `TestFt8Encoder.PackType4CqAnnounce` fixture rather than
inventing new encoding).

### 3.3 — Re-run the D-009 false-positive baseline

Re-run the S5 noise-floor scenario (`qa/rr-study/scenarios/s5-noise.json`, the same
scenario used to characterise D-009's false-positive rate) after the fix and compare
against the 0.042/slot baseline (shim 20260029, see `MEMORY.md` R&R study results). This
is the acceptance gate for "did loosening the length ceiling reopen the false-positive
hole D-009 closed."

---

## 4. Acceptance criteria

The QA engineer will verify the following before approving merge:

- [ ] **AC-1** A literal (non-`<...>`) Type 4 decode of a nonstandard callsign 7–11
  characters long (e.g. a fictional `Q0ABCDE`-shaped call) reaches `ALL.TXT`/the decode
  results — no longer silently dropped by `IsPlausibleMessage`.
- [ ] **AC-2** Existing D-009 regression coverage (`D009FpFilterTests`) still passes
  unmodified — genuinely garbled OSD hits (hex dumps, oversized *standard*-shaped
  tokens beyond 11 chars, malformed grids/reports) are still rejected.
- [ ] **AC-3** New managed-layer test from Action 3.2 passes and demonstrates the fix
  is exercised through `Ft8Decoder`, not just the native P/Invoke layer.
- [ ] **AC-4** S5 false-positive-rate re-run (Action 3.3) shows no statistically
  meaningful regression versus the 0.042/slot baseline. Record the result in the
  change's QA notes.
- [ ] **AC-5** Full test suite green: `dotnet test` — 0 failures.
- [ ] **AC-6** No real off-air callsigns appear in any committed file (this defect's
  own writeup already uses fictional placeholders — verify the fix/tests follow the
  same discipline).

---

## 5. References

- `src/OpenWSFZ.Ft8/Ft8Decoder.cs` — `IsPlausibleMessage` (line 382), `IsCallsignOversized`
  (line 548), D9-R3 rule (line 365) — line numbers as of the D-011 fix commit; the guard's
  ceiling was raised from 6/10 to 11 chars as part of this task
- `tests/OpenWSFZ.Ft8.Tests/HashedCallsignResolutionTests.cs` — bypasses the managed
  layer entirely (calls `Ft8LibInterop.DecodeAll` directly); this is why D-011 evaded
  the existing f-001 test suite
- `qa/rr-study/scenarios/s5-noise.json`, `MEMORY.md` R&R study results — D-009
  false-positive baseline (0.042/slot, shim 20260029) to re-check against
- OpenSpec change: `openspec/changes/f-001-hashed-callsign-resolution/` (design.md
  Context section for the true nonstandard-callsign charset/width; this task does not
  modify that change's artifacts, it is a follow-up defect it exposed)
- Live evidence: 2026-07-03 real-traffic R&R session, OpenWSFZ `ALL.TXT` vs WSJT-X
  `ALL.TXT` line-by-line comparison, and `logs/openswfz-20260703T201415Z.log`
  Trace-level "false-positive guard" rejection lines. **Real third-party callsigns
  observed in that session are not reproduced here per NFR-021** — ask QA directly if
  the raw comparison is needed for deeper debugging; the raw logs remain local/untracked.
