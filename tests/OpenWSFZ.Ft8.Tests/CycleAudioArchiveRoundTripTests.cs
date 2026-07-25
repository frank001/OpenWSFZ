using System;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Threading;
using System.Threading.Tasks;
using FluentAssertions;
using OpenWSFZ.Daemon;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Integration test for the <c>cycle-audio-archive</c> capability's central promise (tasks 7.1,
/// 7.2; spec.md scenario "Archived audio decodes back to the same messages"): a decode cycle's
/// PCM window, written to disk by <see cref="CycleWavWriter"/> and read back, must decode to
/// exactly the same message set as the original in-memory window — and the written file must
/// satisfy the same format contract the existing offline harness (<c>rewindow.py</c>,
/// <c>D001ParamSweep</c>) already asserts (mono, 12 kHz, 16-bit, exactly 180 000 frames).
///
/// <para>
/// Uses the committed <c>synth-qso-01</c> fixture (also used by <see cref="RealSignalFixtureTests"/>,
/// the G6 gate) as the source PCM rather than hand-building a fresh signal with
/// <see cref="TestFt8Encoder"/> — <see cref="Ft8DecoderFixtureTests"/>'s own remarks note that
/// <c>TestFt8Encoder</c>'s <c>PackType1</c> payload (i3=0) is rejected by the native decoder for
/// correctness purposes, so it is unsuitable as a "must actually decode" source here. The fixture
/// is already known-decodable (G6), removing that uncertainty entirely.
/// </para>
///
/// <para>
/// Lives in <c>OpenWSFZ.Ft8.Tests</c> rather than <c>OpenWSFZ.Daemon.Tests</c>: this project
/// already project-references <c>OpenWSFZ.Daemon</c> (for <see cref="CycleWavWriter"/>, a public
/// type — no <c>InternalsVisibleTo</c> needed) and already carries <see cref="WavReader"/> and the
/// synthetic fixtures needed for a real, known-good decode.
/// </para>
/// </summary>
public sealed class CycleAudioArchiveRoundTripTests : IDisposable
{
    private readonly string _tempWavPath;

    public CycleAudioArchiveRoundTripTests()
    {
        _tempWavPath = Path.Combine(
            Path.GetTempPath(), "openwsfz-cycle-archive-roundtrip-" + Path.GetRandomFileName() + ".wav");
    }

    public void Dispose()
    {
        try { File.Delete(_tempWavPath); } catch { /* best-effort */ }
    }

    [Fact(DisplayName =
        "cycle-audio-archive: archived audio decodes back to the same messages as the in-memory window (tasks 7.1, 7.2)")]
    public async Task ArchivedAudio_DecodesBackToSameMessages_AsInMemoryWindow()
    {
        // ── Load a known-decodable source window (same fixture RealSignalFixtureTests/G6 uses) ──
        float[] pcm = LoadEmbeddedWav("Fixtures/synth-qso-01.wav");

        var clock   = new FakeClock(new DateTime(2026, 5, 28, 23, 57, 45, DateTimeKind.Utc));
        var decoder = new Ft8Decoder(clock);

        var inMemoryResults = await decoder.DecodeAsync(pcm, CancellationToken.None);
        inMemoryResults.Should().NotBeEmpty(
            "the synth-qso-01 fixture is a known-decodable signal — this test is meaningless if it decodes to nothing");

        // ── Archive it exactly as CycleArchiveService's writer task would ────────────────────
        var (bytes, clippedSamples) = CycleWavWriter.Encode(pcm);
        clippedSamples.Should().Be(0, "the fixture audio is well within [-1, 1] and must not clip");

        await File.WriteAllBytesAsync(_tempWavPath, bytes);

        // ── task 7.2: format contract — the exact assertions rewindow.py/D001ParamSweep make ──
        // WavReader.Read throws InvalidDataException unless the file is mono/12 kHz/16-bit PCM,
        // so successfully reading it back is itself part of the format assertion.
        float[] readBackPcm = WavReader.Read(_tempWavPath);
        readBackPcm.Should().HaveCount(180_000,
            "the archive format contract requires exactly 180 000 sample frames per file");

        // ── task 7.1: decode the read-back file and compare message sets ────────────────────
        var readBackResults = await decoder.DecodeAsync(readBackPcm, CancellationToken.None);

        var inMemoryMessages = inMemoryResults.Select(r => r.Message).OrderBy(m => m, StringComparer.Ordinal).ToList();
        var readBackMessages = readBackResults.Select(r => r.Message).OrderBy(m => m, StringComparer.Ordinal).ToList();

        readBackMessages.Should().Equal(inMemoryMessages,
            "archiving to a WAV file and reading it back must be lossless enough that the decoder " +
            "recovers exactly the same message set as decoding the original in-memory window");
    }

    // ── Helpers (mirrors RealSignalFixtureTests' embedded-resource loading) ─────────────────

    private static float[] LoadEmbeddedWav(string resourceSuffix)
    {
        using Stream stream = OpenEmbeddedResource(resourceSuffix);
        return WavReader.Read(stream);
    }

    private static Stream OpenEmbeddedResource(string resourceSuffix)
    {
        Assembly asm     = typeof(CycleAudioArchiveRoundTripTests).Assembly;
        string   asmName = asm.GetName().Name!;
        string   resourceName = $"{asmName}.{resourceSuffix.Replace('/', '.')}";

        Stream? stream = asm.GetManifestResourceStream(resourceName);
        if (stream is null)
        {
            string[] allNames = asm.GetManifestResourceNames();
            stream = allNames
                .Where(n => n.EndsWith(resourceSuffix.Replace('/', '.'), StringComparison.OrdinalIgnoreCase))
                .Select(n => asm.GetManifestResourceStream(n))
                .FirstOrDefault(s => s is not null);
        }

        return stream
               ?? throw new InvalidOperationException(
                   $"Embedded resource '{resourceName}' not found. " +
                   $"Available: [{string.Join(", ", asm.GetManifestResourceNames())}]");
    }
}
