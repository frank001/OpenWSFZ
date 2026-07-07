namespace OpenWSFZ.Abstractions;

/// <summary>
/// Thrown by <see cref="ICountryFileConverter"/> when the fetched country-file release cannot be
/// parsed, or a required per-entry field (entity name, CQ zone, ITU zone, continent) is missing or
/// malformed (region-lookup-data-refresh capability). Deliberately thrown rather than silently
/// defaulting missing data to <c>null</c>, so an unexpected upstream schema change surfaces loudly
/// instead of quietly degrading region-lookup accuracy. Callers (the refresh endpoint) SHALL treat
/// this as a failed refresh that leaves existing region data untouched.
/// </summary>
public sealed class CountryFileConversionException : Exception
{
    public CountryFileConversionException(string message) : base(message) { }

    public CountryFileConversionException(string message, Exception innerException)
        : base(message, innerException) { }
}
