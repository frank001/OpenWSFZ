using System.IO.Compression;
using System.Net.Http;
using System.Text;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Daemon;

/// <summary>
/// Fetches country-files.com's current contest country-file release over HTTPS
/// (region-lookup-data-refresh capability). The release is published as a ZIP archive at a
/// stable, version-independent URL that always serves the current release — no index/RSS page
/// scraping is needed to discover "the latest version". This implementation downloads the
/// archive and extracts its <c>cty.plist</c> entry (an XML property list) in memory; the returned
/// text is otherwise unprocessed XML, ready for <see cref="ICountryFileConverter"/>.
/// </summary>
public sealed class HttpCountryFileSource : ICountryFileSource
{
    /// <summary>
    /// Stable URL that always serves the current release's ZIP archive — verified live against
    /// country-files.com at implementation time (see design.md's Addendum,
    /// f-006-region-lookup-country-file-refresh).
    /// </summary>
    public const string ReleaseUrl = "https://www.country-files.com/cty/download/cty_plist.zip";

    private const string PlistEntryName = "cty.plist";

    private readonly HttpClient                        _httpClient;
    private readonly ILogger<HttpCountryFileSource>?    _logger;

    public HttpCountryFileSource(HttpClient httpClient, ILogger<HttpCountryFileSource>? logger = null)
    {
        _httpClient = httpClient;
        _logger     = logger;
    }

    /// <inheritdoc/>
    public async Task<string> FetchAsync(CancellationToken cancellationToken = default)
    {
        byte[] zipBytes;
        try
        {
            using var response = await _httpClient
                .GetAsync(ReleaseUrl, HttpCompletionOption.ResponseHeadersRead, cancellationToken)
                .ConfigureAwait(false);

            if (!response.IsSuccessStatusCode)
            {
                throw new CountryFileFetchException(
                    $"country-files.com returned HTTP {(int)response.StatusCode} " +
                    $"({response.StatusCode}) for '{ReleaseUrl}'.");
            }

            zipBytes = await response.Content.ReadAsByteArrayAsync(cancellationToken).ConfigureAwait(false);
        }
        catch (CountryFileFetchException)
        {
            throw;
        }
        catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException or IOException)
        {
            // A caller-requested cancellation surfaces as OperationCanceledException too;
            // let that propagate as-is rather than being reported as a fetch failure.
            if (cancellationToken.IsCancellationRequested)
                throw;

            _logger?.LogWarning(ex, "Failed to fetch country-file release from '{Url}'.", ReleaseUrl);
            throw new CountryFileFetchException(
                $"Failed to fetch country-file release from '{ReleaseUrl}'.", ex);
        }

        try
        {
            using var zipStream = new MemoryStream(zipBytes);
            using var archive   = new ZipArchive(zipStream, ZipArchiveMode.Read);

            var entry = archive.GetEntry(PlistEntryName)
                ?? throw new CountryFileFetchException(
                    $"Downloaded archive from '{ReleaseUrl}' does not contain an entry named " +
                    $"'{PlistEntryName}'.");

            using var entryStream = entry.Open();
            using var reader       = new StreamReader(entryStream, Encoding.UTF8);
            return await reader.ReadToEndAsync(cancellationToken).ConfigureAwait(false);
        }
        catch (CountryFileFetchException)
        {
            throw;
        }
        catch (Exception ex) when (ex is InvalidDataException or IOException)
        {
            _logger?.LogWarning(ex, "Downloaded archive from '{Url}' is not a readable ZIP archive.", ReleaseUrl);
            throw new CountryFileFetchException(
                $"Downloaded archive from '{ReleaseUrl}' could not be read as a ZIP archive.", ex);
        }
    }
}
