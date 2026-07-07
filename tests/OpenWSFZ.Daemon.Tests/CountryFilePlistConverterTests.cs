using FluentAssertions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Daemon;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// Unit tests for <see cref="CountryFilePlistConverter"/> (region-lookup-data-refresh, f-006).
/// All fixture XML uses fictional Q-prefix/placeholder entities and prefixes only — no real
/// country-file content is copied into a committed test fixture (NFR-021).
/// </summary>
public sealed class CountryFilePlistConverterTests
{
    private readonly CountryFilePlistConverter _converter = new();

    private static string Plist(string body) =>
        $"""
        <?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE plist PUBLIC "-//Apple Computer//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
        <plist version="1.0">
        <dict>
        {body}
        </dict>
        </plist>
        """;

    // ── Normal prefix-block entry ─────────────────────────────────────────────

    [Fact(DisplayName = "f-006 1.4: normal prefix-block entry converts to a CallsignRegionEntry")]
    public void Convert_NormalPrefixBlockEntry_MapsAllFields()
    {
        var xml = Plist("""
            <key>Q9</key>
            <dict>
            <key>Country</key><string>Fictional Land</string>
            <key>Prefix</key><string>Q9</string>
            <key>ADIF</key><integer>999</integer>
            <key>CQZone</key><integer>40</integer>
            <key>ITUZone</key><integer>41</integer>
            <key>Continent</key><string>EU</string>
            <key>Latitude</key><real>1.0</real>
            <key>Longitude</key><real>2.0</real>
            <key>GMTOffset</key><real>0.0</real>
            <key>ExactCallsign</key><false/>
            </dict>
            """);

        var entries = _converter.Convert(xml, prefixBlocksOnly: false);

        entries.Should().ContainSingle();
        var e = entries[0];
        e.PrefixStart.Should().Be("Q9");
        e.PrefixEnd.Should().Be("Q9");
        e.Entity.Should().Be("Fictional Land");
        e.Continent.Should().Be("EU");
        e.CqZone.Should().Be(40);
        e.ItuZone.Should().Be(41);
        e.Synthetic.Should().BeFalse();
    }

    // ── Individual-callsign-flagged entry ─────────────────────────────────────

    [Fact(DisplayName = "f-006 1.4: exact-callsign entry is included when prefixBlocksOnly is false (pass-through mode)")]
    public void Convert_ExactCallsignEntry_PassThroughMode_IsIncluded()
    {
        var xml = Plist("""
            <key>Q1FICTIONAL</key>
            <dict>
            <key>Country</key><string>Fictional Island</string>
            <key>Prefix</key><string>Q1</string>
            <key>ADIF</key><integer>998</integer>
            <key>CQZone</key><integer>10</integer>
            <key>ITUZone</key><integer>11</integer>
            <key>Continent</key><string>OC</string>
            <key>Latitude</key><real>0.0</real>
            <key>Longitude</key><real>0.0</real>
            <key>GMTOffset</key><real>0.0</real>
            <key>ExactCallsign</key><true/>
            </dict>
            """);

        var entries = _converter.Convert(xml, prefixBlocksOnly: false);

        entries.Should().ContainSingle();
        entries[0].PrefixStart.Should().Be("Q1FICTIONAL");
        entries[0].Entity.Should().Be("Fictional Island");
    }

    [Fact(DisplayName = "f-006 1.4: exact-callsign entry is dropped when prefixBlocksOnly is true (CallsignRegionDefaults.cs regeneration mode)")]
    public void Convert_ExactCallsignEntry_PrefixBlocksOnlyMode_IsDropped()
    {
        var xml = Plist("""
            <key>Q1FICTIONAL</key>
            <dict>
            <key>Country</key><string>Fictional Island</string>
            <key>Prefix</key><string>Q1</string>
            <key>ADIF</key><integer>998</integer>
            <key>CQZone</key><integer>10</integer>
            <key>ITUZone</key><integer>11</integer>
            <key>Continent</key><string>OC</string>
            <key>Latitude</key><real>0.0</real>
            <key>Longitude</key><real>0.0</real>
            <key>GMTOffset</key><real>0.0</real>
            <key>ExactCallsign</key><true/>
            </dict>
            <key>Q2</key>
            <dict>
            <key>Country</key><string>Fictional Mainland</string>
            <key>Prefix</key><string>Q2</string>
            <key>ADIF</key><integer>997</integer>
            <key>CQZone</key><integer>12</integer>
            <key>ITUZone</key><integer>13</integer>
            <key>Continent</key><string>AS</string>
            <key>Latitude</key><real>0.0</real>
            <key>Longitude</key><real>0.0</real>
            <key>GMTOffset</key><real>0.0</real>
            <key>ExactCallsign</key><false/>
            </dict>
            """);

        var entries = _converter.Convert(xml, prefixBlocksOnly: true);

        entries.Should().ContainSingle("the exact-callsign entry must be dropped, only the prefix-block entry survives");
        entries[0].PrefixStart.Should().Be("Q2");
    }

    // ── Malformed / incomplete entries ────────────────────────────────────────

    [Theory(DisplayName = "f-006 1.4: entry missing a required field throws CountryFileConversionException")]
    [InlineData("Country")]
    [InlineData("Continent")]
    [InlineData("CQZone")]
    [InlineData("ITUZone")]
    [InlineData("ExactCallsign")]
    public void Convert_EntryMissingRequiredField_Throws(string missingField)
    {
        var fields = new Dictionary<string, string>
        {
            ["Country"]       = "<key>Country</key><string>Fictional Land</string>",
            ["Continent"]     = "<key>Continent</key><string>EU</string>",
            ["CQZone"]        = "<key>CQZone</key><integer>40</integer>",
            ["ITUZone"]       = "<key>ITUZone</key><integer>41</integer>",
            ["ExactCallsign"] = "<key>ExactCallsign</key><false/>",
        };
        fields.Remove(missingField);

        var xml = Plist($"""
            <key>Q9</key>
            <dict>
            {string.Join('\n', fields.Values)}
            </dict>
            """);

        var act = () => _converter.Convert(xml, prefixBlocksOnly: false);

        act.Should().Throw<CountryFileConversionException>()
           .WithMessage("*Q9*", "the error should identify which entry was malformed");
    }

    [Fact(DisplayName = "f-006 1.4: non-integer CQZone throws CountryFileConversionException")]
    public void Convert_NonIntegerZone_Throws()
    {
        var xml = Plist("""
            <key>Q9</key>
            <dict>
            <key>Country</key><string>Fictional Land</string>
            <key>CQZone</key><string>not-a-number</string>
            <key>ITUZone</key><integer>41</integer>
            <key>Continent</key><string>EU</string>
            <key>ExactCallsign</key><false/>
            </dict>
            """);

        var act = () => _converter.Convert(xml, prefixBlocksOnly: false);

        act.Should().Throw<CountryFileConversionException>();
    }

    [Fact(DisplayName = "f-006 1.4: not-well-formed XML throws CountryFileConversionException")]
    public void Convert_NotWellFormedXml_Throws()
    {
        var act = () => _converter.Convert("<plist><dict><key>Q9</key>", prefixBlocksOnly: false);

        act.Should().Throw<CountryFileConversionException>();
    }

    [Fact(DisplayName = "f-006 1.4: missing root <dict> throws CountryFileConversionException")]
    public void Convert_MissingRootDict_Throws()
    {
        var act = () => _converter.Convert("""
            <?xml version="1.0"?>
            <plist version="1.0"></plist>
            """, prefixBlocksOnly: false);

        act.Should().Throw<CountryFileConversionException>();
    }

    [Fact(DisplayName = "f-006 1.4: empty alias key throws CountryFileConversionException")]
    public void Convert_EmptyAliasKey_Throws()
    {
        var xml = Plist("""
            <key></key>
            <dict>
            <key>Country</key><string>Fictional Land</string>
            <key>CQZone</key><integer>40</integer>
            <key>ITUZone</key><integer>41</integer>
            <key>Continent</key><string>EU</string>
            <key>ExactCallsign</key><false/>
            </dict>
            """);

        var act = () => _converter.Convert(xml, prefixBlocksOnly: false);

        act.Should().Throw<CountryFileConversionException>();
    }

    // ── Multiple entries, no filtering ────────────────────────────────────────

    [Fact(DisplayName = "f-006 1.4: multiple entries all convert, and DTD is ignored (no external fetch attempted)")]
    public void Convert_MultipleEntries_AllConverted()
    {
        var xml = Plist("""
            <key>Q1</key>
            <dict>
            <key>Country</key><string>Fictional Land One</string>
            <key>CQZone</key><integer>1</integer>
            <key>ITUZone</key><integer>2</integer>
            <key>Continent</key><string>EU</string>
            <key>ExactCallsign</key><false/>
            </dict>
            <key>Q2</key>
            <dict>
            <key>Country</key><string>Fictional Land Two</string>
            <key>CQZone</key><integer>3</integer>
            <key>ITUZone</key><integer>4</integer>
            <key>Continent</key><string>AS</string>
            <key>ExactCallsign</key><false/>
            </dict>
            """);

        var entries = _converter.Convert(xml, prefixBlocksOnly: false);

        entries.Should().HaveCount(2);
        entries.Select(e => e.PrefixStart).Should().BeEquivalentTo(["Q1", "Q2"]);
    }
}
