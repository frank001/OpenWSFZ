using FluentAssertions;
using Microsoft.AspNetCore.Hosting;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using System.Collections.Concurrent;
using System.Net;
using System.Text;
using Xunit;

namespace OpenWSFZ.Web.Tests;

/// <summary>Captures formatted log messages so a test can assert on exactly what reached the log.</summary>
internal sealed class CapturingLoggerProvider : ILoggerProvider
{
    public ConcurrentQueue<(string Category, LogLevel Level, string Message)> Entries { get; } = new();

    public ILogger CreateLogger(string categoryName) => new CapturingLogger(categoryName, Entries);

    public void Dispose() { }

    private sealed class CapturingLogger(
        string category,
        ConcurrentQueue<(string, LogLevel, string)> sink) : ILogger
    {
        public IDisposable? BeginScope<TState>(TState state) where TState : notnull => null;
        public bool IsEnabled(LogLevel logLevel) => true;
        public void Log<TState>(LogLevel logLevel, EventId eventId, TState state, Exception? exception,
            Func<TState, Exception?, string> formatter)
            => sink.Enqueue((category, logLevel, formatter(state, exception)));
    }
}

/// <summary>Part D: every successful config save logs what it changed, and never a personal value.</summary>
[Trait("Category", "Integration")]
public sealed class ConfigSaveLogTests
{
    private const string SavedPrefix = "Config saved via API: ";

    private static Task<HttpResponseMessage> PostAsync(HttpClient client, string json)
        => client.PostAsync("/api/v1/config", new StringContent(json, Encoding.UTF8, "application/json"));

    private static List<string> SaveLines(CapturingLoggerProvider logs)
        => logs.Entries
            .Where(e => e.Level == LogLevel.Information && e.Message.StartsWith(SavedPrefix, StringComparison.Ordinal))
            .Select(e => e.Message)
            .ToList();

    [Fact(DisplayName = "FR-076: T14: a save changing cycleAudioArchive.mode and tx.callsign logs exactly one line with the mode values and the callsign PATH only")]
    public async Task T14_SaveLogsOneLine_AllowlistedValuesOnly()
    {
        var logs = new CapturingLoggerProvider();
        using var baseFactory = new WebTestFactory();
        using var factory = baseFactory.WithWebHostBuilder(b =>
            b.ConfigureServices(s => s.AddSingleton<ILoggerProvider>(logs)));
        var client = factory.CreateClient();

        await factory.Services.GetRequiredService<IConfigStore>().SaveAsync(new AppConfig
        {
            CycleAudioArchive = new CycleAudioArchiveConfig(mode: CycleAudioArchiveMode.All),
            Tx = new TxConfig(callsign: "Q1AAA"),
            RemoteAccess = new RemoteAccessConfig(enabled: false, passphrase: "Q-old-passphrase"),
        });

        var resp = await PostAsync(client,
            """
            { "cycleAudioArchive": { "mode": "off" },
              "tx": { "callsign": "Q9ZZZ" },
              "remoteAccess": { "enabled": false, "passphrase": "Q-new-passphrase" } }
            """);
        resp.StatusCode.Should().Be(HttpStatusCode.OK);

        var lines = SaveLines(logs);
        lines.Should().HaveCount(1, "exactly one line per successful save");
        var line = lines[0];
        line.Should().Contain("cycleAudioArchive.mode (All→Off)");
        line.Should().Contain("tx.callsign");
        line.Should().Contain("remoteAccess.passphrase");
        line.Should().NotContain("Q1AAA").And.NotContain("Q9ZZZ", "callsign values must never be logged");
        line.Should().NotContain("passphrase\"").And.NotContain("Q-old").And.NotContain("Q-new",
            "passphrase values must never be logged");
        logs.Entries.Select(e => e.Message).Where(m => m.Contains("Q9ZZZ") || m.Contains("Q-new-passphrase"))
            .Should().BeEmpty("no log line of any category may carry the posted callsign or passphrase");
    }

    [Fact(DisplayName = "FR-076: T14b: a save that changes nothing logs \"no changes\"")]
    public async Task T14b_NoChanges()
    {
        var logs = new CapturingLoggerProvider();
        using var baseFactory = new WebTestFactory();
        using var factory = baseFactory.WithWebHostBuilder(b =>
            b.ConfigureServices(s => s.AddSingleton<ILoggerProvider>(logs)));
        var client = factory.CreateClient();

        (await PostAsync(client, "{}")).StatusCode.Should().Be(HttpStatusCode.OK);

        SaveLines(logs).Should().Equal(SavedPrefix + "no changes");
    }

    [Fact(DisplayName = "FR-076: T14c: a rejected save (400) logs no \"Config saved\" line")]
    public async Task T14c_RejectedSave_LogsNothing()
    {
        var logs = new CapturingLoggerProvider();
        using var baseFactory = new WebTestFactory();
        using var factory = baseFactory.WithWebHostBuilder(b =>
            b.ConfigureServices(s => s.AddSingleton<ILoggerProvider>(logs)));
        var client = factory.CreateClient();

        (await PostAsync(client, "{ not json")).StatusCode.Should().Be(HttpStatusCode.BadRequest);

        SaveLines(logs).Should().BeEmpty();
    }

    [Fact(DisplayName = "FR-076: Part D allowlist is exactly the six enum/boolean fields of the spec")]
    public void Allowlist_IsExactlyTheSpecifiedSix()
    {
        ConfigChangeSummary.ValueAllowlist.Keys.Should().BeEquivalentTo(new[]
        {
            "cycleAudioArchive.mode", "decodingEnabled", "tx.autoAnswer",
            "tx.holdTxFreq", "cat.enabled", "remoteAccess.enabled",
        });
    }

    [Fact(DisplayName = "FR-076: Describe: allowlisted values print old→new, others print the path only, output is sorted")]
    public void Describe_PrintsPathsAndAllowlistedValues()
    {
        var before = new AppConfig { DecodingEnabled = true, Tx = new TxConfig(callsign: "Q1AAA", holdTxFreq: false) };
        var after  = before with { DecodingEnabled = false, Tx = new TxConfig(callsign: "Q2BBB", holdTxFreq: true) };

        var text = ConfigChangeSummary.Describe(before, after);

        text.Should().Be("changed decodingEnabled (true→false), tx.callsign, tx.holdTxFreq (false→true)");
    }
}
