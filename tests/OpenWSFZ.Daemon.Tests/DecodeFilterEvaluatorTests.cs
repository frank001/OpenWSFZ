using FluentAssertions;
using OpenWSFZ.Abstractions;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// Unit tests for <see cref="DecodeFilterEvaluator"/> (<c>decode-panel-filtering</c> capability,
/// task 1.3). Covers each axis independently and in combination, the fail-open-on-unresolved
/// rule, absent-<c>WorkedBefore</c>-as-<c>Never</c>, and the <c>Unfiltered</c> default.
///
/// NFR-021: all callsigns use the ITU-unallocated Q-prefix.
/// </summary>
[Trait("Category", "Unit")]
public sealed class DecodeFilterEvaluatorTests
{
    private static DecodeResult MakeDecode(
        RegionInfo?       region       = null,
        WorkedBeforeInfo? workedBefore = null)
        => new(
            Time:         "12:00:00",
            Snr:          0,
            Dt:           0.0,
            FreqHz:       1000,
            Message:      "CQ Q1TST JO22",
            Region:       region,
            WorkedBefore: workedBefore);

    private static readonly RegionInfo MonacoEu =
        new(Continent: "EU", Entity: "Monaco", Synthetic: false, CqZone: 14, ItuZone: 27);

    // ── Unfiltered default ───────────────────────────────────────────────────

    [Fact]
    public void Unfiltered_passes_everything_including_null_region_and_workedbefore()
    {
        var decode = MakeDecode();
        DecodeFilterEvaluator.IsVisible(decode, DecodeFilterState.Unfiltered).Should().BeTrue();
    }

    [Fact]
    public void Unfiltered_passes_a_fully_resolved_decode()
    {
        var decode = MakeDecode(region: MonacoEu, workedBefore: WorkedBeforeInfo.None);
        DecodeFilterEvaluator.IsVisible(decode, DecodeFilterState.Unfiltered).Should().BeTrue();
    }

    // ── Attribute allow-list axes — independently ────────────────────────────

    [Fact]
    public void AllowedEntities_excludes_a_resolved_entity_not_in_the_set()
    {
        var decode = MakeDecode(region: MonacoEu);
        var filter = DecodeFilterState.Unfiltered with { AllowedEntities = new HashSet<string> { "Germany" } };
        DecodeFilterEvaluator.IsVisible(decode, filter).Should().BeFalse();
    }

    [Fact]
    public void AllowedEntities_passes_a_resolved_entity_in_the_set()
    {
        var decode = MakeDecode(region: MonacoEu);
        var filter = DecodeFilterState.Unfiltered with { AllowedEntities = new HashSet<string> { "Monaco" } };
        DecodeFilterEvaluator.IsVisible(decode, filter).Should().BeTrue();
    }

    [Fact]
    public void AllowedContinents_excludes_a_resolved_continent_not_in_the_set()
    {
        var decode = MakeDecode(region: MonacoEu);
        var filter = DecodeFilterState.Unfiltered with { AllowedContinents = new HashSet<string> { "NA" } };
        DecodeFilterEvaluator.IsVisible(decode, filter).Should().BeFalse();
    }

    [Fact]
    public void AllowedCqZones_excludes_a_resolved_zone_not_in_the_set()
    {
        var decode = MakeDecode(region: MonacoEu);
        var filter = DecodeFilterState.Unfiltered with { AllowedCqZones = new HashSet<int> { 5 } };
        DecodeFilterEvaluator.IsVisible(decode, filter).Should().BeFalse();
    }

    [Fact]
    public void AllowedItuZones_excludes_a_resolved_zone_not_in_the_set()
    {
        var decode = MakeDecode(region: MonacoEu);
        var filter = DecodeFilterState.Unfiltered with { AllowedItuZones = new HashSet<int> { 1 } };
        DecodeFilterEvaluator.IsVisible(decode, filter).Should().BeFalse();
    }

    [Fact]
    public void An_explicit_empty_allow_list_filters_everything_on_that_axis()
    {
        var decode = MakeDecode(region: MonacoEu);
        var filter = DecodeFilterState.Unfiltered with { AllowedEntities = new HashSet<string>() };
        DecodeFilterEvaluator.IsVisible(decode, filter).Should().BeFalse();
    }

    // ── Fail-open on unresolved attribute values ─────────────────────────────

    [Fact]
    public void Null_region_is_never_excluded_by_an_active_entity_allow_list()
    {
        var decode = MakeDecode(region: null);
        var filter = DecodeFilterState.Unfiltered with { AllowedEntities = new HashSet<string> { "Germany" } };
        DecodeFilterEvaluator.IsVisible(decode, filter).Should().BeTrue();
    }

    [Fact]
    public void Null_continent_on_a_resolved_region_is_never_excluded_by_an_active_continent_allow_list()
    {
        // Synthetic-style region: resolved Entity, but Continent is null.
        var region = new RegionInfo(Continent: null, Entity: "Synthetic (R&R Study)", Synthetic: true);
        var decode = MakeDecode(region: region);
        var filter = DecodeFilterState.Unfiltered with { AllowedContinents = new HashSet<string> { "EU" } };
        DecodeFilterEvaluator.IsVisible(decode, filter).Should().BeTrue();
    }

    [Fact]
    public void Null_cqzone_on_a_resolved_region_is_never_excluded_by_an_active_cqzone_allow_list()
    {
        var region = new RegionInfo(Continent: "EU", Entity: "Monaco", Synthetic: false, CqZone: null, ItuZone: 27);
        var decode = MakeDecode(region: region);
        var filter = DecodeFilterState.Unfiltered with { AllowedCqZones = new HashSet<int> { 5 } };
        DecodeFilterEvaluator.IsVisible(decode, filter).Should().BeTrue();
    }

    // ── Worked-before tri-state axes ─────────────────────────────────────────

    [Fact]
    public void ContactStates_excludes_a_resolved_state_not_in_the_set()
    {
        var decode = MakeDecode(workedBefore: WorkedBeforeInfo.None with { Contact = WorkedBeforeState.ThisBand });
        var filter = DecodeFilterState.Unfiltered with
        {
            ContactStates = new HashSet<WorkedBeforeState> { WorkedBeforeState.Never, WorkedBeforeState.DifferentBand },
        };
        DecodeFilterEvaluator.IsVisible(decode, filter).Should().BeFalse();
    }

    [Fact]
    public void ContactStates_passes_a_resolved_state_in_the_set()
    {
        var decode = MakeDecode(workedBefore: WorkedBeforeInfo.None with { Contact = WorkedBeforeState.ThisBand });
        var filter = DecodeFilterState.Unfiltered with
        {
            ContactStates = new HashSet<WorkedBeforeState> { WorkedBeforeState.ThisBand },
        };
        DecodeFilterEvaluator.IsVisible(decode, filter).Should().BeTrue();
    }

    [Fact]
    public void Absent_WorkedBefore_is_treated_as_Never_and_filtered_when_Never_is_excluded()
    {
        var decode = MakeDecode(workedBefore: null);
        var filter = DecodeFilterState.Unfiltered with
        {
            ContactStates = new HashSet<WorkedBeforeState> { WorkedBeforeState.DifferentBand, WorkedBeforeState.ThisBand },
        };
        DecodeFilterEvaluator.IsVisible(decode, filter).Should().BeFalse();
    }

    [Fact]
    public void Absent_WorkedBefore_passes_when_Never_is_included_in_an_active_filter()
    {
        var decode = MakeDecode(workedBefore: null);
        var filter = DecodeFilterState.Unfiltered with
        {
            ContactStates = new HashSet<WorkedBeforeState> { WorkedBeforeState.Never },
        };
        DecodeFilterEvaluator.IsVisible(decode, filter).Should().BeTrue();
    }

    [Theory]
    [InlineData(nameof(DecodeFilterState.CountryStates))]
    [InlineData(nameof(DecodeFilterState.ContinentStates))]
    [InlineData(nameof(DecodeFilterState.CqZoneStates))]
    [InlineData(nameof(DecodeFilterState.ItuZoneStates))]
    public void Every_worked_before_axis_independently_excludes_Never_when_active(string axis)
    {
        var decode = MakeDecode(workedBefore: WorkedBeforeInfo.None); // all Never
        var onlyNonNever = new HashSet<WorkedBeforeState> { WorkedBeforeState.ThisBand };

        var filter = axis switch
        {
            nameof(DecodeFilterState.CountryStates)   => DecodeFilterState.Unfiltered with { CountryStates   = onlyNonNever },
            nameof(DecodeFilterState.ContinentStates) => DecodeFilterState.Unfiltered with { ContinentStates = onlyNonNever },
            nameof(DecodeFilterState.CqZoneStates)    => DecodeFilterState.Unfiltered with { CqZoneStates    = onlyNonNever },
            nameof(DecodeFilterState.ItuZoneStates)   => DecodeFilterState.Unfiltered with { ItuZoneStates   = onlyNonNever },
            _ => throw new ArgumentOutOfRangeException(nameof(axis)),
        };

        DecodeFilterEvaluator.IsVisible(decode, filter).Should().BeFalse();
    }

    // ── Combinations ──────────────────────────────────────────────────────────

    [Fact]
    public void A_decode_passing_all_active_axes_is_visible()
    {
        var decode = MakeDecode(
            region:       MonacoEu,
            workedBefore: WorkedBeforeInfo.None with { Contact = WorkedBeforeState.DifferentBand });

        var filter = new DecodeFilterState(
            AllowedEntities:   new HashSet<string> { "Monaco", "Germany" },
            AllowedContinents: new HashSet<string> { "EU" },
            AllowedCqZones:    new HashSet<int> { 14 },
            AllowedItuZones:   new HashSet<int> { 27 },
            ContactStates:     new HashSet<WorkedBeforeState> { WorkedBeforeState.Never, WorkedBeforeState.DifferentBand });

        DecodeFilterEvaluator.IsVisible(decode, filter).Should().BeTrue();
    }

    [Fact]
    public void A_decode_failing_any_single_active_axis_among_several_is_not_visible()
    {
        var decode = MakeDecode(
            region:       MonacoEu,
            workedBefore: WorkedBeforeInfo.None with { Contact = WorkedBeforeState.ThisBand });

        // Every axis passes except ContactStates, which excludes ThisBand.
        var filter = new DecodeFilterState(
            AllowedEntities:   new HashSet<string> { "Monaco" },
            AllowedContinents: new HashSet<string> { "EU" },
            AllowedCqZones:    new HashSet<int> { 14 },
            AllowedItuZones:   new HashSet<int> { 27 },
            ContactStates:     new HashSet<WorkedBeforeState> { WorkedBeforeState.Never, WorkedBeforeState.DifferentBand });

        DecodeFilterEvaluator.IsVisible(decode, filter).Should().BeFalse();
    }
}
