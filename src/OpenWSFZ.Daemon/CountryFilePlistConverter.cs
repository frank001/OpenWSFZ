using System.Globalization;
using System.Xml;
using System.Xml.Linq;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Daemon;

/// <summary>
/// Converts country-files.com's <c>cty.plist</c> release — an Apple-style XML property list, one
/// entry per alias (a prefix block <em>or</em> an individual-callsign exception, keyed by the
/// alias string itself, each already carrying its fully-resolved Country/CQZone/ITUZone/Continent
/// values) — into this project's <see cref="CallsignRegionEntry"/> shape
/// (region-lookup-data-refresh capability).
/// </summary>
/// <remarks>
/// <para>
/// Expected shape (only the fields this converter maps are shown):
/// <code>
/// &lt;plist version="1.0"&gt;
/// &lt;dict&gt;
///   &lt;key&gt;3A&lt;/key&gt;
///   &lt;dict&gt;
///     &lt;key&gt;Country&lt;/key&gt;&lt;string&gt;Monaco&lt;/string&gt;
///     &lt;key&gt;CQZone&lt;/key&gt;&lt;integer&gt;14&lt;/integer&gt;
///     &lt;key&gt;ITUZone&lt;/key&gt;&lt;integer&gt;27&lt;/integer&gt;
///     &lt;key&gt;Continent&lt;/key&gt;&lt;string&gt;EU&lt;/string&gt;
///     &lt;key&gt;ExactCallsign&lt;/key&gt;&lt;false/&gt;
///   &lt;/dict&gt;
///   ...
/// &lt;/dict&gt;
/// &lt;/plist&gt;
/// </code>
/// </para>
/// <para>
/// Unlike the classic <c>cty.dat</c> text format, no inline override syntax (<c>(#)</c>,
/// <c>[#]</c>, <c>{cc}</c>, <c>~#~</c>) needs interpreting here — each alias's CQ/ITU
/// zone/continent are pre-resolved by the data producer. <c>Prefix</c> (the primary DXCC prefix,
/// distinct from the alias key), <c>ADIF</c>, <c>Latitude</c>, <c>Longitude</c>, and
/// <c>GMTOffset</c> are present in the source but not part of <see cref="CallsignRegionEntry"/>
/// and are intentionally ignored.
/// </para>
/// <para>
/// The release carries an external DOCTYPE referencing an Apple DTD URL. Parsing uses
/// <see cref="DtdProcessing.Ignore"/> and a <c>null</c> <see cref="XmlResolver"/> so no external
/// DTD fetch is ever attempted.
/// </para>
/// </remarks>
public sealed class CountryFilePlistConverter : ICountryFileConverter
{
    /// <inheritdoc/>
    public IReadOnlyList<CallsignRegionEntry> Convert(string xml, bool prefixBlocksOnly = false)
    {
        var rootDict = ParseRootDict(xml);

        var topLevel = rootDict.Elements().ToList();
        if (topLevel.Count % 2 != 0)
            throw new CountryFileConversionException(
                "Country-file release's top-level <dict> has an odd number of child elements " +
                "(expected alternating <key>/<dict> pairs).");

        var result = new List<CallsignRegionEntry>(topLevel.Count / 2);

        for (var i = 0; i < topLevel.Count; i += 2)
        {
            var keyEl   = topLevel[i];
            var entryEl = topLevel[i + 1];

            if (keyEl.Name.LocalName != "key" || entryEl.Name.LocalName != "dict")
                throw new CountryFileConversionException(
                    $"Country-file release entry at position {i / 2} is not a <key>/<dict> pair.");

            var alias = keyEl.Value.Trim();
            if (alias.Length == 0)
                throw new CountryFileConversionException(
                    $"Country-file release entry at position {i / 2} has an empty alias key.");

            var entry = ParseEntry(alias, entryEl);
            if (prefixBlocksOnly && entry.ExactCallsign)
                continue; // NFR-021: excluded from the prefix-blocks-only mode (committed defaults).

            result.Add(new CallsignRegionEntry(
                PrefixStart: alias,
                PrefixEnd:   alias,
                Entity:      entry.Country,
                Continent:   entry.Continent,
                CqZone:      entry.CqZone,
                ItuZone:     entry.ItuZone,
                Synthetic:   false));
        }

        return result;
    }

    // ── Parsing helpers ───────────────────────────────────────────────────────

    private static XElement ParseRootDict(string xml)
    {
        XDocument doc;
        try
        {
            var settings = new XmlReaderSettings
            {
                DtdProcessing = DtdProcessing.Ignore,
                XmlResolver   = null,
            };
            using var stringReader = new StringReader(xml);
            using var xmlReader    = XmlReader.Create(stringReader, settings);
            doc = XDocument.Load(xmlReader);
        }
        catch (Exception ex) when (ex is XmlException or FormatException)
        {
            throw new CountryFileConversionException("Country-file release is not well-formed XML.", ex);
        }

        return doc.Root?.Elements().FirstOrDefault(e => e.Name.LocalName == "dict")
            ?? throw new CountryFileConversionException(
                "Country-file release does not have the expected <plist><dict>...</dict></plist> shape.");
    }

    private readonly record struct ParsedEntry(string Country, string Continent, int CqZone, int ItuZone, bool ExactCallsign);

    private static ParsedEntry ParseEntry(string alias, XElement entryEl)
    {
        var fields = entryEl.Elements().ToList();
        if (fields.Count % 2 != 0)
            throw new CountryFileConversionException(
                $"Entry '{alias}' has an odd number of child elements " +
                "(expected alternating <key>/<value> pairs).");

        string? country       = null;
        string? continent     = null;
        int?    cqZone        = null;
        int?    ituZone       = null;
        bool?   exactCallsign = null;

        for (var j = 0; j < fields.Count; j += 2)
        {
            var fieldKeyEl = fields[j];
            var fieldValEl = fields[j + 1];

            if (fieldKeyEl.Name.LocalName != "key")
                throw new CountryFileConversionException(
                    $"Entry '{alias}' is missing an expected <key> element.");

            switch (fieldKeyEl.Value)
            {
                case "Country":
                    country = fieldValEl.Value;
                    break;
                case "Continent":
                    continent = fieldValEl.Value;
                    break;
                case "CQZone":
                    cqZone = ParseZone(alias, "CQZone", fieldValEl);
                    break;
                case "ITUZone":
                    ituZone = ParseZone(alias, "ITUZone", fieldValEl);
                    break;
                case "ExactCallsign":
                    exactCallsign = fieldValEl.Name.LocalName switch
                    {
                        "true"  => true,
                        "false" => false,
                        _ => throw new CountryFileConversionException(
                            $"Entry '{alias}': ExactCallsign is not a boolean plist element."),
                    };
                    break;
                // Prefix / ADIF / Latitude / Longitude / GMTOffset: present in the source release
                // but not part of CallsignRegionEntry — intentionally ignored (see class remarks).
            }
        }

        if (string.IsNullOrWhiteSpace(country))
            throw new CountryFileConversionException($"Entry '{alias}' is missing a Country value.");
        if (string.IsNullOrWhiteSpace(continent))
            throw new CountryFileConversionException($"Entry '{alias}' is missing a Continent value.");
        if (cqZone is null)
            throw new CountryFileConversionException($"Entry '{alias}' is missing a CQZone value.");
        if (ituZone is null)
            throw new CountryFileConversionException($"Entry '{alias}' is missing an ITUZone value.");
        if (exactCallsign is null)
            throw new CountryFileConversionException($"Entry '{alias}' is missing an ExactCallsign value.");

        return new ParsedEntry(country, continent, cqZone.Value, ituZone.Value, exactCallsign.Value);
    }

    private static int ParseZone(string alias, string fieldName, XElement el)
    {
        if (el.Name.LocalName != "integer" ||
            !int.TryParse(el.Value.Trim(), NumberStyles.Integer, CultureInfo.InvariantCulture, out var value))
        {
            throw new CountryFileConversionException(
                $"Entry '{alias}': {fieldName} is not a valid integer plist element.");
        }

        return value;
    }
}
