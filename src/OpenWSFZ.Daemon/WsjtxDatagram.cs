using System.Buffers.Binary;
using System.Text;

namespace OpenWSFZ.Daemon;

/// <summary>
/// Byte-compatible (de)serialisation of the WSJT-X UDP network protocol
/// (<c>NetworkMessage.hpp</c> in the WSJT-X source: a <c>quint32</c> magic number + schema
/// version header, big-endian primitives, length-prefixed UTF-8 strings) for the message subset
/// this daemon implements (<c>external-reporting</c> capability, gridtracker-udp-reporting
/// change). Operates purely on primitive fields passed in and out — no dependency on any other
/// OpenWSFZ type (design.md Decision 5); all OpenWSFZ-specific field mapping lives one layer up,
/// in <see cref="ExternalReportingService"/>.
///
/// <para>
/// <strong>Provenance note:</strong> this is a third-party wire format with no negotiation and
/// no OpenWSFZ-side flexibility. The header framing, <c>Heartbeat</c>, <c>Clear</c>, and
/// <c>Close</c> layouts are simple and well established. The richer message types
/// (<c>Status</c>, <c>Decode</c>, <c>QSOLogged</c>, <c>Reply</c>, <c>Halt Tx</c>,
/// <c>Free Text</c>) are implemented from the publicly documented protocol shape without a live
/// WSJT-X/GridTracker2 wire capture to verify against byte-for-byte (task 2.6 is optional and
/// was not available in this environment) — treat those layouts as best-effort until confirmed
/// against a real capture or a live GridTracker2 session.
/// </para>
/// </summary>
internal static class WsjtxDatagram
{
    /// <summary>WSJT-X protocol magic number (<c>NetworkMessage::Magic</c>).</summary>
    public const uint Magic = 0xadbccbda;

    /// <summary>Schema version this implementation encodes and accepts on decode.</summary>
    public const uint SchemaVersion = 2;

    /// <summary>WSJT-X protocol message type discriminator (<c>NetworkMessage::MessageType</c>).</summary>
    public enum MessageType : uint
    {
        Heartbeat               = 0,
        Status                  = 1,
        Decode                  = 2,
        Clear                   = 3,
        Reply                   = 4,
        QsoLogged               = 5,
        Close                   = 6,
        Replay                  = 7,
        HaltTx                  = 8,
        FreeText                = 9,
        WsprDecode              = 10,
        Location                = 11,
        LoggedAdif              = 12,
        HighlightCallsignInList = 13,
        SwitchConfiguration     = 14,
        Configure               = 15,
    }

    // ── Outbound field payloads ─────────────────────────────────────────────────

    /// <summary>Fields for an outbound Status datagram (<c>Requirement: Outbound Status message</c>).</summary>
    public readonly record struct StatusFields(
        ulong  DialFrequencyHz,
        string Mode,
        string DxCall,
        string Report,
        string TxMode,
        bool   TxEnabled,
        bool   Transmitting,
        bool   Decoding,
        uint   RxDeltaFreqHz,
        uint   TxDeltaFreqHz,
        string MyCall,
        string MyGrid,
        string DxGrid);

    /// <summary>Fields for an outbound Decode datagram (<c>Requirement: Outbound Decode message</c>).</summary>
    public readonly record struct DecodeFields(
        bool   New,
        uint   TimeMsSinceMidnightUtc,
        int    SnrDb,
        double DeltaTimeSeconds,
        uint   DeltaFrequencyHz,
        string Mode,
        string Message,
        bool   LowConfidence);

    /// <summary>Fields for an outbound QSOLogged datagram (<c>Requirement: Outbound QSOLogged message</c>).</summary>
    public readonly record struct QsoLoggedFields(
        DateTimeOffset QsoStartUtc,
        DateTimeOffset QsoEndUtc,
        string         DxCall,
        string         DxGrid,
        ulong          TxFrequencyHz,
        string         Mode,
        string         ReportSent,
        string         ReportReceived,
        string         MyCall,
        string         MyGrid);

    // ── Inbound decode result ───────────────────────────────────────────────────

    /// <summary>Base type for a successfully-parsed inbound datagram's payload.</summary>
    public abstract record InboundMessage
    {
        private InboundMessage() { }

        /// <summary>Client heartbeat (rarely sent inbound, but structurally identical to outbound).</summary>
        public sealed record HeartbeatMessage(int MaxSchemaNumber, string Version, string Revision) : InboundMessage;

        /// <summary>
        /// Operator selected a decoded line to reply to. <see cref="Message"/> is the raw decoded
        /// text (e.g. <c>"CQ Q1TST JO22"</c>) — the caller extracts the callsign from it.
        /// </summary>
        public sealed record ReplyMessage(string Message, uint DeltaFrequencyHz) : InboundMessage;

        /// <summary>Halt Tx — abort any in-progress transmission (always honoured; see spec).</summary>
        public sealed record HaltTxMessage(bool AutoTxOnly) : InboundMessage;

        /// <summary>Free Text — accepted and stored; no transmission effect (see design.md).</summary>
        public sealed record FreeTextMessage(string Text, bool Send) : InboundMessage;

        /// <summary>Client requested close — logged only; never terminates the daemon.</summary>
        public sealed record CloseMessage : InboundMessage;

        /// <summary>
        /// A well-formed but unimplemented message type (Replay, Location, Highlight Callsign,
        /// Switch Configuration, Configure, WSPR Decode, or any type outside this protocol
        /// version's known set). Parsed only far enough to identify the type; the body is not
        /// interpreted.
        /// </summary>
        public sealed record UnsupportedMessage(MessageType Type) : InboundMessage;
    }

    // ── Encoding ─────────────────────────────────────────────────────────────────

    public static byte[] EncodeHeartbeat(string id, int maxSchemaNumber, string version, string revision)
    {
        var w = new Writer();
        WriteHeader(w, MessageType.Heartbeat, id);
        w.WriteInt32(maxSchemaNumber);
        w.WriteString(version);
        w.WriteString(revision);
        return w.ToArray();
    }

    public static byte[] EncodeStatus(string id, in StatusFields f)
    {
        var w = new Writer();
        WriteHeader(w, MessageType.Status, id);
        w.WriteUInt64(f.DialFrequencyHz);
        w.WriteString(f.Mode);
        w.WriteString(f.DxCall);
        w.WriteString(f.Report);
        w.WriteString(f.TxMode);
        w.WriteBool(f.TxEnabled);
        w.WriteBool(f.Transmitting);
        w.WriteBool(f.Decoding);
        w.WriteUInt32(f.RxDeltaFreqHz);
        w.WriteUInt32(f.TxDeltaFreqHz);
        w.WriteString(f.MyCall);
        w.WriteString(f.MyGrid);
        w.WriteString(f.DxGrid);
        // Trailing fields present in later WSJT-X schema revisions — fixed, reasonable defaults
        // so a fixed-order receiver parser stays aligned for the rest of this message.
        w.WriteBool(false);        // TXWatchdog
        w.WriteString("FT8");      // SubMode
        w.WriteBool(false);        // FastMode
        w.WriteByte(0);            // SpecialOperationMode
        w.WriteUInt32(0);          // FrequencyTolerance (not applicable)
        w.WriteUInt32(15);         // TRPeriod (seconds)
        w.WriteString("OpenWSFZ"); // ConfigurationName
        w.WriteString("");         // TXMessage
        return w.ToArray();
    }

    public static byte[] EncodeDecode(string id, in DecodeFields f)
    {
        var w = new Writer();
        WriteHeader(w, MessageType.Decode, id);
        w.WriteBool(f.New);
        w.WriteUInt32(f.TimeMsSinceMidnightUtc);
        w.WriteInt32(f.SnrDb);
        w.WriteDouble(f.DeltaTimeSeconds);
        w.WriteUInt32(f.DeltaFrequencyHz);
        w.WriteString(f.Mode);
        w.WriteString(f.Message);
        w.WriteBool(f.LowConfidence);
        w.WriteBool(false); // OffAir
        return w.ToArray();
    }

    public static byte[] EncodeClear(string id)
    {
        var w = new Writer();
        WriteHeader(w, MessageType.Clear, id);
        return w.ToArray();
    }

    public static byte[] EncodeQsoLogged(string id, in QsoLoggedFields f)
    {
        var w = new Writer();
        WriteHeader(w, MessageType.QsoLogged, id);
        w.WriteDateTimeUtc(f.QsoEndUtc);
        w.WriteString(f.DxCall);
        w.WriteString(f.DxGrid);
        w.WriteUInt64(f.TxFrequencyHz);
        w.WriteString(f.Mode);
        w.WriteString(f.ReportSent);
        w.WriteString(f.ReportReceived);
        w.WriteString("");                 // TXPower — not tracked at this call site
        w.WriteString("");                 // Comments
        w.WriteString("");                 // Name
        w.WriteDateTimeUtc(f.QsoStartUtc);
        w.WriteString(f.MyCall);           // OperatorCall
        w.WriteString(f.MyCall);           // MyCall
        w.WriteString(f.MyGrid);           // MyGrid
        w.WriteString("");                 // ExchangeSent
        w.WriteString("");                 // ExchangeRcvd
        w.WriteString("");                 // ADIF propagation mode
        return w.ToArray();
    }

    public static byte[] EncodeClose(string id)
    {
        var w = new Writer();
        WriteHeader(w, MessageType.Close, id);
        return w.ToArray();
    }

    private static void WriteHeader(Writer w, MessageType type, string id)
    {
        w.WriteUInt32(Magic);
        w.WriteUInt32(SchemaVersion);
        w.WriteUInt32((uint)type);
        w.WriteString(id);
    }

    // ── Decoding ─────────────────────────────────────────────────────────────────

    /// <summary>
    /// Attempts to decode an inbound datagram. Never throws: any parse failure (too short, bad
    /// magic number, unsupported schema version, truncated field) returns <c>false</c> with
    /// <paramref name="message"/> set to <c>null</c> — the caller SHALL discard the datagram and
    /// continue listening (<c>Requirement: Inbound listener never crashes on malformed input</c>).
    /// </summary>
    public static bool TryDecode(ReadOnlySpan<byte> data, out InboundMessage? message)
    {
        message = null;
        try
        {
            var r = new Reader(data);

            var magic = r.ReadUInt32();
            if (magic != Magic) return false;

            var schema = r.ReadUInt32();
            if (schema is not (1 or 2 or 3)) return false; // unsupported schema version

            var typeRaw = r.ReadUInt32();
            _ = r.ReadString(); // Id — consumed to stay aligned; not currently consulted

            if (!Enum.IsDefined(typeof(MessageType), typeRaw))
            {
                message = new InboundMessage.UnsupportedMessage((MessageType)typeRaw);
                return true;
            }

            var type = (MessageType)typeRaw;
            message = type switch
            {
                MessageType.Heartbeat => DecodeHeartbeat(ref r),
                MessageType.Reply     => DecodeReply(ref r),
                MessageType.HaltTx    => DecodeHaltTx(ref r),
                MessageType.FreeText  => DecodeFreeText(ref r),
                MessageType.Close     => new InboundMessage.CloseMessage(),
                _                     => new InboundMessage.UnsupportedMessage(type),
            };
            return true;
        }
        catch (Exception ex) when (ex is EndOfStreamException or ArgumentOutOfRangeException
                                       or IndexOutOfRangeException or OverflowException
                                       or DecoderFallbackException)
        {
            message = null;
            return false;
        }
    }

    private static InboundMessage DecodeHeartbeat(ref Reader r)
    {
        var maxSchema = r.ReadInt32();
        var version   = r.ReadString() ?? "";
        var revision  = r.ReadString() ?? "";
        return new InboundMessage.HeartbeatMessage(maxSchema, version, revision);
    }

    /// <summary>
    /// The inbound Reply datagram has the same field layout as the outbound Decode datagram
    /// (WSJT-X echoes back the selected decode line's fields). Only <c>Message</c> (to extract
    /// the callsign from) and <c>DeltaFrequencyHz</c> are currently consulted by this daemon.
    /// </summary>
    private static InboundMessage DecodeReply(ref Reader r)
    {
        _ = r.TryReadBool(out _);          // New
        _ = r.ReadUInt32();                // Time
        _ = r.ReadInt32();                 // SNR
        _ = r.ReadDouble();                // DeltaTime
        var deltaFreq = r.ReadUInt32();    // DeltaFrequency
        _ = r.ReadString();                // Mode
        var msg = r.ReadString() ?? "";    // Message
        _ = r.TryReadBool(out _);          // LowConfidence
        return new InboundMessage.ReplyMessage(msg, deltaFreq);
    }

    private static InboundMessage DecodeHaltTx(ref Reader r)
    {
        var autoTxOnly = r.TryReadBool(out var v) && v;
        return new InboundMessage.HaltTxMessage(autoTxOnly);
    }

    private static InboundMessage DecodeFreeText(ref Reader r)
    {
        var text = r.ReadString() ?? "";
        var send = r.TryReadBool(out var s) && s; // Send flag — optional across schema revisions
        return new InboundMessage.FreeTextMessage(text, send);
    }

    // ── Low-level big-endian writer ──────────────────────────────────────────────

    private sealed class Writer
    {
        private readonly List<byte> _buf = new(64);

        public void WriteByte(byte v) => _buf.Add(v);

        public void WriteBool(bool v) => _buf.Add(v ? (byte)1 : (byte)0);

        public void WriteInt32(int v) => WriteUInt32(unchecked((uint)v));

        public void WriteUInt32(uint v)
        {
            Span<byte> b = stackalloc byte[4];
            BinaryPrimitives.WriteUInt32BigEndian(b, v);
            _buf.AddRange(b.ToArray());
        }

        public void WriteInt64(long v)
        {
            Span<byte> b = stackalloc byte[8];
            BinaryPrimitives.WriteInt64BigEndian(b, v);
            _buf.AddRange(b.ToArray());
        }

        public void WriteUInt64(ulong v)
        {
            Span<byte> b = stackalloc byte[8];
            BinaryPrimitives.WriteUInt64BigEndian(b, v);
            _buf.AddRange(b.ToArray());
        }

        public void WriteDouble(double v)
        {
            Span<byte> b = stackalloc byte[8];
            BinaryPrimitives.WriteInt64BigEndian(b, BitConverter.DoubleToInt64Bits(v));
            _buf.AddRange(b.ToArray());
        }

        /// <summary>
        /// Writes a WSJT-X-protocol string: a big-endian <c>quint32</c> byte length followed by
        /// UTF-8 bytes; <c>0xFFFFFFFF</c> encodes a null string.
        /// </summary>
        public void WriteString(string? s)
        {
            if (s is null)
            {
                WriteUInt32(0xFFFFFFFF);
                return;
            }

            var bytes = Encoding.UTF8.GetBytes(s);
            WriteUInt32((uint)bytes.Length);
            _buf.AddRange(bytes);
        }

        /// <summary>
        /// Writes a UTC <see cref="DateTimeOffset"/> in Qt's <c>QDateTime</c> <c>QDataStream</c>
        /// wire format (schema ≥ Qt 5.2): <c>qint64</c> Julian day number, <c>qint32</c>
        /// milliseconds since midnight, <c>quint8</c> time spec (<c>1</c> = UTC, always used here).
        /// </summary>
        public void WriteDateTimeUtc(DateTimeOffset dt)
        {
            var utc                  = dt.UtcDateTime;
            var julianDay             = ToJulianDayNumber(utc.Year, utc.Month, utc.Day);
            var msecsSinceMidnight    = (int)utc.TimeOfDay.TotalMilliseconds;
            WriteInt64(julianDay);
            WriteInt32(msecsSinceMidnight);
            WriteByte(1); // Qt::UTC
        }

        /// <summary>
        /// Gregorian-calendar Julian Day Number for <paramref name="y"/>/<paramref name="m"/>/
        /// <paramref name="d"/>, matching Qt's own <c>julianDayFromDate</c> algorithm.
        /// </summary>
        private static long ToJulianDayNumber(int y, int m, int d)
        {
            long a  = (14 - m) / 12;
            long yy = y + 4800 - a;
            long mm = m + 12 * a - 3;
            return d + (153 * mm + 2) / 5 + 365 * yy + yy / 4 - yy / 100 + yy / 400 - 32045;
        }

        public byte[] ToArray() => _buf.ToArray();
    }

    // ── Low-level big-endian reader ──────────────────────────────────────────────

    private ref struct Reader
    {
        private readonly ReadOnlySpan<byte> _data;
        private int _pos;

        public Reader(ReadOnlySpan<byte> data)
        {
            _data = data;
            _pos  = 0;
        }

        private ReadOnlySpan<byte> Take(int count)
        {
            if (count < 0 || _pos + count > _data.Length) throw new EndOfStreamException();
            var slice = _data.Slice(_pos, count);
            _pos += count;
            return slice;
        }

        public bool TryReadBool(out bool value)
        {
            if (_pos + 1 > _data.Length) { value = false; return false; }
            value = Take(1)[0] != 0;
            return true;
        }

        public uint ReadUInt32() => BinaryPrimitives.ReadUInt32BigEndian(Take(4));

        public int ReadInt32() => BinaryPrimitives.ReadInt32BigEndian(Take(4));

        public double ReadDouble() => BitConverter.Int64BitsToDouble(BinaryPrimitives.ReadInt64BigEndian(Take(8)));

        public string? ReadString()
        {
            var len = ReadUInt32();
            if (len == 0xFFFFFFFF) return null;
            if (len == 0) return string.Empty;
            var bytes = Take(checked((int)len));
            return Encoding.UTF8.GetString(bytes);
        }
    }
}
