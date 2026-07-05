using FluentAssertions;
using Microsoft.AspNetCore.Hosting.Server;
using Microsoft.AspNetCore.Hosting.Server.Features;
using Microsoft.Extensions.DependencyInjection;
using OpenWSFZ.Abstractions;
using System.Linq;
using System.Net;
using System.Text.Json;
using Xunit;

namespace OpenWSFZ.Web.Tests;

// ── Test double ───────────────────────────────────────────────────────────────

/// <summary>
/// Controllable <see cref="ILogFileSource"/> test double for
/// <c>GET /api/v1/logs/tail</c> / <c>GET /api/v1/logs/full</c> endpoint tests
/// (log-viewer, f-004-operator-visibility-improvements).
/// </summary>
internal sealed class MockLogFileSource : ILogFileSource
{
    public string? CurrentLogFilePath { get; set; }
}

// ── Fixture ───────────────────────────────────────────────────────────────────

/// <summary>
/// Live Kestrel fixture for the log-viewer endpoint tests. Wires a
/// <see cref="MockLogFileSource"/> so tests can point at a real temp file with known
/// contents, or leave it <see langword="null"/> to exercise the "no active log file" path.
/// </summary>
public sealed class LogEndpointFixture : IAsyncLifetime
{
    internal readonly TestConfigStore   ConfigStore   = new();
    internal readonly MockLogFileSource LogFileSource = new();

    private Microsoft.AspNetCore.Builder.WebApplication? _app;
    public  HttpClient Client { get; private set; } = null!;

    public async Task InitializeAsync()
    {
        _app = WebApp.Create(
            port:              0,
            configStore:       ConfigStore,
            configureServices: services =>
                services.AddSingleton<ILogFileSource>(LogFileSource));

        await _app.StartAsync();

        var addr = _app.Services
            .GetRequiredService<IServer>()
            .Features.Get<IServerAddressesFeature>()!
            .Addresses.First();

        Client = new HttpClient { BaseAddress = new Uri($"http://127.0.0.1:{new Uri(addr).Port}") };
    }

    public async Task DisposeAsync()
    {
        Client.Dispose();
        if (_app is not null)
        {
            await _app.StopAsync();
            await _app.DisposeAsync();
        }
    }
}

// ── Tests ─────────────────────────────────────────────────────────────────────

/// <summary>
/// Integration tests for <c>GET /api/v1/logs/tail</c> and <c>GET /api/v1/logs/full</c>
/// (log-viewer spec).
/// </summary>
[Collection("log-endpoint-tests")]
public sealed class LogEndpointTests : IClassFixture<LogEndpointFixture>, IDisposable
{
    private readonly LogEndpointFixture _fixture;
    private readonly string             _tempDir;

    public LogEndpointTests(LogEndpointFixture fixture)
    {
        _fixture = fixture;
        _tempDir = Path.Combine(Path.GetTempPath(), "owsfz-log-endpoint-" + Path.GetRandomFileName());
        Directory.CreateDirectory(_tempDir);
    }

    public void Dispose()
    {
        // Reset shared fixture state so subsequent tests in this collection start clean.
        _fixture.LogFileSource.CurrentLogFilePath = null;
        try { Directory.Delete(_tempDir, recursive: true); } catch { /* best-effort */ }
    }

    /// <summary>
    /// Writes a log file with no trailing newline terminator, so splitting the read-back
    /// content on '\n' produces exactly <paramref name="lines"/>.Length entries — avoiding
    /// the "trailing empty line" artifact a real Serilog file (which always ends with a
    /// newline after its last entry) would otherwise introduce into an exact-count assertion.
    /// </summary>
    private string WriteLogFile(params string[] lines)
    {
        var path = Path.Combine(_tempDir, "test.log");
        File.WriteAllText(path, string.Join('\n', lines));
        return path;
    }

    // ── GET /api/v1/logs/tail ─────────────────────────────────────────────────

    [Fact(DisplayName = "log-viewer: GET /logs/tail returns an empty array (HTTP 200) when no active log file")]
    public async Task LogsTail_WhenNoActiveFile_ReturnsEmptyArray()
    {
        _fixture.LogFileSource.CurrentLogFilePath = null;

        var response = await _fixture.Client.GetAsync("/api/v1/logs/tail");

        response.StatusCode.Should().Be(HttpStatusCode.OK,
            "no active log file must return an empty result, not an error status");
        var body = await response.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(body);
        doc.RootElement.GetProperty("lines").GetArrayLength().Should().Be(0);
    }

    [Fact(DisplayName = "log-viewer: GET /logs/tail?lines=N returns exactly the last N lines")]
    public async Task LogsTail_WithExplicitLines_ReturnsLastNLines()
    {
        var allLines = Enumerable.Range(1, 10).Select(i => $"line-{i}").ToArray();
        _fixture.LogFileSource.CurrentLogFilePath = WriteLogFile(allLines);

        var response = await _fixture.Client.GetAsync("/api/v1/logs/tail?lines=3");

        response.StatusCode.Should().Be(HttpStatusCode.OK);
        var body = await response.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(body);
        var returned = doc.RootElement.GetProperty("lines")
            .EnumerateArray().Select(e => e.GetString()).ToArray();

        returned.Should().Equal(["line-8", "line-9", "line-10"],
            "the last 3 lines must be returned in file order (oldest first)");
    }

    [Fact(DisplayName = "log-viewer: GET /logs/tail with no lines param returns every line when the file has fewer than 150")]
    public async Task LogsTail_DefaultParam_ReturnsAllLinesWhenFewerThanDefault()
    {
        var allLines = Enumerable.Range(1, 5).Select(i => $"line-{i}").ToArray();
        _fixture.LogFileSource.CurrentLogFilePath = WriteLogFile(allLines);

        var response = await _fixture.Client.GetAsync("/api/v1/logs/tail");

        response.StatusCode.Should().Be(HttpStatusCode.OK);
        var body = await response.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(body);
        doc.RootElement.GetProperty("lines").GetArrayLength().Should().Be(5,
            "a 5-line file must return all 5 lines when the default cap (150) is not exceeded");
    }

    // ── GET /api/v1/logs/full ─────────────────────────────────────────────────

    [Fact(DisplayName = "log-viewer: GET /logs/full returns an empty text/plain body when no active log file")]
    public async Task LogsFull_WhenNoActiveFile_ReturnsEmptyBody()
    {
        _fixture.LogFileSource.CurrentLogFilePath = null;

        var response = await _fixture.Client.GetAsync("/api/v1/logs/full");

        response.StatusCode.Should().Be(HttpStatusCode.OK,
            "no active log file must return an empty body, not an error status");
        response.Content.Headers.ContentType?.MediaType.Should().Be("text/plain");
        var body = await response.Content.ReadAsStringAsync();
        body.Should().BeEmpty();
    }

    [Fact(DisplayName = "log-viewer: GET /logs/full returns the complete current file contents as text/plain")]
    public async Task LogsFull_WithActiveFile_ReturnsCompleteContents()
    {
        _fixture.LogFileSource.CurrentLogFilePath = WriteLogFile("alpha", "beta", "gamma");

        var response = await _fixture.Client.GetAsync("/api/v1/logs/full");

        response.StatusCode.Should().Be(HttpStatusCode.OK);
        response.Content.Headers.ContentType?.MediaType.Should().Be("text/plain");
        var body = await response.Content.ReadAsStringAsync();
        body.Should().Be("alpha\nbeta\ngamma",
            "the full endpoint must return the file's exact current contents");
    }
}
