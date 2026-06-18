# Developer Handoff — D-001 H6 AP Decode: C# Wiring

**Date:** 2026-06-18 (supersedes same-date draft — see revision note below)
**QA Engineer:** (HK-000 procedure)
**Defect:** D-001 — Co-channel decode gap (GitHub Issue #3)

> **Revision note (2026-06-18):** Prior draft listed Step A (stale comment fix) as outstanding.
> That was completed at commit `24c4d80` before this document was finalised. Step A is removed.
> Step E (callsign packing) has been rewritten with an explicit algorithm — the prior draft
> deferred to "check pack.c", which is not actionable.

---

## 1. Context

Shim 20260020 (`diag/d001-h6-ap-probe`, merged `6870f0b`) deployed the H6 directed AP
decode interop seam. `ft8_set_ap_bits()` in the native shim accepts packed mycall/hiscall
bits and injects them as ±40.0 LLR hard constraints into the pass-0 LDPC input path. All
three platform binaries are at shim 20260020. The seam is complete.

**No production code calls `SetApBits`.** `ap_active` is always false. The AP decode path
is never exercised.

Diagnostic work has established:

- LDPC convergence failure is the confirmed root cause (shim 20260018 candidate-count logging)
- Post-norm mean|LLR| is a tautological constant — useless as a discriminator (shim 20260019, H_LLR REFUTED)
- Pre-norm variance (37–60) overlaps all S7 families — also useless (shim 20260020, H_LLR_VAR REFUTED)
- Revised failure model: **high-confidence wrong-sign LLRs** from alternating symbol dominance
  under equal-SNR co-channel interference
- AP decode directly addresses this: clamping 56 known-callsign bits to correct sign (±40.0
  LLR) overrides the wrong-sign waterfall LLRs before LDPC runs

This is the highest-priority remaining action for D-001.

---

## 2. Branch Name

```
fix/d001-h6-ap-wire-csharp
```

---

## 3. Actions

Work in the order given. Each step must build and leave tests green before moving to the next.

---

### Step 1 — Implement `Ft8CallsignPacker` (new file, new tests)

**This is the hardest step. Do not skip to Step 2 until it is correct and tested.**

The shim's `ft8_set_ap_bits` accepts 28-bit packed callsign bits, MSB-first, in 4 bytes.
The shim does **not** expose `ft8_pack28`. You must implement it in C#.

**New file:** `src/OpenWSFZ.Ft8/Ft8CallsignPacker.cs`

The FT8 28-bit standard-callsign packing algorithm (from the FT8 protocol spec, §3.1):

```
Normalise the callsign to exactly 6 ASCII characters as follows:
  - If the callsign has a digit in position 1 (zero-indexed), it is already
    in the form [A-Z][0-9][...] — pad to 6 with trailing spaces.
  - If the callsign has a digit in position 2, prepend one space so the digit
    falls at position 2, then pad to 6 with trailing spaces.
  - E.g. "W1AW"  → " W1AW " (space prepended, 1 trailing space)
           "VK2BJ" → "VK2BJ " (1 trailing space)
           "G3ABC" → " G3ABC" (space prepended)

Encode each of the 6 normalised positions using these character sets:
  Position 0: " ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789" (37 values: space=0, A-Z=1–26, 0–9=27–36)
  Position 1: "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"  (36 values: A-Z=0–25, 0–9=26–35)
  Position 2: "0123456789"                             (10 values: 0–9)
  Position 3: " ABCDEFGHIJKLMNOPQRSTUVWXYZ"            (27 values: space=0, A-Z=1–26)
  Position 4: " ABCDEFGHIJKLMNOPQRSTUVWXYZ"            (27 values)
  Position 5: " ABCDEFGHIJKLMNOPQRSTUVWXYZ"            (27 values)

N28 = (((((n0 * 36 + n1) * 10 + n2) * 27 + n3) * 27 + n4) * 27 + n5) + 2063592 + 1000
     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
     The +2063592+1000 offset (= 2064592) places standard callsigns above the reserved
     range used by CQ (0), DE (1), QRZ (2), and CQ_nnn (3–1002).

Pack N28 into 4 bytes, MSB-first:
  byte[0] = (N28 >> 21) & 0x7F
  byte[1] = (N28 >> 14) & 0x7F  (only 7 bits needed per byte since N28 ≤ 2^28 − 1)
  byte[2] = (N28 >>  7) & 0x7F
  byte[3] =  N28        & 0x7F

  More precisely (MSB-first bit packing for the 28-bit value):
  byte[0] = (byte)((N28 >> 20) & 0xFF)
  byte[1] = (byte)((N28 >> 12) & 0xFF)
  byte[2] = (byte)((N28 >>  4) & 0xFF)
  byte[3] = (byte)((N28 <<  4) & 0xF0)   ← bits 0–3 of N28 in the high nibble of byte 3
```

**Scope restriction for this task:** implement and test standard callsigns only. The QSO
answerer only ever works with callsigns decoded from standard FT8 QSO messages, which are
always standard callsigns. Non-standard callsigns, CQ tokens, DE, and QRZ are out of scope.
If a callsign fails the standard-format validation, return an empty array — `SetApBits`
treats an empty array as "AP disabled" and degrades gracefully.

A callsign is a **standard callsign** if, after optional leading-space normalisation, it
matches the regex `^[A-Z0-9][A-Z0-9][0-9][A-Z ][A-Z ][A-Z ]$` (6-char normalised form).

**New test file:** `tests/OpenWSFZ.Ft8.Tests/Ft8CallsignPackerTests.cs`

Write unit tests verifying known-good pack values against the FT8 protocol spec.
Use only Q-prefix ITU-unallocated callsigns (NFR-021): `Q1ABC`, `Q9XYZ`, `QA1BC`, etc.
Derive expected N28 values by hand from the algorithm above and assert `byte[]` output.
Include at least: a 1-prefix callsign, a 2-prefix callsign, one with trailing spaces,
and one that fails validation (returns empty array).

---

### Step 2 — New record: `Ft8ApConstraints`

**New file:** `src/OpenWSFZ.Ft8/Ft8ApConstraints.cs`

```csharp
namespace OpenWSFZ.Ft8;

/// <summary>
/// AP decode constraints for a directed FT8 decode (H6, D-001).
/// Packed bit arrays for mycall and hiscall, injected as hard LLR
/// constraints (±40.0) into the pass-0 LDPC input via ft8_set_ap_bits().
/// </summary>
/// <param name="MycallBits">
///   28-bit packed mycall, MSB-first, 4 bytes. Produced by
///   <see cref="Ft8CallsignPacker.Pack28"/>. Empty array disables the mycall constraint.
/// </param>
/// <param name="HiscallBits">
///   28-bit packed hiscall, MSB-first, 4 bytes.
/// </param>
public sealed record Ft8ApConstraints(byte[] MycallBits, byte[] HiscallBits);
```

---

### Step 3 — Wire `SetApBits` into `Ft8Decoder`

**File:** `src/OpenWSFZ.Ft8/Ft8Decoder.cs`

**3a.** Add a private field and a thread-safe setter:

```csharp
private volatile Ft8ApConstraints? _apConstraints;

/// <summary>
/// Supplies AP bit constraints for the next decode cycle (H6, D-001).
/// Call before <see cref="DecodeAsync"/> during active QSO states.
/// Pass <c>null</c> to disable AP decode (default; shim behaves as pre-20260020).
/// </summary>
public void SetApConstraints(Ft8ApConstraints? constraints)
    => _apConstraints = constraints;
```

**3b.** Inside the existing `Task.Run` lambda in `DecodeAsync`, add the `SetApBits` call
**before** the `_interop.DecodeAll(normalisedPcm)` line. The existing comment block already
documents the TLS thread-affinity constraint — place the new call immediately before
`DecodeAll`, consistent with that contract:

```csharp
// AP decode constraints (H6, D-001): must be set on the same thread as DecodeAll.
// Snapshot to avoid tearing — _apConstraints is volatile but is a reference type.
var ap = _apConstraints;
if (ap is not null)
    _interop.SetApBits(ap.MycallBits, ap.HiscallBits);
else
    _interop.SetApBits([], []);  // explicitly clear any TLS residue from a prior cycle

var r = _interop.DecodeAll(normalisedPcm);
```

**3c.** Add `SetApBits` to `IFt8NativeInterop` — it is already there. Add a no-op
implementation to any test doubles used in `OpenWSFZ.Ft8.Tests` if they do not already
implement it (check `FakeFt8NativeInterop` or equivalent).

---

### Step 4 — Wire from `QsoAnswererService`

**File:** `src/OpenWSFZ.Daemon/QsoAnswererService.cs`

**4a.** Inject `Ft8Decoder` (the concrete type, not `IModeDecoder`) into
`QsoAnswererService` via constructor. The production DI registration in `Program.cs`
already has `Ft8Decoder` as a singleton — add it as a constructor parameter alongside the
existing `ChannelReader<IReadOnlyList<DecodeResult>>` parameter. The decoder is **not**
used to decode inside `QsoAnswererService`; it is used only to call `SetApConstraints`.

If injecting the concrete type feels wrong, extract a minimal interface
`IApConstraintSink` with a single `SetApConstraints(Ft8ApConstraints?)` method, implement
it on `Ft8Decoder`, and inject `IApConstraintSink`. Either approach is acceptable.

**4b.** When a QSO becomes active — specifically, when `_partner` is set and the state
transitions to `WaitReport` — compute and apply AP constraints:

```csharp
// Called at the point where _partner and _state are assigned (currently the
// "answer CQ" path, around line 296 in QsoAnswererService.cs):
var mycallBits  = Ft8CallsignPacker.Pack28(configStore.Current.Tx?.Callsign ?? "");
var hiscallBits = Ft8CallsignPacker.Pack28(partner);
_decoder.SetApConstraints(
    mycallBits.Length > 0 && hiscallBits.Length > 0
        ? new Ft8ApConstraints(mycallBits, hiscallBits)
        : null);
```

If either callsign fails packing (returns empty array), pass `null` — AP is disabled and
the decoder falls back to standard behaviour. Log a warning in this case.

**4c.** When the QSO ends or is aborted — in `ResetToIdle()` or equivalent — clear the
constraints:

```csharp
_decoder.SetApConstraints(null);
```

---

### Step 5 — Integration test for H6 efficacy

**File:** `tests/OpenWSFZ.Ft8.Tests/D001H6ApDecodeTests.cs` (new file)

This is the authoritative efficacy test for H6. It must use the **real native decoder**
(not a fake), so it belongs in `OpenWSFZ.Ft8.Tests` alongside the existing WAV-fixture
decode tests.

**Fixture:** Commit a synthetic co_channel WAV to
`tests/OpenWSFZ.Ft8.Tests/Fixtures/cochannel_equal_snr_0db.wav` — two equal-SNR FT8
signals at the same audio frequency, synthesised using `qa/rr-study/synth/` with known
callsigns and a known SNR (e.g., 0 dB, matching S7 part P0). Use Q-prefix callsigns only
(NFR-021), e.g. mycall = `Q1OFZ`, hiscall = `Q9XYZ`.

**Test structure:**

```csharp
[Fact(DisplayName = "D-001 H6: AP decode recovers co-channel message when AP bits are correct")]
public async Task ApDecode_WithCorrectBits_RecoversCoChannelMessage()
{
    // Arrange: load WAV, construct real decoder
    // Act: call SetApConstraints with correct packed bits, then DecodeAsync
    // Assert: decoded results contain the expected message
}

[Fact(DisplayName = "D-001 H6: blind decode fails on co-channel (baseline regression guard)")]
public async Task BlindDecode_WithoutApBits_FailsOnCoChannel()
{
    // Arrange: same WAV, no AP constraints
    // Act: DecodeAsync with _apConstraints = null
    // Assert: result count == 0 (baseline: AP decode is what makes the difference)
}
```

Both tests must pass before the branch is submitted for review.

---

## 4. Acceptance Criteria

- [ ] `Ft8CallsignPacker.Pack28` correctly encodes standard callsigns per the FT8 spec
      algorithm; unit tests pass with Q-prefix callsigns only (NFR-021)
- [ ] `Pack28` returns an empty array for non-standard callsigns without throwing
- [ ] `SetApBits` is called on the same thread-pool thread as `DecodeAll` (inside
      the `Task.Run` lambda); the existing TLS comment block is not split across an await
- [ ] `SetApBits([], [])` is called when constraints are null, clearing TLS residue
- [ ] `QsoAnswererService` calls `SetApConstraints` when entering `WaitReport` and clears
      it in `ResetToIdle`
- [ ] If either callsign fails packing, a warning is logged and AP is disabled gracefully
- [ ] Integration test: AP decode recovers at least the mycall or hiscall message from the
      co_channel fixture when correct bits are supplied
- [ ] Integration test: blind decode (no AP) returns 0 results from the same fixture
- [ ] All 457 existing tests still pass; 0 errors, 0 warnings
- [ ] No real or ITU-assignable callsigns in any new fixture or test (NFR-021)

---

## 5. References

- Shim 20260020 seam: `src/OpenWSFZ.Ft8/Native/ft8_shim.c` §AP decode setter (line ~908)
- Native bit layout: `ft8_shim.c` lines ~1018–1055 (maps packed bits → `log174[0..55]`)
- P/Invoke declaration: `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs` §`SetApBits`
- Interface: `src/OpenWSFZ.Ft8/Interop/IFt8NativeInterop.cs` §`SetApBits`
- Failure mechanism (wrong-sign LLRs): `qa/rr-study/results/2026-06-18-3c2ad02/report.md` §5
- FT8 protocol spec (callsign encoding, §3.1): Franke & Taylor, WSJT-X documentation
- D-001 diagnostic history and lessons learned: `memory/MEMORY.md` §NS-001
- HK-000 procedure: `memory/MEMORY.md` §HK-000
- GitHub Issue #3
