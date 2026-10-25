using System.Buffers.Binary;
using System.Text;

namespace OpenWSFZ.Daemon.PskReporter;

/// <summary>The receiver (this station) record of a PSK Reporter datagram.</summary>
/// <param name="Callsign">The station's own callsign (<c>tx.callsign</c>).</param>
/// <param name="Locator">The station's own Maidenhead locator (<c>tx.grid</c>).</param>
/// <param name="Software">The <c>decodingSoftware</c> string, <c>OpenWSFZ &lt;VERSION&gt;</c>.</param>
/// <param name="Antenna">Free-text antenna description; empty omits the field (and its descriptor entry).</param>
internal sealed record PskReceiver(string Callsign, string Locator, string Software, string Antenna);

/// <summary>One received station to report.</summary>
/// <param name="Callsign">The sender's callsign exactly as decoded.</param>
/// <param name="Locator">The sender's locator when the decoded message carried one in the grid position, else <c>null</c>.</param>
/// <param name="FrequencyHz">Dial frequency at capture plus the audio offset, in Hz.</param>
/// <param name="Snr">The decode's SNR in dB (clamped into a signed byte on the wire).</param>
/// <param name="FlowStartSeconds">The cycle start, Unix seconds.</param>
/// <param name="Mode">The <c>mode</c> string; always <c>FT8</c> in the product (a parameter only so the protocol page's own worked example can be reproduced).</param>
internal sealed record PskSpot(string Callsign, string? Locator, uint FrequencyHz, int Snr, uint FlowStartSeconds, string Mode = "FT8");

/// <summary>A field a sender record can carry.</summary>
internal enum PskField { Callsign, Frequency, Snr, Imd, Mode, Source, Locator, FlowStart }

/// <summary>A sender template: its id and its fields IN WIRE ORDER (a record's bytes follow this order).</summary>
internal sealed record PskSenderTemplate(ushort Id, IReadOnlyList<PskField> Fields);

/// <summary>
/// The pure encoder for PSK Reporter's simplified IPFIX datagrams (issue #262). The reference is the public protocol page
/// (<c>https://pskreporter.info/pskdev.html</c>) and QA's hand-built golden fixtures (<c>qa/rr-study/psk-reporter-262/</c>), never any
/// prose list. No WSJT-X source is involved. All integers are big-endian; every set is zero-padded to a multiple of 4 bytes and its
/// length field includes its header and padding.
/// </summary>
internal static class PskReporterEncoder
{
    /// <summary>Largest datagram the service sends, a decision value from the path MTU (not from the protocol page).</summary>
    public const int MaxDatagramBytes = 1400;

    /// <summary>IPFIX version field.</summary>
    private const ushort IpfixVersion = 0x000A;

    /// <summary>Header length: version, total length, export time, sequence number, session id.</summary>
    private const int HeaderBytes = 16;

    /// <summary>Set id of an options template set (the receiver descriptor).</summary>
    private const ushort OptionsTemplateSetId = 3;

    /// <summary>Set id of a template set (the sender descriptors).</summary>
    private const ushort TemplateSetId = 2;

    /// <summary>Template id of the receiver record.</summary>
    private const ushort ReceiverTemplateId = 0x9992;

    /// <summary>Template id of the 8-field sender record (with <c>senderLocator</c>).</summary>
    private const ushort SenderWithLocatorTemplateId = 0x9993;

    /// <summary>Template id of the 7-field sender record (without <c>senderLocator</c>).</summary>
    private const ushort SenderNoLocatorTemplateId = 0x9994;

    /// <summary>PSK Reporter's IANA private enterprise number (30351).</summary>
    private const uint EnterpriseNumber = 30351;

    /// <summary>Set the enterprise bit of an information element id.</summary>
    private const ushort EnterpriseBit = 0x8000;

    /// <summary>Variable-length field marker in a template field specifier.</summary>
    private const ushort VariableLength = 0xFFFF;

    /// <summary>The IANA information element <c>flowStartSeconds</c> (no enterprise part).</summary>
    private const ushort FlowStartSecondsElement = 150;

    // PSK Reporter enterprise information elements (30351.n).
    private const ushort SenderCallsign      = 1;
    private const ushort ReceiverCallsign    = 2;
    private const ushort SenderLocator       = 3;
    private const ushort ReceiverLocator     = 4;
    private const ushort Frequency           = 5;
    private const ushort Snr                 = 6;
    private const ushort Imd                 = 7;
    private const ushort DecodingSoftware    = 8;
    private const ushort AntennaInformation  = 9;
    private const ushort Mode                = 10;
    private const ushort InformationSource   = 11;

    /// <summary>The longest string the wire format carries (a 1-byte length, 255 is reserved).</summary>
    private const int MaxStringBytes = 254;

    /// <summary><c>informationSource</c> 1: automatic.</summary>
    private const byte AutomaticSource = 1;

    /// <summary>
    /// <c>iMD</c> (intermodulation distortion) is always 0: OpenWSFZ does not measure it, and the Captain ruled (D4, 2026-10-25) that
    /// the field is sent as 0 rather than omitted.
    /// </summary>
    private const sbyte ImdNotMeasured = 0;

    /// <summary>The 8-field sender template (template id <c>0x9993</c>): for a message that carries a grid.</summary>
    public static readonly PskSenderTemplate WithLocator = new(SenderWithLocatorTemplateId,
        [PskField.Callsign, PskField.Frequency, PskField.Snr, PskField.Imd, PskField.Mode, PskField.Source, PskField.Locator, PskField.FlowStart]);

    /// <summary>The 7-field sender template (template id <c>0x9994</c>): the same without <c>senderLocator</c>.</summary>
    public static readonly PskSenderTemplate NoLocator = new(SenderNoLocatorTemplateId,
        [PskField.Callsign, PskField.Frequency, PskField.Snr, PskField.Imd, PskField.Mode, PskField.Source, PskField.FlowStart]);

    /// <summary>
    /// Builds one datagram: header, the template sets when <paramref name="includeTemplates"/>, one receiver record, then one sender block
    /// per template that has records (the 8-field block, for spots with a locator, first; then the 7-field block).
    /// </summary>
    public static byte[] Encode(
        PskReceiver receiver, IReadOnlyList<PskSpot> spots, uint exportTime, uint sequence, uint sessionId, bool includeTemplates)
    {
        var blocks = new List<(PskSenderTemplate, IReadOnlyList<PskSpot>)>
        {
            (WithLocator, spots.Where(s => !string.IsNullOrEmpty(s.Locator)).ToList()),
            (NoLocator,   spots.Where(s => string.IsNullOrEmpty(s.Locator)).ToList()),
        };
        return Encode(receiver, blocks, includeTemplates ? [WithLocator, NoLocator] : [], exportTime, sequence, sessionId);
    }

    /// <summary>
    /// The general form: any sender templates, described when listed in <paramref name="describe"/>; empty blocks are not written.
    /// Internal so the protocol page's own worked datagram (a 5-field template the product never sends) can be reproduced byte for byte.
    /// </summary>
    internal static byte[] Encode(
        PskReceiver receiver, IReadOnlyList<(PskSenderTemplate Template, IReadOnlyList<PskSpot> Spots)> blocks,
        IReadOnlyList<PskSenderTemplate> describe, uint exportTime, uint sequence, uint sessionId)
    {
        bool antenna = receiver.Antenna.Length > 0;

        using var body = new MemoryStream();
        if (describe.Count > 0) Write(body, ReceiverDescriptor(antenna));
        foreach (var t in describe) Write(body, SenderDescriptor(t));
        Write(body, ReceiverRecord(receiver, antenna));
        foreach (var (template, spots) in blocks)
            if (spots.Count > 0) Write(body, SenderBlock(template, spots));

        var datagram = new byte[HeaderBytes + (int)body.Length];
        BinaryPrimitives.WriteUInt16BigEndian(datagram.AsSpan(0),  IpfixVersion);
        BinaryPrimitives.WriteUInt16BigEndian(datagram.AsSpan(2),  (ushort)datagram.Length);
        BinaryPrimitives.WriteUInt32BigEndian(datagram.AsSpan(4),  exportTime);
        BinaryPrimitives.WriteUInt32BigEndian(datagram.AsSpan(8),  sequence);
        BinaryPrimitives.WriteUInt32BigEndian(datagram.AsSpan(12), sessionId);
        body.ToArray().CopyTo(datagram, HeaderBytes);
        return datagram;
    }

    /// <summary>
    /// Takes spots from the front of <paramref name="spots"/> while the whole datagram stays within <see cref="MaxDatagramBytes"/>.
    /// At least one spot is always taken when any exist (a single record is far below the limit).
    /// </summary>
    /// <returns>How many leading spots fit.</returns>
    public static int CountThatFit(PskReceiver receiver, IReadOnlyList<PskSpot> spots, bool includeTemplates)
    {
        int taken = 0;
        for (int n = 1; n <= spots.Count; n++)
        {
            if (Encode(receiver, spots.Take(n).ToList(), 0, 0, 0, includeTemplates).Length > MaxDatagramBytes) break;
            taken = n;
        }
        return taken;
    }

    // ── descriptors ──────────────────────────────────────────────────────────────────────────────────────────────────

    private static byte[] ReceiverDescriptor(bool antenna)
    {
        var fields = new List<byte[]> { EnterpriseField(ReceiverCallsign, VariableLength), EnterpriseField(ReceiverLocator, VariableLength), EnterpriseField(DecodingSoftware, VariableLength) };
        if (antenna) fields.Add(EnterpriseField(AntennaInformation, VariableLength));

        var body = new List<byte>();
        body.AddRange(U16(ReceiverTemplateId));
        body.AddRange(U16((ushort)fields.Count));
        body.AddRange(U16(1));                                   // scope field count 1: the options template
        foreach (var f in fields) body.AddRange(f);
        return Set(OptionsTemplateSetId, body.ToArray());
    }

    /// <summary>
    /// The sender descriptor. The field ORDER is the contract: for the product templates callsign, frequency, sNR, iMD, mode,
    /// informationSource, then (8-field only) senderLocator, then flowStartSeconds. A record's bytes follow this order.
    /// </summary>
    private static byte[] SenderDescriptor(PskSenderTemplate template)
    {
        var fields = template.Fields.Select(f => f switch
        {
            PskField.Callsign  => EnterpriseField(SenderCallsign, VariableLength),
            PskField.Frequency => EnterpriseField(Frequency, 4),
            PskField.Snr       => EnterpriseField(Snr, 1),
            PskField.Imd       => EnterpriseField(Imd, 1),
            PskField.Mode      => EnterpriseField(Mode, VariableLength),
            PskField.Source    => EnterpriseField(InformationSource, 1),
            PskField.Locator   => EnterpriseField(SenderLocator, VariableLength),
            PskField.FlowStart => IanaField(FlowStartSecondsElement, 4),
            _                  => throw new ArgumentOutOfRangeException(nameof(template)),
        }).ToList();

        var body = new List<byte>();
        body.AddRange(U16(template.Id));
        body.AddRange(U16((ushort)fields.Count));
        foreach (var f in fields) body.AddRange(f);
        return Set(TemplateSetId, body.ToArray());
    }

    private static byte[] EnterpriseField(ushort element, ushort length)
    {
        var b = new byte[8];
        BinaryPrimitives.WriteUInt16BigEndian(b.AsSpan(0), (ushort)(EnterpriseBit | element));
        BinaryPrimitives.WriteUInt16BigEndian(b.AsSpan(2), length);
        BinaryPrimitives.WriteUInt32BigEndian(b.AsSpan(4), EnterpriseNumber);
        return b;
    }

    private static byte[] IanaField(ushort element, ushort length)
    {
        var b = new byte[4];
        BinaryPrimitives.WriteUInt16BigEndian(b.AsSpan(0), element);
        BinaryPrimitives.WriteUInt16BigEndian(b.AsSpan(2), length);
        return b;
    }

    // ── records ──────────────────────────────────────────────────────────────────────────────────────────────────────

    private static byte[] ReceiverRecord(PskReceiver r, bool antenna)
    {
        var body = new List<byte>();
        body.AddRange(VarString(r.Callsign));
        body.AddRange(VarString(r.Locator));
        body.AddRange(VarString(r.Software));
        if (antenna) body.AddRange(VarString(r.Antenna));
        return RecordSet(ReceiverTemplateId, body.ToArray());
    }

    private static byte[] SenderBlock(PskSenderTemplate template, IReadOnlyList<PskSpot> spots)
    {
        var body = new List<byte>();
        foreach (var s in spots)
        {
            foreach (var field in template.Fields)
            {
                switch (field)
                {
                    case PskField.Callsign:  body.AddRange(VarString(s.Callsign)); break;
                    case PskField.Frequency: body.AddRange(U32(s.FrequencyHz)); break;
                    case PskField.Snr:       body.Add(unchecked((byte)(sbyte)Math.Clamp(s.Snr, sbyte.MinValue, sbyte.MaxValue))); break;
                    case PskField.Imd:       body.Add(unchecked((byte)ImdNotMeasured)); break;
                    case PskField.Mode:      body.AddRange(VarString(s.Mode)); break;
                    case PskField.Source:    body.Add(AutomaticSource); break;
                    case PskField.Locator:   body.AddRange(VarString(s.Locator ?? "")); break;
                    case PskField.FlowStart: body.AddRange(U32(s.FlowStartSeconds)); break;
                }
            }
        }
        return RecordSet(template.Id, body.ToArray());
    }

    // ── primitives ───────────────────────────────────────────────────────────────────────────────────────────────────

    /// <summary>A set (id, length, body padded to a multiple of 4; the length includes the 4-byte set header and the padding).</summary>
    private static byte[] Set(ushort setId, byte[] body) => PaddedSet(setId, body);

    /// <summary>A data set: its set id is the template id of the records it carries.</summary>
    private static byte[] RecordSet(ushort templateId, byte[] body) => PaddedSet(templateId, body);

    private static byte[] PaddedSet(ushort id, byte[] body)
    {
        int padded = (body.Length + 3) & ~3;
        var set = new byte[4 + padded];
        BinaryPrimitives.WriteUInt16BigEndian(set.AsSpan(0), id);
        BinaryPrimitives.WriteUInt16BigEndian(set.AsSpan(2), (ushort)set.Length);
        body.CopyTo(set, 4);
        return set;
    }

    /// <summary>A variable-length string: a 1-byte length (at most 254) then UTF-8; longer text is cut on a character boundary.</summary>
    private static byte[] VarString(string text)
    {
        var bytes = Encoding.UTF8.GetBytes(text);
        if (bytes.Length > MaxStringBytes)
        {
            int cut = MaxStringBytes;
            while (cut > 0 && (bytes[cut] & 0xC0) == 0x80) cut--;   // never split a multi-byte character
            bytes = bytes[..cut];
        }
        var result = new byte[1 + bytes.Length];
        result[0] = (byte)bytes.Length;
        bytes.CopyTo(result, 1);
        return result;
    }

    private static byte[] U16(ushort v) { var b = new byte[2]; BinaryPrimitives.WriteUInt16BigEndian(b, v); return b; }
    private static byte[] U32(uint v)   { var b = new byte[4]; BinaryPrimitives.WriteUInt32BigEndian(b, v); return b; }

    private static void Write(MemoryStream s, byte[] bytes) => s.Write(bytes, 0, bytes.Length);
}
