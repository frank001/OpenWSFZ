using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Daemon;
using OpenWSFZ.Daemon.PskReporter;

namespace OpenWSFZ.Daemon.Tests.PskReporter;

/// <summary>Shared fakes for the PSK Reporter upload tests (issue #262). Q-prefix callsigns only (NFR-021).</summary>
internal static class PskTestSupport
{
    public static readonly DateTime T0 = new(2026, 10, 25, 12, 0, 0, DateTimeKind.Utc);

    public static readonly RegionInfo Real = new("EU", "TestLand", false);

    /// <summary>A real-looking identity (a non-Q call). Fixed text, no real person: the call is a plain example.</summary>
    public static PskIdentity Identity(string call = "W9XYZ", string grid = "JO33", string antenna = "") => new(call, grid, antenna, "OpenWSFZ 0.64");

    public static DecodeResult Decode(string message, int freqHz = 1500, int snr = -10, RegionInfo? region = null, bool unknownRegion = false)
        => new("12:00:00", snr, 0.2, freqHz, message, unknownRegion ? null : region ?? Real);

    public static DecodeBatch Batch(DateTime cycleStart, double? dialMHz, params DecodeResult[] results)
        => new(new DateTimeOffset(DateTime.SpecifyKind(cycleStart, DateTimeKind.Utc)), results, 1, dialMHz);

    /// <summary>Parses the sender records out of the 7-field and 8-field blocks of one of OUR datagrams: (call, locator, freq, snr, imd).</summary>
    public static List<(string Call, string? Locator, uint Freq, sbyte Snr, byte Imd)> ParseSpots(byte[] d)
    {
        var spots = new List<(string, string?, uint, sbyte, byte)>();
        int pos = 16;
        while (pos < d.Length)
        {
            int id  = (d[pos] << 8) | d[pos + 1];
            int len = (d[pos + 2] << 8) | d[pos + 3];
            if (id is 0x9993 or 0x9994)
            {
                int p = pos + 4, end = pos + len;
                while (end - p >= 12)     // a record is never shorter; trailing padding is at most 3 bytes
                {
                    int cl = d[p++]; string call = System.Text.Encoding.UTF8.GetString(d, p, cl); p += cl;
                    uint freq = (uint)((d[p] << 24) | (d[p + 1] << 16) | (d[p + 2] << 8) | d[p + 3]); p += 4;
                    sbyte snr = unchecked((sbyte)d[p++]); byte imd = d[p++];
                    int ml = d[p++]; p += ml; p++;                                 // mode, informationSource
                    string? loc = null;
                    if (id == 0x9993) { int ll = d[p++]; loc = System.Text.Encoding.UTF8.GetString(d, p, ll); p += ll; }
                    p += 4;                                                         // flowStartSeconds
                    spots.Add((call, loc, freq, snr, imd));
                }
            }
            pos += len;
        }
        return spots;
    }

    public static uint Sequence(byte[] d) => (uint)((d[8] << 24) | (d[9] << 16) | (d[10] << 8) | d[11]);
    public static uint SessionId(byte[] d) => (uint)((d[12] << 24) | (d[13] << 16) | (d[14] << 8) | d[15]);
    public static bool HasTemplates(byte[] d) => ((d[16] << 8) | d[17]) == 3;

    /// <summary>The datagram's set ids in order (template sets 2 and 3, then data sets), for assertions on its shape.</summary>
    public static List<int> SetIds(byte[] d)
    {
        var ids = new List<int>();
        int pos = 16;
        while (pos < d.Length) { ids.Add((d[pos] << 8) | d[pos + 1]); pos += (d[pos + 2] << 8) | d[pos + 3]; }
        return ids;
    }
}

/// <summary>A clock the test advances.</summary>
internal sealed class FakeClock : IClock
{
    public DateTime UtcNow { get; set; } = PskTestSupport.T0;
    public void Advance(TimeSpan by) => UtcNow += by;
}

/// <summary>Captures every entry of every level; used to assert counts and that no callsign is ever logged.</summary>
internal sealed class CapturingLogger<T> : ILogger<T>
{
    private readonly List<(LogLevel Level, string Message)> _entries = [];
    public IReadOnlyList<(LogLevel Level, string Message)> Entries { get { lock (_entries) return [.. _entries]; } }
    public IDisposable? BeginScope<TState>(TState state) where TState : notnull => null;
    public bool IsEnabled(LogLevel logLevel) => true;
    public void Log<TState>(LogLevel logLevel, EventId eventId, TState state, Exception? exception, Func<TState, Exception?, string> formatter)
    {
        lock (_entries) _entries.Add((logLevel, formatter(state, exception)));
    }
    public int Count(LogLevel level) => Entries.Count(e => e.Level == level);
}

/// <summary>An in-memory configuration store; <see cref="SaveAsync"/> raises <see cref="OnSaved"/> as the real one does.</summary>
internal sealed class FakeConfigStore : IConfigStore
{
    public FakeConfigStore(AppConfig? initial = null) => Current = initial ?? new AppConfig();
    public AppConfig Current { get; private set; }
    public event Action<AppConfig>? OnSaved;
    public Task SaveAsync(AppConfig config, CancellationToken ct = default)
    {
        Current = config;
        OnSaved?.Invoke(config);
        return Task.CompletedTask;
    }
    public Task ReloadAsync(CancellationToken ct = default) => Task.CompletedTask;
}

/// <summary>A transport that records every datagram and can be told to throw.</summary>
internal sealed class FakeTransport : IPskTransport
{
    public readonly List<byte[]> Sent = [];
    public volatile bool Throw;
    public volatile bool Disposed;
    public Task SendAsync(byte[] datagram, CancellationToken ct)
    {
        if (Throw) throw new System.Net.Sockets.SocketException((int)System.Net.Sockets.SocketError.HostNotFound);
        lock (Sent) Sent.Add(datagram);
        return Task.CompletedTask;
    }
    public int SentCount { get { lock (Sent) return Sent.Count; } }
    public void Dispose() => Disposed = true;
}
