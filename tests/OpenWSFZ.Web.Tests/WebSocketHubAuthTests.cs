using System.Net.WebSockets;
using System.Text;
using System.Text.Json;
using FluentAssertions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Web;
using Xunit;

namespace OpenWSFZ.Web.Tests;

/// <summary>
/// Unit tests for <see cref="WebSocketHub.AuthenticateViaFrameAsync"/> covering the
/// fragmented-frame reassembly fix (R5-SEC-F4).
/// <para>
/// Prior to the fix, the method called <c>ReceiveAsync</c> exactly once and deserialised
/// whatever bytes came back. A client that fragments the auth frame across two or more
/// WebSocket messages (<c>EndOfMessage = false</c> on the first) produced incomplete JSON,
/// which failed to deserialise and closed the connection with a misleading
/// "Authentication required" — a safe failure mode, but not the intended behaviour.
/// The fix loops <c>ReceiveAsync</c> until <c>EndOfMessage == true</c>, accumulating bytes
/// in a <see cref="MemoryStream"/> before parsing.
/// </para>
/// Uses a <see cref="FakeWebSocket"/> test double that replays a pre-configured sequence
/// of receive results, so fragmentation, oversized frames, and malformed JSON can be
/// exercised deterministically without a real socket or network round-trip.
/// </summary>
[Trait("Category", "Unit")]
public sealed class WebSocketHubAuthTests
{
    private static readonly IAuthPolicy AlwaysAuthorized = new NullAuthPolicy();

    // ── Fake WebSocket test double ────────────────────────────────────────────

    /// <summary>
    /// Minimal <see cref="WebSocket"/> test double that replays a queued sequence of
    /// frames from <see cref="ReceiveAsync"/> and records the arguments passed to
    /// <see cref="CloseAsync"/> for assertions.
    /// <para>
    /// Only <see cref="ReceiveAsync"/> and <see cref="CloseAsync"/> are implemented —
    /// the only two members <see cref="WebSocketHub.AuthenticateViaFrameAsync"/> calls.
    /// <see cref="State"/> also needs a real (non-throwing) value because
    /// <c>TryCloseAsync</c> inspects it before deciding whether to call
    /// <see cref="CloseAsync"/> — that is plumbing the method under test relies on, not
    /// behaviour under test. Every other abstract member throws
    /// <see cref="NotImplementedException"/> because it is never reached.
    /// </para>
    /// </summary>
    private sealed class FakeWebSocket : WebSocket
    {
        private readonly Queue<(byte[] Payload, WebSocketMessageType MessageType, bool EndOfMessage, int? CountOverride)> _frames;

        private WebSocketState _state = WebSocketState.Open;

        public WebSocketCloseStatus? ClosedWithStatus      { get; private set; }
        public string?               ClosedWithDescription { get; private set; }
        public bool                  CloseAsyncCalled       { get; private set; }

        public FakeWebSocket(
            params (byte[] Payload, WebSocketMessageType MessageType, bool EndOfMessage, int? CountOverride)[] frames)
            => _frames = new(frames);

        public override WebSocketCloseStatus? CloseStatus            => throw new NotImplementedException();
        public override string?               CloseStatusDescription => throw new NotImplementedException();
        public override WebSocketState        State                  => _state;
        public override string?               SubProtocol            => throw new NotImplementedException();

        public override void Abort() => throw new NotImplementedException();

        public override Task CloseAsync(
            WebSocketCloseStatus closeStatus, string? statusDescription, CancellationToken cancellationToken)
        {
            CloseAsyncCalled      = true;
            ClosedWithStatus      = closeStatus;
            ClosedWithDescription = statusDescription;
            _state                = WebSocketState.Closed;
            return Task.CompletedTask;
        }

        public override Task CloseOutputAsync(
            WebSocketCloseStatus closeStatus, string? statusDescription, CancellationToken cancellationToken)
            => throw new NotImplementedException();

        public override void Dispose() { /* no unmanaged resources to release */ }

        public override Task<WebSocketReceiveResult> ReceiveAsync(
            ArraySegment<byte> buffer, CancellationToken cancellationToken)
        {
            if (_frames.Count == 0)
            {
                throw new InvalidOperationException(
                    "FakeWebSocket: no more queued frames — test scenario under-specified.");
            }

            var (payload, messageType, endOfMessage, countOverride) = _frames.Dequeue();

            // Copy only as many bytes as physically fit. The oversized-frame test
            // deliberately reports a Count larger than the real payload — the SUT's
            // 4096-byte size guard must reject the frame before it is ever read back
            // out of the accumulation buffer.
            var toCopy = Math.Min(payload.Length, buffer.Count);
            Array.Copy(payload, 0, buffer.Array!, buffer.Offset, toCopy);

            var count = countOverride ?? payload.Length;
            return Task.FromResult(new WebSocketReceiveResult(count, messageType, endOfMessage));
        }

        public override Task SendAsync(
            ArraySegment<byte> buffer, WebSocketMessageType messageType, bool endOfMessage,
            CancellationToken cancellationToken)
            => throw new NotImplementedException();
    }

    // ── Non-regression: single, complete frame ────────────────────────────────

    [Fact(DisplayName = "R5-SEC-F4: single well-formed auth frame authenticates (non-regression)")]
    public async Task Auth_SingleFrame_ValidKey_ReturnsTrue()
    {
        var json = JsonSerializer.SerializeToUtf8Bytes(new { type = "auth", key = "secret" });
        var ws   = new FakeWebSocket((json, WebSocketMessageType.Text, true, null));

        var result = await WebSocketHub.AuthenticateViaFrameAsync(
            ws, new PassphraseAuthPolicy("secret"), CancellationToken.None);

        result.Should().BeTrue("a single, complete, well-formed auth frame must authenticate");
        ws.CloseAsyncCalled.Should().BeFalse("a successful authentication must not close the socket");
    }

    // ── R5-SEC-F4: fragmented frame reassembly ────────────────────────────────

    [Fact(DisplayName = "R5-SEC-F4: fragmented auth frame (two continuation frames) reassembles and authenticates")]
    public async Task Auth_Fragmented_TwoFrames_ValidKey_ReturnsTrue()
    {
        var full    = JsonSerializer.SerializeToUtf8Bytes(new { type = "auth", key = "secret" });
        var splitAt = full.Length / 2;
        var first   = full[..splitAt];
        var second  = full[splitAt..];

        // .NET's WebSocketMessageType enum has no distinct "continuation" value — the real
        // ManagedWebSocket reports the same Text/Binary type on every fragment of a message,
        // not just the first. The SUT only inspects MessageType on the first fragment anyway
        // (firstFragment guard), so this mirrors actual runtime behaviour.
        var ws = new FakeWebSocket(
            (first,  WebSocketMessageType.Text, false, null),
            (second, WebSocketMessageType.Text, true,  null));

        var result = await WebSocketHub.AuthenticateViaFrameAsync(
            ws, new PassphraseAuthPolicy("secret"), CancellationToken.None);

        result.Should().BeTrue(
            "a fragmented auth frame must be reassembled across ReceiveAsync calls before parsing (R5-SEC-F4)");
        ws.CloseAsyncCalled.Should().BeFalse("a successful authentication must not close the socket");
    }

    [Fact(DisplayName = "R5-SEC-F4: fragmented auth frame with wrong key is rejected with close code 4001")]
    public async Task Auth_Fragmented_TwoFrames_WrongKey_ReturnsFalse()
    {
        var full    = JsonSerializer.SerializeToUtf8Bytes(new { type = "auth", key = "wrong-key" });
        var splitAt = full.Length / 2;
        var first   = full[..splitAt];
        var second  = full[splitAt..];

        var ws = new FakeWebSocket(
            (first,  WebSocketMessageType.Text, false, null),
            (second, WebSocketMessageType.Text, true,  null));

        var result = await WebSocketHub.AuthenticateViaFrameAsync(
            ws, new PassphraseAuthPolicy("secret"), CancellationToken.None);

        result.Should().BeFalse("the reassembled key must still be validated against the auth policy");
        ws.CloseAsyncCalled.Should().BeTrue("an authentication failure must close the socket");
        ((int)ws.ClosedWithStatus!.Value).Should().Be(4001);
    }

    // ── Guard rails preserved by the rewrite ──────────────────────────────────

    [Fact(DisplayName = "R5-SEC-F4: oversized single frame is rejected before parsing")]
    public async Task Auth_SingleFrame_OversizedFrame_ReturnsFalse()
    {
        // The physical payload is tiny; CountOverride simulates a frame whose reported
        // size exceeds the 4096-byte guard, which must reject it before ever touching
        // the accumulated buffer contents.
        var dummy = new byte[10];
        var ws    = new FakeWebSocket((dummy, WebSocketMessageType.Text, true, 5000));

        var result = await WebSocketHub.AuthenticateViaFrameAsync(
            ws, AlwaysAuthorized, CancellationToken.None);

        result.Should().BeFalse("a frame larger than the 4096-byte guard must be rejected");
        ws.CloseAsyncCalled.Should().BeTrue();
        ((int)ws.ClosedWithStatus!.Value).Should().Be(4001);
    }

    [Fact(DisplayName = "R5-SEC-F4: malformed JSON in a complete frame is rejected")]
    public async Task Auth_SingleFrame_InvalidJson_ReturnsFalse()
    {
        var malformed = Encoding.UTF8.GetBytes("{not valid json");
        var ws        = new FakeWebSocket((malformed, WebSocketMessageType.Text, true, null));

        var result = await WebSocketHub.AuthenticateViaFrameAsync(
            ws, AlwaysAuthorized, CancellationToken.None);

        result.Should().BeFalse("malformed JSON must not authenticate, even from a policy that authorises everything");
        ws.CloseAsyncCalled.Should().BeTrue();
        ((int)ws.ClosedWithStatus!.Value).Should().Be(4001);
    }

    [Fact(DisplayName = "R5-SEC-F4: a binary first frame is rejected without attempting to parse it")]
    public async Task Auth_BinaryFrame_ReturnsFalse()
    {
        var payload = new byte[] { 0x01, 0x02, 0x03 };
        var ws      = new FakeWebSocket((payload, WebSocketMessageType.Binary, true, null));

        var result = await WebSocketHub.AuthenticateViaFrameAsync(
            ws, AlwaysAuthorized, CancellationToken.None);

        result.Should().BeFalse("the first fragment of the auth frame must be a Text message");
        ws.CloseAsyncCalled.Should().BeTrue();
        ((int)ws.ClosedWithStatus!.Value).Should().Be(4001);
    }
}
