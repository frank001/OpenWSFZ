using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Threading;
using System.Threading.Tasks;
using FluentAssertions;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Ft8;
using OpenWSFZ.Ft8.Interop;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Unit tests for the PCM-domain Successive Interference Cancellation (SIC) feature
/// introduced in fix-D001 (FT8_SHIM_VERSION = 20260003, K_MAX_PASSES = 3).
/// </summary>
public sealed class PcmSicTests
{
    // ── Task 8.1 — PCM buffer immutability ───────────────────────────────────

    /// <summary>
    /// Verifies that <c>ft8_decode_all</c> (via <see cref="Ft8LibInterop.DecodeAll"/>)
    /// does not mutate the caller's PCM buffer, even when multiple signals are decoded
    /// and the PCM-domain subtraction step is triggered.
    ///
    /// <para>
    /// The spec guarantees: "the original <c>pcm</c> argument SHALL be byte-identical
    /// before and after the call (verifiable by checksum over the 180 000 samples)."
    /// </para>
    /// </summary>
    [Fact(DisplayName = "fix-D001 8.1: DecodeAll does not mutate the input PCM buffer (checksum invariant)")]
    public void DecodeAll_MultiSignalFixture_DoesNotMutatePcmBuffer()
    {
        // Arrange — load the synthetic multi-signal fixture.
        float[] pcm = LoadFixtureWav("synth-qso-01.wav");
        pcm.Should().HaveCount(180_000, "fixture must be exactly 15 s × 12 kHz = 180 000 samples");

        // Compute a checksum of the input buffer BEFORE decode.
        double checksumBefore = ComputeChecksum(pcm);

        // Act — run the full native decode (direct P/Invoke, bypassing silence guard).
        _ = Ft8LibInterop.DecodeAll(pcm);

        // Assert — checksum is byte-identical after decode.
        double checksumAfter = ComputeChecksum(pcm);
        checksumAfter.Should().Be(checksumBefore,
            "ft8_decode_all must not write to the caller's PCM buffer — " +
            "the pcm_residual copy is internal to the native shim (Decision 6)");
    }

    // ── Task 8.2 — Three-pass counts sum to total ────────────────────────────

    /// <summary>
    /// Verifies that after a decode on a multi-signal fixture:
    /// <list type="bullet">
    ///   <item><see cref="Ft8LibInterop.GetLastPassCounts"/> returns an array of length 3.</item>
    ///   <item>The sum of the three per-pass counts equals the total returned by <see cref="Ft8LibInterop.DecodeAll"/>.</item>
    /// </list>
    ///
    /// <para>
    /// Both calls MUST be on the same thread — no <c>Task.Run</c> wrapper — because
    /// <c>ft8_get_last_pass_counts</c> reads from the TLS slot written by <c>ft8_decode_all</c>.
    /// </para>
    /// </summary>
    [Fact(DisplayName = "fix-D001 8.2: GetLastPassCounts(3) returns length 3 whose sum equals total decode count")]
    public void GetLastPassCounts_AfterDecodeOnMultiSignalFixture_ThreePassSumEqualsTotal()
    {
        // Arrange
        float[] pcm = LoadFixtureWav("synth-qso-01.wav");

        // Act — both calls on the SAME thread (no Task.Run).
        Ft8NativeResult[] results = Ft8LibInterop.DecodeAll(pcm);
        int[] counts = Ft8LibInterop.GetLastPassCounts(3);

        // Assert 1 — exactly 3 entries (K_MAX_PASSES = 3).
        counts.Should().HaveCount(3,
            "the native shim executes exactly K_MAX_PASSES = 3 passes; " +
            "GetLastPassCounts(3) must return an array of length 3");

        // Assert 2 — sum equals total result count.
        int sumOfCounts = counts.Sum();
        sumOfCounts.Should().Be(results.Length,
            "the per-pass new-decode counts must sum to the total number of " +
            "results returned by DecodeAll — a mismatch indicates a TLS accounting " +
            "regression or result-buffer overflow");
    }

    // ── Task 8.3 — Per-pass debug log messages ───────────────────────────────

    /// <summary>
    /// Verifies that <see cref="Ft8Decoder"/> logs exactly 3 Debug-level messages of the
    /// form <c>"Iterative subtraction: pass N of 3, K new decodes."</c> (N = 1, 2, 3)
    /// after each decode cycle.
    ///
    /// <para>
    /// The spec requirement: "the log output SHALL contain 3 messages matching the pattern
    /// <c>'Iterative subtraction: pass N of 3, K new decodes'</c> for N = 1, 2, 3."
    /// </para>
    /// </summary>
    [Fact(DisplayName = "fix-D001 8.3: Ft8Decoder logs exactly 3 'Iterative subtraction: pass N of 3' messages per cycle")]
    public async Task DecodeAsync_MultiSignalFixture_LogsThreePassMessagesAtDebug()
    {
        // Arrange
        float[] pcm    = LoadFixtureWav("synth-qso-01.wav");
        var     clock  = new FakeClock(new DateTime(2026, 6, 7, 0, 0, 0, DateTimeKind.Utc));
        var     logger = new CaptureLogger<Ft8Decoder>();
        var     decoder = new Ft8Decoder(clock, logger);

        // Act
        _ = await decoder.DecodeAsync(pcm, CancellationToken.None);

        // Assert — exactly 3 "Iterative subtraction: pass N of 3" messages at Debug level.
        var passMessages = logger.Messages
            .Where(m => m.message.Contains("Iterative subtraction: pass", StringComparison.Ordinal)
                     && m.message.Contains("of 3", StringComparison.Ordinal)
                     && m.level == LogLevel.Debug)
            .ToList();

        passMessages.Should().HaveCount(3,
            "Ft8Decoder must log one Debug message per pass (3 passes total); " +
            $"actual Debug messages: [{string.Join(" | ", logger.Messages.Where(m => m.level == LogLevel.Debug).Select(m => m.message))}]");

        // Verify the 3 messages carry N = 1, 2, 3 respectively.
        for (int n = 1; n <= 3; n++)
        {
            string expectedFragment = $"pass {n} of 3";
            passMessages.Should().Contain(
                m => m.message.Contains(expectedFragment, StringComparison.Ordinal),
                $"log message for pass {n} of 3 must be present");
        }
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private static float[] LoadFixtureWav(string wavFileName)
    {
        Assembly asm     = Assembly.GetExecutingAssembly();
        string   asmName = asm.GetName().Name!;
        string   fullName = $"{asmName}.Fixtures.{wavFileName}";

        Stream? stream = asm.GetManifestResourceStream(fullName);
        if (stream is null)
        {
            stream = asm.GetManifestResourceNames()
                .Where(n => n.EndsWith(wavFileName, StringComparison.OrdinalIgnoreCase))
                .Select(n => asm.GetManifestResourceStream(n))
                .FirstOrDefault(s => s is not null);
        }

        if (stream is null)
            throw new InvalidOperationException(
                $"Embedded WAV resource '{fullName}' not found. " +
                $"Available: [{string.Join(", ", asm.GetManifestResourceNames())}]");

        using (stream)
            return WavReader.Read(stream);
    }

    private static double ComputeChecksum(float[] pcm)
    {
        double sum = 0.0;
        for (int i = 0; i < pcm.Length; i++)
            sum += pcm[i] * (i + 1.0); // weighted sum to catch single-element changes
        return sum;
    }

    // ── Simple capture logger ─────────────────────────────────────────────────

    private sealed class CaptureLogger<T> : ILogger<T>
    {
        private readonly List<(LogLevel level, string message)> _messages = new();

        public IReadOnlyList<(LogLevel level, string message)> Messages => _messages;

        public IDisposable? BeginScope<TState>(TState state) where TState : notnull => null;

        public bool IsEnabled(LogLevel logLevel) => true; // capture all levels

        public void Log<TState>(
            LogLevel              logLevel,
            EventId               eventId,
            TState                state,
            Exception?            exception,
            Func<TState, Exception?, string> formatter)
        {
            _messages.Add((logLevel, formatter(state, exception)));
        }
    }
}
