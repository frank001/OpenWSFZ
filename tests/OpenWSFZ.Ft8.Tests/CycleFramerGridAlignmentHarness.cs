using System.Threading.Channels;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Deterministic simulation harness for <see cref="CycleFramer"/>'s UTC-grid alignment.
///
/// <para>
/// Shared by <c>CycleFramerClockDriftOracleTests</c>. Exists as its own file because the
/// oracle's credibility rests on it: the harness — not the assertions — is what makes the
/// difference between "the framer re-measured where it drifted to" and "the framer moved the
/// window back". See <c>dev-tasks/2026-08-02-reopen-cycleframer-clock-drift-still-present-
/// after-pr118.md</c> §4.2.
/// </para>
///
/// <para>
/// <b>Why not a plain <see cref="Channel"/> plus a manually-advanced clock?</b> The pre-existing
/// oracle drove the framer from a background task over an unbounded channel, advancing a
/// <see cref="FakeClock"/> in lock-step with whole 180 000-sample windows. That only stays
/// faithful while the framer consumes exactly 180 000 source samples per cycle — which is
/// precisely the behaviour under test. Once the framer starts varying its consumption, the
/// producer and the clock desynchronise from the framer's true read position and the simulated
/// wall clock becomes fiction. Both types below remove that failure mode by construction.
/// </para>
/// </summary>
internal static class GridAlignmentHarness
{
    /// <summary>
    /// Modulus applied to the source's per-sample index ramp so every marker stays exactly
    /// representable in a <see cref="float"/> (all integers below 2^24 are). 1 000 000 samples
    /// is ~83 s at 12 kHz — an order of magnitude more than the largest misalignment any of
    /// these tests produce (~4.2 s), so <see cref="UnwrapSampleIndex"/> can always resolve a
    /// marker back to its true global index without ambiguity.
    /// </summary>
    public const long MarkerModulus = 1_000_000;

    /// <summary>
    /// Recovers the true global source-sample index from a wrapped ramp marker, given a rough
    /// expectation of where it should be. Correct for any true index within
    /// ±<see cref="MarkerModulus"/>/2 of <paramref name="expected"/>.
    /// </summary>
    public static long UnwrapSampleIndex(long expected, float marker)
    {
        long delta = (((long)marker - expected) % MarkerModulus + MarkerModulus) % MarkerModulus;
        if (delta > MarkerModulus / 2)
        {
            delta -= MarkerModulus;
        }

        return expected + delta;
    }
}

/// <summary>
/// A synthetic capture device that produces samples at an arbitrary <em>effective</em> sample
/// rate, hands them to <see cref="CycleFramer"/> on demand, and drives a <see cref="FakeClock"/>
/// from its own production position.
///
/// <para>
/// <b>The clock is a consequence of production, not an input.</b> After every chunk handed over,
/// the clock is set to the instant that chunk's <em>last</em> sample was captured — which is when
/// a real capture callback delivers a buffer. The framer therefore reads a wall clock that is
/// genuinely consistent with the audio it is holding, at every point where it chooses to read
/// one, with no possibility of the simulation racing ahead of or behind the code under test.
/// </para>
///
/// <para>
/// Every sample carries its own global source index (modulo
/// <see cref="GridAlignmentHarness.MarkerModulus"/>) as its value. That ramp is the whole point:
/// it lets a test read, straight out of an emitted window's first sample, <em>which source
/// samples actually landed in that window</em>. An implementation that snaps the emitted
/// timestamp to the grid without moving the window cannot fake it.
/// </para>
/// </summary>
internal sealed class SimulatedCaptureDevice : ChannelReader<float[]>
{
    private readonly FakeClock _clock;
    private readonly DateTime  _originUtc;
    private readonly double    _effectiveHz;
    private readonly int       _chunkSamples;
    private readonly long      _totalSamples;

    private long _produced;
    private long _dropAtSample = -1;
    private long _dropSamples;
    private long _stepAtSample = -1;
    private TimeSpan _step;

    /// <param name="clock">Clock driven by this device; overwritten on every chunk handed out.</param>
    /// <param name="originUtc">True UTC instant at which source sample index 0 was captured.</param>
    /// <param name="effectiveHz">
    /// The device's real sample rate. 12 000 is nominal; the affected hardware measures
    /// 11 999.42 (48.4 ppm slow).
    /// </param>
    /// <param name="chunkSamples">
    /// Samples per delivered buffer. 2048 matches <c>WasapiAudioSource</c>'s read buffer and
    /// <c>ArecordAudioSource</c>/<c>SoxAudioSource</c>'s <c>ChunkBytes</c>, so the sub-chunk
    /// timing granularity the framer has to cope with here is the real one.
    /// </param>
    /// <param name="totalSamples">Production budget; the reader completes once exhausted.</param>
    public SimulatedCaptureDevice(
        FakeClock clock,
        DateTime  originUtc,
        double    effectiveHz,
        int       chunkSamples,
        long      totalSamples)
    {
        _clock        = clock;
        _originUtc    = originUtc;
        _effectiveHz  = effectiveHz;
        _chunkSamples = chunkSamples;
        _totalSamples = totalSamples;
        SyncClock();
    }

    /// <summary>True UTC instant at which source sample index 0 was captured.</summary>
    public DateTime OriginUtc => _originUtc;

    /// <summary>The device's real sample rate, in Hz.</summary>
    public double EffectiveHz => _effectiveHz;

    /// <summary>
    /// A step applied to the wall clock on top of the production position — an NTP correction,
    /// a sleep/resume, or a VM pause. Setting it does not change which samples exist; it changes
    /// what UTC the framer believes them to have been captured at, which is exactly what a clock
    /// step is.
    /// </summary>
    public TimeSpan ClockOffset { get; private set; } = TimeSpan.Zero;

    /// <summary>
    /// Schedules a system-clock step to be applied once production passes
    /// <paramref name="atSample"/>. No audio is gained or lost — only the UTC the framer
    /// believes it to have been captured at moves, which is exactly what an NTP correction,
    /// a sleep/resume, or a VM pause does.
    /// </summary>
    public void ScheduleClockStep(long atSample, TimeSpan step)
    {
        _stepAtSample = atSample;
        _step         = step;
    }

    /// <summary>
    /// Schedules a silent loss of <paramref name="samples"/> source samples once production
    /// passes <paramref name="atSample"/>. The device still <em>captures</em> them — real time
    /// passes and the sample-index ramp advances — they simply never reach the framer, which is
    /// what <c>WasapiAudioSource</c>'s warn-only buffer-overrun and channel-write-failure
    /// branches do in the field.
    /// </summary>
    public void ScheduleDrop(long atSample, long samples)
    {
        _dropAtSample = atSample;
        _dropSamples  = samples;
    }

    /// <summary>Total source samples the device has captured so far (delivered or dropped).</summary>
    public long ProducedSamples => _produced;

    /// <summary>
    /// The source-sample index at which a window covering the wall-clock instant
    /// <paramref name="gridLine"/> must begin, given this device's real production rate and any
    /// clock step in force.
    ///
    /// <para>
    /// Callers must pass a <b>UTC 15-second grid line</b>, not an emitted <c>CycleStart</c>.
    /// Passing the emitted label makes the quantity self-referential and identically zero on
    /// unfixed <c>main</c>, whose label truthfully reports the drifted open time — see
    /// <c>CycleFramerClockDriftOracleTests.SampleMisalignment</c>.
    /// </para>
    /// </summary>
    public double ExpectedFirstSampleIndex(DateTime gridLine)
        => ((gridLine - _originUtc).TotalSeconds - ClockOffset.TotalSeconds) * _effectiveHz;

    public override bool TryRead(out float[] item)
    {
        if (_produced >= _totalSamples)
        {
            item = null!;
            return false;
        }

        if (_stepAtSample >= 0 && _produced >= _stepAtSample)
        {
            ClockOffset  += _step;
            _stepAtSample = -1;
            SyncClock();
        }

        if (_dropAtSample >= 0 && _produced >= _dropAtSample)
        {
            // The dropped audio genuinely happened: the ramp advances and so does the clock.
            _produced    += _dropSamples;
            _dropAtSample = -1;
            SyncClock();

            if (_produced >= _totalSamples)
            {
                item = null!;
                return false;
            }
        }

        int n     = (int)Math.Min(_chunkSamples, _totalSamples - _produced);
        var chunk = new float[n];

        long marker = _produced % GridAlignmentHarness.MarkerModulus;
        for (int i = 0; i < n; i++)
        {
            chunk[i] = marker;
            if (++marker == GridAlignmentHarness.MarkerModulus)
            {
                marker = 0;
            }
        }

        _produced += n;
        SyncClock();

        item = chunk;
        return true;
    }

    public override ValueTask<bool> WaitToReadAsync(CancellationToken cancellationToken = default)
    {
        cancellationToken.ThrowIfCancellationRequested();
        return new ValueTask<bool>(_produced < _totalSamples);
    }

    private void SyncClock()
        => _clock.UtcNow = _originUtc.AddSeconds(_produced / _effectiveHz) + ClockOffset;
}

/// <summary>
/// Collects what each emitted window claims and what audio it actually contains, without
/// retaining the 720 KB PCM buffers — a 24 h simulation emits ~5 760 of them.
/// </summary>
internal sealed class WindowRecorder : ChannelWriter<(float[] Pcm, DateTime CycleStart, double? DialFrequencyMHz)>
{
    /// <summary>One entry per emitted window, in emission order.</summary>
    public List<RecordedWindow> Windows { get; } = new();

    public override bool TryWrite((float[] Pcm, DateTime CycleStart, double? DialFrequencyMHz) item)
    {
        Windows.Add(new RecordedWindow(
            CycleStart:      item.CycleStart,
            FirstSample:     item.Pcm[0],
            LastSample:      item.Pcm[^1],
            Length:          item.Pcm.Length,
            DialFrequencyMHz: item.DialFrequencyMHz));
        return true;
    }

    public override ValueTask<bool> WaitToWriteAsync(CancellationToken cancellationToken = default)
        => new(true);

    /// <summary>What one emitted window claimed, and the ramp markers at its two ends.</summary>
    /// <param name="CycleStart">The UTC instant the framer says this window began.</param>
    /// <param name="FirstSample">Ramp marker of the window's first sample — its true source index, wrapped.</param>
    /// <param name="LastSample">Ramp marker of the window's last sample (zero if the tail was padded).</param>
    /// <param name="Length">Emitted buffer length; must always be exactly 180 000.</param>
    /// <param name="DialFrequencyMHz">The dial-frequency snapshot carried with the window.</param>
    internal readonly record struct RecordedWindow(
        DateTime CycleStart,
        float    FirstSample,
        float    LastSample,
        int      Length,
        double?  DialFrequencyMHz);
}
