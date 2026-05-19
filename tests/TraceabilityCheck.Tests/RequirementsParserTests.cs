using FluentAssertions;
using TraceabilityCheck;
using Xunit;

namespace TraceabilityCheck.Tests;

public sealed class RequirementsParserTests
{
    [Fact(DisplayName = "P0-Tool: All declared requirement IDs are extracted from a well-formed REQUIREMENTS.md")]
    public void Parse_WellFormedContent_ExtractsAllIds()
    {
        const string content = """
            ## Functional Requirements
            FR-001 The system shall do X.
            FR-002 The system shall do Y.
            NFR-001 The system shall be fast.
            NFR-015 The system shall be secure.
            """;

        var ids = RequirementsParser.Parse(content);

        ids.Should().BeEquivalentTo(["FR-001", "FR-002", "NFR-001", "NFR-015"]);
    }

    [Fact(DisplayName = "P0-Tool: Each ID is extracted exactly once regardless of how many times it appears")]
    public void Parse_DuplicateIds_DeduplicatesResult()
    {
        const string content = "FR-001 appears here. And FR-001 appears again.";

        var ids = RequirementsParser.Parse(content);

        ids.Should().ContainSingle(id => id == "FR-001");
    }

    [Fact(DisplayName = "P0-Tool: Malformed identifier FR-1 (too few digits) surfaces a parse error")]
    public void Parse_MalformedTooFewDigits_ThrowsFormatException()
    {
        const string content = "FR-1 This is a malformed ID.";

        var act = () => RequirementsParser.Parse(content);

        act.Should().Throw<FormatException>()
            .WithMessage("*FR-1*");
    }

    [Fact(DisplayName = "P0-Tool: Malformed identifier FR-12 (two digits) surfaces a parse error")]
    public void Parse_MalformedTwoDigits_ThrowsFormatException()
    {
        const string content = "FR-12 Two-digit ID.";

        var act = () => RequirementsParser.Parse(content);

        act.Should().Throw<FormatException>();
    }

    [Fact(DisplayName = "P0-Tool: Lowercase nfr-001 is treated as malformed (case-sensitive)")]
    public void Parse_LowercasePrefix_ThrowsFormatException()
    {
        const string content = "nfr-001 lowercase should be rejected.";

        var act = () => RequirementsParser.Parse(content);

        act.Should().Throw<FormatException>();
    }

    [Fact(DisplayName = "P0-Tool: Empty content returns an empty set")]
    public void Parse_EmptyContent_ReturnsEmptySet()
    {
        var ids = RequirementsParser.Parse(string.Empty);

        ids.Should().BeEmpty();
    }

    [Fact(DisplayName = "P0-Tool: Content with no requirement IDs returns an empty set")]
    public void Parse_ContentWithoutIds_ReturnsEmptySet()
    {
        const string content = "This document has no requirement identifiers at all.";

        var ids = RequirementsParser.Parse(content);

        ids.Should().BeEmpty();
    }
}
