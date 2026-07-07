using System.IO.Compression;
using System.Net;
using FluentAssertions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Daemon;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// Unit tests for <see cref="HttpCountryFileSource"/> (region-lookup-data-refresh, f-006).
/// Uses a fake <see cref="HttpMessageHandler"/> so no test depends on live network access to
/// country-files.com.
/// </summary>
public sealed class HttpCountryFileSourceTests
{
    /// <summary>Builds a minimal in-memory ZIP archive containing a single <c>cty.plist</c> entry.</summary>
    private static byte[] BuildFixtureZip(string plistXml, string entryName = "cty.plist")
    {
        using var stream = new MemoryStream();
        using (var archive = new ZipArchive(stream, ZipArchiveMode.Create, leaveOpen: true))
        {
            var entry = archive.CreateEntry(entryName);
            using var entryStream = entry.Open();
            using var writer = new StreamWriter(entryStream);
            writer.Write(plistXml);
        }
        return stream.ToArray();
    }

    private const string FixturePlist = """
        <?xml version="1.0" encoding="UTF-8"?>
        <plist version="1.0"><dict>
        <key>Q9</key>
        <dict><key>Country</key><string>Fictional Land</string>
        <key>CQZone</key><integer>40</integer><key>ITUZone</key><integer>41</integer>
        <key>Continent</key><string>EU</string><key>ExactCallsign</key><false/></dict>
        </dict></plist>
        """;

    /// <summary>Fake handler that returns a canned response or throws a canned exception.</summary>
    private sealed class FakeHandler : HttpMessageHandler
    {
        private readonly Func<HttpResponseMessage>? _responseFactory;
        private readonly Exception?                 _exceptionToThrow;

        public FakeHandler(Func<HttpResponseMessage> responseFactory) => _responseFactory = responseFactory;
        public FakeHandler(Exception exceptionToThrow) => _exceptionToThrow = exceptionToThrow;

        protected override Task<HttpResponseMessage> SendAsync(
            HttpRequestMessage request, CancellationToken cancellationToken)
        {
            if (_exceptionToThrow is not null) throw _exceptionToThrow;
            return Task.FromResult(_responseFactory!());
        }
    }

    private static HttpCountryFileSource MakeSource(HttpMessageHandler handler) =>
        new(new HttpClient(handler));

    // ── Success ────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "f-006 1.5: successful fetch extracts cty.plist and returns its XML text")]
    public async Task FetchAsync_Success_ReturnsPlistText()
    {
        var zipBytes = BuildFixtureZip(FixturePlist);
        var handler  = new FakeHandler(() => new HttpResponseMessage(HttpStatusCode.OK)
        {
            Content = new ByteArrayContent(zipBytes),
        });
        var source = MakeSource(handler);

        var xml = await source.FetchAsync();

        xml.Should().Contain("Fictional Land");
        xml.Should().Contain("<key>Q9</key>");
    }

    // ── Non-success HTTP status ───────────────────────────────────────────────

    [Fact(DisplayName = "f-006 1.5: non-success HTTP status throws CountryFileFetchException")]
    public async Task FetchAsync_NonSuccessStatus_Throws()
    {
        var handler = new FakeHandler(() => new HttpResponseMessage(HttpStatusCode.NotFound));
        var source  = MakeSource(handler);

        var act = async () => await source.FetchAsync();

        (await act.Should().ThrowAsync<CountryFileFetchException>())
            .WithMessage("*404*");
    }

    [Fact(DisplayName = "f-006 1.5: HTTP 500 throws CountryFileFetchException")]
    public async Task FetchAsync_ServerError_Throws()
    {
        var handler = new FakeHandler(() => new HttpResponseMessage(HttpStatusCode.InternalServerError));
        var source  = MakeSource(handler);

        var act = async () => await source.FetchAsync();

        await act.Should().ThrowAsync<CountryFileFetchException>();
    }

    // ── Network failure / timeout ─────────────────────────────────────────────

    [Fact(DisplayName = "f-006 1.5: network failure (HttpRequestException) throws CountryFileFetchException")]
    public async Task FetchAsync_NetworkFailure_Throws()
    {
        var handler = new FakeHandler(new HttpRequestException("Simulated DNS failure."));
        var source  = MakeSource(handler);

        var act = async () => await source.FetchAsync();

        (await act.Should().ThrowAsync<CountryFileFetchException>())
            .WithInnerException<HttpRequestException>();
    }

    [Fact(DisplayName = "f-006 1.5: timeout (TaskCanceledException, not caller-requested) throws CountryFileFetchException")]
    public async Task FetchAsync_Timeout_Throws()
    {
        var handler = new FakeHandler(new TaskCanceledException("Simulated timeout."));
        var source  = MakeSource(handler);

        var act = async () => await source.FetchAsync(CancellationToken.None);

        await act.Should().ThrowAsync<CountryFileFetchException>();
    }

    [Fact(DisplayName = "f-006 1.5: caller-requested cancellation propagates as OperationCanceledException, not CountryFileFetchException")]
    public async Task FetchAsync_CallerCancellation_PropagatesAsOperationCanceled()
    {
        using var cts = new CancellationTokenSource();
        cts.Cancel();
        var handler = new FakeHandler(new TaskCanceledException("Simulated cancellation."));
        var source  = MakeSource(handler);

        var act = async () => await source.FetchAsync(cts.Token);

        await act.Should().ThrowAsync<OperationCanceledException>();
    }

    // ── Malformed ZIP / missing entry ─────────────────────────────────────────

    [Fact(DisplayName = "f-006 1.5: malformed ZIP bytes throw CountryFileFetchException")]
    public async Task FetchAsync_MalformedZip_Throws()
    {
        var handler = new FakeHandler(() => new HttpResponseMessage(HttpStatusCode.OK)
        {
            Content = new ByteArrayContent([0x00, 0x01, 0x02, 0x03]),
        });
        var source = MakeSource(handler);

        var act = async () => await source.FetchAsync();

        await act.Should().ThrowAsync<CountryFileFetchException>();
    }

    [Fact(DisplayName = "f-006 1.5: ZIP missing the cty.plist entry throws CountryFileFetchException")]
    public async Task FetchAsync_ZipMissingPlistEntry_Throws()
    {
        var zipBytes = BuildFixtureZip(FixturePlist, entryName: "unexpected-file.txt");
        var handler  = new FakeHandler(() => new HttpResponseMessage(HttpStatusCode.OK)
        {
            Content = new ByteArrayContent(zipBytes),
        });
        var source = MakeSource(handler);

        var act = async () => await source.FetchAsync();

        (await act.Should().ThrowAsync<CountryFileFetchException>())
            .WithMessage("*cty.plist*");
    }
}
