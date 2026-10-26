using FluentAssertions;
using OpenWSFZ.Daemon.PskReporter;
using Xunit;

namespace OpenWSFZ.Daemon.Tests.PskReporter;

/// <summary>
/// FR-089 (issue #262): the datagram's bytes. The expected bytes are QA's hand-built fixtures
/// (<c>build_t1_fixture.py</c> + the three <c>.hex</c> files, copied unchanged), built from the protocol page and NOT from the
/// encoder under test. Q-prefix callsigns only (NFR-021).
/// </summary>
public sealed class PskReporterEncoderTests
{
    // The T1 inputs of build_t1_fixture.py (t1()): session 0xA1B2C3D4, sequence 7, export 2026-10-25T11:35:00Z, cycle start 11:34:45Z, dial 14.074 MHz.
    private const uint SessionId = 0xA1B2C3D4;
    private static readonly uint Export = Unix(2026, 10, 25, 11, 35, 0);
    private static readonly uint Cycle  = Unix(2026, 10, 25, 11, 34, 45);
    private const uint DialHz = 14_074_000;

    private static uint Unix(int y, int mo, int d, int h, int mi, int s)
        => (uint)new DateTimeOffset(y, mo, d, h, mi, s, TimeSpan.Zero).ToUnixTimeSeconds();

    private static byte[] Fixture(string name)
    {
        using var s = typeof(PskReporterEncoderTests).Assembly.GetManifestResourceStream($"PskReporter.Fixtures.{name}.hex")
                      ?? throw new InvalidOperationException($"fixture {name} not embedded");
        using var r = new StreamReader(s);
        return Convert.FromHexString(string.Concat(r.ReadToEnd().Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries)));
    }

    private static PskReceiver Receiver(string antenna = "") => new("Q1OFZ", "JO33", "OpenWSFZ 0.63", antenna);
    private static PskSpot WithGrid()    => new("Q1ABC", "JO22", DialHz + 1500, -12, Cycle);
    private static PskSpot WithoutGrid() => new("Q2DEF", null,   DialHz + 987,  -5,  Cycle);

    [Fact(DisplayName = "FR-089: T1: one receiver record and two sender records (8-field block first, then the 7-field block) equal QA's fixture byte for byte")]
    public void T1_GoldenBytes_8And7Field()
    {
        var bytes = PskReporterEncoder.Encode(Receiver(), [WithoutGrid(), WithGrid()], Export, 7, SessionId, includeTemplates: true);
        Convert.ToHexString(bytes).Should().Be(Convert.ToHexString(Fixture("t1_8field_and_7field")));
    }

    [Fact(DisplayName = "FR-089: T1: with an antenna text the receiver descriptor and record carry the fourth field, equal to QA's fixture")]
    public void T1_GoldenBytes_WithAntenna()
    {
        var bytes = PskReporterEncoder.Encode(Receiver("Q1 test antenna"), [WithGrid(), WithoutGrid()], Export, 7, SessionId, includeTemplates: true);
        Convert.ToHexString(bytes).Should().Be(Convert.ToHexString(Fixture("t1_with_antenna")));
    }

    [Fact(DisplayName = "FR-089: T1: no templates, sequence 9 and an SNR of -132 (clamped to the byte 0x80) equal QA's fixture")]
    public void T1_GoldenBytes_TemplatesNotDue_SnrClamped()
    {
        var spot  = new PskSpot("Q1ABC", "JO22", DialHz + 1510, -132, Cycle + 300);
        var bytes = PskReporterEncoder.Encode(Receiver(), [spot], Export + 300, 9, SessionId, includeTemplates: false);
        Convert.ToHexString(bytes).Should().Be(Convert.ToHexString(Fixture("t1_templates_not_due_snr_clamped")));
    }

    [Fact(DisplayName = "FR-089: T1: the protocol page's own worked datagram (172 bytes, sequence 1, Q-calls of the same length) is reproduced by the product encoder")]
    public void T1_PageWorkedDatagram_Reproduced()
    {
        // Same inputs as selfcheck() in build_t1_fixture.py: a 5-field sender template (callsign, frequency, mode, source, flowStart), mode PSK.
        var fiveField = new PskSenderTemplate(0x9993, [PskField.Callsign, PskField.Frequency, PskField.Mode, PskField.Source, PskField.FlowStart]);
        var receiver  = new PskReceiver("Q1DQ", "FN42hn", "Homebrew v5.6", "");
        PskSpot[] spots =
        [
            new("Q1DQ",   null, 14070567, 0, 1200960084, "PSK"),
            new("Q1MBXZ", null, 14070987, 0, 1200960104, "PSK"),
        ];
        var bytes = PskReporterEncoder.Encode(receiver, [(fiveField, spots)], [fiveField], 1200960114, 1, 0);

        bytes.Length.Should().Be(0xAC);
        Convert.ToHexString(bytes).Should().Be(
            "000A00AC47953272000000010000000000030024999200030001" + "8002FFFF0000768F" + "8004FFFF0000768F" + "8008FFFF0000768F" + "0000"
            + "0002002C99930005" + "8001FFFF0000768F" + "800500040000768F" + "800AFFFF0000768F" + "800B00010000768F" + "00960004"
            + "99920020" + "04" + Hex("Q1DQ") + "06" + Hex("FN42hn") + "0D" + Hex("Homebrew v5.6") + "0000"
            + "9993002C" + "04" + Hex("Q1DQ") + "00D6B327" + "03" + Hex("PSK") + "01" + "47953254"
            + "06" + Hex("Q1MBXZ") + "00D6B4CB" + "03" + Hex("PSK") + "01" + "47953268" + "0000");
    }

    private static string Hex(string ascii) => Convert.ToHexString(System.Text.Encoding.ASCII.GetBytes(ascii));

    [Fact(DisplayName = "FR-089: T13: iMD is 0 in every record, and the SNR is clamped at -128 and 127 (-132 gives 0x80, 200 gives 0x7F)")]
    public void T13_Imd_Zero_And_SnrClamp()
    {
        var spots = new[]
        {
            new PskSpot("Q1ABC", null, DialHz, -132, Cycle), new PskSpot("Q2DEF", null, DialHz, 200, Cycle), new PskSpot("Q3GHI", null, DialHz, -5, Cycle),
        };
        var bytes = PskReporterEncoder.Encode(Receiver(), spots, Export, 0, SessionId, includeTemplates: false);

        // The 7-field block (set id 0x9994), the last set: 3 records of [len call(5)] freq(4) snr imd [len mode(3)] source flow(4) = 21 bytes each.
        int blockStart = bytes.Length - (4 + ((3 * 21 + 3) & ~3));
        ((bytes[blockStart] << 8) | bytes[blockStart + 1]).Should().Be(0x9994);
        var snrs = new List<byte>(); var imds = new List<byte>();
        for (int i = 0; i < 3; i++)
        {
            int rec = blockStart + 4 + i * 21;
            snrs.Add(bytes[rec + 1 + 5 + 4]);
            imds.Add(bytes[rec + 1 + 5 + 4 + 1]);
        }
        snrs.Should().Equal(0x80, 0x7F, 0xFB);
        imds.Should().Equal(0, 0, 0);
    }

    [Fact(DisplayName = "FR-089: T13: a message with a grid goes in the 0x9993 block and one without in the 0x9994 block, 8-field first; one kind alone gives one block")]
    public void T13_BlocksByGrid_OrderAndSingleKind()
    {
        SetIds(PskReporterEncoder.Encode(Receiver(), [WithoutGrid(), WithGrid()], Export, 0, SessionId, false)).Should().Equal(0x9992, 0x9993, 0x9994);
        SetIds(PskReporterEncoder.Encode(Receiver(), [WithGrid()],    Export, 0, SessionId, false)).Should().Equal(0x9992, 0x9993);
        SetIds(PskReporterEncoder.Encode(Receiver(), [WithoutGrid()], Export, 0, SessionId, false)).Should().Equal(0x9992, 0x9994);
    }

    [Fact(DisplayName = "FR-089: every set is a multiple of 4 bytes, the header length is the datagram length, and a packed datagram never exceeds 1,400 bytes")]
    public void Framing_Padding_And_Limit()
    {
        var spots = Enumerable.Range(0, 200)
            .Select(i => new PskSpot($"Q{i % 9}AB{(char)('A' + i % 26)}", i % 2 == 0 ? "JO22" : null, DialHz + (uint)i, -(i % 30), Cycle)).ToList();
        int fit = PskReporterEncoder.CountThatFit(Receiver(), spots, includeTemplates: true);
        fit.Should().BeGreaterThan(10).And.BeLessThan(200);

        var bytes = PskReporterEncoder.Encode(Receiver(), spots.Take(fit).ToList(), Export, 0, SessionId, true);
        bytes.Length.Should().BeLessThanOrEqualTo(PskReporterEncoder.MaxDatagramBytes);
        PskReporterEncoder.Encode(Receiver(), spots.Take(fit + 1).ToList(), Export, 0, SessionId, true).Length
            .Should().BeGreaterThan(PskReporterEncoder.MaxDatagramBytes, "CountThatFit stops exactly at the limit");
        ((bytes[2] << 8) | bytes[3]).Should().Be(bytes.Length);

        int pos = 16;
        while (pos < bytes.Length)
        {
            int len = (bytes[pos + 2] << 8) | bytes[pos + 3];
            (len % 4).Should().Be(0);
            pos += len;
        }
        pos.Should().Be(bytes.Length);
    }

    /// <summary>The set ids of a datagram's data sets (ids at or above 256), in order.</summary>
    private static List<int> SetIds(byte[] d)
    {
        var ids = new List<int>();
        int pos = 16;
        while (pos < d.Length)
        {
            int id = (d[pos] << 8) | d[pos + 1];
            if (id >= 256) ids.Add(id);
            pos += (d[pos + 2] << 8) | d[pos + 3];
        }
        return ids;
    }
}
