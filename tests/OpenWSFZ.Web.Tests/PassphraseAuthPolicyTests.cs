using System.Net;
using FluentAssertions;
using OpenWSFZ.Web;
using Xunit;

namespace OpenWSFZ.Web.Tests;

/// <summary>
/// Unit tests for <see cref="PassphraseAuthPolicy"/> covering SEC-002A
/// (constant-time comparison) and the loopback bypass.
/// </summary>
[Trait("Category", "Unit")]
public sealed class PassphraseAuthPolicyTests
{
    private static readonly IPAddress LanIp      = IPAddress.Parse("192.168.1.42");
    private static readonly IPAddress LoopbackIp = IPAddress.Loopback;

    // ── SEC-002A: Constant-time comparison ────────────────────────────────────

    [Fact(DisplayName = "SEC-002: Correct X-Api-Key from LAN IP is authorised")]
    public void IsAuthorized_CorrectHeaderFromLan_ReturnsTrue()
    {
        var policy = new PassphraseAuthPolicy("supersecret");

        policy.IsAuthorized(LanIp, apiKeyHeader: "supersecret", keyQueryParam: null)
              .Should().BeTrue("correct X-Api-Key must be accepted from a LAN origin");
    }

    [Fact(DisplayName = "SEC-002: Wrong X-Api-Key from LAN IP is rejected")]
    public void IsAuthorized_WrongHeaderFromLan_ReturnsFalse()
    {
        var policy = new PassphraseAuthPolicy("supersecret");

        policy.IsAuthorized(LanIp, apiKeyHeader: "wrongkey", keyQueryParam: null)
              .Should().BeFalse("wrong X-Api-Key must be rejected from a LAN origin");
    }

    [Fact(DisplayName = "SEC-002: Empty X-Api-Key from LAN IP is rejected")]
    public void IsAuthorized_EmptyHeaderFromLan_ReturnsFalse()
    {
        var policy = new PassphraseAuthPolicy("supersecret");

        policy.IsAuthorized(LanIp, apiKeyHeader: null, keyQueryParam: null)
              .Should().BeFalse("missing X-Api-Key must be rejected from a LAN origin");
    }

    [Fact(DisplayName = "SEC-002: Key with same prefix but extra chars is rejected (length check)")]
    public void IsAuthorized_PrefixOfCorrectKey_ReturnsFalse()
    {
        // Timing attack: a prefix of the correct passphrase must not be accepted.
        // FixedTimeEquals returns false when byte lengths differ (before the constant-time
        // comparison) — this test confirms that the length check is enforced.
        var policy = new PassphraseAuthPolicy("supersecret");

        policy.IsAuthorized(LanIp, apiKeyHeader: "super", keyQueryParam: null)
              .Should().BeFalse("a prefix of the configured passphrase must not be accepted");
    }

    [Fact(DisplayName = "SEC-002: Key that is a superset of the passphrase is rejected")]
    public void IsAuthorized_SupersetOfCorrectKey_ReturnsFalse()
    {
        var policy = new PassphraseAuthPolicy("supersecret");

        policy.IsAuthorized(LanIp, apiKeyHeader: "supersecret!", keyQueryParam: null)
              .Should().BeFalse("a key longer than the configured passphrase must not be accepted");
    }

    [Fact(DisplayName = "SEC-002: Correct ?key= query param from LAN IP is authorised (backward compat)")]
    public void IsAuthorized_CorrectQueryParamFromLan_ReturnsTrue()
    {
        var policy = new PassphraseAuthPolicy("supersecret");

        policy.IsAuthorized(LanIp, apiKeyHeader: null, keyQueryParam: "supersecret")
              .Should().BeTrue("correct ?key= is still accepted for non-browser clients");
    }

    // ── Loopback bypass (unchanged from original spec) ────────────────────────

    [Fact(DisplayName = "SEC-002: Loopback origin is always authorised regardless of key")]
    public void IsAuthorized_AnyKeyFromLoopback_ReturnsTrue()
    {
        var policy = new PassphraseAuthPolicy("supersecret");

        policy.IsAuthorized(LoopbackIp, apiKeyHeader: null, keyQueryParam: null)
              .Should().BeTrue("loopback origin must bypass passphrase check (D1)");
    }

    [Fact(DisplayName = "SEC-002: Loopback with wrong key is still authorised")]
    public void IsAuthorized_WrongKeyFromLoopback_ReturnsTrue()
    {
        var policy = new PassphraseAuthPolicy("supersecret");

        policy.IsAuthorized(LoopbackIp, apiKeyHeader: "wrongkey", keyQueryParam: null)
              .Should().BeTrue("loopback bypass must not depend on the key value");
    }

    // ── Null remoteIp (used by WS auth-frame path — SEC-002B) ─────────────────

    [Fact(DisplayName = "SEC-002: Correct header with null remoteIp is authorised (WS auth-frame path)")]
    public void IsAuthorized_CorrectHeaderNullIp_ReturnsTrue()
    {
        // WebSocketHub.AuthenticateViaFrameAsync calls IsAuthorized with remoteIp = null
        // to bypass the loopback check (it has already been confirmed non-loopback by
        // the call site). The header carries the key extracted from the WS auth frame.
        var policy = new PassphraseAuthPolicy("supersecret");

        policy.IsAuthorized(remoteIp: null, apiKeyHeader: "supersecret", keyQueryParam: null)
              .Should().BeTrue("null remoteIp with correct header must be authorised");
    }

    [Fact(DisplayName = "SEC-002: Wrong header with null remoteIp is rejected (WS auth-frame path)")]
    public void IsAuthorized_WrongHeaderNullIp_ReturnsFalse()
    {
        var policy = new PassphraseAuthPolicy("supersecret");

        policy.IsAuthorized(remoteIp: null, apiKeyHeader: "wrongkey", keyQueryParam: null)
              .Should().BeFalse("null remoteIp with wrong header must be rejected");
    }
}
