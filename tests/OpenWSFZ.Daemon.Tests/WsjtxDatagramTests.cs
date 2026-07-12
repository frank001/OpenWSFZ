using System.Buffers.Binary;
using System.Text;
using FluentAssertions;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// Unit tests for <see cref="WsjtxDatagram"/> (gridtracker-udp-reporting, task 2.5).
/// Covers byte-exact encode assertions for every outbound type, decode round-trips for every
/// inbound type, and the malformed-input resilience guarantee (never throws).
/// </summary>
[Trait("Category", "Unit")]
public sealed class WsjtxDatagramTests
{
    // ── Helpers ──────────────────────────────────────────────────────────────

    private static uint ReadU32BE(byte[] data, int offset) =>
        BinaryPrimitives.ReadUInt32BigEndian(data.AsSpan(offset, 4));

    /// <summary>Encodes a WSJT-X-protocol string field (len-prefixed UTF-8) for hand-built expected buffers.</summary>
    private static byte[] Utf8Field(string s)
    {
        var bytes = Encoding.UTF8.GetBytes(s);
        var buf   = new byte[4 + bytes.Length];
        BinaryPrimitives.WriteUInt32BigEndian(buf, (uint)bytes.Length);
        bytes.CopyTo(buf, 4);
        return buf;
    }

    // ── Header framing (all message types) ──────────────────────────────────

    [Fact(DisplayName = "Every encoded datagram starts with magic + schema + type + id")]
    public void Encode_AllTypes_StartWithCorrectHeader()
    {
        var datagram = WsjtxDatagram.EncodeHeartbeat("OpenWSFZ", 3, "1.0.0", "abc123");

        ReadU32BE(datagram, 0).Should().Be(WsjtxDatagram.Magic);
        ReadU32BE(datagram, 4).Should().Be(WsjtxDatagram.SchemaVersion);
        ReadU32BE(datagram, 8).Should().Be((uint)WsjtxDatagram.MessageType.Heartbeat);
    }

    // ── Byte-exact encode: Heartbeat ────────────────────────────────────────

    [Fact(DisplayName = "EncodeHeartbeat produces the exact expected byte sequence")]
    public void EncodeHeartbeat_ProducesExactBytes()
    {
        var actual = WsjtxDatagram.EncodeHeartbeat("OpenWSFZ", 3, "1.2.3", "rev1");

        var expected = new List<byte>();
        expected.AddRange(BitConverter.GetBytes(WsjtxDatagram.Magic).Reverse());
        expected.AddRange(BitConverter.GetBytes(WsjtxDatagram.SchemaVersion).Reverse());
        expected.AddRange(BitConverter.GetBytes((uint)WsjtxDatagram.MessageType.Heartbeat).Reverse());
        expected.AddRange(Utf8Field("OpenWSFZ"));
        expected.AddRange(BitConverter.GetBytes(3).Reverse());
        expected.AddRange(Utf8Field("1.2.3"));
        expected.AddRange(Utf8Field("rev1"));

        actual.Should().Equal(expected);
    }

    // ── Byte-exact encode: Clear / Close (header only) ──────────────────────

    [Fact(DisplayName = "EncodeClear produces header-only bytes with the Clear type")]
    public void EncodeClear_ProducesHeaderOnlyBytes()
    {
        var actual = WsjtxDatagram.EncodeClear("OpenWSFZ");

        var expected = new List<byte>();
        expected.AddRange(BitConverter.GetBytes(WsjtxDatagram.Magic).Reverse());
        expected.AddRange(BitConverter.GetBytes(WsjtxDatagram.SchemaVersion).Reverse());
        expected.AddRange(BitConverter.GetBytes((uint)WsjtxDatagram.MessageType.Clear).Reverse());
        expected.AddRange(Utf8Field("OpenWSFZ"));

        actual.Should().Equal(expected);
    }

    [Fact(DisplayName = "EncodeClose produces header-only bytes with the Close type")]
    public void EncodeClose_ProducesHeaderOnlyBytes()
    {
        var actual = WsjtxDatagram.EncodeClose("OpenWSFZ");
        actual.Length.Should().Be(12 + Utf8Field("OpenWSFZ").Length);
        ReadU32BE(actual, 8).Should().Be((uint)WsjtxDatagram.MessageType.Close);
    }

    // ── Encode: Status / Decode / QSOLogged — field-presence sanity ─────────

    [Fact(DisplayName = "EncodeStatus embeds the operator/DX callsigns as UTF-8 substrings")]
    public void EncodeStatus_ContainsExpectedStrings()
    {
        var fields = new WsjtxDatagram.StatusFields(
            DialFrequencyHz: 14_074_000,
            Mode:            "FT8",
            DxCall:          "Q1TST",
            Report:          "+05",
            TxMode:          "FT8",
            TxEnabled:       true,
            Transmitting:    false,
            Decoding:        true,
            RxDeltaFreqHz:   900,
            TxDeltaFreqHz:   1500,
            MyCall:          "Q1OFZ",
            MyGrid:          "JO33",
            DxGrid:          "JO22");

        var datagram = WsjtxDatagram.EncodeStatus("OpenWSFZ", fields);
        var text     = Encoding.UTF8.GetString(datagram);

        text.Should().Contain("Q1TST").And.Contain("Q1OFZ").And.Contain("JO33").And.Contain("JO22");
        ReadU32BE(datagram, 8).Should().Be((uint)WsjtxDatagram.MessageType.Status);
    }

    [Fact(DisplayName = "EncodeDecode embeds the decoded message text")]
    public void EncodeDecode_ContainsMessageText()
    {
        var fields = new WsjtxDatagram.DecodeFields(
            New:                    true,
            TimeMsSinceMidnightUtc: 12345,
            SnrDb:                  -10,
            DeltaTimeSeconds:       0.2,
            DeltaFrequencyHz:       1500,
            Mode:                   "~",
            Message:                "CQ Q1TST JO22",
            LowConfidence:          false);

        var datagram = WsjtxDatagram.EncodeDecode("OpenWSFZ", fields);
        Encoding.UTF8.GetString(datagram).Should().Contain("CQ Q1TST JO22");
        ReadU32BE(datagram, 8).Should().Be((uint)WsjtxDatagram.MessageType.Decode);
    }

    [Fact(DisplayName = "EncodeQsoLogged embeds partner callsign and grid")]
    public void EncodeQsoLogged_ContainsPartnerFields()
    {
        var fields = new WsjtxDatagram.QsoLoggedFields(
            QsoStartUtc:    new DateTimeOffset(2026, 7, 12, 14, 29, 15, TimeSpan.Zero),
            QsoEndUtc:      new DateTimeOffset(2026, 7, 12, 14, 30, 0, TimeSpan.Zero),
            DxCall:         "Q1TST",
            DxGrid:         "JO22",
            TxFrequencyHz:  14_074_000,
            Mode:           "FT8",
            ReportSent:     "+05",
            ReportReceived: "-03",
            MyCall:         "Q1OFZ",
            MyGrid:         "JO33");

        var datagram = WsjtxDatagram.EncodeQsoLogged("OpenWSFZ", fields);
        Encoding.UTF8.GetString(datagram).Should().Contain("Q1TST").And.Contain("Q1OFZ");
        ReadU32BE(datagram, 8).Should().Be((uint)WsjtxDatagram.MessageType.QsoLogged);
    }

    // ── Decode: Heartbeat ────────────────────────────────────────────────────

    [Fact(DisplayName = "TryDecode parses a Heartbeat datagram encoded by EncodeHeartbeat")]
    public void TryDecode_Heartbeat_RoundTrips()
    {
        var datagram = WsjtxDatagram.EncodeHeartbeat("GridTracker2", 3, "2.1.0", "revX");

        var ok = WsjtxDatagram.TryDecode(datagram, out var message);

        ok.Should().BeTrue();
        message.Should().BeOfType<WsjtxDatagram.InboundMessage.HeartbeatMessage>();
        var hb = (WsjtxDatagram.InboundMessage.HeartbeatMessage)message!;
        hb.MaxSchemaNumber.Should().Be(3);
        hb.Version.Should().Be("2.1.0");
        hb.Revision.Should().Be("revX");
    }

    // ── Decode: Reply (mirrors Decode's field layout) ───────────────────────

    [Fact(DisplayName = "TryDecode parses a Reply datagram and extracts the message text")]
    public void TryDecode_Reply_ExtractsMessage()
    {
        // Hand-build a Reply datagram: header + New(bool) + Time(u32) + SNR(i32) +
        // DeltaTime(double) + DeltaFrequency(u32) + Mode(str) + Message(str) + LowConfidence(bool).
        var buf = new List<byte>();
        void U32(uint v) { Span<byte> b = stackalloc byte[4]; BinaryPrimitives.WriteUInt32BigEndian(b, v); buf.AddRange(b.ToArray()); }
        void I32(int v)  => U32(unchecked((uint)v));
        void Str(string s) { var bytes = Encoding.UTF8.GetBytes(s); U32((uint)bytes.Length); buf.AddRange(bytes); }
        void Dbl(double v) { Span<byte> b = stackalloc byte[8]; BinaryPrimitives.WriteInt64BigEndian(b, BitConverter.DoubleToInt64Bits(v)); buf.AddRange(b.ToArray()); }

        U32(WsjtxDatagram.Magic);
        U32(WsjtxDatagram.SchemaVersion);
        U32((uint)WsjtxDatagram.MessageType.Reply);
        Str("GridTracker2");
        buf.Add(1);              // New = true
        U32(51300);              // Time
        I32(-10);                // SNR
        Dbl(0.1);                // DeltaTime
        U32(1500);               // DeltaFrequency
        Str("~");                // Mode
        Str("CQ Q1TST JO22");    // Message
        buf.Add(0);               // LowConfidence = false

        var ok = WsjtxDatagram.TryDecode(buf.ToArray(), out var message);

        ok.Should().BeTrue();
        var reply = message.Should().BeOfType<WsjtxDatagram.InboundMessage.ReplyMessage>().Subject;
        reply.Message.Should().Be("CQ Q1TST JO22");
        reply.DeltaFrequencyHz.Should().Be(1500);
    }

    // ── Decode: Halt Tx ──────────────────────────────────────────────────────

    [Fact(DisplayName = "TryDecode parses a Halt Tx datagram")]
    public void TryDecode_HaltTx_Parses()
    {
        var buf = new List<byte>();
        void U32(uint v) { Span<byte> b = stackalloc byte[4]; BinaryPrimitives.WriteUInt32BigEndian(b, v); buf.AddRange(b.ToArray()); }
        void Str(string s) { var bytes = Encoding.UTF8.GetBytes(s); U32((uint)bytes.Length); buf.AddRange(bytes); }

        U32(WsjtxDatagram.Magic);
        U32(WsjtxDatagram.SchemaVersion);
        U32((uint)WsjtxDatagram.MessageType.HaltTx);
        Str("GridTracker2");
        buf.Add(1); // AutoTxOnly = true

        var ok = WsjtxDatagram.TryDecode(buf.ToArray(), out var message);

        ok.Should().BeTrue();
        message.Should().BeOfType<WsjtxDatagram.InboundMessage.HaltTxMessage>();
    }

    // ── Decode: Free Text ────────────────────────────────────────────────────

    [Fact(DisplayName = "TryDecode parses a Free Text datagram and extracts the text")]
    public void TryDecode_FreeText_ExtractsText()
    {
        var buf = new List<byte>();
        void U32(uint v) { Span<byte> b = stackalloc byte[4]; BinaryPrimitives.WriteUInt32BigEndian(b, v); buf.AddRange(b.ToArray()); }
        void Str(string s) { var bytes = Encoding.UTF8.GetBytes(s); U32((uint)bytes.Length); buf.AddRange(bytes); }

        U32(WsjtxDatagram.Magic);
        U32(WsjtxDatagram.SchemaVersion);
        U32((uint)WsjtxDatagram.MessageType.FreeText);
        Str("GridTracker2");
        Str("TEST MSG");
        buf.Add(1); // Send = true

        var ok = WsjtxDatagram.TryDecode(buf.ToArray(), out var message);

        ok.Should().BeTrue();
        var ft = message.Should().BeOfType<WsjtxDatagram.InboundMessage.FreeTextMessage>().Subject;
        ft.Text.Should().Be("TEST MSG");
    }

    // ── Decode: Close ────────────────────────────────────────────────────────

    [Fact(DisplayName = "TryDecode parses a Close datagram")]
    public void TryDecode_Close_Parses()
    {
        var datagram = WsjtxDatagram.EncodeClose("GridTracker2");

        var ok = WsjtxDatagram.TryDecode(datagram, out var message);

        ok.Should().BeTrue();
        message.Should().BeOfType<WsjtxDatagram.InboundMessage.CloseMessage>();
    }

    // ── Decode: unrecognised-but-well-formed types are accepted, not acted on ─

    [Theory(DisplayName = "TryDecode accepts well-formed unsupported types without error")]
    [InlineData((uint)WsjtxDatagram.MessageType.Replay)]
    [InlineData((uint)WsjtxDatagram.MessageType.Location)]
    [InlineData((uint)WsjtxDatagram.MessageType.HighlightCallsignInList)]
    [InlineData((uint)WsjtxDatagram.MessageType.SwitchConfiguration)]
    [InlineData((uint)WsjtxDatagram.MessageType.Configure)]
    [InlineData((uint)WsjtxDatagram.MessageType.WsprDecode)]
    public void TryDecode_UnsupportedTypes_ReturnsUnsupportedMessage(uint typeRaw)
    {
        var type = (WsjtxDatagram.MessageType)typeRaw;
        var buf = new List<byte>();
        void U32(uint v) { Span<byte> b = stackalloc byte[4]; BinaryPrimitives.WriteUInt32BigEndian(b, v); buf.AddRange(b.ToArray()); }
        void Str(string s) { var bytes = Encoding.UTF8.GetBytes(s); U32((uint)bytes.Length); buf.AddRange(bytes); }

        U32(WsjtxDatagram.Magic);
        U32(WsjtxDatagram.SchemaVersion);
        U32((uint)type);
        Str("WSJT-X");

        var ok = WsjtxDatagram.TryDecode(buf.ToArray(), out var message);

        ok.Should().BeTrue("a well-formed but unimplemented type must not be treated as malformed");
        var unsupported = message.Should().BeOfType<WsjtxDatagram.InboundMessage.UnsupportedMessage>().Subject;
        unsupported.Type.Should().Be(type);
    }

    // ── Malformed-input resilience ───────────────────────────────────────────

    [Fact(DisplayName = "TryDecode discards a 3-byte garbage datagram without throwing")]
    public void TryDecode_TruncatedGarbage_ReturnsFalse()
    {
        var garbage = new byte[] { 0x01, 0x02, 0x03 };

        var act = () => WsjtxDatagram.TryDecode(garbage, out _);
        act.Should().NotThrow();

        WsjtxDatagram.TryDecode(garbage, out var message).Should().BeFalse();
        message.Should().BeNull();
    }

    [Fact(DisplayName = "TryDecode rejects a datagram with a bad magic number")]
    public void TryDecode_BadMagic_ReturnsFalse()
    {
        var buf = new byte[16];
        BinaryPrimitives.WriteUInt32BigEndian(buf.AsSpan(0), 0xdeadbeef);
        BinaryPrimitives.WriteUInt32BigEndian(buf.AsSpan(4), WsjtxDatagram.SchemaVersion);
        BinaryPrimitives.WriteUInt32BigEndian(buf.AsSpan(8), (uint)WsjtxDatagram.MessageType.Heartbeat);

        WsjtxDatagram.TryDecode(buf, out var message).Should().BeFalse();
        message.Should().BeNull();
    }

    [Fact(DisplayName = "TryDecode rejects an unsupported schema version")]
    public void TryDecode_UnsupportedSchema_ReturnsFalse()
    {
        var buf = new byte[16];
        BinaryPrimitives.WriteUInt32BigEndian(buf.AsSpan(0), WsjtxDatagram.Magic);
        BinaryPrimitives.WriteUInt32BigEndian(buf.AsSpan(4), 99);
        BinaryPrimitives.WriteUInt32BigEndian(buf.AsSpan(8), (uint)WsjtxDatagram.MessageType.Heartbeat);

        WsjtxDatagram.TryDecode(buf, out var message).Should().BeFalse();
        message.Should().BeNull();
    }

    [Fact(DisplayName = "TryDecode rejects a datagram truncated mid-string-length field")]
    public void TryDecode_TruncatedStringLength_ReturnsFalse()
    {
        // Valid header, then a string-length field claiming a huge length with no data following.
        var buf = new List<byte>();
        void U32(uint v) { Span<byte> b = stackalloc byte[4]; BinaryPrimitives.WriteUInt32BigEndian(b, v); buf.AddRange(b.ToArray()); }
        U32(WsjtxDatagram.Magic);
        U32(WsjtxDatagram.SchemaVersion);
        U32((uint)WsjtxDatagram.MessageType.Heartbeat);
        U32(999_999); // claimed Id string length far exceeding the remaining buffer

        var act = () => WsjtxDatagram.TryDecode(buf.ToArray(), out _);
        act.Should().NotThrow();
        WsjtxDatagram.TryDecode(buf.ToArray(), out var message).Should().BeFalse();
        message.Should().BeNull();
    }

    [Fact(DisplayName = "TryDecode handles a zero-length buffer without throwing")]
    public void TryDecode_EmptyBuffer_ReturnsFalse()
    {
        var act = () => WsjtxDatagram.TryDecode(ReadOnlySpan<byte>.Empty, out _);
        act.Should().NotThrow();
        WsjtxDatagram.TryDecode(ReadOnlySpan<byte>.Empty, out var message).Should().BeFalse();
        message.Should().BeNull();
    }

    [Theory(DisplayName = "TryDecode survives a range of fuzzed random buffers without throwing")]
    [InlineData(0)]
    [InlineData(1)]
    [InlineData(2)]
    [InlineData(4)]
    [InlineData(8)]
    [InlineData(16)]
    [InlineData(32)]
    [InlineData(64)]
    public void TryDecode_FuzzedRandomBuffers_NeverThrows(int length)
    {
        var rnd = new Random(12345 + length);
        for (var i = 0; i < 50; i++)
        {
            var buf = new byte[length];
            rnd.NextBytes(buf);

            var act = () => WsjtxDatagram.TryDecode(buf, out _);
            act.Should().NotThrow();
        }
    }
}
