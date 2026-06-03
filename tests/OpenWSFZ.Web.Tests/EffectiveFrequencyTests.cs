using FluentAssertions;
using OpenWSFZ.Abstractions;
using Xunit;

namespace OpenWSFZ.Web.Tests;

/// <summary>
/// Unit tests for <see cref="WebApp.ResolveEffectiveFrequency"/> — the three-tier
/// dial frequency resolution rule (FR-039).
/// </summary>
[Trait("Category", "Unit")]
public sealed class EffectiveFrequencyTests
{
    // ── Tier 1: Live CAT value wins ───────────────────────────────────────────

    [Theory(DisplayName = "FR-039: Tier-1 — live CAT value wins over persisted and manual")]
    [InlineData(14.074, true,  7.074, 3.573, 14.074)]
    [InlineData(14.074, false, 7.074, 3.573, 14.074)]
    public void ResolveEffectiveFrequency_LiveCat_ReturnsLive(
        double? liveFreq,
        bool    catEnabled,
        double? lastPolled,
        double  manualFreq,
        double  expected)
    {
        var catState = new FakeCatState(liveFreq);
        var config   = BuildConfig(catEnabled, lastPolled, manualFreq);

        var result = WebApp.ResolveEffectiveFrequency(catState, config);

        result.Should().BeApproximately(expected, 1e-9);
    }

    // ── Tier 2: Persisted last-known CAT value (only when enabled) ────────────

    [Fact(DisplayName = "FR-039: Tier-2 — persisted CAT frequency used when no live value and CAT enabled")]
    public void ResolveEffectiveFrequency_NoLive_CatEnabled_ReturnsLastPolled()
    {
        var catState = new FakeCatState(null);   // session restart — no live value
        var config   = BuildConfig(catEnabled: true, lastPolled: 7.074, manualFreq: 3.573);

        var result = WebApp.ResolveEffectiveFrequency(catState, config);

        result.Should().BeApproximately(7.074, 1e-9);
    }

    [Fact(DisplayName = "FR-039: Tier-2 — persisted CAT frequency ignored when CAT disabled")]
    public void ResolveEffectiveFrequency_NoLive_CatDisabled_IgnoresLastPolled()
    {
        var catState = new FakeCatState(null);
        var config   = BuildConfig(catEnabled: false, lastPolled: 7.074, manualFreq: 3.573);

        var result = WebApp.ResolveEffectiveFrequency(catState, config);

        result.Should().BeApproximately(3.573, 1e-9,
            "persisted frequency must be ignored when CAT is disabled");
    }

    // ── Tier 3: Manual fallback ───────────────────────────────────────────────

    [Fact(DisplayName = "FR-039: Tier-3 — manual dial frequency used when no CAT")]
    public void ResolveEffectiveFrequency_NoLive_NoCat_ReturnsManual()
    {
        var catState = new FakeCatState(null);
        var config   = BuildConfig(catEnabled: false, lastPolled: null, manualFreq: 7.074);

        var result = WebApp.ResolveEffectiveFrequency(catState, config);

        result.Should().BeApproximately(7.074, 1e-9);
    }

    // ── Null catState ─────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-039: Null catState falls through to manual frequency")]
    public void ResolveEffectiveFrequency_NullCatState_ReturnsManual()
    {
        var config = BuildConfig(catEnabled: false, lastPolled: null, manualFreq: 7.074);

        var result = WebApp.ResolveEffectiveFrequency(null, config);

        result.Should().BeApproximately(7.074, 1e-9);
    }

    // ── All null / zero ───────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-039: All null or zero inputs return 0.0")]
    public void ResolveEffectiveFrequency_AllNull_ReturnsZero()
    {
        var catState = new FakeCatState(null);
        var config   = new AppConfig();    // no Cat, no DecodeLog

        var result = WebApp.ResolveEffectiveFrequency(catState, config);

        result.Should().Be(0.0);
    }

    // ── Five parameterised theory cases from the spec ─────────────────────────

    [Theory(DisplayName = "FR-039: Three-tier resolution — spec scenarios")]
    [InlineData(14.074, true,  7.074, 3.573, 14.074)]   // Live CAT active
    [InlineData(null,   true,  7.074, 3.573, 7.074)]    // Session restart, CAT enabled
    [InlineData(null,   false, 7.074, 3.573, 3.573)]    // CAT disabled, persisted ignored
    [InlineData(null,   false, null,  7.074, 7.074)]    // No CAT, manual only
    [InlineData(null,   false, null,  0.0,   0.0)]      // All null/zero
    public void ResolveEffectiveFrequency_SpecScenarios(
        double? liveFreq,
        bool    catEnabled,
        double? lastPolled,
        double  manualFreq,
        double  expected)
    {
        ICatState? catState = liveFreq.HasValue ? new FakeCatState(liveFreq) : new FakeCatState(null);
        var config = BuildConfig(catEnabled, lastPolled, manualFreq);

        var result = WebApp.ResolveEffectiveFrequency(catState, config);

        result.Should().BeApproximately(expected, 1e-9);
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private static AppConfig BuildConfig(bool catEnabled, double? lastPolled, double manualFreq)
        => new AppConfig() with
        {
            Cat = new CatConfig
            {
                Enabled                = catEnabled,
                LastPolledFrequencyMHz = lastPolled,
            },
            DecodeLog = new DecodeLogConfig
            {
                DialFrequencyMHz = manualFreq,
            },
        };

    private sealed class FakeCatState : ICatState
    {
        public FakeCatState(double? freq)
        {
            DialFrequencyMHz = freq;
            Status           = freq.HasValue
                ? CatConnectionStatus.Connected
                : CatConnectionStatus.Disabled;
        }

        public double?            DialFrequencyMHz { get; }
        public CatConnectionStatus Status           { get; }

        public void Update(double? freq, CatConnectionStatus status)
            => throw new NotSupportedException();
    }
}
