using FluentAssertions;
using OpenWSFZ.Ft8.Interop;
using Xunit;
using Xunit.Abstractions;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// PAYLOAD-FIT (shim 20260081): the lean engine fits every published result from its decoded payload, whatever its text looks like. The text gate of the classic
/// subtraction pass (no <c>&lt;...&gt;</c> hash placeholder, at least three tokens) protected nothing in lean, because the lean fit encodes the tones from the 77-bit
/// payload, never from the text. The fixture is a strong signal whose message carries a hash placeholder (a type-4 message built bit by bit, since the text encoder cannot pack a hash; the hashed call is not in a fresh process's table, so it renders
/// as <c>&lt;...&gt;</c>), and a much weaker message on the same carrier 125 ms later that round 0 cannot decode: the failed candidate is inside the strong signal's
/// patch window, so step 2e asks for the fit. Before the change no <c>SUB</c> row exists and the weak message is never found; after it, the strong signal is
/// subtracted in round 1 and the weak message is found there. Synthetic Q-prefix content only (NFR-021). No delay anywhere (TESTING_STRATEGY section 11).
/// </summary>
[Trait("Category", "RequiresNativeBinary")]
public sealed class LeanEnginePayloadFitTests(ITestOutputHelper output) : IDisposable
{
    private const string HashedCall = "Q1ABC";
    private const string OtherCall = "Q5XYZ/P";
    private const string ShortStrong = "CQ Q5XYZ/P";
    private const string Weak = "Q3GHI Q4JKL -07";
    private const int PcmSamples = 180_000;
    private const float StrongAmp = 0.10f;
    private const float WeakAmp = 0.04f;
    private const double CarrierHz = 1500.0;
    private const int StrongStart = 6_000;
    private const int WeakStart = 7_500;
    private const double NoiseSigma = 0.02;
    private const int NoiseSeed = 7;
    private const float PcmTargetRms = 0.20f;
    private const double SubFreqToleranceHz = 3.2;

    public void Dispose()
    {
        Ft8LibInterop.SetDecodeParams(10, 0.10f, 60);
        Ft8LibInterop.SetCqApEnabled(false);
        Ft8LibInterop.LeanShutdown();
    }

    private static byte[] SaveHashState()
    {
        var image = new byte[Ft8LibInterop.HashStateSize()];
        Ft8LibInterop.HashStateSave(image);
        return image;
    }

    /// <summary>Tones of a type-4 message: the first call as a 12-bit hash (never resolvable in a fresh process), the second as literal text.</summary>
    private static int[] HashedTones()
    {
        byte[] bits = TestFt8Encoder.PackType4HashReference(TestFt8Encoder.Compute12BitCode(HashedCall), OtherCall);
        return TestFt8Encoder.BitsToSymbols(TestFt8Encoder.LdpcEncode(TestFt8Encoder.AppendCrc14(bits)));
    }

    private static int[] TextTones(string message)
    {
        var t = new byte[79]; Ft8LibInterop.EncodeMessage(message, t);
        return t.Select(x => (int)x).ToArray();
    }

    private static float[] Synth(int[] strongTones, float weakAmp)
    {
        var a = TestFt8Encoder.SymbolsToPcm(strongTones, CarrierHz, StrongStart, StrongAmp);
        var t2 = new byte[79]; Ft8LibInterop.EncodeMessage(Weak, t2);
        var b = TestFt8Encoder.SymbolsToPcm(t2.Select(t => (int)t).ToArray(), CarrierHz, WeakStart, weakAmp);
        var rng = new Random(NoiseSeed);
        var pcm = new float[PcmSamples];
        for (int i = 0; i < PcmSamples; i++)
        {
            double u1 = 1.0 - rng.NextDouble(), u2 = 1.0 - rng.NextDouble();
            pcm[i] = a[i] + b[i] + (float)(NoiseSigma * Math.Sqrt(-2.0 * Math.Log(u1)) * Math.Cos(2.0 * Math.PI * u2));
        }
        return Ft8Decoder.NormalisePcm(pcm, PcmTargetRms);
    }

    private static LeanCycleOutcome Lean(float[] pcm, int threads = 2)
        => Ft8LibInterop.DecodeLeanCycle(pcm, new LeanCycleParams(threads, Rounds: true, Probe: true));

    private void AssertStrongIsFittedAndWeakIsFound(Func<int[]> strongTones, Func<string, bool> strongShowsAsExpected, string why)
    {
        // Encoding a hashed call may add it to the process-global hash table; restore the empty state before the decode so the hash cannot resolve.
        byte[] fresh = SaveHashState();
        float[] pcm = Synth(strongTones(), WeakAmp);
        Ft8LibInterop.HashStateRestore(fresh);

        var o = Lean(pcm);
        Ft8LibInterop.HashStateRestore(fresh);

        output.WriteLine("results: " + string.Join(" | ", o.Results.Select((r, i) => $"{r.FreqHz} Hz r{o.Rounds[i]} '{r.Message.TrimEnd()}'")));
        var subs = o.ProbeRows.Where(r => r.Kind == LeanProbe.Sub).ToArray();
        output.WriteLine("SUB rows: " + string.Join("; ", subs.Select(r => $"r{r.Round} {r.FreqHz:F1} Hz supp {r.SuppDb:F1} dB")));

        o.Stats.Error.Should().Be(LeanCycleStats.Ok);
        int strongAt = Array.FindIndex(o.Results, r => strongShowsAsExpected(r.Message.TrimEnd()));
        strongAt.Should().BeGreaterThanOrEqualTo(0, $"precondition: the strong signal decodes in round 0 and its text is {why}");
        o.Rounds[strongAt].Should().Be(0);

        subs.Should().Contain(r => Math.Abs(r.FreqHz - CarrierHz) <= SubFreqToleranceHz && r.Amp > 0f,
            $"a result whose text is {why} is fitted from its payload and a SUB row is written for it");
        o.Stats.Rounds[1].Fits.Should().BeGreaterThanOrEqualTo(1, "the round counts the fit");
        o.Stats.Rounds[1].Subtracted.Should().BeGreaterThanOrEqualTo(1);
        o.Results.Should().Contain(r => r.Message.TrimEnd() == Weak, "with the strong signal subtracted, round 1 finds the masked one");
    }

    [Fact(DisplayName = "FR-108: PAYLOAD-FIT test (a): a result whose text is a <...> hash placeholder is fitted from its payload: a SUB row and a counted fit, and the masked signal beneath it is found")]
    public void HashPlaceholderResult_IsFitted()
        => AssertStrongIsFittedAndWeakIsFound(HashedTones, m => m.Contains('<'), "a <...> hash placeholder");

    [Fact(DisplayName = "FR-108: PAYLOAD-FIT test (b): a result with fewer than three tokens is fitted from its payload too")]
    public void ShortResult_IsFitted()
        => AssertStrongIsFittedAndWeakIsFound(() => TextTones(ShortStrong), m => m.Split(' ', StringSplitOptions.RemoveEmptyEntries).Length < 3, "shorter than three tokens");
}
