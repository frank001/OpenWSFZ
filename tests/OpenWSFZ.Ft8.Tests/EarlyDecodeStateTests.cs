using FluentAssertions;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Ft8.Interop;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// decode-early-batch-panel (#122 step 4, phase 4a; FR-083), tasks 3.3 and 3.4: the early entry of <see cref="Ft8Decoder"/>
/// and the native save / restore of the process-global decode state (R4).
///
/// <para>
/// Two kinds of test. The <b>fake-interop</b> tests pin the managed bracket (what is called, in what order, and that the
/// restore runs when the native call throws). The <b>real-native</b> tests (A2b) drive the real <c>libft8</c>: they capture
/// the saved image of EVERY process-global the decode writes before an early decode, run the early decode on a window that
/// adds callsigns and moves counters, and assert the image after is <b>byte-identical</b>. They also prove, region by
/// region, that the restore really writes every region of the image back (a restore that omitted one global could not pass
/// the doctored-image test). Test-suite parallelism is disabled assembly-wide (<c>AssemblyInfo.cs</c>): the native state
/// is one process-global, so each real-native test restores the image it found before it returns.
/// </para>
/// </summary>
public sealed class EarlyDecodeStateTests
{
    // ── Fake interop that records the order of every call ─────────────────────

    private sealed class RecordingInterop : IFt8NativeInterop
    {
        public readonly List<string> Events = [];
        public Func<float[], Ft8NativeResult[]> OnDecodeAll = _ => [];
        public Exception? ThrowOnDecodeAll;
        public Exception? ThrowOnSave;
        public int AnalyticCalls;
        public int StateSize = 64;

        public int MaxDecodePasses => 2;

        public Ft8NativeResult[] DecodeAll(float[] pcm)
        {
            Events.Add("decode");
            if (ThrowOnDecodeAll is not null) throw ThrowOnDecodeAll;
            return OnDecodeAll(pcm);
        }

        public int[]  GetLastPassCounts(int maxPasses)      { Events.Add("passCounts"); return [0, 0]; }
        public int[]  GetLastCandidateCounts(int maxPasses) => [0, 0];
        public float  GetLastNoiseFloorDb()                  => -70.0f;
        public int    GetHashTableRejectCount()              => 0;
        public int GetH12DisplayingCount() => 0;
        public int GetH12AmbiguousCount()  => 0;
        public int GetH12DivergentCount()  => 0;
        public int GetH12SuppressedCount() => 0;
        public (float[] MeanAbs, float[] PrenormVariance, int[] FailCount) GetLastLlrStats(int maxPasses)
            => (new float[maxPasses], new float[maxPasses], new int[maxPasses]);

        public void SetApBits(byte[] mycallBits, byte[] hiscallBits) => Events.Add($"setAp:{mycallBits.Length}:{hiscallBits.Length}");
        public void SetDecodeParams(int kMinScorePass2, float osdCorrThreshold, int osdNhardMax) { }

        public (float DeltaFreqHz, float DeltaTimeS, float SyncScore, int CoarseDtSamp, int FineDtSamp) RefineCandidate(
            float[] pcm, int coarseFreqHz, float coarseTimeOffsetS) => (0f, 0f, 0f, 0, 0);

        public float[] CoherentLlrAt(float[] pcm, float freqHz, float timeOffsetS) => new float[174];

        public (float[] SignalDb, float[] LocalNoiseDb) GetLastSnrTerms(int maxDecoded)
            => (Array.Empty<float>(), Array.Empty<float>());

        public byte[] EncodeMessage(string message) => new byte[79];

        public (float[] Re, float[] Im) SubfeasComputeAnalytic(float[] pcm)
        {
            AnalyticCalls++;
            return (new float[180_000], new float[180_000]);
        }

        public (int ReturnCode, float[] Shat) SubfeasFitSignal(
            float[] xARe, float[] xAIm, byte[] tones, float decodedDtS, float decodedFreqHz, IntPtr cancelFlag)
            => (0, new float[180_000]);

        public int HashStateSize() => StateSize;

        public void HashStateSave(byte[] buffer)
        {
            Events.Add($"save:{buffer.Length}");
            if (ThrowOnSave is not null) throw ThrowOnSave;
        }

        public void HashStateRestore(byte[] buffer) => Events.Add($"restore:{buffer.Length}");
    }

    private sealed class ListLogger : ILogger<Ft8Decoder>
    {
        public readonly List<(LogLevel Level, string Text)> Lines = [];
        public IDisposable? BeginScope<TState>(TState state) where TState : notnull => null;
        public bool IsEnabled(LogLevel logLevel) => true;
        public void Log<TState>(LogLevel logLevel, EventId eventId, TState state, Exception? exception,
            Func<TState, Exception?, string> formatter) => Lines.Add((logLevel, formatter(state, exception)));
    }

    private static readonly Ft8NativeResult OneResult = new() { FreqHz = 1234, Dt = 0.2f, Snr = -5, Message = "Q1TST Q2TST JO33" };

    private static float[] LoudPcm()
    {
        var pcm = new float[180_000];
        Array.Fill(pcm, 0.1f);
        return pcm;
    }

    private static Ft8Decoder Build(IFt8NativeInterop interop, ILogger<Ft8Decoder>? logger = null)
        => new(new FakeClock(new DateTime(2026, 10, 3, 15, 0, 0, DateTimeKind.Utc)), logger, interop);

    private static readonly DateTime Cycle = new(2026, 10, 3, 15, 0, 0, DateTimeKind.Utc);

    // ── 3.3 managed bracket (fake interop) ────────────────────────────────────

    [Fact(DisplayName = "FR-083: 3.3a the early entry is pass 0 only: with the subtraction flag ON it runs no residual pass, while the ordinary decode does")]
    public async Task EarlyEntry_SubtractionOn_RunsNoResidualPass()
    {
        var interop = new RecordingInterop { OnDecodeAll = _ => [OneResult] };
        var decoder = Build(interop);
        decoder.SetSubtractionEnabled(true);

        var early = await decoder.DecodeEarlyAsync(LoudPcm(), Cycle, "40m");
        early.Should().ContainSingle();
        interop.AnalyticCalls.Should().Be(0, "the early entry never reads the flag and never runs SubtractionPass");

        // Control (HK-026): the same decoder and flag through the ordinary entry DOES run the residual pass, so the
        // zero above is the early entry's doing and not a fake that never reaches the pass.
        await decoder.DecodeAsync(LoudPcm(), Cycle, "40m");
        interop.AnalyticCalls.Should().BeGreaterThan(0);
    }

    [Fact(DisplayName = "FR-083: 3.3b the early entry brackets the native call: save, then set AP bits and decode in the same lambda, then restore")]
    public async Task EarlyEntry_BracketsTheNativeCall_InOrder()
    {
        var interop = new RecordingInterop { OnDecodeAll = _ => [OneResult], StateSize = 64 };
        await Build(interop).DecodeEarlyAsync(LoudPcm(), Cycle, null);

        interop.Events.Should().Equal("save:64", "setAp:0:0", "decode", "passCounts", "restore:64");
    }

    [Fact(DisplayName = "FR-083: 3.3c the restore runs when the native call throws, and the exception still propagates")]
    public async Task EarlyEntry_RestoreRunsWhenTheNativeCallThrows()
    {
        var interop = new RecordingInterop { ThrowOnDecodeAll = new InvalidOperationException("boom"), StateSize = 64 };
        var act = async () => await Build(interop).DecodeEarlyAsync(LoudPcm(), Cycle, null);

        await act.Should().ThrowAsync<InvalidOperationException>().WithMessage("boom");
        interop.Events.Should().Equal("save:64", "setAp:0:0", "decode", "restore:64");
    }

    [Fact(DisplayName = "FR-083: 3.3d a failed save restores nothing (there is no valid image to put back)")]
    public async Task EarlyEntry_FailedSave_NeverRestores()
    {
        var interop = new RecordingInterop { ThrowOnSave = new InvalidOperationException("no image"), StateSize = 64 };
        var act = async () => await Build(interop).DecodeEarlyAsync(LoudPcm(), Cycle, null);

        await act.Should().ThrowAsync<InvalidOperationException>().WithMessage("no image");
        interop.Events.Should().Equal("save:64");
    }

    [Fact(DisplayName = "FR-083: 3.3e the ordinary decode never saves or restores the state (its path is unchanged)")]
    public async Task OrdinaryDecode_NeverSavesOrRestores()
    {
        var interop = new RecordingInterop { OnDecodeAll = _ => [OneResult] };
        var decoder = Build(interop);
        await decoder.DecodeAsync(LoudPcm(), Cycle, "40m");
        await decoder.DecodeTwoStageAsync(LoudPcm(), Cycle, "40m", _ => Task.CompletedTask);

        interop.Events.Should().NotContain(e => e.StartsWith("save") || e.StartsWith("restore"));
    }

    [Fact(DisplayName = "FR-083: 3.3f the early entry writes none of the per-cycle Information lines (they would duplicate the Cycle lines log parsers read)")]
    public async Task EarlyEntry_WritesNoPerCycleInformationLine()
    {
        var logger  = new ListLogger();
        var decoder = Build(new RecordingInterop { OnDecodeAll = _ => [OneResult] }, logger);

        await decoder.DecodeEarlyAsync(LoudPcm(), Cycle, "40m");
        logger.Lines.Should().NotContain(l => l.Level == LogLevel.Information, "the early service writes its own one line");

        await decoder.DecodeAsync(LoudPcm(), Cycle, "40m");
        logger.Lines.Should().Contain(l => l.Level == LogLevel.Information && l.Text.Contains("decode(s) found"),
            "control: the ordinary decode still writes its Cycle line");
    }

    [Fact(DisplayName = "FR-083: 3.3g a silent early window decodes nothing and does not touch the native state")]
    public async Task EarlyEntry_SilentWindow_NeverReachesNative()
    {
        var interop = new RecordingInterop { OnDecodeAll = _ => [OneResult] };
        var results = await Build(interop).DecodeEarlyAsync(new float[180_000], Cycle, null);

        results.Should().BeEmpty();
        interop.Events.Should().BeEmpty();
    }

    // ── Real native: A2b ──────────────────────────────────────────────────────

    // Layout of the native image (ft8_shim.c, ft8_hash_state_image_t). Pinned here so the doctored-image test can reach
    // every region; ft8_hash_state_size() is asserted equal to the sum, so a field added to the image without an update
    // here fails.
    private static readonly (string Name, int Offset, int Length)[] ImageRegions =
    [
        ("g_session_hash_table",        0,       4096 * 20 + 4),
        ("g_hash_table_initialised",    81_924,  4),
        ("g_hash_table_reject_count",   81_928,  4),
        ("g_h12_announce_clock",        81_932,  4),
        ("g_h12_displaying",            81_936,  4),
        ("g_h12_ambiguous",             81_940,  4),
        ("g_h12_divergent",             81_944,  4),
        ("g_h12_suppressed",            81_948,  4),
        ("g_h12_code_out_of_range",     81_952,  4),
        ("g_h12_by_code_displaying",    81_956,  4096 * 4),
        ("g_h12_by_code_ambiguous",     98_340,  4096 * 4),
        ("g_h12_by_code_divergent",     114_724, 4096 * 4),
        ("g_h12_unresolved_by_code",    131_108, 4096 * 4),
    ];

    private static byte[] SaveImage()
    {
        var buf = new byte[Ft8LibInterop.HashStateSize()];
        Ft8LibInterop.HashStateSave(buf);
        return buf;
    }

    private static float[] BuildType4Pcm(string nonstandardCallsign, double freqHz)
    {
        byte[] bits = TestFt8Encoder.PackType4CqAnnounce(nonstandardCallsign);
        byte[] info = TestFt8Encoder.AppendCrc14(bits);
        byte[] cw   = TestFt8Encoder.LdpcEncode(info);
        return TestFt8Encoder.SymbolsToPcm(TestFt8Encoder.BitsToSymbols(cw), freqHz);
    }

    private static float[] BuildEncodedPcm(string message, double freqHz)
    {
        var tones = new byte[Ft8LibInterop.EncodedToneCount];
        Ft8LibInterop.EncodeMessage(message, tones);
        return TestFt8Encoder.SymbolsToPcm(tones.Select(t => (int)t).ToArray(), freqHz);
    }

    /// <summary>A window with a Type 4 announcement (adds a callsign to the hash table) and a Type 1 hash reference to it.</summary>
    private static float[] BuildStateMovingWindow(string callsign)
    {
        var a = BuildType4Pcm(callsign, 1_000.0);
        var b = BuildEncodedPcm($"Q1TST {callsign} JO33", 2_000.0);
        var sum = new float[a.Length];
        for (int i = 0; i < sum.Length; i++) sum[i] = a[i] + b[i];
        return sum;
    }

    /// <summary>The first <paramref name="keepSamples"/> samples of <paramref name="pcm"/>, zero after, as the framer's early window is.</summary>
    private static float[] ZeroTail(float[] pcm, int keepSamples)
    {
        var cut = (float[])pcm.Clone();
        Array.Clear(cut, keepSamples, cut.Length - keepSamples);
        return cut;
    }

    private static Ft8Decoder BuildReal() => new(new FakeClock(new DateTime(2026, 10, 3, 15, 0, 0, DateTimeKind.Utc)));

    [Fact(DisplayName = "FR-083: 3.4a the native image has the pinned size and the pinned regions cover it exactly")]
    public void NativeImage_SizeMatchesTheRegionTable()
    {
        int size = Ft8LibInterop.HashStateSize();
        size.Should().Be(ImageRegions.Sum(r => r.Length));
        ImageRegions.Zip(ImageRegions.Skip(1), (a, b) => a.Offset + a.Length == b.Offset).Should().AllBeEquivalentTo(true);
        (ImageRegions[^1].Offset + ImageRegions[^1].Length).Should().Be(size);
    }

    [Fact(DisplayName = "FR-083: 3.4b two saves of an unchanged state are byte-identical (padding is deterministic)")]
    public void TwoSaves_OfAnUnchangedState_AreByteIdentical()
        => SaveImage().Should().Equal(SaveImage());

    [Fact(DisplayName = "FR-083: 3.4c A2b: the saved image before an early decode equals the image after the restore, byte for byte, on a window that adds callsigns and moves counters")]
    public async Task A2b_StateRoundTrip_IsByteIdentical()
    {
        // Build the window FIRST: the TX encoder (ft8_encode_message) bumps the process-global announce clock, which is
        // part of the image, so an image captured before building would not be the state the decode starts from.
        var window = BuildStateMovingWindow("Q0ERLYZ");
        var early  = ZeroTail(window, 156_000);
        var original = SaveImage();
        try
        {
            var before = SaveImage();

            var results = await BuildReal().DecodeEarlyAsync(early, Cycle, null);
            results.Should().Contain(r => r.Message.Contains("Q0ERLYZ"),
                "the early decode must actually decode the announcement, or it has nothing to undo");

            SaveImage().Should().Equal(before, "the restore puts back every byte of every process-global the decode wrote");

            // Control (HK-026): an ORDINARY decode of the same window DOES change the image, so equality above is the
            // restore's doing and not a decode that never touched the state.
            await BuildReal().DecodeAsync(early, Cycle, null);
            SaveImage().Should().NotEqual(before, "an ordinary decode adds the callsign to the hash table");
        }
        finally
        {
            Ft8LibInterop.HashStateRestore(original);
        }
    }

    [Fact(DisplayName = "FR-083: 3.4d the restore writes every region of the image back: a doctored byte in any region sticks")]
    public void Restore_WritesEveryRegionBack()
    {
        var original = SaveImage();
        try
        {
            foreach (var (name, offset, length) in ImageRegions)
            {
                var doctored = (byte[])original.Clone();
                // The last byte of the region, XOR 1: stays a valid value in every region (a flag stays 0 or 1 in its low
                // byte; counters and table bytes are free).
                int at = offset + length - (name == "g_hash_table_initialised" ? 4 : 1);
                doctored[at] ^= 1;

                Ft8LibInterop.HashStateRestore(doctored);
                SaveImage().Should().Equal(doctored, $"region {name} must be restored from the image");
            }
        }
        finally
        {
            Ft8LibInterop.HashStateRestore(original);
        }
        SaveImage().Should().Equal(original);
    }

    [Fact(DisplayName = "FR-083: 3.4e a final decode after an early decode gives the same results and the same state as a final decode without it")]
    public async Task FinalDecode_AfterEarlyDecode_EqualsFinalDecodeWithoutIt()
    {
        var window = BuildStateMovingWindow("Q0ERLXZ");   // built first, see 3.4c
        var early  = ZeroTail(window, 156_000);
        var original = SaveImage();
        try
        {

            // Without an early decode.
            var without      = await BuildReal().DecodeAsync(window, Cycle, null);
            var imageWithout = SaveImage();

            // With one first, from the same starting state.
            Ft8LibInterop.HashStateRestore(original);
            await BuildReal().DecodeEarlyAsync(early, Cycle, null);
            var with      = await BuildReal().DecodeAsync(window, Cycle, null);
            var imageWith = SaveImage();

            with.Select(r => (r.Message, r.FreqHz, r.Snr)).Should().Equal(without.Select(r => (r.Message, r.FreqHz, r.Snr)));
            imageWith.Should().Equal(imageWithout);
        }
        finally
        {
            Ft8LibInterop.HashStateRestore(original);
        }
    }

    [Fact(DisplayName = "FR-083: 3.4f the native calls reject a wrong-sized buffer instead of overrunning it")]
    public void NativeCalls_RejectWrongSizedBuffers()
    {
        int size = Ft8LibInterop.HashStateSize();
        var tooSmall = () => Ft8LibInterop.HashStateSave(new byte[size - 1]);
        tooSmall.Should().Throw<InvalidOperationException>();
        var wrongLength = () => Ft8LibInterop.HashStateRestore(new byte[size - 1]);
        wrongLength.Should().Throw<InvalidOperationException>();
    }
}
