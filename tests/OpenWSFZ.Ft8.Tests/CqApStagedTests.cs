using FluentAssertions;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Ft8.Interop;
using Xunit;
using Xunit.Abstractions;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// CQ-AP D3 / D6 through the whole staged decode (pass 0, the residual pass, the third pass, the coherent fallback and the late round) on the real
/// native library: the flag set once for the cycle reaches every native decode of it, the attempts of all of them are summed into the one
/// <c>cq-ap: attempts=N decodes=M</c> line, and a decode of any batch carries its tag. Q-prefix calls only (NFR-021); counts only.
/// </summary>
[Collection("subfeas-native-pool")]
[Trait("Category", "Integration")]
public sealed class CqApStagedTests(ITestOutputHelper output)
{
    private static readonly DateTime CycleStart = new(2026, 11, 10, 12, 0, 0, DateTimeKind.Utc);
    private const string Strong = "Q9XYZ Q8ABC JO22";
    private const string WeakCq = "CQ Q1ABC JO22";
    private const double NoiseSigma = 0.05;

    private sealed class CapturingLogger : ILogger<Ft8Decoder>
    {
        public List<string> Lines { get; } = [];
        public IDisposable? BeginScope<TState>(TState state) where TState : notnull => null;
        public bool IsEnabled(LogLevel logLevel) => true;
        public void Log<TState>(LogLevel logLevel, EventId eventId, TState state, Exception? exception, Func<TState, Exception?, string> formatter)
        {
            if (logLevel == LogLevel.Information) Lock(formatter(state, exception));
        }
        private void Lock(string s) { lock (Lines) Lines.Add(s); }
    }

    /// <summary>One cycle with a strong message (so the residual pass has something to subtract) and a weak CQ, in seeded noise.</summary>
    private static float[] Cycle(int seed, double weakSnrDb)
    {
        var pcm = new float[180_000];
        void Add(string message, double hz, double snrDb)
        {
            var tones = new byte[Ft8LibInterop.EncodedToneCount];
            Ft8LibInterop.EncodeMessage(message, tones);
            double amp = Math.Sqrt(2.0 * NoiseSigma * NoiseSigma * (2500.0 / 6000.0) * Math.Pow(10.0, snrDb / 10.0));
            var frame = TestFt8Encoder.SymbolsToPcm(tones.Select(t => (int)t).ToArray(), hz, 6_000, (float)amp);
            for (int i = 0; i < pcm.Length; i++) pcm[i] += frame[i];
        }
        Add(Strong, 800.0, -4.0);
        Add(WeakCq, 1600.0, weakSnrDb);
        var rng = new Random(seed);
        for (int i = 0; i < pcm.Length; i++)
        {
            double u1 = 1.0 - rng.NextDouble(), u2 = 1.0 - rng.NextDouble();
            pcm[i] += (float)(NoiseSigma * Math.Sqrt(-2.0 * Math.Log(u1)) * Math.Cos(2.0 * Math.PI * u2));
        }
        return Ft8Decoder.NormalisePcm(pcm, 0.20f);
    }

    private static async Task<(List<(int Batch, DecodeResult[] Decodes)> Batches, List<string> Lines)> RunStaged(float[] pcm, bool cqAp, DecodingDepth depth)
    {
        var log = new CapturingLogger();
        var decoder = new Ft8Decoder(new FakeClock(CycleStart), log);
        decoder.SetSubtractionEnabled(true);
        decoder.SetDecodingDepth(depth);
        decoder.SetCqApEnabled(cqAp);
        var batches = new List<(int, DecodeResult[])>();
        await decoder.DecodeStagedAsync(pcm, CycleStart, null, (n, b) =>
        {
            batches.Add((n, b.ToArray()));
            return Task.CompletedTask;
        });
        return (batches, log.Lines);
    }

    [Fact(DisplayName = "FR-103: CQ-AP D3/D6: staged and Deep, the flag reaches the residual and third-pass decodes - the line's attempts exceed pass 0's own, exactly one line is written, and OFF writes none")]
    public async Task FlagReachesEveryNativeDecode_AndOneLinePerCycle()
    {
        var pcm = Cycle(seed: 41, weakSnrDb: -20);

        // Pass 0 alone, same audio, on this thread: the attempts the residual and later decodes are added to.
        Ft8LibInterop.SetCqApEnabled(true);
        int pass0Attempts;
        try
        {
            Ft8LibInterop.DecodeAll(pcm);
            pass0Attempts = Ft8LibInterop.GetLastCqApStats().Attempts;
        }
        finally { Ft8LibInterop.SetCqApEnabled(false); }

        var (batches, lines) = await RunStaged(pcm, cqAp: true, DecodingDepth.Deep);
        var cqLines = lines.Where(l => l.Contains("cq-ap:")).ToList();
        cqLines.Should().ContainSingle("one Information line per cycle, written after the whole staged decode");

        var m = System.Text.RegularExpressions.Regex.Match(cqLines[0], @"cq-ap: attempts=(\d+) decodes=(\d+)");
        m.Success.Should().BeTrue(cqLines[0]);
        int attempts = int.Parse(m.Groups[1].Value), decodes = int.Parse(m.Groups[2].Value);
        output.WriteLine($"pass-0 attempts {pass0Attempts}; staged line: attempts={attempts} decodes={decodes}; batches {string.Join(",", batches.Select(b => $"{b.Batch}:{b.Decodes.Length}"))}");

        attempts.Should().BeGreaterThan(pass0Attempts, "the residual pass (and the third pass) ran their own CQ attempts: the flag travelled with the cycle");
        decodes.Should().Be(batches.SelectMany(b => b.Decodes).Count(d => d.ApKind == ApKind.Cq), "M is the decodes published, whatever batch they left in");

        var (_, offLines) = await RunStaged(pcm, cqAp: false, DecodingDepth.Deep);
        offLines.Should().NotContain(l => l.Contains("cq-ap"), "flag OFF: no new log line");
    }

    [Fact(DisplayName = "FR-103: CQ-AP D3: staged, flag OFF vs ON: every decode OFF publishes ON publishes too (extra, never instead), and OFF never carries a cq tag")]
    public async Task Staged_OnOnlyAdds()
    {
        int cqTagged = 0;
        for (int seed = 40; seed < 52; seed++)
        {
            var pcm = Cycle(seed, weakSnrDb: -20);
            var (offBatches, _) = await RunStaged(pcm, cqAp: false, DecodingDepth.Deep);
            var (onBatches, _) = await RunStaged(pcm, cqAp: true, DecodingDepth.Deep);

            var off = offBatches.SelectMany(b => b.Decodes).ToList();
            var on = onBatches.SelectMany(b => b.Decodes).ToList();
            off.Should().NotContain(d => d.ApKind != ApKind.None);
            foreach (string text in off.Select(d => d.Message))
                on.Select(d => d.Message).Should().Contain(text, $"seed {seed}: ON never loses a decode OFF makes");
            cqTagged += on.Count(d => d.ApKind == ApKind.Cq);
        }
        output.WriteLine($"cq-tagged decodes over 12 staged cycles: {cqTagged}");
        cqTagged.Should().BeGreaterThan(0, "at least one staged cycle must have been decoded by the CQ attempt, or the test proves nothing");
    }
}
