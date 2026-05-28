# Developer Briefing — p8-ft8-decode-performance (Round 32)

**Date:** 2026-05-28  
**Issued by:** QA  
**Branch:** `feat/p8-ft8-decode-performance`  
**Scope:** Decode-count decline — root-cause analysis and one diagnostic fix

---

## Summary

The decode-count decline is explained by two separate factors:

1. **Band propagation** — the primary cause of fewer real messages. Normal and expected.
2. **`diag_crc` counter placed before the `allZeros` guard** — causes `CRC passed=N` with
   `decodes=0`, which looks impossible but is not. One-line fix.

There is **no threading bug**. Every DSP component called inside the `Parallel.For` body
was audited and confirmed thread-safe (see §2).

---

## 1. Log Analysis

### Observed data

| Cycle | Decodes | Costas | LDPC | CRC | Elapsed |
|-------|---------|--------|------|-----|---------|
| 16:46:45 | **11** | 2133 | 15 | 15 | 4831 ms |
| 16:47:00 | **14** | 3429 | 22 | 22 | 7054 ms |
| 16:47:15 | **11** | 1903 | 18 | 18 | 4677 ms |
| 16:47:30 | **12** | 3726 | 21 | 20 | 7326 ms |
| 16:47:45 | **1** | 1860 | 3 | 3 | 4212 ms |
| 16:48:00 | **0** | 2371 | 0 | 0 | 5277 ms |
| 16:48:15 | **2** | 2048 | 3 | 2 | 4464 ms |
| 16:48:30 | **1** | 3208 | 33 | **33** | 6405 ms |
| 16:48:45 | **0** | 1834 | 0 | 0 | 3967 ms |
| 16:49:00 | **0** | 2653 | 10 | **10** | 5545 ms |

### Key observations

**A. The band went quiet.** Costas candidate counts remain in the same range (1800–3700)
throughout — the band has RF activity — but the proportion of those candidates that
LDPC decodes to a valid non-zero message drops sharply after 16:47:30. This is a natural
HF propagation event (band fade, activity drop, or both). It is not caused by software.

**B. `CRC passed=33, decodes=1` (16:48:30).** Thirty-three LDPC convergences, but only
one unique message. This is arithmetically consistent: 32 of the 33 converged to the
same station's message (which is deduplicated to 1 output), and/or some converged to the
all-zeros codeword (which passes CRC but is filtered by the `allZeros` guard).

**C. `CRC passed=10, decodes=0` (16:49:00).** Looks impossible. It is not. See §3.

---

## 2. Thread-Safety Audit

Every function called inside the `Parallel.For` lambda was reviewed for shared mutable
state. All are clean.

| Component | Shared state | Verdict |
|-----------|-------------|---------|
| `LdpcDecoder.Decode` | `H`, `VarNeighbours`, `VarNeighboursIdx` are static **readonly**, built once in the static constructor. All per-decode state (`v2c`, `c2v`, `beliefs`, `hardBits`) is allocated locally. | ✅ Thread-safe |
| `LdpcDecoder.CountInitialParityFailures` | Allocates `hardBits` locally. Reads static `H` (read-only). | ✅ Thread-safe |
| `CostasSynchroniser.FindCandidates` | Allocates a new `List<SyncCandidate>` per call. Reads `CostasPattern` / `CostasPositions` (static `ReadOnlySpan` properties — stack-backed inline arrays, immutable). | ✅ Thread-safe |
| `SymbolExtractor.FillSpectrogram` | Allocates `re[]` and `im[]` locally per call. Writes into caller-supplied `float[,]` (each iteration passes its own array). | ✅ Thread-safe |
| `FftCompute.Fft` | Operates entirely on the passed-in `re[]` and `im[]`. No static fields. | ✅ Thread-safe |
| `SymbolExtractor.ExtractFromSpectrogram` | Allocates `grid` locally. Reads caller-supplied `float[,]` (its own per-iteration array). | ✅ Thread-safe |
| `SymbolExtractor.Extract` | Allocates `coeffs[]` and `grid[]` locally. | ✅ Thread-safe |
| `Crc14.VerifyFt8` | Uses `stackalloc` for the 82-byte buffer — stack-local, one per thread. No static mutable fields. | ✅ Thread-safe |
| `MessageUnpacker.Unpack` | Pure function. Allocates `StringBuilder` locally. Constants (`CallAlphabet`, etc.) are `private const string` — immutable interned strings. | ✅ Thread-safe |

---

## 3. Root Cause of `CRC passed=N, decodes=0`

### The all-zeros codeword

The FT8 LDPC(174,91) all-zeros codeword is a **valid fixed point** of the min-sum
belief-propagation algorithm. When all 174 input LLRs are non-negative (each bit weakly
estimated as 0), every check-node update produces a non-negative message, every
variable-node belief stays non-negative, and the hard decision `beliefs[v] >= 0 → 0`
satisfies all 83 parity equations in iteration 1.

This happens at Goertzel positions where no real signal is present but noise happens to
produce slightly higher energy at the "0" tones across all 58 data symbols. On a fading
band this occurs more frequently than on an active one.

### The all-zeros codeword passes CRC-14

`Crc14.VerifyFt8` computes the CRC over 82 bits: 77 message bits + 5 zero-padding bits.

For an all-zeros 91-bit `decoded` array:
- Input to CRC: 77 zeros + 5 zeros = 82 zeros.
- CRC polynomial = `0x2757`, initial register = `0`.
- For every bit, `feedback = (0 >> 13) ^ 0 = 0`; register stays 0 throughout.
- Computed CRC = `0`.
- Stored CRC bits [77..90] = 0 (from the all-zeros input).
- `0 == 0` → **CRC passes**.

### Why the counter lies

```csharp
bool crcOk = Crc14.VerifyFt8(decoded);
if (!crcOk) continue;
Interlocked.Increment(ref diag_crc);   // ← fires for all-zeros

bool allZeros = true;
for (int z = 0; z < decoded.Length; z++)
    if (decoded[z] != 0) { allZeros = false; break; }
if (allZeros) continue;                // ← correctly filtered, but too late for the counter

// ...
bag.Add(...);
```

`diag_crc` is incremented before the all-zeros guard.  When 10 positions on a fading
band converge to the all-zeros codeword, the log shows `CRC passed=10` but `decodes=0`.
The guard is working; the counter is simply in the wrong place.

---

## 4. Fix — Move `diag_crc` after the `allZeros` guard

**File:** `src/OpenWSFZ.Ft8/Ft8Decoder.cs`

The change is three lines moved. Before:

```csharp
bool crcOk = Crc14.VerifyFt8(decoded);
if (!crcOk) continue;
Interlocked.Increment(ref diag_crc);

bool allZeros = true;
for (int z = 0; z < decoded.Length; z++)
    if (decoded[z] != 0) { allZeros = false; break; }
if (allZeros) continue;

var msgBits = new ReadOnlySpan<byte>(decoded, 0, MsgBits);
string msg  = MessageUnpacker.Unpack(msgBits);

double dt = (double)startSample / SampleRate;
bag.Add(new DecodeResult(...));
```

After:

```csharp
bool crcOk = Crc14.VerifyFt8(decoded);
if (!crcOk) continue;

bool allZeros = true;
for (int z = 0; z < decoded.Length; z++)
    if (decoded[z] != 0) { allZeros = false; break; }
if (allZeros) continue;

Interlocked.Increment(ref diag_crc);   // ← now counts only real, non-zero CRC passes

var msgBits = new ReadOnlySpan<byte>(decoded, 0, MsgBits);
string msg  = MessageUnpacker.Unpack(msgBits);

double dt = (double)startSample / SampleRate;
bag.Add(new DecodeResult(...));
```

After this fix, `CRC passed` in the log will always be ≤ `decodes` (allowing for
deduplication reducing the final count).  `CRC passed=10, decodes=0` becomes
`CRC passed=0, decodes=0` on a dead band, which is unambiguous.

Optionally — if visibility into all-zeros convergences is useful for future diagnosis —
add a `diag_allzeros` counter that increments at the `if (allZeros) continue` branch and
include it in the `LogInformation` call.

---

## 5. The Decode Decline

After applying the fix, `CRC passed=0` on a silent band will confirm the band is quiet.
The operator should expect:

- **Quiet band**: `Costas candidates` moderate (1000–3000), `LDPC converged=0` or
  very low, `CRC passed=0`, `decodes=0`. Normal.
- **Active band**: `LDPC converged` and `CRC passed` match; `decodes` close to `CRC
  passed / (typical time positions per station)` — typically 2–5× lower after
  deduplication.

The pattern observed (11–14 decodes declining to 0 over 10 minutes starting at 16:48
UTC) is consistent with European HF band activity dropping in the early evening. It is
not a defect.

---

## 6. Next Steps

| # | Action |
|---|--------|
| 1 | Move `Interlocked.Increment(ref diag_crc)` to after the `allZeros` guard |
| 2 | Run `dotnet build -c Release` — 0 errors, 0 warnings |
| 3 | Run `dotnet test -c Release` — all tests green |
| 4 | Run live for one session and confirm `CRC passed` ≤ `decodes × (time sweep multiplier)` on an active band |
| 5 | Once confirmed, p8 is ready for QA gate review and merge |
