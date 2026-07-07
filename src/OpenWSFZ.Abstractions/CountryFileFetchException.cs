namespace OpenWSFZ.Abstractions;

/// <summary>
/// Thrown by <see cref="ICountryFileSource"/> when the current country-file release cannot be
/// fetched — network failure, non-success HTTP status, timeout, or an unreadable/corrupt archive
/// (region-lookup-data-refresh capability). Callers (the refresh endpoint) SHALL treat this as a
/// failed refresh that leaves existing region data untouched.
/// </summary>
public sealed class CountryFileFetchException : Exception
{
    public CountryFileFetchException(string message) : base(message) { }

    public CountryFileFetchException(string message, Exception innerException)
        : base(message, innerException) { }
}
