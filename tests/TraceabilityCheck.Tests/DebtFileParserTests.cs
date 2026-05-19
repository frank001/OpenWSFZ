using FluentAssertions;
using TraceabilityCheck;
using Xunit;

namespace TraceabilityCheck.Tests;

/// <summary>
/// Tests for <see cref="DebtFileParser"/>.
/// Task 4.10 extension — debt-file parsing scenarios.
/// </summary>
public sealed class DebtFileParserTests
{
    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    /// <summary>Writes content to a temp file and returns its path.</summary>
    private static string WriteTempFile(string content)
    {
        var path = Path.Combine(Path.GetTempPath(), Path.GetRandomFileName() + ".md");
        File.WriteAllText(path, content);
        return path;
    }

    // -------------------------------------------------------------------------
    // Non-existent file
    // -------------------------------------------------------------------------

    [Fact(DisplayName = "P0-Tool: DebtFileParser returns empty set when file does not exist")]
    public void Parse_FileNotFound_ReturnsEmptySet()
    {
        var result = DebtFileParser.Parse(Path.Combine(Path.GetTempPath(), "nonexistent-debt-file.md"));

        result.Should().BeEmpty();
    }

    // -------------------------------------------------------------------------
    // Well-formed content
    // -------------------------------------------------------------------------

    [Fact(DisplayName = "P0-Tool: DebtFileParser extracts FR and NFR IDs from a well-formed debt file")]
    public void Parse_WellFormedContent_ExtractsBothFrAndNfrIds()
    {
        var content = """
            # Traceability Debt

            ## Pending — Phase 1

            FR-001  # Some functional requirement
            NFR-002  # Some non-functional requirement
            FR-007  # Another one
            """;
        var path = WriteTempFile(content);

        try
        {
            var result = DebtFileParser.Parse(path);

            result.Should().BeEquivalentTo(new[] { "FR-001", "NFR-002", "FR-007" });
        }
        finally
        {
            File.Delete(path);
        }
    }

    [Fact(DisplayName = "P0-Tool: DebtFileParser skips markdown heading lines starting with #")]
    public void Parse_HeadingLines_AreSkipped()
    {
        var content = """
            # This heading is skipped
            ## This sub-heading is also skipped
            FR-001  # only this ID is extracted
            """;
        var path = WriteTempFile(content);

        try
        {
            var result = DebtFileParser.Parse(path);

            result.Should().ContainSingle(id => id == "FR-001");
        }
        finally
        {
            File.Delete(path);
        }
    }

    [Fact(DisplayName = "P0-Tool: DebtFileParser skips blank lines without error")]
    public void Parse_BlankLines_AreSkipped()
    {
        var content = """
            FR-001  # first

            FR-002  # second after blank

            """;
        var path = WriteTempFile(content);

        try
        {
            var result = DebtFileParser.Parse(path);

            result.Should().BeEquivalentTo(new[] { "FR-001", "FR-002" });
        }
        finally
        {
            File.Delete(path);
        }
    }

    [Fact(DisplayName = "P0-Tool: DebtFileParser returns empty set for a file containing only headings and blank lines")]
    public void Parse_OnlyHeadingsAndBlanks_ReturnsEmptySet()
    {
        var content = """
            # Title

            ## Section

            """;
        var path = WriteTempFile(content);

        try
        {
            var result = DebtFileParser.Parse(path);

            result.Should().BeEmpty();
        }
        finally
        {
            File.Delete(path);
        }
    }

    [Fact(DisplayName = "P0-Tool: DebtFileParser ignores inline comment text after the ID on the same line")]
    public void Parse_InlineComment_IsIgnored()
    {
        var content = "FR-005  # This comment should be ignored entirely\n";
        var path = WriteTempFile(content);

        try
        {
            var result = DebtFileParser.Parse(path);

            result.Should().ContainSingle(id => id == "FR-005");
        }
        finally
        {
            File.Delete(path);
        }
    }

    [Fact(DisplayName = "P0-Tool: DebtFileParser de-duplicates repeated IDs within the file")]
    public void Parse_DuplicateIds_AreDeduped()
    {
        var content = """
            FR-001  # first mention
            FR-001  # duplicate mention
            """;
        var path = WriteTempFile(content);

        try
        {
            var result = DebtFileParser.Parse(path);

            result.Should().ContainSingle(id => id == "FR-001");
        }
        finally
        {
            File.Delete(path);
        }
    }
}
