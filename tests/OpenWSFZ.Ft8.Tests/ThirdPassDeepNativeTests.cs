using System.Reflection;
using FluentAssertions;
using OpenWSFZ.Abstractions;
using Xunit;
using Xunit.Abstractions;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// third-pass-deep (#240 step 1, B8 managed-only): the third pass against the REAL native library — the same fit, the
/// same residual decode — on the synthetic fixture cycles. Proves the incremental form runs end to end on the real fit
/// (no native change was needed), that Deep is additive on real audio (batches 1 and 2 equal Normal's), and that
/// exactly one third-pass outcome is recorded per cycle that had pass-0 decodes.
///
/// <para>🔒 NFR-021 / HK-037: synthetic Q-prefix fixtures; counts and outcomes only.</para>
/// </summary>
[Collection("subfeas-native-pool")]
public sealed class ThirdPassDeepNativeTests
{
    private static readonly DateTime CycleStart = new(2026, 10, 18, 12, 0, 0, DateTimeKind.Utc);
    private readonly ITestOutputHelper _out;

    public ThirdPassDeepNativeTests(ITestOutputHelper output) => _out = output;

    private static float[] Fixture(string name)
    {
        var asm = Assembly.GetExecutingAssembly();
        string resource = asm.GetManifestResourceNames().Single(n => n.EndsWith(name, StringComparison.OrdinalIgnoreCase));
        using Stream s = asm.GetManifestResourceStream(resource)!;
        return WavReader.Read(s);
    }

    private static async Task<(Ft8Decoder Decoder, List<(int Batch, string[] Messages)> Batches)> Run(string wav, DecodingDepth depth)
    {
        var decoder = new Ft8Decoder(new FakeClock(CycleStart));
        decoder.SetSubtractionEnabled(true);
        decoder.SetDecodingDepth(depth);
        var got = new List<(int, string[])>();
        await decoder.DecodeStagedAsync(Fixture(wav), CycleStart, null, (n, b) =>
        {
            got.Add((n, b.Select(r => r.Message).ToArray()));
            return Task.CompletedTask;
        });
        return (decoder, got);
    }

    [Theory(DisplayName = "B3+B8 (real native): Deep is additive on real audio — batches 1 and 2 equal Normal's, batch 3 is new against both, one outcome per cycle")]
    [InlineData("synth-qso-01.wav")]
    [InlineData("synth-qso-02.wav")]
    [InlineData("synth-qso-03.wav")]
    public async Task Deep_OnRealNative_IsAdditive(string wav)
    {
        var (normalDecoder, normal) = await Run(wav, DecodingDepth.Normal);
        var (deepDecoder, deep) = await Run(wav, DecodingDepth.Deep);

        normalDecoder.GetThirdPassStatus().Should().Be(new ThirdPassStatus("Normal", 0, 0, 0, 0, 0, 0));

        foreach (var (batch, messages) in normal)
            deep.Single(d => d.Batch == batch).Messages.Should().Equal(messages, $"batch {batch} is untouched by Deep");

        var known = deep.Where(d => d.Batch <= 2).SelectMany(d => d.Messages).ToHashSet(StringComparer.Ordinal);
        foreach (var b3 in deep.Where(d => d.Batch == 3))
            b3.Messages.Should().NotBeEmpty().And.OnlyContain(m => !known.Contains(m), "batch 3 carries only decodes new against batches 1 and 2");

        var st = deepDecoder.GetThirdPassStatus();
        bool pass0Found = deep.Single(d => d.Batch == 1).Messages.Length > 0;
        long outcomes = st.Runs + st.SkippedNoNew + st.SkippedAbandoned;
        outcomes.Should().Be(pass0Found ? 1 : 0, "one outcome per cycle that had pass-0 decodes (a skip or a run)");
        st.Abandoned.Should().Be(0);
        st.Failed.Should().Be(0);
        _out.WriteLine($"{wav}: batches=[{string.Join(",", deep.Select(d => $"{d.Batch}:{d.Messages.Length}"))}] " +
                       $"runs={st.Runs} skippedNoNew={st.SkippedNoNew} decodes={st.Decodes}");
    }
}
