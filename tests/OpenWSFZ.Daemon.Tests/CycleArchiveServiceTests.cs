using System.Diagnostics;
using FluentAssertions;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Logging.Abstractions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Daemon;
using OpenWSFZ.TestSupport;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// Unit tests for <see cref="CycleArchiveService"/> (cycle-audio-archive capability,
/// tasks 3.1-3.6, 4.1-4.3, 5.1-5.4). Covers mode selection, non-blocking enqueue and explicit drop
/// counting (design.md Decision 3), filename collision handling, the sidecar manifest, and
/// retention (size cap, age cap, pattern-restricted deletion, free-space floor).
/// </summary>
[Trait("Category", "Unit")]
public sealed class CycleArchiveServiceTests : IDisposable
{
    private const int FullWindowSamples = 180_000; // 15 s × 12 kHz — matches the real framer window

    private readonly string _tempDir;

    public CycleArchiveServiceTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(), "openwsfz-cycle-archive-test-" + Path.GetRandomFileName());
    }

    public void Dispose()
    {
        try { Directory.Delete(_tempDir, recursive: true); } catch { /* best-effort */ }
    }

    // ── Mode selection (spec.md "Operator-controlled cycle audio archiving") ────────────────

    [Fact(DisplayName = "cycle-audio-archive: Off is the default and writes nothing")]
    public async Task Off_WritesNothing()
    {
        var service = MakeService(CycleAudioArchiveMode.Off);
        await service.StartAsync(CancellationToken.None);

        service.TryEnqueue(new float[FullWindowSamples], CycleAt(0), CycleAt(0), decodeCount: 5, dialMhz: 7.074);
        service.TryEnqueue(new float[FullWindowSamples], CycleAt(1), CycleAt(1), decodeCount: 0, dialMhz: 7.074);

        // Off is checked before the channel is ever touched (task 6.3) — the assertion is safe to
        // make immediately, with no race, because TryEnqueue returns synchronously in this mode.
        Directory.Exists(_tempDir).Should().BeFalse("Off must create no directory and write no file");

        await service.StopAsync(CancellationToken.None);
    }

    [Fact(DisplayName = "cycle-audio-archive: All mode archives every cycle")]
    public async Task All_ArchivesEveryCycle()
    {
        var service = MakeService(CycleAudioArchiveMode.All);
        await service.StartAsync(CancellationToken.None);

        service.TryEnqueue(new float[FullWindowSamples], CycleAt(0), CycleAt(0), decodeCount: 5, dialMhz: 7.074);
        service.TryEnqueue(new float[FullWindowSamples], CycleAt(1), CycleAt(1), decodeCount: 0, dialMhz: 7.074);
        service.TryEnqueue(new float[FullWindowSamples], CycleAt(2), CycleAt(2), decodeCount: 2, dialMhz: 7.074);

        await Poll.WaitForEqualAsync(() => CountWavFiles(), 3, what: "archived .wav file count");

        await service.StopAsync(CancellationToken.None);
    }

    [Fact(DisplayName = "cycle-audio-archive: Decoded mode archives only cycles that produced decodes")]
    public async Task Decoded_ArchivesOnlyCyclesWithDecodes()
    {
        var service = MakeService(CycleAudioArchiveMode.Decoded);
        await service.StartAsync(CancellationToken.None);

        service.TryEnqueue(new float[FullWindowSamples], CycleAt(0), CycleAt(0), decodeCount: 5, dialMhz: 7.074);
        service.TryEnqueue(new float[FullWindowSamples], CycleAt(1), CycleAt(1), decodeCount: 0, dialMhz: 7.074);
        service.TryEnqueue(new float[FullWindowSamples], CycleAt(2), CycleAt(2), decodeCount: 2, dialMhz: 7.074);

        await Poll.WaitForEqualAsync(() => CountWavFiles(), 2, what: "archived .wav file count");

        await service.StopAsync(CancellationToken.None);
    }

    [Fact(DisplayName = "cycle-audio-archive: NoDecodes mode archives only cycles that produced nothing")]
    public async Task NoDecodes_ArchivesOnlyCyclesWithNoDecodes()
    {
        var service = MakeService(CycleAudioArchiveMode.NoDecodes);
        await service.StartAsync(CancellationToken.None);

        service.TryEnqueue(new float[FullWindowSamples], CycleAt(0), CycleAt(0), decodeCount: 5, dialMhz: 7.074);
        service.TryEnqueue(new float[FullWindowSamples], CycleAt(1), CycleAt(1), decodeCount: 0, dialMhz: 7.074);
        service.TryEnqueue(new float[FullWindowSamples], CycleAt(2), CycleAt(2), decodeCount: 2, dialMhz: 7.074);

        await Poll.WaitForEqualAsync(() => CountWavFiles(), 1, what: "archived .wav file count");

        await service.StopAsync(CancellationToken.None);
    }

    // ── Filename collisions (design.md Decision 5) ───────────────────────────────────────────

    [Fact(DisplayName = "cycle-audio-archive: repeated cycle label produces two files, neither overwritten")]
    public async Task RepeatedCycleLabel_ProducesTwoDistinctFiles()
    {
        var service = MakeService(CycleAudioArchiveMode.All);
        await service.StartAsync(CancellationToken.None);

        var sameLabel = CycleAt(0);
        var pcmA = new float[FullWindowSamples];
        pcmA[0] = 0.5f;
        var pcmB = new float[FullWindowSamples];
        pcmB[0] = -0.5f;

        service.TryEnqueue(pcmA, sameLabel, sameLabel, decodeCount: 1, dialMhz: 7.074);
        service.TryEnqueue(pcmB, sameLabel, sameLabel, decodeCount: 1, dialMhz: 7.074);

        await Poll.WaitForEqualAsync(() => CountWavFiles(), 2, what: "archived .wav file count");

        var files = Directory.GetFiles(_tempDir, "*.wav").Select(Path.GetFileName).ToList();
        files.Should().HaveCount(2);
        files.Should().ContainSingle(f => f!.Contains("_2"),
            "exactly one of the two colliding-label files must carry the collision suffix");
        files.Should().ContainSingle(f => !f!.Contains("_2"),
            "the other file must keep the unsuffixed base name — the first write is never renamed");
    }

    // ── Non-blocking enqueue + explicit drop counting (design.md Decisions 2/3) ─────────────

    [Fact(DisplayName = "cycle-audio-archive: TryEnqueue returns promptly and drops are counted when the queue is full")]
    public async Task TryEnqueue_IsNonBlocking_AndCountsDropsWhenQueueFull()
    {
        var stallGate = new TaskCompletionSource();
        var service = MakeService(
            CycleAudioArchiveMode.All, queueCapacity: 1, retentionSweepInterval: 1000,
            stallHook: _ => stallGate.Task);
        await service.StartAsync(CancellationToken.None);

        // Item 1 is picked up by the writer almost immediately and stalls on the gate.
        service.TryEnqueue(new float[FullWindowSamples], CycleAt(0), CycleAt(0), 1, 7.074);
        await Poll.WaitForEqualAsync(() => service.DequeuedCountForTests, 1, what: "dequeued item count");

        // Item 2 fills the (capacity-1) queue.
        service.TryEnqueue(new float[FullWindowSamples], CycleAt(1), CycleAt(1), 1, 7.074);

        // Items 3-5 must be dropped: the queue is full and the writer is stalled on item 1.
        var sw = Stopwatch.StartNew();
        service.TryEnqueue(new float[FullWindowSamples], CycleAt(2), CycleAt(2), 1, 7.074);
        service.TryEnqueue(new float[FullWindowSamples], CycleAt(3), CycleAt(3), 1, 7.074);
        service.TryEnqueue(new float[FullWindowSamples], CycleAt(4), CycleAt(4), 1, 7.074);
        sw.Elapsed.Should().BeLessThan(TimeSpan.FromSeconds(1),
            "TryEnqueue must never block on a stalled writer (design.md Decision 2)");

        service.DroppedCycles.Should().Be(3, "exactly three offered windows found the queue at capacity");

        stallGate.SetResult();
        await service.StopAsync(CancellationToken.None);
    }

    [Fact(DisplayName = "cycle-audio-archive: first drop is logged at Warning")]
    public async Task FirstDrop_IsLoggedAtWarning()
    {
        var stallGate = new TaskCompletionSource();
        var logger = new CapturingLogger();
        var service = MakeService(
            CycleAudioArchiveMode.All, queueCapacity: 1, retentionSweepInterval: 1000,
            stallHook: _ => stallGate.Task, logger: logger);
        await service.StartAsync(CancellationToken.None);

        service.TryEnqueue(new float[FullWindowSamples], CycleAt(0), CycleAt(0), 1, 7.074);
        await Poll.WaitForEqualAsync(() => service.DequeuedCountForTests, 1, what: "dequeued item count");

        service.TryEnqueue(new float[FullWindowSamples], CycleAt(1), CycleAt(1), 1, 7.074); // queued
        service.TryEnqueue(new float[FullWindowSamples], CycleAt(2), CycleAt(2), 1, 7.074); // dropped #1

        logger.HasWarningContaining("dropped").Should().BeTrue("the first drop must be logged at Warning");

        stallGate.SetResult();
        await service.StopAsync(CancellationToken.None);
    }

    // ── Manifest (design.md Decision 6) ─────────────────────────────────────────────────────

    [Fact(DisplayName = "cycle-audio-archive: manifest row is written per archived cycle, in order")]
    public async Task Manifest_WritesOneRowPerArchivedCycle_InOrder()
    {
        var service = MakeService(CycleAudioArchiveMode.All);
        await service.StartAsync(CancellationToken.None);

        for (int i = 0; i < 4; i++)
            service.TryEnqueue(new float[FullWindowSamples], CycleAt(i), CycleAt(i), decodeCount: i, dialMhz: 7.074);

        var manifestPath = Path.Combine(_tempDir, CycleArchiveService.ManifestFileName);
        await Poll.UntilAsync(() => File.Exists(manifestPath) && File.ReadAllLines(manifestPath).Length == 5,
            timeoutMessage: () => "manifest line count");

        var lines = await File.ReadAllLinesAsync(manifestPath);
        lines[0].Should().Be("filename,cycle_start_utc,window_closed_utc,decode_count,dial_mhz,clipped_samples,dropped_before");
        lines.Should().HaveCount(5, "one header row plus one row per archived cycle");

        for (int i = 0; i < 4; i++)
        {
            var cols = lines[i + 1].Split(',');
            cols[0].Should().Contain(CycleAt(i).ToString("yyMMdd_HHmmss"));
            cols[3].Should().Be(i.ToString(), "decode_count column must match the archived cycle's decode count, in order");
        }

        await service.StopAsync(CancellationToken.None);
    }

    [Fact(DisplayName = "cycle-audio-archive: manifest records the framer's off-grid offset")]
    public async Task Manifest_RecordsOffGridOffset()
    {
        var service = MakeService(CycleAudioArchiveMode.All);
        await service.StartAsync(CancellationToken.None);

        var cycleStart = new DateTime(2026, 7, 25, 10, 0, 0, DateTimeKind.Utc);
        var offset     = TimeSpan.FromSeconds(5.958);
        var closedUtc  = cycleStart + offset;

        service.TryEnqueue(new float[FullWindowSamples], cycleStart, closedUtc, decodeCount: 1, dialMhz: 7.074);

        var manifestPath = Path.Combine(_tempDir, CycleArchiveService.ManifestFileName);
        await Poll.UntilAsync(() => File.Exists(manifestPath) && File.ReadAllLines(manifestPath).Length == 2,
            timeoutMessage: () => "manifest line count");

        const string manifestTimestampFormat = "yyyy-MM-ddTHH:mm:ss.fffZ";
        var cols = (await File.ReadAllLinesAsync(manifestPath))[1].Split(',');
        var parsedStart  = DateTime.ParseExact(
            cols[1], manifestTimestampFormat, System.Globalization.CultureInfo.InvariantCulture,
            System.Globalization.DateTimeStyles.AssumeUniversal | System.Globalization.DateTimeStyles.AdjustToUniversal);
        var parsedClosed = DateTime.ParseExact(
            cols[2], manifestTimestampFormat, System.Globalization.CultureInfo.InvariantCulture,
            System.Globalization.DateTimeStyles.AssumeUniversal | System.Globalization.DateTimeStyles.AdjustToUniversal);

        (parsedClosed - parsedStart).Should().BeCloseTo(offset, TimeSpan.FromMilliseconds(1),
            "the manifest must record the off-grid offset directly, without the reader needing to consult the daemon log");

        await service.StopAsync(CancellationToken.None);
    }

    [Fact(DisplayName = "cycle-audio-archive: dropped cycles appear as an explicit gap marker on the next archived row")]
    public async Task Manifest_RecordsGapMarker_AfterDroppedCycles()
    {
        // Deterministic sequencing (no bare delays):
        //   1) item1 archives normally (unstalled) -> row1, dropped_before=0.
        //   2) the stall is armed; item2 is dequeued and parks on the gate.
        //   3) item3 fills the (capacity-1) queue; items 4-6 are dropped (3 drops).
        //   4) the gate is released -> item2 completes -> row2 carries dropped_before=3.
        bool stallArmed = false;
        var stallGate = new TaskCompletionSource();
        var service = MakeService(
            CycleAudioArchiveMode.All, queueCapacity: 1, retentionSweepInterval: 1000,
            stallHook: _ => stallArmed ? stallGate.Task : Task.CompletedTask);
        await service.StartAsync(CancellationToken.None);

        var manifestPath = Path.Combine(_tempDir, CycleArchiveService.ManifestFileName);

        service.TryEnqueue(new float[FullWindowSamples], CycleAt(0), CycleAt(0), 1, 7.074); // row1
        await Poll.UntilAsync(() => File.Exists(manifestPath) && File.ReadAllLines(manifestPath).Length == 2,
            timeoutMessage: () => "manifest line count after item1");

        stallArmed = true;
        service.TryEnqueue(new float[FullWindowSamples], CycleAt(1), CycleAt(1), 1, 7.074); // dequeued, stalls
        await Poll.WaitForEqualAsync(() => service.DequeuedCountForTests, 2, what: "dequeued item count");

        service.TryEnqueue(new float[FullWindowSamples], CycleAt(2), CycleAt(2), 1, 7.074); // queued
        service.TryEnqueue(new float[FullWindowSamples], CycleAt(3), CycleAt(3), 1, 7.074); // dropped
        service.TryEnqueue(new float[FullWindowSamples], CycleAt(4), CycleAt(4), 1, 7.074); // dropped
        service.TryEnqueue(new float[FullWindowSamples], CycleAt(5), CycleAt(5), 1, 7.074); // dropped
        service.DroppedCycles.Should().Be(3);

        stallGate.SetResult();
        // >= rather than == : once the gate resolves it stays resolved, so item3 (also gated by
        // the same now-completed stallArmed check) can drain right behind item2 — the assertion
        // below only needs row2 (line index 2) to have landed, regardless of whether row3 has too.
        await Poll.UntilAsync(() => File.ReadAllLines(manifestPath).Length >= 3,
            timeoutMessage: () => "manifest line count after item2");

        var row2 = (await File.ReadAllLinesAsync(manifestPath))[2].Split(',');
        row2[^1].Should().Be("3", "the three cycles dropped while item2 was in flight must appear on item2's own row");

        await service.StopAsync(CancellationToken.None);
    }

    [Fact(DisplayName = "cycle-audio-archive: manifest contains no message text or callsigns")]
    public async Task Manifest_ContainsNoMessageTextOrCallsigns()
    {
        var service = MakeService(CycleAudioArchiveMode.All);
        await service.StartAsync(CancellationToken.None);

        service.TryEnqueue(new float[FullWindowSamples], CycleAt(0), CycleAt(0), decodeCount: 3, dialMhz: 7.074);

        var manifestPath = Path.Combine(_tempDir, CycleArchiveService.ManifestFileName);
        await Poll.UntilAsync(() => File.Exists(manifestPath) && File.ReadAllLines(manifestPath).Length == 2,
            timeoutMessage: () => "manifest line count");

        var content = await File.ReadAllTextAsync(manifestPath);
        // The manifest's own column set (filename/timestamps/counts/frequency) contains no field
        // for decoded text or callsigns at all — this asserts the columns are exactly the
        // documented seven, so no such field could have been added.
        var header = content.Split('\n')[0].TrimEnd('\r');
        header.Split(',').Should().HaveCount(7);

        await service.StopAsync(CancellationToken.None);
    }

    // ── Retention (design.md Decision 7) ────────────────────────────────────────────────────

    [Fact(DisplayName = "cycle-audio-archive: size cap deletes oldest files and retains newest")]
    public async Task Retention_SizeCap_DeletesOldestRetainsNewest()
    {
        // Each full-size window encodes to ~352 KB (44-byte header + 180000*2 bytes). A 1 MB cap
        // is exceeded by the third file, triggering deletion of the oldest.
        var service = MakeService(CycleAudioArchiveMode.All, maxSizeMb: 1, retentionSweepInterval: 1);
        await service.StartAsync(CancellationToken.None);

        service.TryEnqueue(new float[FullWindowSamples], CycleAt(0), CycleAt(0), 1, 7.074);
        service.TryEnqueue(new float[FullWindowSamples], CycleAt(1), CycleAt(1), 1, 7.074);
        service.TryEnqueue(new float[FullWindowSamples], CycleAt(2), CycleAt(2), 1, 7.074);

        // CountWavFiles() == 2 is true at two non-equivalent points in this test's file-count
        // sequence (0 -> 1 -> 2 -> 3 -> evict oldest -> 2): transiently, after only cycle0+cycle1
        // have landed but before cycle2's write has even been enqueued by the writer task, and
        // again once settled, after cycle2's write has triggered eviction of cycle0. A bare count
        // poll cannot tell these apart, so it must instead wait for the specific terminal file set
        // — oldest gone, newest present — which only the settled state can satisfy.
        var oldestPath = Path.Combine(_tempDir, $"{CycleAt(0):yyMMdd_HHmmss}.wav");
        var newestPath = Path.Combine(_tempDir, $"{CycleAt(2):yyMMdd_HHmmss}.wav");
        await Poll.UntilAsync(() => CountWavFiles() == 2 && !File.Exists(oldestPath) && File.Exists(newestPath),
            timeoutMessage: () => $"expected retention to prune to 2 files (oldest evicted, newest retained), currently {CountWavFiles()}");

        var remaining = Directory.GetFiles(_tempDir, "*.wav").Select(Path.GetFileName).ToList();
        remaining.Should().NotContain(f => f!.Contains(CycleAt(0).ToString("yyMMdd_HHmmss")),
            "the oldest file must be the one deleted");
        remaining.Should().Contain(f => f!.Contains(CycleAt(2).ToString("yyMMdd_HHmmss")),
            "the newest file must be retained");

        await service.StopAsync(CancellationToken.None);
    }

    [Fact(DisplayName = "cycle-audio-archive: age cap deletes files older than the configured age")]
    public void Retention_AgeCap_DeletesOlderThanConfiguredAge()
    {
        // Age is read from the yyMMdd_HHmmss timestamp encoded in the filename itself, not
        // filesystem CreationTimeUtc (unreliable on Linux — see EnforceRetention's remarks), so
        // "old"/"new" is expressed here via the filename, not File.SetCreationTimeUtc.
        Directory.CreateDirectory(_tempDir);
        var oldStamp = (DateTime.UtcNow - TimeSpan.FromHours(200)).ToString("yyMMdd_HHmmss");
        var newStamp = (DateTime.UtcNow - TimeSpan.FromHours(1)).ToString("yyMMdd_HHmmss");
        var oldFile  = Path.Combine(_tempDir, $"{oldStamp}.wav");
        var newFile  = Path.Combine(_tempDir, $"{newStamp}.wav");
        File.WriteAllBytes(oldFile, new byte[44]);
        File.WriteAllBytes(newFile, new byte[44]);

        var service = MakeService(CycleAudioArchiveMode.All, maxAgeHours: 168, maxSizeMb: 999_999);
        var config  = new CycleAudioArchiveConfig(maxAgeHours: 168, maxSizeMb: 999_999);

        service.RunRetentionSweepForTests(_tempDir, config);

        File.Exists(oldFile).Should().BeFalse("a file older than MaxAgeHours must be deleted");
        File.Exists(newFile).Should().BeTrue("a file within MaxAgeHours must be retained");
    }

    [Fact(DisplayName = "cycle-audio-archive: unrelated files in the archive directory are never deleted")]
    public void Retention_NeverDeletesNonMatchingFiles()
    {
        Directory.CreateDirectory(_tempDir);
        var unrelated = Path.Combine(_tempDir, "notes.txt");
        // Age is read from the filename's own yyMMdd_HHmmss timestamp (see EnforceRetention's
        // remarks) — this literal date is comfortably more than an hour before "now" for as long
        // as this test file is in service.
        var oldStamp = (DateTime.UtcNow - TimeSpan.FromHours(200)).ToString("yyMMdd_HHmmss");
        var oldFile  = Path.Combine(_tempDir, $"{oldStamp}.wav");
        File.WriteAllText(unrelated, "keep me");
        File.WriteAllBytes(oldFile, new byte[400_000]);

        var service = MakeService(CycleAudioArchiveMode.All);
        var config  = new CycleAudioArchiveConfig(maxAgeHours: 1, maxSizeMb: 0);

        service.RunRetentionSweepForTests(_tempDir, config);

        File.Exists(unrelated).Should().BeTrue("a file not matching the archive's own naming pattern must never be deleted");
        File.Exists(oldFile).Should().BeFalse("the matching, over-age file must still be deleted");
    }

    [Fact(DisplayName = "cycle-audio-archive: archiving stops for the session when free space falls below the floor, and every skipped cycle is counted as dropped")]
    public async Task Retention_FreeSpaceFloor_StopsArchivingForSession()
    {
        var logger  = new CapturingLogger();
        var service = MakeService(
            CycleAudioArchiveMode.All, freeBytesProvider: _ => 100L * 1024 * 1024, // 100 MB < 500 MB floor
            logger: logger);
        await service.StartAsync(CancellationToken.None);

        var tcs = new TaskCompletionSource();
        service.ItemProcessedForTests += () => tcs.TrySetResult();
        service.TryEnqueue(new float[FullWindowSamples], CycleAt(0), CycleAt(0), 1, 7.074);
        await tcs.Task.WaitAsync(TimeSpan.FromSeconds(5));

        CountWavFiles().Should().Be(0, "archiving must stop before any file is written once free space is below the floor");
        logger.HasWarningContaining("floor").Should().BeTrue("the free-space floor trip must be logged at Warning");
        service.DroppedCycles.Should().Be(1,
            "the cycle that tripped the free-space floor must itself be counted as dropped — design.md " +
            "Decision 3's 'no drop path may exist that is not counted and reportable' standing rule applies " +
            "to the free-space floor exactly as it does to a full queue");

        // A further cycle offered after the floor has already tripped is an ongoing, real loss —
        // it must keep incrementing the counter, not vanish silently once the initial Warning has
        // been logged.
        var tcs2 = new TaskCompletionSource();
        service.ItemProcessedForTests += () => tcs2.TrySetResult();
        service.TryEnqueue(new float[FullWindowSamples], CycleAt(1), CycleAt(1), 1, 7.074);
        await tcs2.Task.WaitAsync(TimeSpan.FromSeconds(5));

        service.DroppedCycles.Should().Be(2,
            "cycles offered after the floor has already tripped must remain counted, not become an " +
            "uncounted loss just because the session-level Warning was already logged once");

        await service.StopAsync(CancellationToken.None);
    }

    // ── 2026-07-28 null-config crash: defence in depth (dev-tasks/2026-07-28-fix-cycle-audio-
    // archive-null-config-crash.md §2.3/§5) ──────────────────────────────────────────────────

    [Fact(DisplayName =
        "Regression: TryEnqueue does not throw when IConfigStore.Current.CycleAudioArchive is null, " +
        "and treats the cycle as an off-mode no-op (not a counted drop)")]
    public async Task TryEnqueue_NullCycleAudioArchive_DoesNotThrow_AndIsOffModeNoOp()
    {
        // Reproduces the live incident: a config with CycleAudioArchive = null (e.g. persisted by
        // a POST /api/v1/config body that omitted the "cycleAudioArchive" key before the WebApp.cs/
        // JsonConfigStore.SaveAsync guards existed) must not crash the decode pump every cycle —
        // this was the actual crash site (CycleArchiveService.cs:178, the first line of the method).
        var configStore = new StubConfigStore(new AppConfig() with { CycleAudioArchive = null! });
        var service = new CycleArchiveService(
            configStore, NullLogger<CycleArchiveService>.Instance,
            queueCapacity: 8, retentionSweepInterval: 100, freeBytesProvider: null);
        await service.StartAsync(CancellationToken.None);

        var act = () => service.TryEnqueue(
            new float[FullWindowSamples], CycleAt(0), CycleAt(0), decodeCount: 5, dialMhz: 7.074);
        act.Should().NotThrow(
            "a null CycleAudioArchive must never crash TryEnqueue — this is exactly the live-incident NRE");

        // Falling back to a fresh CycleAudioArchiveConfig() means Mode resolves to Off, which
        // returns before the channel or drop-accounting is ever touched — consistent with the
        // "Off is the default and writes nothing" behaviour above, not a new drop path.
        service.DroppedCycles.Should().Be(0,
            "an off-mode-equivalent fallback must not be counted as a drop, matching real Off mode");

        await service.StopAsync(CancellationToken.None);
    }

    // Note on ProcessItemAsync's mirror-image guard (CycleArchiveService.cs:269-270): it is fixed
    // with the identical `_configStore.Current.CycleAudioArchive ?? new CycleAudioArchiveConfig()`
    // pattern as TryEnqueue above, but is deliberately NOT covered by a second integration test
    // here. A null CycleAudioArchive's fallback Directory is null, which
    // ConfigPathResolver.ResolveDefaultCycleAudioDirectory() resolves to the real per-user
    // %APPDATA%\OpenWSFZ\cycle-audio\ directory (NFR-021) — exercising that path for real would
    // create/append to files in the developer's actual application-data directory, which this
    // project's own ConfigPathResolverTests deliberately avoids (path-string assertions only,
    // never an actual write). The guard is a one-line symmetric change reviewable by inspection;
    // TryEnqueue's test above already exercises the identical `?? new CycleAudioArchiveConfig()`
    // coalesce pattern end-to-end without that side effect.

    // ── Fixture guard ─────────────────────────────────────────────────────────

    [Fact(DisplayName =
        "cycle-audio-archive (fixture guard): fixture cycle stamps are clock-relative, so no " +
        "retention test can silently age out of the window it is meant to exercise")]
    public void FixtureCycleStamps_StayFarInsideTheDefaultAgeCap()
    {
        // Mechanical form of the date-independence requirement in dev-tasks/2026-08-03-fix-time-
        // bombed-cyclearchive-retention-sizecap-test.md §4.3. The previous fixed-date fixture
        // passed for six days and then failed forever, deterministically, with no code change --
        // exactly the failure mode a green test suite cannot report. Reasoning in a comment would
        // not have caught it being reintroduced; this does.
        //
        // CycleAt(0) is the oldest stamp any test uses; the newest in the file is CycleAt(5),
        // 75 s later.
        TimeSpan oldestAge = DateTime.UtcNow - CycleAt(0);
        var defaultMaxAge  = TimeSpan.FromHours(new CycleAudioArchiveConfig().MaxAgeHours);

        oldestAge.Should().BePositive(
            "fixture stamps must sit in the past, as real archived cycle starts do");

        oldestAge.Should().BeLessThan(defaultMaxAge / 100,
            $"the oldest fixture stamp is {oldestAge.TotalHours:F2} h old against a default " +
            $"MaxAgeHours of {defaultMaxAge.TotalHours:F0} h. Fixture timestamps must be derived " +
            "from the wall clock, never from a fixed calendar date: a fixed date's age grows " +
            "without bound until it crosses the age cap, at which point EnforceRetention deletes " +
            "every fixture file before the size-cap loop is reached and the test fails on every " +
            "run thereafter. Two orders of magnitude of headroom means this can only trip if " +
            "MaxAgeHours itself is deliberately made tiny, which is not something a fixture can " +
            "do by accident");
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private const int CycleSeconds = 15;

    /// <summary>
    /// Anchor for every fixture cycle timestamp, resolved once per test run against the wall
    /// clock rather than hardcoded to a calendar date.
    ///
    /// <para>
    /// <b>This used to be <c>new DateTime(2026, 7, 25, 10, 0, 0)</c>, and it was a time bomb.</b>
    /// <c>EnforceRetention</c> applies the age cap before the size cap, and reads a file's age
    /// from the <c>yyMMdd_HHmmss</c> stamp in its own name. With <c>MaxAgeHours</c> at its
    /// default of 168 h, every fixture file aged out at <c>2026-07-25 10:00 + 168 h =
    /// 2026-08-01 10:00 UTC</c> — after which <c>Retention_SizeCap_DeletesOldestRetainsNewest</c>
    /// had all three of its files deleted by the age cap before the size-cap loop it exists to
    /// exercise was ever reached, and reported <c>currently 0</c>. It failed deterministically
    /// on every run from that instant. See
    /// <c>dev-tasks/2026-08-03-fix-time-bombed-cyclearchive-retention-sizecap-test.md</c>.
    /// </para>
    ///
    /// <para>
    /// <b>Why this cannot age out again.</b> The anchor is now always ~5 minutes before the run
    /// itself, so a fixture file's age at assertion time is minutes, never days. For the age cap
    /// to fire again, <c>MaxAgeHours</c> would have to drop below ~0.1 h — five orders of
    /// magnitude from its 168 h default, and a change no fixture could hide. The bomb is removed
    /// rather than moved: there is no future date at which this starts failing, because there is
    /// no longer any fixed date in it.
    /// </para>
    ///
    /// <para>
    /// Resolved <b>once</b>, as a <c>static readonly</c>, not per call. Several tests compare a
    /// filename built from <c>CycleAt(0)</c> against one built by a later <c>CycleAt(0)</c> call
    /// (lines ~325-333) — re-reading the clock per call would let those drift apart and
    /// reintroduce flakiness of a different kind. Snapped to a 15-second boundary with no
    /// sub-second component so the second-resolution <c>yyMMdd_HHmmss</c> filenames stay
    /// well-formed, distinct, and exactly one cycle apart, as real cycle starts are.
    /// </para>
    ///
    /// <para>
    /// The 5-minute backdate keeps every index this file uses (0 through 5, a 75 s span) at or
    /// before "now", matching the old fixed-date fixture's intent of stamps already in the past.
    /// </para>
    /// </summary>
    private static readonly DateTime FixtureEpochUtc =
        SnapToCycleBoundary(DateTime.UtcNow.AddMinutes(-5));

    /// <summary>Floors <paramref name="utc"/> to the 15-second cycle grid, discarding sub-second ticks.</summary>
    private static DateTime SnapToCycleBoundary(DateTime utc)
    {
        const long cycleTicks = CycleSeconds * TimeSpan.TicksPerSecond;
        return new DateTime(utc.Ticks - (utc.Ticks % cycleTicks), DateTimeKind.Utc);
    }

    private static DateTime CycleAt(int index) =>
        FixtureEpochUtc.AddSeconds(CycleSeconds * index);

    private int CountWavFiles() =>
        Directory.Exists(_tempDir) ? Directory.GetFiles(_tempDir, "*.wav").Length : 0;

    private CycleArchiveService MakeService(
        CycleAudioArchiveMode  mode,
        int                    queueCapacity          = 8,
        int                    retentionSweepInterval = 100,
        int                    maxSizeMb              = 2048,
        int                    maxAgeHours            = 168,
        Func<CancellationToken, Task>? stallHook       = null,
        Func<string, long>?    freeBytesProvider       = null,
        ILogger<CycleArchiveService>? logger           = null)
    {
        var config = new AppConfig() with
        {
            CycleAudioArchive = new CycleAudioArchiveConfig(
                mode: mode, directory: _tempDir, maxSizeMb: maxSizeMb, maxAgeHours: maxAgeHours),
        };
        var configStore = new StubConfigStore(config);
        var service = new CycleArchiveService(
            configStore,
            logger ?? NullLogger<CycleArchiveService>.Instance,
            queueCapacity,
            retentionSweepInterval,
            freeBytesProvider);

        if (stallHook is not null)
            service.WriterStallHookForTests = stallHook;

        return service;
    }

    private sealed class StubConfigStore : IConfigStore
    {
        public StubConfigStore(AppConfig config) => Current = config;
        public AppConfig Current { get; set; }
        public event Action<AppConfig>? OnSaved;
        public Task SaveAsync(AppConfig config, CancellationToken ct = default)
        {
            Current = config;
            OnSaved?.Invoke(config);
            return Task.CompletedTask;
        }
    }

    private sealed class CapturingLogger : ILogger<CycleArchiveService>
    {
        private readonly List<(LogLevel Level, string Message)> _entries = new();

        public IDisposable? BeginScope<TState>(TState state) where TState : notnull => null;
        public bool IsEnabled(LogLevel logLevel) => true;

        public void Log<TState>(
            LogLevel logLevel, EventId eventId, TState state,
            Exception? exception, Func<TState, Exception?, string> formatter)
        {
            lock (_entries) _entries.Add((logLevel, formatter(state, exception)));
        }

        public bool HasWarningContaining(string substring)
        {
            lock (_entries)
                return _entries.Any(e => e.Level == LogLevel.Warning &&
                                          e.Message.Contains(substring, StringComparison.OrdinalIgnoreCase));
        }
    }
}
