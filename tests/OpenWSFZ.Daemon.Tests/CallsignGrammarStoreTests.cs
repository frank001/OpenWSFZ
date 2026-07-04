using FluentAssertions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Daemon;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// Unit tests for <see cref="CallsignGrammarStore"/> (<c>f-002-callsign-structure-region-lookup</c>).
/// Mirrors <see cref="FrequencyStoreTests"/>'s temp-directory isolation pattern.
/// </summary>
public sealed class CallsignGrammarStoreTests : IDisposable
{
    private readonly string _dir;

    public CallsignGrammarStoreTests()
    {
        _dir = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(_dir);
    }

    public void Dispose() => Directory.Delete(_dir, recursive: true);

    private string FilePath() => Path.Combine(_dir, "callsign-grammar.json");

    private CallsignGrammarStore MakeStore() => new(FilePath());

    [Fact(DisplayName = "f-002 5.3: default callsign-grammar.json written when absent")]
    public async Task LoadAsync_FileAbsent_WritesBuiltInDefaults()
    {
        var store = MakeStore();

        await store.LoadAsync();

        File.Exists(FilePath()).Should().BeTrue();
        store.Current.DigitRunMax.Should().Be(3);
        store.Current.TotalLengthMax.Should().Be(11);
        store.Current.SuffixLengthMax.Should().Be(6);
    }

    [Fact(DisplayName = "f-002 5.3: default callsign-grammar.json carries the Q-series synthetic carve-out")]
    public async Task LoadAsync_FileAbsent_IncludesSyntheticCarveOut()
    {
        var store = MakeStore();

        await store.LoadAsync();

        store.Current.ReservedPrefixExclusions.Should().ContainSingle(
            e => e.Prefix == "Q" && e.SyntheticCarveOut,
            "the Q-series synthetic carve-out (NFR-021) must be present by default");
    }

    [Fact(DisplayName = "f-002 5.3: existing callsign-grammar.json loaded, not overwritten")]
    public async Task LoadAsync_FileExists_LoadsWithoutOverwriting()
    {
        var customJson = """
            {
              "digitRunMax": 4,
              "totalLengthMax": 12,
              "suffixLengthMax": 7,
              "reservedPrefixExclusions": []
            }
            """;
        await File.WriteAllTextAsync(FilePath(), customJson);
        var originalContent = await File.ReadAllTextAsync(FilePath());

        var store = MakeStore();
        await store.LoadAsync();

        store.Current.DigitRunMax.Should().Be(4);
        store.Current.TotalLengthMax.Should().Be(12);
        store.Current.SuffixLengthMax.Should().Be(7);
        store.Current.ReservedPrefixExclusions.Should().BeEmpty();

        var afterContent = await File.ReadAllTextAsync(FilePath());
        afterContent.Should().Be(originalContent);
    }

    [Fact(DisplayName = "f-002 5.3: malformed callsign-grammar.json falls back to built-in defaults, does not overwrite")]
    public async Task LoadAsync_MalformedFile_FallsBackToBuiltInDefaultsWithoutOverwriting()
    {
        await File.WriteAllTextAsync(FilePath(), "{ this is not valid json }");
        var originalContent = await File.ReadAllTextAsync(FilePath());

        var store = MakeStore();
        await store.LoadAsync();

        store.Current.Should().Be(CallsignGrammarConfig.BuiltInDefault);

        var afterContent = await File.ReadAllTextAsync(FilePath());
        afterContent.Should().Be(originalContent, "the malformed file must NOT be overwritten");
    }
}
