using FluentAssertions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Config;
using OpenWSFZ.Web;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// Regression tests for the decode-pump band-change guard after the
/// DEFECT-cycle-discard-on-restart fix (FR-039).
///
/// Guards: at window-open time catState.DialFrequencyMHz may be null (first
/// CAT poll has not yet completed), but LastPolledFrequencyMHz carries the
/// persisted value from the previous session.  Both comparator sites must
/// resolve to the same effective frequency so the cycle is NOT discarded.
/// </summary>
[Trait("Category", "Unit")]
public sealed class DecodeFrequencyGuardTests
{
    // ── Scenario: null live state + persisted value → no spurious discard ──

    [Fact(DisplayName = "FR-039: effective frequency equals persisted value when live CAT is null at window-open")]
    public void WindowOpen_LiveCatNull_ReturnsPersistedFrequency()
    {
        // Arrange — simulate the state at window-open: no poll has completed yet.
        var config = new AppConfig() with
        {
            Cat = new CatConfig
            {
                Enabled                = true,
                RigModel               = "SerialCat",
                LastPolledFrequencyMHz = 7.074,
            },
        };
        ICatState? catStateAtWindowOpen = null;   // no live session state yet

        // Act — this is what the dialFreqProvider delegate now calls.
        var freqAtOpen = WebApp.ResolveEffectiveFrequency(catStateAtWindowOpen, config);

        // Assert — must resolve to the persisted value, not 0.0 / "unknown".
        freqAtOpen.Should().BeApproximately(7.074, 1e-9,
            "the persisted LastPolledFrequencyMHz must be returned when live CAT state is null");
    }

    [Fact(DisplayName = "FR-039: effective frequency at window-close equals persisted value when first poll returns same frequency")]
    public void WindowClose_FirstPollReturnsSameFreq_EffectiveFreqUnchanged()
    {
        // Arrange — simulate the state at window-close: first poll just completed.
        const double persistedMHz = 7.074;
        var config = new AppConfig() with
        {
            Cat = new CatConfig
            {
                Enabled                = true,
                RigModel               = "SerialCat",
                LastPolledFrequencyMHz = persistedMHz,
            },
        };

        // After the first poll catState.DialFrequencyMHz returns the same value.
        var catStateAtWindowClose = new StubCatState(persistedMHz);

        // Act
        var freqAtClose = WebApp.ResolveEffectiveFrequency(catStateAtWindowClose, config);

        // Assert
        freqAtClose.Should().BeApproximately(persistedMHz, 1e-9,
            "live CAT value takes priority and equals the persisted frequency — no band-change detected");
    }

    [Fact(DisplayName = "FR-039: window-open and window-close effective frequencies match → cycle is NOT discarded")]
    public void OpenAndCloseFrequenciesMatch_NoBandChange()
    {
        // Arrange — the comparison performed by the decode pump.
        const double persistedMHz = 7.074;
        var config = new AppConfig() with
        {
            Cat = new CatConfig
            {
                Enabled                = true,
                RigModel               = "SerialCat",
                LastPolledFrequencyMHz = persistedMHz,
            },
        };

        // Window-open: live state is null (no poll yet) → resolves to persisted.
        var freqAtOpen = (double?)WebApp.ResolveEffectiveFrequency(null, config);

        // Window-close: first poll completed and returned the same frequency.
        var freqAtClose = (double?)WebApp.ResolveEffectiveFrequency(
            new StubCatState(persistedMHz), config);

        // The decode-pump guard: windowDialFreq != currentDialFreq → discard.
        var wouldDiscard = freqAtOpen != freqAtClose;

        // Assert — the cycle must NOT be discarded.
        wouldDiscard.Should().BeFalse(
            "both comparator sites resolve to the same effective frequency when the " +
            "radio has not changed bands, so the band-change guard must not fire");
    }

    // ── Scenario: true band change is still detected ──────────────────────

    [Fact(DisplayName = "FR-039: cycle IS discarded when radio genuinely changes band during window")]
    public void TrueBandChange_CycleDiscarded()
    {
        // Arrange — operator moves from 40 m to 20 m during the 15-second window.
        const double openMHz  = 7.074;
        const double closeMHz = 14.074;
        var config = new AppConfig() with
        {
            Cat = new CatConfig
            {
                Enabled                = true,
                RigModel               = "SerialCat",
                LastPolledFrequencyMHz = openMHz,
            },
        };

        var freqAtOpen  = (double?)WebApp.ResolveEffectiveFrequency(null, config);
        var freqAtClose = (double?)WebApp.ResolveEffectiveFrequency(
            new StubCatState(closeMHz), config);

        var wouldDiscard = freqAtOpen != freqAtClose;

        // Assert — the cycle MUST be discarded (this is the legitimate guard path).
        wouldDiscard.Should().BeTrue(
            "a genuine band change during the capture window must still trigger the discard guard");
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private sealed class StubCatState : ICatState
    {
        private readonly double _freq;
        public StubCatState(double freqMHz) => _freq = freqMHz;

        public double?              DialFrequencyMHz   => _freq;
        public CatConnectionStatus  Status             => CatConnectionStatus.Connected;
        public string?              RigModel           => null;
    }
}
