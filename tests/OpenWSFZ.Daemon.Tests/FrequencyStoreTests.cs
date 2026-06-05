using System.Text.Json;
using FluentAssertions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Daemon;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// Unit tests for <see cref="FrequencyStore"/> (FR-042).
/// Uses a temporary directory so tests are fully isolated and parallel-safe.
/// </summary>
public sealed class FrequencyStoreTests : IDisposable
{
    private readonly string _dir;

    public FrequencyStoreTests()
    {
        _dir = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(_dir);
    }

    public void Dispose()
    {
        Directory.Delete(_dir, recursive: true);
    }

    private string FilePath() => Path.Combine(_dir, "frequencies.json");

    private FrequencyStore MakeStore() => new(FilePath());

    // ── Default file creation ─────────────────────────────────────────────

    [Fact(DisplayName = "FR-042: default frequencies.json written when absent")]
    public async Task LoadAsync_FileAbsent_WritesDefaultList()
    {
        var store = MakeStore();

        await store.LoadAsync();

        File.Exists(FilePath()).Should().BeTrue();

        var entries = store.Entries;
        entries.Should().HaveCount(15);
        entries.Should().OnlyContain(e => e.Protocol == "FT8");
        entries[0].FrequencyMHz.Should().BeApproximately(1.840, 0.0001);
        entries[14].FrequencyMHz.Should().BeApproximately(432.065, 0.0001);
    }

    [Fact(DisplayName = "FR-042: existing frequencies.json loaded, not overwritten")]
    public async Task LoadAsync_FileExists_LoadsWithoutOverwriting()
    {
        // Write a custom list before the store starts.
        var custom = new[]
        {
            new FrequencyEntry("FT8", 7.074, "40m"),
            new FrequencyEntry("FT8", 14.074, "20m"),
        };
        var customJson = JsonSerializer.Serialize(
            new { entries = custom },
            new JsonSerializerOptions { PropertyNamingPolicy = JsonNamingPolicy.CamelCase });
        await File.WriteAllTextAsync(FilePath(), customJson);
        var originalContent = await File.ReadAllTextAsync(FilePath());

        var store = MakeStore();
        await store.LoadAsync();

        store.Entries.Should().HaveCount(2);
        store.Entries[0].FrequencyMHz.Should().Be(7.074);

        // File must not be overwritten.
        var afterContent = await File.ReadAllTextAsync(FilePath());
        afterContent.Should().Be(originalContent);
    }

    // ── Malformed file ────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-042: malformed frequencies.json falls back to defaults, does not overwrite")]
    public async Task LoadAsync_MalformedFile_FallsBackToDefaultsWithoutOverwriting()
    {
        await File.WriteAllTextAsync(FilePath(), "{ this is not valid json }");
        var originalContent = await File.ReadAllTextAsync(FilePath());

        var store = MakeStore();
        await store.LoadAsync();

        // In-memory defaults are used.
        store.Entries.Should().HaveCount(15);
        store.Entries.Should().OnlyContain(e => e.Protocol == "FT8");

        // Malformed file is preserved for operator inspection.
        var afterContent = await File.ReadAllTextAsync(FilePath());
        afterContent.Should().Be(originalContent,
            "the malformed file must NOT be overwritten");
    }

    // ── SaveAsync ─────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-042: SaveAsync updates in-memory list and persists to file")]
    public async Task SaveAsync_UpdatesEntriesAndPersistsFile()
    {
        var store = MakeStore();
        await store.LoadAsync();

        var newEntries = new List<FrequencyEntry>
        {
            new("FT8", 7.074, "40m"),
            new("FT8", 14.074, "20m"),
        };

        await store.SaveAsync(newEntries);

        store.Entries.Should().HaveCount(2);
        store.Entries[0].FrequencyMHz.Should().Be(7.074);

        // Read back from disk to verify persistence.
        var json = await File.ReadAllTextAsync(FilePath());
        json.Should().Contain("7.074").And.Contain("14.074");
    }

    [Fact(DisplayName = "FR-042: SaveAsync writes atomically — file never partially written")]
    public async Task SaveAsync_IsAtomic_FileAlwaysCompleteAfterWrite()
    {
        var store = MakeStore();
        await store.LoadAsync();

        // Write twice in quick succession and verify the file is always valid JSON.
        var batch1 = new List<FrequencyEntry> { new("FT8", 7.074, "40m") };
        var batch2 = new List<FrequencyEntry> { new("FT8", 14.074, "20m"), new("FT8", 21.074, "15m") };

        await Task.WhenAll(store.SaveAsync(batch1), store.SaveAsync(batch2));

        // Either batch is fine; the file must be valid JSON.
        var json = await File.ReadAllTextAsync(FilePath());
        var act = () => JsonDocument.Parse(json);
        act.Should().NotThrow("the file must always be valid JSON after an atomic write");
    }

    // ── Sort-order invariant (FR-042) ─────────────────────────────────────

    [Fact(DisplayName = "FR-042: SaveAsync persists entries sorted by FrequencyMHz ascending regardless of input order")]
    public async Task SaveAsync_SortsByFrequencyMHzAscending()
    {
        var store = MakeStore();
        await store.LoadAsync();

        // Supply entries in deliberately descending order.
        var unordered = new List<FrequencyEntry>
        {
            new("FT8", 14.074, "20m"),
            new("FT8",  1.840, "160m"),
            new("FT8",  7.074, "40m"),
        };

        await store.SaveAsync(unordered);

        // In-memory list must be sorted.
        store.Entries[0].FrequencyMHz.Should().Be(1.840);
        store.Entries[1].FrequencyMHz.Should().Be(7.074);
        store.Entries[2].FrequencyMHz.Should().Be(14.074);

        // Round-trip: a fresh store loaded from the persisted file must also be sorted.
        var store2 = MakeStore();
        await store2.LoadAsync();
        store2.Entries[0].FrequencyMHz.Should().Be(1.840);
        store2.Entries[1].FrequencyMHz.Should().Be(7.074);
        store2.Entries[2].FrequencyMHz.Should().Be(14.074);
    }

    [Fact(DisplayName = "FR-042: LoadAsync sorts in-memory entries by FrequencyMHz ascending when the file was written out of order")]
    public async Task LoadAsync_UnsortedFile_SortsEntriesInMemory()
    {
        // Write a pre-existing file whose entries are in descending order
        // (simulating a file saved before the sort invariant was introduced).
        var unsortedJson = """
            {
              "entries": [
                { "protocol": "FT8", "frequencyMHz": 14.074, "description": "20m" },
                { "protocol": "FT8", "frequencyMHz":  1.840, "description": "160m" },
                { "protocol": "FT8", "frequencyMHz":  7.074, "description": "40m" }
              ]
            }
            """;
        await File.WriteAllTextAsync(FilePath(), unsortedJson);

        var store = MakeStore();
        await store.LoadAsync();

        // The file must NOT be overwritten — sort is in-memory only.
        var afterContent = await File.ReadAllTextAsync(FilePath());
        afterContent.Should().Contain("14.074",
            "the original (unsorted) file must be preserved as-is");

        // But the in-memory list must be sorted.
        store.Entries[0].FrequencyMHz.Should().Be(1.840);
        store.Entries[1].FrequencyMHz.Should().Be(7.074);
        store.Entries[2].FrequencyMHz.Should().Be(14.074);
    }

    // ── Round-trip fidelity ───────────────────────────────────────────────

    [Fact(DisplayName = "FR-042: SaveAsync preserves round-trip — loaded entries match saved entries")]
    public async Task SaveAsync_RoundTrip_PreservesAllFields()
    {
        var store = MakeStore();
        await store.LoadAsync();

        var entries = new List<FrequencyEntry>
        {
            new("FT8",  7.074, "40m"),
            new("FT4", 10.136, "30m"),
            new("JT65", 14.076, ""),   // empty description
        };
        await store.SaveAsync(entries);

        // Create a fresh store from the same file to verify round-trip.
        var store2 = MakeStore();
        await store2.LoadAsync();

        store2.Entries.Should().HaveCount(3);
        store2.Entries[0].Should().Be(entries[0]);
        store2.Entries[1].Should().Be(entries[1]);
        store2.Entries[2].Should().Be(entries[2]);
    }
}
