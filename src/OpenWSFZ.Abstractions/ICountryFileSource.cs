namespace OpenWSFZ.Abstractions;

/// <summary>
/// Fetches the current country-file release from country-files.com
/// (region-lookup-data-refresh capability). Implementations own all I/O needed to produce
/// ready-to-parse XML text — including, for the real HTTP implementation, downloading the
/// release archive and extracting its XML property-list entry in memory — so that
/// <see cref="ICountryFileConverter"/> stays a pure, I/O-free function over the returned text.
/// Never invoked automatically; only ever called in response to an explicit operator-triggered
/// refresh request.
/// </summary>
public interface ICountryFileSource
{
    /// <summary>
    /// Fetches the current release and returns its XML (property-list) text.
    /// </summary>
    /// <exception cref="CountryFileFetchException">
    /// The release could not be fetched — network failure, non-success HTTP status, timeout, or
    /// an unreadable/corrupt archive.
    /// </exception>
    Task<string> FetchAsync(CancellationToken cancellationToken = default);
}
