# QA Review — `feat/p10-decoder-ground-truth`

**Reviewer:** QA Engineer  
**Date:** 2026-05-29  
**Branch:** `feat/p10-decoder-ground-truth`  
**Verdict:** ❌ NOT APPROVED — 3 required fixes before merge

---

## Summary

The delivery is substantively correct. All tasks 1–10.1 are complete, the G6 gate is properly wired, the decision gate has been closed at 0.0% recovery (→ Phase 2A: port `ft8_lib`), and the change specification is satisfied. Three code defects must be resolved before merge. Two advisory notes are included for awareness.

---

## Required Fixes

### Fix 1 — `src/OpenWSFZ.Daemon/AllTxtWriter.cs` 🔴 HIGH

**Problem:** `AppendAsync` catches only `IOException` and `UnauthorizedAccessException`. If `config.Path` is an empty string, `new StreamWriter("", …)` throws `ArgumentException`. If it contains a Windows reserved device name with a colon suffix (e.g. `"con:"`), it throws `NotSupportedException`. Neither derives from `IOException`, so both escape the try-catch, propagate to the outer `catch (Exception ex)` in `Program.cs`, and are logged as `Error("Decode error: …")` — wrong level, wrong message — on every 15-second decode cycle thereafter.

**Design requirement breached:** `p9/design.md` Risks section:
> *"Invalid path configured → `AllTxtWriter` SHALL log a Warning and skip writing for that cycle; it SHALL NOT throw."*

**Fix:** Add a final catch-all after the two existing catch blocks.

```csharp
// AllTxtWriter.cs — AppendAsync try/catch

catch (IOException ex)
{
    _logger.LogWarning(ex,
        "FR-028: Failed to write decode log to '{Path}' — {Message}. " +
        "Decode results and WebSocket broadcast are unaffected.",
        path, ex.Message);
}
catch (UnauthorizedAccessException ex)
{
    _logger.LogWarning(ex,
        "FR-028: Access denied writing decode log to '{Path}' — {Message}. " +
        "Decode results and WebSocket broadcast are unaffected.",
        path, ex.Message);
}
catch (Exception ex)   // ← ADD THIS
{
    _logger.LogWarning(ex,
        "FR-028: Cannot write decode log to '{Path}' — {Message}. " +
        "Decode results and WebSocket broadcast are unaffected.",
        path, ex.Message);
}
```

---

### Fix 2 — `tests/OpenWSFZ.Ft8.Tests/WavReader.cs` 🟡 MEDIUM

**Problem:** The chunk-walking loop reads exactly `chunkSize` bytes and immediately reads the next chunk header. The RIFF specification requires that any chunk whose data is an odd number of bytes is followed by one silent pad byte (not counted in `chunkSize`) to maintain word alignment. Without this step, a WAV with any odd-sized chunk — for example a `LIST/INFO` metadata tag containing a 7-character software name — reads the next chunk header one byte early, producing a garbage FourCC and throwing `InvalidDataException("Not a RIFF file")`.

The three committed WSJT-X fixtures happen to have even-sized chunks, so no existing test catches this.

**Fix:** After every `reader.ReadBytes(chunkSize)` call, skip the pad byte if the chunk size is odd.

```csharp
// WavReader.cs — chunk walk switch statement

case "fmt ":
    audioFormat   = reader.ReadInt16();
    channels      = reader.ReadInt16();
    sampleRate    = reader.ReadInt32();
    reader.ReadInt32(); // byte rate
    reader.ReadInt16(); // block align
    bitsPerSample = reader.ReadInt16();
    int extra = chunkSize - 16;
    if (extra > 0) reader.ReadBytes(extra);
    if (chunkSize % 2 != 0 && stream.Position < stream.Length) reader.ReadByte(); // ← ADD
    break;

case "data":
    audioData = reader.ReadBytes(chunkSize);
    if (chunkSize % 2 != 0 && stream.Position < stream.Length) reader.ReadByte(); // ← ADD
    break;

default:
    reader.ReadBytes(chunkSize);
    if (chunkSize % 2 != 0 && stream.Position < stream.Length) reader.ReadByte(); // ← ADD
    break;
```

**Suggested test:** Add a `WavReaderTests` case that constructs a hand-crafted WAV with an odd-sized `JUNK` chunk followed by a valid `data` chunk, and asserts the correct sample count is returned.

---

### Fix 3 — `tests/OpenWSFZ.Ft8.Tests/ReplayHarnessTests.cs` 🟡 MEDIUM

**Problem:** In the per-file `foreach` loop, `ParseClockFromTimestamp(timestamp)` is called **between** the `WavReader.Read` try-catch and the `decoder.DecodeAsync` try-catch — inside neither. If the corpus directory contains any file whose stem does not match the `YYMMDD_HHMMSS` pattern (a stray file, a backup, a name shorter than 13 characters), `int.Parse` throws `FormatException` or the range slice throws `ArgumentOutOfRangeException`. Neither is caught; the exception propagates and fails the **entire harness test** instead of logging `[SKIP]` and continuing.

**Current structure (simplified):**

```csharp
foreach (string wavPath in wavFiles)
{
    try   { pcm = WavReader.Read(wavPath); }
    catch { _out.WriteLine("[SKIP]..."); continue; }

    var clock = ParseClockFromTimestamp(timestamp);  // ← UNGUARDED — throws here = whole test dies

    try   { results = await decoder.DecodeAsync(...); }
    catch { _out.WriteLine("[ERROR]..."); continue; }
}
```

**Fix:** Wrap `ParseClockFromTimestamp` in its own try-catch.

```csharp
FakeClock clock;
try
{
    clock = ParseClockFromTimestamp(timestamp);
}
catch (Exception ex)
{
    _out.WriteLine($"[SKIP] {wavName}: cannot parse timestamp — {ex.Message}");
    continue;
}
```

---

## Advisory Notes

These do not block merge but should be addressed when convenient.

### Note A — `AllTxtWriter.cs` — Midnight-crossing timestamp (LOW)

The `date` component of each ALL.TXT line is derived from `cycleUtc`, while `timePart` comes from `result.Time`. For a decode cycle that spans midnight UTC, a signal decoded at e.g. `00:00:05` will be stamped `260528_000005` when the correct date is `260529`. WSJT-X avoids this by using a single timestamp source.

This is the documented design decision **D3** in `p9/design.md` and the `cycleUtc` XML doc comment acknowledges it. No action required at this time; flag if ALL.TXT timestamp fidelity becomes important in a later change.

### Note B — `tests/OpenWSFZ.Daemon.Tests/AllTxtWriterTests.cs` — Dead code in test stub (LOW)

`StubConfigStore.SaveAsync` contains:

```csharp
Current.GetType(); // suppress unused warning on the event field
```

`Current.GetType()` has no side effects. The comment is incorrect — `OnSaved?.Invoke(config)` on the very next line already constitutes a use of the `OnSaved` field; the compiler does not raise CS0067. Please remove the dead call and its comment.

---

## Compliance Checklist

| Item | Status |
|---|---|
| All tasks 1–10.1 complete | ✅ |
| FR-029 cited in test display names | ✅ |
| NFR-016 cited in G6 gate test | ✅ |
| G6 wired in `ci.yml` inside G1 `dotnet test` | ✅ |
| Decision gate closed — 0.0% → Phase 2A | ✅ |
| `findings.md` written by harness | ✅ |
| D3 (midnight timestamp) documented | ✅ |
| Fix 1 — `AllTxtWriter` SHALL NOT throw violated | ❌ |
| Fix 2 — RIFF odd-byte padding absent | ❌ |
| Fix 3 — Harness aborts on bad filename | ❌ |

---

## Re-Submission

Please address Fixes 1–3 and re-submit for a focused re-review. Advisory Notes A and B may be resolved in the same pass or deferred to a housekeeping commit — at your discretion.
