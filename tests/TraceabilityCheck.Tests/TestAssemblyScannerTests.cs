using FluentAssertions;
using TraceabilityCheck;
using Xunit;

namespace TraceabilityCheck.Tests;

public sealed class TestAssemblyScannerTests
{
    [Fact(DisplayName = "P0-Tool: Display name with a single requirement ID is recognised")]
    public void ExtractIds_SingleId_ReturnsOneId()
    {
        const string displayName = "FR-007: When the daemon starts it should emit the welcome banner on stdout";

        var ids = TestAssemblyScanner.ExtractIds(displayName);

        ids.Should().ContainSingle(id => id == "FR-007");
    }

    [Fact(DisplayName = "P0-Tool: Display name with multiple comma-separated IDs is recognised")]
    public void ExtractIds_MultipleIds_ReturnsAllIds()
    {
        const string displayName = "FR-002, NFR-004: When asked to bind elsewhere it binds to 127.0.0.1";

        var ids = TestAssemblyScanner.ExtractIds(displayName);

        ids.Should().BeEquivalentTo(["FR-002", "NFR-004"]);
    }

    [Fact(DisplayName = "P0-Tool: Display name without a leading requirement ID returns an empty collection")]
    public void ExtractIds_NoLeadingId_ReturnsEmpty()
    {
        const string displayName = "When the daemon starts it should emit the welcome banner on stdout";

        var ids = TestAssemblyScanner.ExtractIds(displayName);

        ids.Should().BeEmpty();
    }

    [Fact(DisplayName = "P0-Tool: Display name with only a description (no ID prefix at all) returns empty")]
    public void ExtractIds_PlainDescription_ReturnsEmpty()
    {
        const string displayName = "P0-Tool: This is a P0 tool self-test with a colon but no FR/NFR prefix";

        var ids = TestAssemblyScanner.ExtractIds(displayName);

        ids.Should().BeEmpty();
    }

    [Fact(DisplayName = "P0-Tool: Display name with three comma-separated IDs is recognised")]
    public void ExtractIds_ThreeIds_ReturnsAllThree()
    {
        const string displayName = "FR-001, FR-002, NFR-003: Multi-req scenario";

        var ids = TestAssemblyScanner.ExtractIds(displayName);

        ids.Should().BeEquivalentTo(["FR-001", "FR-002", "NFR-003"]);
    }
}
