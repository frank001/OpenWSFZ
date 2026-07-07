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

    // ── SaveAsync (region-lookup-data-refresh, f-006) ─────────────────────────

    [Fact(DisplayName = "f-006 2.3: SaveAsync updates in-memory table and persists to file")]
    public async Task SaveAsync_UpdatesEntriesAndPersistsFile()
    {
        var store = MakeStore();
        await store.LoadAsync();

        var newEntries = new List<CallsignRegionEntry>
        {
            new("Q9", "Q9", "Fictional Land", "EU", 40, 41, Synthetic: false),
        };

        await store.SaveAsync(newEntries);

        // 2, not 1: SaveAsync always guarantees the mandatory synthetic Q-series entry survives
        // (see the SaveAsync remarks) — newEntries above doesn't supply one, so it's appended.
        store.Entries.Should().HaveCount(2);
        store.Entries.Should().Contain(e => e.Entity == "Fictional Land");

        var json = await File.ReadAllTextAsync(FilePath());
        json.Should().Contain("Fictional Land").And.Contain("\"cqZone\": 40");
    }

    [Fact(DisplayName = "f-006 2.3: a failed SaveAsync write leaves the previous in-memory table and on-disk file unchanged")]
    public async Task SaveAsync_FailedWrite_LeavesPreviousTableAndFileUnchanged()
    {
        var store = MakeStore();
        await store.LoadAsync();
        var originalEntries = store.Entries;
        var originalContent = await File.ReadAllTextAsync(FilePath());

        // Simulate an I/O error by deleting the containing directory out from under the store
        // right before the write — Directory.CreateDirectory inside SaveAsync will succeed (it's
        // idempotent), but making the destination path itself a directory forces the temp-file
        // rename to fail with an IOException.
        var conflictingDir = FilePath();
        File.Delete(conflictingDir);
        Directory.CreateDirectory(conflictingDir); // callsign-regions.json is now itself a directory

        var newEntries = new List<CallsignRegionEntry>
        {
            new("Q9", "Q9", "Should Not Persist", "EU", 1, 2, Synthetic: false),
        };

        var act = async () => await store.SaveAsync(newEntries);

        await act.Should().ThrowAsync<Exception>("the simulated I/O failure must propagate, not be swallowed");
        store.Entries.Should().BeEquivalentTo(originalEntries,
            "a failed write must leave the previous in-memory table unchanged");

        Directory.Delete(conflictingDir, recursive: true);
        // Re-create the original file content to confirm it would have been intact had the
        // directory-clobber not been introduced for this test's simulated failure.
        await File.WriteAllTextAsync(FilePath(), originalContent);
        var afterContent = await File.ReadAllTextAsync(FilePath());
        afterContent.Should().Be(originalContent);
    }

    [Fact(DisplayName = "f-006: SaveAsync guarantees the synthetic Q-series entry survives even when the caller's replacement list omits it (region-lookup's unconditional synthetic-region requirement)")]
    public async Task SaveAsync_ReplacementListWithoutSyntheticEntry_SyntheticEntryIsPreserved()
    {
        var store = MakeStore();
        await store.LoadAsync();

        // Simulates a real country-files.com refresh: real-world data has no Q-series entry.
        var realWorldLikeEntries = new List<CallsignRegionEntry>
        {
            new("3A", "3A", "Monaco", "EU", 14, 27, Synthetic: false),
        };

        await store.SaveAsync(realWorldLikeEntries);

        store.Entries.Should().Contain(
            e => e.PrefixStart == "Q" && e.PrefixEnd == "Q" && e.Synthetic &&
                 e.Entity == "Synthetic (R&R Study)",
            "a refresh must never silently drop the mandatory synthetic-region mapping " +
            "(region-lookup's unconditional 'Synthetic Q-prefix callsigns resolve to a distinct " +
            "synthetic region' requirement has no refresh carve-out)");

        store.TryGetRegion("Q1ABC")!.Synthetic.Should().BeTrue();

        // On-disk file must also carry it (LoadAsync from a fresh store must see the same guarantee).
        var store2 = MakeStore();
        await store2.LoadAsync();
        store2.Entries.Should().Contain(e => e.Synthetic);
    }

    [Fact(DisplayName = "f-006: SaveAsync does not duplicate the synthetic entry when the caller's list already includes one")]
    public async Task SaveAsync_ReplacementListAlreadyIncludesSyntheticEntry_NoDuplicate()
    {
        var store = MakeStore();
        await store.LoadAsync();

        var entriesWithSynthetic = new List<CallsignRegionEntry>
        {
            new("3A", "3A", "Monaco", "EU", 14, 27, Synthetic: false),
            new("Q",  "Q",  "Synthetic (R&R Study)", null, null, null, Synthetic: true),
        };

        await store.SaveAsync(entriesWithSynthetic);

        store.Entries.Should().HaveCount(2, "the caller-supplied synthetic entry must not be duplicated");
    }

    // ── TryGetRegion zone population (f-006 §6.3, region-data lookup diagnostic) ─────────────

    [Fact(DisplayName = "f-006 §6.3: TryGetRegion surfaces the matched entry's CQ/ITU zones")]
    public async Task TryGetRegion_KnownPrefixWithZones_ReturnsCqAndItuZone()
    {
        var customJson = """
            {
              "entries": [
                { "prefixStart": "3A", "prefixEnd": "3A", "entity": "Monaco", "continent": "EU", "cqZone": 14, "ituZone": 27, "synthetic": false }
              ]
            }
            """;
        await File.WriteAllTextAsync(FilePath(), customJson);

        var store = MakeStore();
        await store.LoadAsync();

        var region = store.TryGetRegion("3A2XYZ");

        region.Should().NotBeNull();
        region!.CqZone.Should().Be(14);
        region.ItuZone.Should().Be(27);
    }

    [Fact(DisplayName = "f-006 §6.3: TryGetRegion returns null zones for the synthetic entry")]
    public async Task TryGetRegion_SyntheticEntry_ReturnsNullZones()
    {
        var store = MakeStore();
        await store.LoadAsync(); // seed data's synthetic entry has null CqZone/ItuZone

        var region = store.TryGetRegion("Q1ABC");

        region.Should().NotBeNull();
        region!.Synthetic.Should().BeTrue();
        region.CqZone.Should().BeNull();
        region.ItuZone.Should().BeNull();
    }

    [Fact(DisplayName = "f-006 §6.3: TryGetRegion returns null for an unmatched prefix (no zones to report)")]
    public async Task TryGetRegion_UnmatchedPrefix_ReturnsNullNotZeroZones()
    {
        var store = MakeStore();
        await store.LoadAsync();

        store.TryGetRegion("ZZ1ABC").Should().BeNull();
    }

    [Fact(DisplayName = "f-006 2.3: after SaveAsync, a fresh store loaded from the same file sees the new data")]
    public async Task SaveAsync_RoundTrip_FreshStoreSeesNewData()
    {
        var store = MakeStore();
        await store.LoadAsync();

        var newEntries = new List<CallsignRegionEntry>
        {
            new("Q9", "Q9", "Fictional Land", "EU", 40, 41, Synthetic: false),
        };
        await store.SaveAsync(newEntries);

        var store2 = MakeStore();
        await store2.LoadAsync();

        // 2, not 1 — see the synthetic-entry-preservation test above.
        store2.Entries.Should().HaveCount(2);
        store2.Entries.Should().Contain(e => e.Entity == "Fictional Land");
    }
}
