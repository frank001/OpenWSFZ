# Phase 0b findings — cross-input determinism, and a fifth SPEC defect

**Author:** QA session, 2026-07-25. **Scope:** SPEC.md section 7.4(b) (cross-input determinism
control) and section 7.3 (provenance-distinctness guard), following the Architect's Phase 0
ratification (SPEC.md section 14) and its four fixed defects.

## §7.3 guard — built, verified, no issues

`score_recall.py`'s `check_provenance()` implements the amended wording exactly: refuses any
same-delta pairing except the whitelisted delta=0-vs-delta=0 identity anchor, which is asserted
to return exactly 1.0000. Verified all three cases directly: identity anchor passes (1.0000
across 25/25 cycles), a genuine same-delta/different-provenance pairing is refused with a clear
error, and the shuffled-pairing control (`--shift`) is correctly exempted (it compares different
cycles' content by design, not a self-comparison).

## §7.4(b) — built, initially FAILED, root-caused, fixed differently than the SPEC prescribes

Ran the forward-vs-reverse decode-order comparison on arm A's 25 reference cycles (segment 0):
**14/25 cycles mismatched.** Not a small effect.

**Diagnosis, not a shrug.** Inspecting the actual mismatched messages showed the difference was
never a missing or extra decode — it was hash-resolution formatting: `<...> DG0JW -14` (forward
order, cycle 0 decoded first) vs `<PD00DOG> DG0JW -14` (reverse order, cycle 0 decoded last,
after the station's full callsign had already been seen in a later-numbered, earlier-decoded
window). Traced to `src/OpenWSFZ.Ft8/Native/ft8_shim.c` line 627:
`g_session_hash_table` is a **process-global static**, by design "session-scoped... resetting to
0 only on daemon restart" (the shim's own comments, tied to decision markers R3-2/D3). This is
correct, deliberate production behaviour — a live daemon should keep resolving hashed callsigns
across an entire session — not a bug.

**SPEC.md section 7.4(b) prescribes "use a fresh decoder instance per window and re-assert" as
the fix. Tried it, and it does not work**: added a `--fresh-decoder-per-wav` flag to
`D001ParamSweep` (qa/rr-study/d001-param-sweep-2026-07-22/Program.cs, zero `src/` changes) that
constructs a new managed `Ft8Decoder` per WAV. Identical 14/25 mismatch afterward, byte-for-byte
the same pattern. This is expected in hindsight: the hash table lives in native static memory,
not in the managed wrapper object a fresh `Ft8Decoder()` call touches. Only a fresh **process**
(or a native-level reset the current public API doesn't expose) would actually clear it. This is
a fifth pre-existing SPEC defect, in the same class as the Architect's four — recorded here
per section 3's standing rule rather than silently worked around.

**The fix that does work: canonicalize hash-bracketed tokens before matching, not before
decoding.** Both `<...>` (unresolved) and `<PD00DOG>` (resolved) denote the decoder's best
information about the *same* underlying transmission; which form appears depends on decode
order, not on the signal itself. Added `normalize_hash_tokens()` to `score_recall.py`
(`<[^>]*>` &rarr; `<HASH>`) behind an explicit `--normalize-hash-tokens` flag (opt-in, not
silently on) on both `score_recall.py recall` and `cross_input_determinism.py`. Result:
**0/25 mismatches**, confirmed via the actual control script, not just an ad-hoc check.

**Checked whether this changes anything already ratified into SPEC.md section 2.5 — it
doesn't.** Re-scored the original delta in {2.0, 3.0, 5.0, 7.5} sweep with normalization on:

| delta | median (original) | median (normalized) |
|---|---|---|
| 2.0 | 0.9200 | 0.9200 |
| 3.0 | 0.0769 | 0.0769 |
| 5.0 | 0.0000 | 0.0000 |
| 7.5 | 0.0000 | 0.0000 |

IQR and mean shifted by <0.002 at delta=2.0 (one or two cycles' hash timing happened to differ)
and not at all elsewhere. The established facts in section 2.5 stand. This makes sense in
hindsight too: Phase 0's reference and every test arm were decoded in the same order (forward,
single segment, k ascending) in separate processes, so their hash-table trajectories tracked
each other closely — the confound is real but was nearly invisible in Phase 0's specific
construction. It will not necessarily stay invisible once Phase 1b spans multiple segments and
400 stratified cycles, where a given delta shift has more room to move which cycle first
resolves a given station's hash relative to the reference arm.

**Recommendation:** use `--normalize-hash-tokens` for all recall scoring from here on
(Phase 1a onward), not just the determinism control. It has demonstrated zero cost against the
figures already in hand and a demonstrated ability to eliminate a real confound. Not applying it
by default without saying so, in keeping with this study's own standing rule about provenance
and not silently patching around defects.

## Not yet resolved

Whether `D001ParamSweep --fresh-decoder-per-wav` (built above) is worth keeping now that it's
established not to fix the actual problem. Recommend keeping it (harmless, documented, and
correctly scoped as a no-op for this specific hazard) rather than reverting, since a future
session may still want per-WAV decoder isolation for an unrelated reason (e.g. isolating
`hashTableRejectCount` itself as a per-window metric).
