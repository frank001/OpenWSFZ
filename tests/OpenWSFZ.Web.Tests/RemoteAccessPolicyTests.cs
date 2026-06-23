using System.Net;
using FluentAssertions;
using Microsoft.Extensions.Logging.Abstractions;
using OpenWSFZ.Web;
using Xunit;

namespace OpenWSFZ.Web.Tests;

/// <summary>
/// Unit tests for <see cref="LanBindPolicy"/> and <see cref="PassphraseAuthPolicy"/>.
/// Tasks 7.1 – 7.4 (lan-remote-access).
/// </summary>
[Trait("Category", "Unit")]
public sealed class RemoteAccessPolicyTests
{
    // ── 7.1 — LanBindPolicy ──────────────────────────────────────────────────

    [Fact(DisplayName = "7.1a: LanBindPolicy.Resolve(Loopback, 8080) returns 0.0.0.0:8080")]
    public void LanBindPolicy_Resolve_Loopback_ReturnsAnyPort8080()
    {
        var policy = new LanBindPolicy(NullLogger<LanBindPolicy>.Instance);

        var ep = policy.Resolve(IPAddress.Loopback, 8080);

        ep.Address.Should().Be(IPAddress.Any, "LanBindPolicy must always bind to 0.0.0.0");
        ep.Port.Should().Be(8080);
    }

    [Fact(DisplayName = "7.1b: LanBindPolicy.Resolve(Any, 9000) returns 0.0.0.0:9000")]
    public void LanBindPolicy_Resolve_Any_ReturnsAnyPort9000()
    {
        var policy = new LanBindPolicy(NullLogger<LanBindPolicy>.Instance);

        var ep = policy.Resolve(IPAddress.Any, 9000);

        ep.Address.Should().Be(IPAddress.Any, "LanBindPolicy must always bind to 0.0.0.0");
        ep.Port.Should().Be(9000);
    }

    // ── 7.2 — PassphraseAuthPolicy: non-loopback, passphrase = "secret" ──────

    private static readonly IPAddress NonLoopback = IPAddress.Parse("192.168.1.100");

    [Fact(DisplayName = "7.2a: IsAuthorized(nonLoopback, \"secret\", null) → true (correct X-Api-Key)")]
    public void PassphraseAuth_CorrectHeader_Authorized()
    {
        var policy = new PassphraseAuthPolicy("secret");

        policy.IsAuthorized(NonLoopback, "secret", null).Should().BeTrue(
            "correct X-Api-Key header must be authorized");
    }

    [Fact(DisplayName = "7.2b: IsAuthorized(nonLoopback, \"wrong\", null) → false (wrong X-Api-Key)")]
    public void PassphraseAuth_WrongHeader_Unauthorized()
    {
        var policy = new PassphraseAuthPolicy("secret");

        policy.IsAuthorized(NonLoopback, "wrong", null).Should().BeFalse(
            "wrong X-Api-Key header must be rejected");
    }

    [Fact(DisplayName = "7.2c: IsAuthorized(nonLoopback, null, \"secret\") → true (correct ?key= param)")]
    public void PassphraseAuth_CorrectQueryParam_Authorized()
    {
        var policy = new PassphraseAuthPolicy("secret");

        policy.IsAuthorized(NonLoopback, null, "secret").Should().BeTrue(
            "correct ?key= query param (WebSocket path) must be authorized");
    }

    [Fact(DisplayName = "7.2d: IsAuthorized(nonLoopback, null, \"wrong\") → false (wrong ?key=)")]
    public void PassphraseAuth_WrongQueryParam_Unauthorized()
    {
        var policy = new PassphraseAuthPolicy("secret");

        policy.IsAuthorized(NonLoopback, null, "wrong").Should().BeFalse(
            "wrong ?key= query param must be rejected");
    }

    [Fact(DisplayName = "7.2e: IsAuthorized(nonLoopback, null, null) → false (no credentials)")]
    public void PassphraseAuth_NoCredentials_Unauthorized()
    {
        var policy = new PassphraseAuthPolicy("secret");

        policy.IsAuthorized(NonLoopback, null, null).Should().BeFalse(
            "request with no credentials from non-loopback must be rejected");
    }

    // ── 7.3 — PassphraseAuthPolicy: loopback bypass ──────────────────────────

    [Fact(DisplayName = "7.3a: IsAuthorized(127.0.0.1, null, null) → true (loopback bypass)")]
    public void PassphraseAuth_Loopback_AlwaysAuthorized()
    {
        var policy = new PassphraseAuthPolicy("secret");

        policy.IsAuthorized(IPAddress.Loopback, null, null).Should().BeTrue(
            "loopback origin must always be trusted regardless of credentials (D1)");
    }

    [Fact(DisplayName = "7.3b: IsAuthorized(::1, null, null) → true (IPv6 loopback bypass)")]
    public void PassphraseAuth_IPv6Loopback_AlwaysAuthorized()
    {
        var policy = new PassphraseAuthPolicy("secret");

        policy.IsAuthorized(IPAddress.IPv6Loopback, null, null).Should().BeTrue(
            "IPv6 loopback (::1) must also be trusted regardless of credentials (D1)");
    }

    // ── 7.4 — PassphraseAuthPolicy: null/empty passphrase ────────────────────

    [Fact(DisplayName = "7.4a: PassphraseAuthPolicy(null) returns true for any origin")]
    public void PassphraseAuth_NullPassphrase_AlwaysAuthorized()
    {
        var policy = new PassphraseAuthPolicy(null);

        policy.IsAuthorized(NonLoopback, null,     null).Should().BeTrue(
            "null passphrase config means open LAN access — always authorized");
        policy.IsAuthorized(NonLoopback, "wrong",  null).Should().BeTrue(
            "null passphrase config means any header value is irrelevant");
    }

    [Fact(DisplayName = "7.4b: PassphraseAuthPolicy(\"\") returns true for any origin")]
    public void PassphraseAuth_EmptyPassphrase_AlwaysAuthorized()
    {
        var policy = new PassphraseAuthPolicy("");

        policy.IsAuthorized(NonLoopback, null,    null).Should().BeTrue(
            "empty passphrase config means open LAN access — always authorized");
        policy.IsAuthorized(NonLoopback, "wrong", null).Should().BeTrue(
            "empty passphrase config means any header value is irrelevant");
    }
}
