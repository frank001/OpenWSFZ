using System.Globalization;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Channels;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Config;

namespace OpenWSFZ.Daemon;

/// <summary>
/// Writes each decode cycle's 15-second PCM window to a WSJT-X-byte-compatible <c>.wav</c> file
/// under operator control (<c>cycle-audio-archive</c> capability). Modelled directly on
/// <see cref="ExternalReportingService"/>'s <see cref="IHostedService"/> shape and on
/// <see cref="AllTxtWriter"/>'s position in the decode pump.
///
/// <para>
/// <b>Decode-pump safety (design.md Decision 2):</b> <see cref="TryEnqueue"/> is non-blocking and
/// SHALL NOT be awaited by its caller. All file I/O — WAV encode, write, manifest append,
/// retention sweep — happens on a single dedicated background writer task, never on the calling
/// (decode-pump) thread. A stalled disk therefore never stalls decoding.
/// </para>
///
/// <para>
/// <b>Drop accounting (design.md Decision 3):</b> the internal queue is a
/// <see cref="BoundedChannelFullMode.DropWrite"/> channel. Every drop-mode
/// (<c>DropOldest</c>/<c>DropNewest</c>/<c>DropWrite</c>) bounded channel makes
/// <see cref="ChannelWriter{T}.TryWrite"/> return <c>true</c> unconditionally in .NET — a defect
/// found in this exact codebase on 2026-07-25 (<c>WasapiAudioSource.cs</c>'s unreachable
/// drop-warning). This class never relies on that return value: <see cref="TryEnqueue"/> compares
/// the channel's current count against its capacity <em>before</em> writing and increments
/// <see cref="DroppedCycles"/> explicitly when it cannot accept.
/// </para>
/// </summary>
public sealed class CycleArchiveService : IHostedService, IAsyncDisposable
{
    /// <summary>Sidecar manifest filename, written inside the archive directory.</summary>
    public const string ManifestFileName = "cycle-archive.csv";

    private const string ManifestHeader =
        "filename,cycle_start_utc,window_closed_utc,decode_count,dial_mhz,clipped_samples,dropped_before";

    /// <summary>Free-disk-space floor (design.md Decision 7) below which archiving stops for the session.</summary>
    public const int FreeSpaceFloorMb = 500;

    // Archive's own filename pattern (design.md Decision 5): YYMMDD_HHMMSS[_n].wav.
    // Retention deletion is restricted to files matching this pattern — never a directory wipe.
    private static readonly Regex ArchiveFilenamePattern =
        new(@"^\d{6}_\d{6}(_\d+)?\.wav$", RegexOptions.Compiled);

    private readonly IConfigStore                     _configStore;
    private readonly ILogger<CycleArchiveService>     _logger;
    private readonly int                              _queueCapacity;
    private readonly int                              _retentionSweepInterval;
    private readonly Func<string, long>                _freeBytesProvider;

    private Channel<ArchiveItem>?    _channel;
    private CancellationTokenSource? _cts;
    private Task?                    _writerTask;

    private long _droppedCycles;
    private int  _droppedSincePreviousRow;
    private int  _cyclesSinceSweep;   // writer-task-owned only; no concurrent access
    private bool _spaceFloorHit;      // writer-task-owned only; no concurrent access

    /// <summary>
    /// Fired (test-only) after each item is fully processed (written, manifest-appended, and any
    /// retention sweep run), whether it succeeded or the writer loop caught and logged a failure.
    /// Lets tests await a deterministic point instead of an arbitrary delay.
    /// </summary>
    internal event Action? ItemProcessedForTests;

    /// <summary>
    /// Test-only hook: when set, awaited as the very first step of processing each item, before
    /// any file-system access. Lets tests deterministically hold the writer "stalled" on a
    /// specific item (via an uncompleted <see cref="Task"/>) to exercise queue-full/drop and
    /// non-blocking-enqueue behaviour without a real slow disk.
    /// </summary>
    internal Func<CancellationToken, Task>? WriterStallHookForTests { get; set; }

    /// <summary>
    /// Test-only: process-lifetime count of items the writer loop has dequeued from the channel
    /// (incremented before any stall hook or processing runs), so tests can confirm a specific
    /// item has left the queue and is now "in flight" before proceeding.
    /// </summary>
    internal int DequeuedCountForTests => Volatile.Read(ref _dequeuedCountForTests);
    private int _dequeuedCountForTests;

    /// <summary>Process-lifetime count of cycles dropped because the archive queue was at capacity.</summary>
    public long DroppedCycles => Interlocked.Read(ref _droppedCycles);

    /// <summary>Production constructor — all dependencies from DI, standard cadence constants.</summary>
    public CycleArchiveService(IConfigStore configStore, ILogger<CycleArchiveService> logger)
        : this(configStore, logger, queueCapacity: 8, retentionSweepInterval: 100, freeBytesProvider: null)
    {
    }

    /// <summary>
    /// Test constructor — allows overriding the queue capacity, the retention-sweep cadence, and
    /// the free-disk-space provider so unit tests can exercise capacity/retention/free-space-floor
    /// behaviour without waiting for 100 real cycles or filling a real disk.
    /// </summary>
    internal CycleArchiveService(
        IConfigStore                  configStore,
        ILogger<CycleArchiveService>  logger,
        int                           queueCapacity,
        int                           retentionSweepInterval,
        Func<string, long>?           freeBytesProvider)
    {
        _configStore            = configStore;
        _logger                 = logger;
        _queueCapacity          = queueCapacity;
        _retentionSweepInterval = retentionSweepInterval;
        _freeBytesProvider      = freeBytesProvider ?? DefaultFreeBytesProvider;
    }

    // ── IHostedService ────────────────────────────────────────────────────────

    /// <inheritdoc/>
    public Task StartAsync(CancellationToken cancellationToken)
    {
        _channel = Channel.CreateBounded<ArchiveItem>(new BoundedChannelOptions(_queueCapacity)
        {
            FullMode     = BoundedChannelFullMode.DropWrite,
            SingleWriter = true,
            SingleReader = true,
        });

        _cts = new CancellationTokenSource();
        var token = _cts.Token;
        _writerTask = Task.Run(() => WriterLoopAsync(token), CancellationToken.None);
        return Task.CompletedTask;
    }

    /// <inheritdoc/>
    public async Task StopAsync(CancellationToken cancellationToken)
    {
        var cts = Interlocked.Exchange(ref _cts, null);
        if (cts is null) return;

        _channel?.Writer.TryComplete();
        await cts.CancelAsync().ConfigureAwait(false);

        if (_writerTask is not null)
        {
            try
            {
                await _writerTask.WaitAsync(TimeSpan.FromSeconds(3), CancellationToken.None)
                                  .ConfigureAwait(false);
            }
            catch (TimeoutException) { /* acceptable on shutdown */ }
            catch (OperationCanceledException) { /* expected */ }
        }

        cts.Dispose();
    }

    /// <inheritdoc/>
    public async ValueTask DisposeAsync() => await StopAsync(CancellationToken.None).ConfigureAwait(false);

    // ── Decode-pump entry point (design.md Decision 2) ──────────────────────

    /// <summary>
    /// Offers one decode cycle's window to the archive. Non-blocking; returns immediately.
    /// SHALL NOT be awaited by the caller (design.md Decision 2). When the mode is <c>Off</c>
    /// (the default) this costs exactly one config-property read and one comparison — no
    /// allocation, no channel access, no file-system access (spec.md "Off is the default and
    /// writes nothing").
    /// </summary>
    /// <param name="pcm">The cycle's float PCM window. Not copied — the caller must not mutate it afterwards.</param>
    /// <param name="cycleStart">The framer's reported cycle-start timestamp (used as the filename label).</param>
    /// <param name="closedUtc">True wall-clock instant the window closed (manifest provenance, design.md Decision 6).</param>
    /// <param name="decodeCount">Number of decodes this cycle produced (drives Decoded/NoDecodes mode selection).</param>
    /// <param name="dialMhz">Dial frequency snapshot in MHz, recorded in the manifest.</param>
    public void TryEnqueue(float[] pcm, DateTime cycleStart, DateTime closedUtc, int decodeCount, double dialMhz)
    {
        // Defence in depth (dev-tasks/2026-07-28-fix-cycle-audio-archive-null-config-crash.md,
        // mirrors AllTxtWriter.AppendAsync's D-010 guard): read CycleAudioArchive defensively so
        // this method cannot throw unguarded even if some future code path reintroduces a null
        // CycleAudioArchive into IConfigStore.Current. The actual root cause — a null-persisting
        // POST /api/v1/config body — is fixed at the source in WebApp.cs and JsonConfigStore.
        // SaveAsync, but this is the method that crashed the daemon outright (no catch above it on
        // the decode-pump call site), so it must be self-defending regardless.
        var mode = (_configStore.Current.CycleAudioArchive ?? new CycleAudioArchiveConfig()).Mode;
        if (mode == CycleAudioArchiveMode.Off)
            return;

        var channel = _channel;
        if (channel is null)
            return; // StartAsync has not run (e.g. a minimal test fixture) — nothing to enqueue to

        bool shouldArchive = mode switch
        {
            CycleAudioArchiveMode.All       => true,
            CycleAudioArchiveMode.Decoded   => decodeCount > 0,
            CycleAudioArchiveMode.NoDecodes => decodeCount == 0,
            _                               => false,
        };
        if (!shouldArchive)
            return;

        // design.md Decision 3: TryWrite's return value cannot be trusted on this channel — count
        // against capacity explicitly, before writing, instead.
        if (channel.Reader.Count >= _queueCapacity)
        {
            RecordDrop("the archive queue is at capacity");
            return;
        }

        channel.Writer.TryWrite(new ArchiveItem(pcm, cycleStart, closedUtc, decodeCount, dialMhz));
    }

    /// <summary>
    /// Increments <see cref="DroppedCycles"/> and the manifest's next-row gap marker, and logs at
    /// Warning on the first drop and every 100th thereafter. Called for every path by which a
    /// cycle fails to be archived — queue-full (<see cref="TryEnqueue"/>) and post-free-space-floor
    /// skips (<see cref="ProcessItemAsync"/>) alike — per design.md Decision 3's standing rule that
    /// no drop path in this capability may be uncounted.
    /// </summary>
    private void RecordDrop(string reason)
    {
        var dropped = Interlocked.Increment(ref _droppedCycles);
        Interlocked.Increment(ref _droppedSincePreviousRow);

        if (dropped == 1 || dropped % 100 == 0)
        {
            _logger.LogWarning(
                "cycle-audio-archive: dropped cycle #{Dropped} — {Reason}.",
                dropped, reason);
        }
    }

    // ── Writer task ───────────────────────────────────────────────────────────

    private async Task WriterLoopAsync(CancellationToken ct)
    {
        var channel = _channel!;
        try
        {
            await foreach (var item in channel.Reader.ReadAllAsync(ct).ConfigureAwait(false))
            {
                Interlocked.Increment(ref _dequeuedCountForTests);
                try
                {
                    await ProcessItemAsync(item, ct).ConfigureAwait(false);
                }
                catch (Exception ex)
                {
                    _logger.LogWarning(ex, "cycle-audio-archive: failed to archive a cycle — continuing.");
                }
                finally
                {
                    ItemProcessedForTests?.Invoke();
                }
            }
        }
        catch (OperationCanceledException) { /* shutdown */ }
    }

    private async Task ProcessItemAsync(ArchiveItem item, CancellationToken ct)
    {
        if (WriterStallHookForTests is { } stall)
            await stall(ct).ConfigureAwait(false);

        if (_spaceFloorHit)
        {
            // The floor already tripped on an earlier item this session — every cycle offered
            // since is a real, ongoing loss and must be counted like any other drop path
            // (design.md Decision 3's standing rule), not just the single Warning logged at the
            // moment of the original trip below.
            RecordDrop("archiving remains stopped for the session — free disk space previously fell below the floor");
            return;
        }

        // Defence in depth — same reasoning as TryEnqueue's guard above.
        var config    = _configStore.Current.CycleAudioArchive ?? new CycleAudioArchiveConfig();
        var directory = string.IsNullOrWhiteSpace(config.Directory)
            ? ConfigPathResolver.ResolveDefaultCycleAudioDirectory()
            : config.Directory;

        System.IO.Directory.CreateDirectory(directory);

        if (!HasEnoughFreeSpace(directory))
        {
            _spaceFloorHit = true;
            _logger.LogWarning(
                "cycle-audio-archive: free disk space on '{Directory}' is below the {FloorMb} MB " +
                "floor — archiving stopped for the remainder of the session.",
                directory, FreeSpaceFloorMb);
            RecordDrop("free disk space fell below the floor");
            return;
        }

        var (bytes, clipped) = CycleWavWriter.Encode(item.Pcm);

        var baseFilename = item.CycleStart.ToString("yyMMdd_HHmmss", CultureInfo.InvariantCulture) + ".wav";
        var filename     = ResolveCollisionFreeFilename(directory, baseFilename);
        if (filename != baseFilename)
        {
            _logger.LogDebug(
                "cycle-audio-archive: filename collision for '{Base}' — writing to '{Filename}' instead " +
                "(design.md Decision 5 — the drift correction can move cycleStart backwards).",
                baseFilename, filename);
        }

        var path = Path.Combine(directory, filename);
        await using (var stream = new FileStream(
            path, FileMode.CreateNew, FileAccess.Write, FileShare.None, bufferSize: 4096, useAsync: true))
        {
            await stream.WriteAsync(bytes, ct).ConfigureAwait(false);
        }

        if (config.WriteManifest)
            await AppendManifestAsync(directory, filename, item, clipped, ct).ConfigureAwait(false);

        _cyclesSinceSweep++;
        if (_cyclesSinceSweep >= _retentionSweepInterval)
        {
            _cyclesSinceSweep = 0;
            EnforceRetention(directory, config);
        }
    }

    /// <summary>
    /// Finds the first available filename for <paramref name="baseFilename"/> in
    /// <paramref name="directory"/>, appending <c>_2</c>, <c>_3</c>, … on collision
    /// (design.md Decision 5). Never overwrites an existing recording.
    /// </summary>
    private static string ResolveCollisionFreeFilename(string directory, string baseFilename)
    {
        if (!File.Exists(Path.Combine(directory, baseFilename)))
            return baseFilename;

        var stem = baseFilename[..^".wav".Length];
        int suffix = 2;
        string candidate;
        do
        {
            candidate = $"{stem}_{suffix}.wav";
            suffix++;
        }
        while (File.Exists(Path.Combine(directory, candidate)));

        return candidate;
    }

    // ── Manifest (design.md Decision 6) ─────────────────────────────────────

    private async Task AppendManifestAsync(
        string directory, string filename, ArchiveItem item, int clipped, CancellationToken ct)
    {
        var manifestPath = Path.Combine(directory, ManifestFileName);
        bool exists      = File.Exists(manifestPath);
        var droppedSincePrevious = Interlocked.Exchange(ref _droppedSincePreviousRow, 0);

        var row = string.Join(',',
            filename,
            FormatManifestTimestamp(item.CycleStart),
            FormatManifestTimestamp(item.ClosedUtc),
            item.DecodeCount.ToString(CultureInfo.InvariantCulture),
            item.DialMhz.ToString("F3", CultureInfo.InvariantCulture),
            clipped.ToString(CultureInfo.InvariantCulture),
            droppedSincePrevious.ToString(CultureInfo.InvariantCulture));

        await using var writer = new StreamWriter(manifestPath, append: true) { NewLine = "\n" };
        if (!exists)
            await writer.WriteLineAsync(ManifestHeader).ConfigureAwait(false);
        await writer.WriteLineAsync(row).ConfigureAwait(false);
    }

    private static string FormatManifestTimestamp(DateTime value) =>
        value.ToString("yyyy-MM-ddTHH:mm:ss.fffZ", CultureInfo.InvariantCulture);

    // ── Retention (design.md Decision 7) ────────────────────────────────────

    private bool HasEnoughFreeSpace(string directory)
    {
        try
        {
            return _freeBytesProvider(directory) >= FreeSpaceFloorMb * 1024L * 1024L;
        }
        catch
        {
            // Best-effort: if free space cannot be determined, do not block archiving on that basis.
            return true;
        }
    }

    private static long DefaultFreeBytesProvider(string directory)
    {
        var root = Path.GetPathRoot(Path.GetFullPath(directory));
        if (string.IsNullOrEmpty(root))
            return long.MaxValue;
        return new DriveInfo(root).AvailableFreeSpace;
    }

    /// <summary>
    /// Enforces the size cap (<see cref="CycleAudioArchiveConfig.MaxSizeMb"/>) and age cap
    /// (<see cref="CycleAudioArchiveConfig.MaxAgeHours"/>), oldest-first. Deletion is restricted to
    /// files in <paramref name="directory"/> matching <see cref="ArchiveFilenamePattern"/> — never
    /// a directory wipe (design.md Decision 7).
    /// </summary>
    private void EnforceRetention(string directory, CycleAudioArchiveConfig config)
    {
        try
        {
            // "Oldest" is determined from the cycle timestamp encoded in the filename itself
            // (yyMMdd_HHmmss), not filesystem CreationTimeUtc: on Linux, most filesystems have no
            // reliable birth time, and .NET's CreationTimeUtc there commonly reports the same
            // value as LastWriteTimeUtc (or worse) — found 2026-07-25 when this sweep, ordered by
            // CreationTimeUtc, deleted the wrong file under WSL. Parsing the filename is also the
            // more correct notion of "age" regardless of platform: a cycle's true age is when it
            // was captured, not when its file happens to have been last touched on disk.
            var files = new DirectoryInfo(directory)
                .GetFiles()
                .Where(f => ArchiveFilenamePattern.IsMatch(f.Name))
                .Select(f => (File: f, CycleUtc: ParseCycleTimestamp(f.Name)))
                .OrderBy(x => x.CycleUtc)
                .ToList();

            var cutoffAgeUtc = DateTime.UtcNow - TimeSpan.FromHours(config.MaxAgeHours);

            foreach (var x in files.Where(x => x.CycleUtc < cutoffAgeUtc).ToList())
            {
                TryDelete(x.File);
                files.Remove(x);
            }

            var maxBytes = config.MaxSizeMb * 1024L * 1024L;
            long total   = files.Sum(x => x.File.Length);
            int i = 0;
            while (total > maxBytes && i < files.Count)
            {
                total -= files[i].File.Length;
                TryDelete(files[i].File);
                i++;
            }
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "cycle-audio-archive: retention sweep on '{Directory}' failed.", directory);
        }
    }

    /// <summary>
    /// Parses the <c>yyMMdd_HHmmss</c> cycle timestamp from the first 13 characters of an archive
    /// filename already confirmed to match <see cref="ArchiveFilenamePattern"/> (so this cannot
    /// fail for any file <see cref="EnforceRetention"/> passes to it — any trailing collision
    /// suffix, e.g. <c>_2</c>, sits after the part parsed here and is ignored).
    /// </summary>
    private static DateTime ParseCycleTimestamp(string fileName) =>
        DateTime.ParseExact(
            fileName[..13], "yyMMdd_HHmmss", CultureInfo.InvariantCulture,
            DateTimeStyles.AssumeUniversal | DateTimeStyles.AdjustToUniversal);

    private void TryDelete(FileInfo file)
    {
        try
        {
            file.Delete();
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex,
                "cycle-audio-archive: failed to delete '{File}' during a retention sweep.", file.FullName);
        }
    }

    /// <summary>
    /// Test-only hook (internal, exercised via <c>InternalsVisibleTo</c>): forces a retention
    /// sweep on the given directory/config without waiting for the real sweep cadence.
    /// </summary>
    internal void RunRetentionSweepForTests(string directory, CycleAudioArchiveConfig config) =>
        EnforceRetention(directory, config);

    private readonly record struct ArchiveItem(
        float[]  Pcm,
        DateTime CycleStart,
        DateTime ClosedUtc,
        int      DecodeCount,
        double   DialMhz);
}
