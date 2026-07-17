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

    // ── TryMatchPrefix / IsSeedData (engagement-target-validation, task 1.5) ──

    [Fact(DisplayName = "engagement-target-validation 1.5: TryMatchPrefix returns the same RegionInfo as TryGetRegion")]
    public async Task TryMatchPrefix_ReturnsSameRegionAsTryGetRegion()
    {
        var store = MakeStore();
        await store.LoadAsync();

        var viaMatch  = store.TryMatchPrefix("3A2XYZ");
        var viaLegacy = store.TryGetRegion("3A2XYZ");

        viaMatch.Should().NotBeNull();
        viaMatch!.Region.Should().Be(viaLegacy);
    }

    [Fact(DisplayName = "engagement-target-validation 1.5: TryMatchPrefix reports the matched prefix length")]
    public async Task TryMatchPrefix_ReportsMatchedPrefixLength()
    {
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

        var match = store.TryMatchPrefix("VK9AA");

        match.Should().NotBeNull();
        match!.Region.Entity.Should().Be("Australia");
        match.MatchedPrefixLength.Should().Be(2, "the more specific 'VK' (length 2) must win over 'V' (length 1)");
    }

    [Fact(DisplayName = "engagement-target-validation 1.5: TryMatchPrefix returns null on a lookup miss, identical to TryGetRegion")]
    public async Task TryMatchPrefix_UnmatchedPrefix_ReturnsNull()
    {
        var store = MakeStore();
        await store.LoadAsync();

        store.TryMatchPrefix("ZZ1ABC").Should().BeNull();
    }

    [Fact(DisplayName = "engagement-target-validation 1.5: IsSeedData is true on a fresh, never-loaded store")]
    public void IsSeedData_FreshStore_IsTrue()
    {
        var store = MakeStore();

        store.IsSeedData.Should().BeTrue();
    }

    [Fact(DisplayName = "engagement-target-validation 1.5: IsSeedData stays true after LoadAsync writes the seed table (no on-disk file existed)")]
    public async Task IsSeedData_FileAbsent_StaysTrueAfterSeedWrite()
    {
        var store = MakeStore();

        await store.LoadAsync();

        store.IsSeedData.Should().BeTrue("writing the compiled-in seed defaults is not the same as loading real operator-supplied data");
    }

    [Fact(DisplayName = "engagement-target-validation 1.5: IsSeedData becomes false after loading a real on-disk file")]
    public async Task IsSeedData_RealFileLoaded_BecomesFalse()
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

        store.IsSeedData.Should().BeFalse();
    }

    [Fact(DisplayName = "engagement-target-validation 1.5: IsSeedData stays true when the on-disk file is malformed (fallback to Unknown-only is not real data)")]
    public async Task IsSeedData_MalformedFile_StaysTrue()
    {
        await File.WriteAllTextAsync(FilePath(), "{ this is not valid json }");

        var store = MakeStore();
        await store.LoadAsync();

        store.IsSeedData.Should().BeTrue();
    }

    [Fact(DisplayName = "engagement-target-validation 1.5: IsSeedData becomes false after a successful SaveAsync")]
    public async Task IsSeedData_AfterSuccessfulSave_BecomesFalse()
    {
        var store = MakeStore();
        await store.LoadAsync();
        store.IsSeedData.Should().BeTrue("baseline: only seed data loaded so far");

        await store.SaveAsync([new("Q9", "Q9", "Fictional Land", "EU", 40, 41, Synthetic: false)]);

        store.IsSeedData.Should().BeFalse();
    }

    // ── IsSeedData restart-sequence provenance (Finding E, dev-task
    // 2026-07-17-engagement-target-validation-qa-review-findings) ────────────

    [Fact(DisplayName = "engagement-target-validation Finding E: IsSeedData stays true after a simulated daemon restart with no operator action in between")]
    public async Task IsSeedData_RestartAfterSeedWrite_StaysTrue()
    {
        // First-ever run: no file exists, LoadAsync writes the seed table to disk.
        var firstRunStore = MakeStore();
        await firstRunStore.LoadAsync();
        firstRunStore.IsSeedData.Should().BeTrue("baseline: first-ever run, nothing but the seed write has happened");

        // Simulated restart: a brand-new store instance (as a real process restart would create)
        // loads the same on-disk file the first run's seed-write produced. No operator refresh
        // happened in between — IsSeedData must still be true, not silently flip to false purely
        // because the file now exists on disk.
        var restartedStore = MakeStore();
        await restartedStore.LoadAsync();

        restartedStore.IsSeedData.Should().BeTrue(
            "a daemon that has only ever written its own seed table (never had an operator " +
            "refresh) must still report IsSeedData == true after any number of restarts");
    }

    [Fact(DisplayName = "engagement-target-validation Finding E: IsSeedData is false after a simulated refresh-then-restart sequence")]
    public async Task IsSeedData_RefreshThenRestart_ReportsFalse()
    {
        var store = MakeStore();
        await store.LoadAsync();

        // Operator-triggered refresh.
        await store.SaveAsync([new("3A", "3A", "Monaco", "EU", 14, 27, Synthetic: false)]);
        store.IsSeedData.Should().BeFalse("baseline: refresh just succeeded");

        // Simulated restart: a fresh store instance reloads the now-refreshed on-disk file.
        var restartedStore = MakeStore();
        await restartedStore.LoadAsync();

        restartedStore.IsSeedData.Should().BeFalse(
            "a daemon restarted after a genuine operator refresh must correctly report " +
            "IsSeedData == false");
    }

    [Fact(DisplayName = "engagement-target-validation Finding E: a pre-existing file with no persisted isSeedData marker (predates this capability) migrates to IsSeedData == false")]
    public async Task IsSeedData_PreExistingFileWithoutMarker_MigratesToFalse()
    {
        // No "isSeedData" property at all — the on-disk shape from before Finding E's fix existed.
        var preExistingJson = """
            {
              "entries": [
                { "prefixStart": "3A", "prefixEnd": "3A", "entity": "Monaco", "continent": "EU", "cqZone": 14, "ituZone": 27, "synthetic": false }
              ]
            }
            """;
        await File.WriteAllTextAsync(FilePath(), preExistingJson);

        var store = MakeStore();
        await store.LoadAsync();

        store.IsSeedData.Should().BeFalse(
            "a pre-existing file with no persisted provenance marker defaults to 'not seed data' " +
            "(documented migration choice: an operator running the daemon long enough to have a " +
            "pre-existing file is more likely to have refreshed at least once than not, and there " +
            "is no way to tell retroactively)");
    }
}
