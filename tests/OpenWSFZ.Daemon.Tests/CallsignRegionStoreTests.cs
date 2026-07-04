using FluentAssertions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Daemon;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// Unit tests for <see cref="CallsignRegionStore"/> (<c>f-002-callsign-structure-region-lookup</c>).
/// Mirrors <see cref="FrequencyStoreTests"/>'s temp-directory isolation pattern.
/// </summary>
public sealed class CallsignRegionStoreTests : IDisposable
{
    private readonly string _dir;

    public CallsignRegionStoreTests()
    {
        _dir = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(_dir);
    }

    public void Dispose() => Directory.Delete(_dir, recursive: true);

    private string FilePath() => Path.Combine(_dir, "callsign-regions.json");

    private CallsignRegionStore MakeStore() => new(FilePath());

    [Fact(DisplayName = "f-002 5.3: default callsign-regions.json written when absent")]
    public async Task LoadAsync_FileAbsent_WritesSeedData()
    {
        var store = MakeStore();

        await store.LoadAsync();

        File.Exists(FilePath()).Should().BeTrue();
        store.Entries.Should().HaveCount(CallsignRegionDefaults.Entries.Count);
    }

    [Fact(DisplayName = "f-002 5.3: default callsign-regions.json carries the mandatory synthetic Q-series entry")]
    public async Task LoadAsync_FileAbsent_IncludesSyntheticEntry()
    {
        var store = MakeStore();

        await store.LoadAsync();

        store.Entries.Should().ContainSingle(
            e => e.PrefixStart == "Q" && e.PrefixEnd == "Q" && e.Synthetic && e.Entity == "Synthetic (R&R Study)");
    }

    [Fact(DisplayName = "f-002 5.3: existing callsign-regions.json loaded, not overwritten")]
    public async Task LoadAsync_FileExists_LoadsWithoutOverwriting()
    {
        var customJson = """
            {
              "entries": [
                { "prefixStart": "3A", "prefixEnd": "3A", "entity": "Monaco", "continent": "EU", "cqZone": 14, "ituZone": 27, "synthetic": false }
              ]
            }
            """;
        await File.WriteAllTextAsync(FilePath(), customJson);
        var originalContent = await File.ReadAllTextAsync(FilePath());

        var store = MakeStore();
        await store.LoadAsync();

        store.Entries.Should().HaveCount(1);
        store.Entries[0].Entity.Should().Be("Monaco");

        var afterContent = await File.ReadAllTextAsync(FilePath());
        afterContent.Should().Be(originalContent);
    }

    [Fact(DisplayName = "f-002 5.3: malformed callsign-regions.json falls back to Unknown-only, does not overwrite")]
    public async Task LoadAsync_MalformedFile_FallsBackToUnknownOnlyWithoutOverwriting()
    {
        await File.WriteAllTextAsync(FilePath(), "{ this is not valid json }");
        var originalContent = await File.ReadAllTextAsync(FilePath());

        var store = MakeStore();
        await store.LoadAsync();

        store.Entries.Should().BeEmpty("a malformed region file has no safe non-empty fallback — all lookups resolve to Unknown");
        store.TryGetRegion("Q1ABC").Should().BeNull();

        var afterContent = await File.ReadAllTextAsync(FilePath());
        afterContent.Should().Be(originalContent, "the malformed file must NOT be overwritten");
    }

    // ── TryGetRegion lookup semantics ─────────────────────────────────────────

    [Fact(DisplayName = "f-002 5.4: unmatched prefix resolves to null (Unknown)")]
    public async Task TryGetRegion_UnmatchedPrefix_ReturnsNull()
    {
        var store = MakeStore();
        await store.LoadAsync(); // seeds the default table (no entry starts with "ZZ")

        store.TryGetRegion("ZZ1ABC").Should().BeNull();
    }

    [Fact(DisplayName = "f-002: recognised prefix resolves continent and entity from the seeded default table")]
    public async Task TryGetRegion_RecognisedPrefixFromSeedTable_ResolvesRegion()
    {
        var store = MakeStore();
        await store.LoadAsync();

        var region = store.TryGetRegion("3A2XYZ"); // 3A = Monaco per CallsignRegionDefaults

        region.Should().NotBeNull();
        region!.Entity.Should().Be("Monaco");
        region.Continent.Should().Be("EU");
        region.Synthetic.Should().BeFalse();
    }

    [Fact(DisplayName = "f-002: synthetic Q-prefix resolves to the distinct synthetic region from the seeded default table")]
    public async Task TryGetRegion_SyntheticPrefixFromSeedTable_ResolvesSyntheticRegion()
    {
        var store = MakeStore();
        await store.LoadAsync();

        var region = store.TryGetRegion("Q1ABC");

        region.Should().NotBeNull();
        region!.Synthetic.Should().BeTrue();
        region.Entity.Should().Be("Synthetic (R&R Study)");
    }

    [Fact(DisplayName = "f-002: TryGetRegion prefers the longest (most specific) matching prefix range")]
    public async Task TryGetRegion_PrefersLongestMatchingPrefix()
    {
        // Two overlapping entries: a broad 1-char "V" block and a more specific 2-char "VK"
        // block. A token starting "VK" must resolve to the more specific entry.
        var customJson = """
            {
              "entries": [
                { "prefixStart": "V",  "prefixEnd": "V",  "entity": "Generic V-block", "continent": null, "cqZone": null, "ituZone": null, "synthetic": false },
                { "prefixStart": "VK", "prefixEnd": "VK", "entity": "Australia",       "continent": "OC", "cqZone": null, "ituZone": null, "synthetic": false }
              ]
            }
            """;
        await File.WriteAllTextAsync(FilePath(), customJson);

        var store = MakeStore();
        await store.LoadAsync();

        var region = store.TryGetRegion("VK9AA");

        region.Should().NotBeNull();
        region!.Entity.Should().Be("Australia",
            "the longer, more specific 'VK' prefix range must win over the shorter 'V' range");
    }
}
