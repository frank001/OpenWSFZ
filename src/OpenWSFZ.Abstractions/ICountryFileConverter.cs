namespace OpenWSFZ.Abstractions;

/// <summary>
/// Pure, synchronous conversion from a country-file release's XML (property-list) text into this
/// project's <see cref="CallsignRegionEntry"/> shape (region-lookup-data-refresh capability).
/// No I/O — trivially unit-testable with small, hand-written fixture XML documents.
/// </summary>
public interface ICountryFileConverter
{
    /// <summary>
    /// Converts <paramref name="xml"/> into a list of <see cref="CallsignRegionEntry"/> records.
    /// </summary>
    /// <param name="xml">The release's XML (property-list) text, as returned by <see cref="ICountryFileSource"/>.</param>
    /// <param name="prefixBlocksOnly">
    /// <c>true</c> to drop source rows flagged as an individual-callsign exception (rather than a
    /// prefix block) — used when regenerating the git-committed <c>CallsignRegionDefaults.cs</c>,
    /// which must never contain a real callsign. <c>false</c> (default) passes them through
    /// unfiltered — used for the runtime <c>callsign-regions.json</c> refresh path, which is never
    /// committed to version control.
    /// </param>
    /// <exception cref="CountryFileConversionException">
    /// <paramref name="xml"/> is not well-formed, does not have the expected shape, or an entry is
    /// missing a required field.
    /// </exception>
    IReadOnlyList<CallsignRegionEntry> Convert(string xml, bool prefixBlocksOnly = false);
}
