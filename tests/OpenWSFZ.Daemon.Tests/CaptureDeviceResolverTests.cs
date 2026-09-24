using FluentAssertions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Daemon;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// Table tests for <see cref="CaptureDeviceResolver.Resolve"/> — every branch and scenario in
/// <c>openspec/changes/capture-device-reresolution/specs/audio-device/spec.md</c>'s "Stale
/// capture device identifier is re-resolved" requirement (capture-device-reresolution #187,
/// design.md Decisions 1–2). A pure function over an already-enumerated list — no fakes, no
/// async, no time dependency needed.
/// </summary>
public sealed class CaptureDeviceResolverTests
{
    private static AudioDeviceInfo Device(string id, string name, bool available = true)
        => new(id, name, available);

    // ── CannotResolve ────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-070: empty enumeration resolves to CannotResolve")]
    public void Resolve_EmptyEnumeration_ReturnsCannotResolve()
    {
        var result = CaptureDeviceResolver.Resolve("id-1", "Mic", devices: []);

        result.Kind.Should().Be(CaptureDeviceResolutionKind.CannotResolve,
            "an empty enumeration means there is nothing better to try than the configured ID unchanged");
    }

    [Fact(DisplayName = "FR-070: null configured friendly name resolves to CannotResolve, even with devices present")]
    public void Resolve_NullConfiguredName_ReturnsCannotResolve()
    {
        var devices = new[] { Device("id-1", "Mic") };

        var result = CaptureDeviceResolver.Resolve("id-2", configuredName: null, devices);

        result.Kind.Should().Be(CaptureDeviceResolutionKind.CannotResolve,
            "with no configured name there is no basis for a name match, and the configured ID is absent");
    }

    // ── UseConfigured ────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-070: configured ID present and available resolves to UseConfigured")]
    public void Resolve_ConfiguredIdPresentAndAvailable_ReturnsUseConfigured()
    {
        var devices = new[] { Device("id-1", "Mic") };

        var result = CaptureDeviceResolver.Resolve("id-1", "Mic", devices);

        result.Kind.Should().Be(CaptureDeviceResolutionKind.UseConfigured);
    }

    [Fact(DisplayName = "Scenario \"Configured device present is never replaced\": UseConfigured even when a DIFFERENT available device also bears the configured friendly name")]
    public void Resolve_ConfiguredIdPresentWithDifferentMatchingNameElsewhere_ReturnsUseConfigured()
    {
        // The configured device's OWN current name differs from the stored friendly name, and a
        // second, different device happens to carry that stored name — an operator-chosen device
        // is never second-guessed by name (design D2).
        var devices = new[]
        {
            Device("id-1", "Renamed Mic"),   // the configured ID, name has since changed
            Device("id-2", "Old Mic Name"),  // a different device, bearing the configured name
        };

        var result = CaptureDeviceResolver.Resolve("id-1", "Old Mic Name", devices);

        result.Kind.Should().Be(CaptureDeviceResolutionKind.UseConfigured,
            "the configured ID is present and available — its current name is irrelevant");
    }

    [Fact(DisplayName = "FR-070: UseConfigured even when the configured device's current name differs from the stored friendly name")]
    public void Resolve_ConfiguredIdPresentWithDifferentName_StillReturnsUseConfigured()
    {
        var devices = new[] { Device("id-1", "A Totally Different Name") };

        var result = CaptureDeviceResolver.Resolve("id-1", "Original Stored Name", devices);

        result.Kind.Should().Be(CaptureDeviceResolutionKind.UseConfigured);
    }

    // ── Adopt ────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "Scenario \"Rotated endpoint ID is adopted\": configured ID absent, exactly one available device matches the name")]
    public void Resolve_ConfiguredIdAbsent_OneNameMatch_ReturnsAdopt()
    {
        var devices = new[] { Device("{BBBB}", "Microphone (2- USB Audio CODEC )") };

        var result = CaptureDeviceResolver.Resolve("{AAAA}", "Microphone (2- USB Audio CODEC )", devices);

        result.Kind.Should().Be(CaptureDeviceResolutionKind.Adopt);
        result.NewId.Should().Be("{BBBB}");
        result.MatchCount.Should().Be(1);
    }

    [Fact(DisplayName = "FR-070: configured ID null (never configured) with one name match still Adopts")]
    public void Resolve_ConfiguredIdNull_OneNameMatch_ReturnsAdopt()
    {
        var devices = new[] { Device("id-new", "Mic") };

        var result = CaptureDeviceResolver.Resolve(configuredId: null, "Mic", devices);

        result.Kind.Should().Be(CaptureDeviceResolutionKind.Adopt);
        result.NewId.Should().Be("id-new");
    }

    // ── NotFound ─────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-070: configured ID absent, zero name matches resolves to NotFound")]
    public void Resolve_ConfiguredIdAbsent_ZeroNameMatches_ReturnsNotFound()
    {
        var devices = new[] { Device("id-1", "Some Other Mic") };

        var result = CaptureDeviceResolver.Resolve("id-gone", "My Mic", devices);

        result.Kind.Should().Be(CaptureDeviceResolutionKind.NotFound);
        result.MatchCount.Should().Be(0);
    }

    [Fact(DisplayName = "Scenario \"Disabled-only match is not adopted\": the only name match is unavailable")]
    public void Resolve_OnlyMatchIsUnavailable_ReturnsNotFound()
    {
        var devices = new[] { Device("id-1", "My Mic", available: false) };

        var result = CaptureDeviceResolver.Resolve("id-gone", "My Mic", devices);

        result.Kind.Should().Be(CaptureDeviceResolutionKind.NotFound,
            "capture cannot be opened on a disabled endpoint — it must never be adopted");
    }

    [Theory(DisplayName = "Scenario \"Near-miss names do not match\"")]
    [InlineData("Microphone (3- USB Audio CODEC )")]  // prefix renumbered
    [InlineData("Microphone (2- USB Audio CODEC)")]   // trailing space missing
    public void Resolve_NearMissName_DoesNotMatch(string actualName)
    {
        var devices = new[] { Device("id-1", actualName) };

        var result = CaptureDeviceResolver.Resolve("id-gone", "Microphone (2- USB Audio CODEC )", devices);

        result.Kind.Should().Be(CaptureDeviceResolutionKind.NotFound,
            "matching is byte-for-byte ordinal — no trim, no case-fold, no substring, no prefix tolerance");
    }

    [Fact(DisplayName = "FR-070: matching is case-sensitive")]
    public void Resolve_CaseDifference_DoesNotMatch()
    {
        var devices = new[] { Device("id-1", "microphone") };

        var result = CaptureDeviceResolver.Resolve("id-gone", "Microphone", devices);

        result.Kind.Should().Be(CaptureDeviceResolutionKind.NotFound);
    }

    // ── Ambiguous ────────────────────────────────────────────────────────────

    [Fact(DisplayName = "Scenario \"Ambiguous name is never guessed\": configured ID absent, two available devices match the name")]
    public void Resolve_ConfiguredIdAbsent_TwoNameMatches_ReturnsAmbiguous()
    {
        var devices = new[] { Device("id-1", "Mic"), Device("id-2", "Mic") };

        var result = CaptureDeviceResolver.Resolve("id-gone", "Mic", devices);

        result.Kind.Should().Be(CaptureDeviceResolutionKind.Ambiguous);
        result.MatchCount.Should().Be(2);
    }

    [Fact(DisplayName = "FR-070: three or more matches are also Ambiguous, with the exact count")]
    public void Resolve_ThreeNameMatches_ReturnsAmbiguousWithExactCount()
    {
        var devices = new[] { Device("id-1", "Mic"), Device("id-2", "Mic"), Device("id-3", "Mic") };

        var result = CaptureDeviceResolver.Resolve(null, "Mic", devices);

        result.Kind.Should().Be(CaptureDeviceResolutionKind.Ambiguous);
        result.MatchCount.Should().Be(3);
    }

    [Fact(DisplayName = "FR-070: a disabled device sharing the name does not count toward Ambiguous")]
    public void Resolve_DisabledDeviceSharingName_DoesNotCountTowardAmbiguous()
    {
        var devices = new[] { Device("id-1", "Mic"), Device("id-2", "Mic", available: false) };

        var result = CaptureDeviceResolver.Resolve(null, "Mic", devices);

        result.Kind.Should().Be(CaptureDeviceResolutionKind.Adopt,
            "only the one available match counts — the disabled one is not a candidate at all");
        result.NewId.Should().Be("id-1");
    }
}
