using FluentAssertions;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Audio;
using System.Diagnostics;
using System.Runtime.InteropServices;
using Xunit;

namespace OpenWSFZ.Audio.Tests;

// ── Test doubles ──────────────────────────────────────────────────────────────

/// <summary>
/// <see cref="IAudioSource"/> that yields chunks forever until the
/// <see cref="CancellationToken"/> is cancelled.
/// </summary>
internal sealed class InfiniteAudioSource : IAudioSource
{
    public int SampleRate   => 12_000;
    public int ChannelCount => 1;

    public async IAsyncEnumerable<float[]> CaptureAsync(
        string deviceId,
        [System.Runtime.CompilerServices.EnumeratorCancellation] CancellationToken ct)
    {
        while (!ct.IsCancellationRequested)
        {
            await Task.Delay(10, ct).ConfigureAwait(false);
            yield return new float[2048];
        }
    }

    public ValueTask DisposeAsync() => ValueTask.CompletedTask;
}

#if WASAPI_SUPPORTED
/// <summary>
/// Minimal <see cref="ILogger{T}"/> that records whether a Warning-or-higher
/// entry was emitted. Used in T-1 to verify enumeration failures are logged.
/// </summary>
internal sealed class CapturingLogger<T> : ILogger<T>
{
    public bool HasWarning { get; private set; }

    IDisposable? ILogger.BeginScope<TState>(TState state) => null;
    bool ILogger.IsEnabled(LogLevel logLevel) => true;

    void ILogger.Log<TState>(
        LogLevel logLevel,
        EventId eventId,
        TState state,
        Exception? exception,
        Func<TState, Exception?, string> formatter)
    {
        if (logLevel >= LogLevel.Warning)
            HasWarning = true;
    }
}
#endif

// ── CaptureManager unit tests ─────────────────────────────────────────────────

public sealed class CaptureManagerTests
{
    // Task 12.4
    [Fact(DisplayName = "FR-003: CaptureManager.IsCapturing is false before StartAsync")]
    public async Task IsCapturing_IsFalse_BeforeStartAsync()
    {
        await using var cm = new CaptureManager(new InfiniteAudioSource());
        cm.IsCapturing.Should().BeFalse(
            "no capture session has been started yet");
    }

    // Task 12.5
    [Fact(DisplayName = "FR-003: CaptureManager.IsCapturing is true after StartAsync, false after StopAsync")]
    public async Task IsCapturing_IsTrue_AfterStartAsync_AndFalse_AfterStopAsync()
    {
        await using var cm = new CaptureManager(new InfiniteAudioSource());

        await cm.StartAsync("test-device");

        cm.IsCapturing.Should().BeTrue(
            "capture was started with an infinite source");

        await cm.StopAsync();

        cm.IsCapturing.Should().BeFalse(
            "capture was explicitly stopped");
    }

    // B9 regression test
    [Fact(DisplayName = "B9: CaptureManager raises CaptureFailed when IAudioSource throws AudioCaptureException")]
    public async Task StartAsync_WhenSourceThrows_RaisesCaptureFailed()
    {
        // Arrange
        var exception = new AudioCaptureException("test-device", "device not found");
        await using var cm = new CaptureManager(new FaultyAudioSource(exception));

        var failureTcs = new TaskCompletionSource<Exception>(
            TaskCreationOptions.RunContinuationsAsynchronously);
        cm.CaptureFailed += ex => failureTcs.TrySetResult(ex);

        // Act
        await cm.StartAsync("test-device");

        // Assert — the event must fire and carry the original exception.
        var caughtEx = await failureTcs.Task.WaitAsync(TimeSpan.FromSeconds(5));

        caughtEx.Should().BeSameAs(exception,
            "CaptureFailed must surface the original exception to the subscriber");

        cm.IsCapturing.Should().BeFalse(
            "IsCapturing must be false once the capture task has faulted");
    }
}

// ── ArecordAudioSource unit tests ─────────────────────────────────────────────

public sealed class ArecordAudioSourceTests
{
    // Task 12.2
    [Fact(DisplayName = "FR-003: ArecordAudioSource yields chunks when subprocess produces valid FLOAT_LE output")]
    public async Task CaptureAsync_YieldsCorrectChunks_WhenSubprocessOutputsFloatLeBytes()
    {
        // Arrange: 2 048 floats of known values.
        const int ChunkFloats = 2048;
        var expected = new float[ChunkFloats];
        for (int i = 0; i < expected.Length; i++)
            expected[i] = (float)(i % 100) / 100f;

        // Write as FLOAT_LE bytes to a temp file.
        var tempFile = Path.GetTempFileName();
        try
        {
            var bytes = new byte[ChunkFloats * sizeof(float)];
            MemoryMarshal.AsBytes(expected.AsSpan()).CopyTo(bytes);
            await File.WriteAllBytesAsync(tempFile, bytes);

            // ArecordAudioSource with a factory that cats the temp file.
            var source = new ArecordAudioSource(_ => ArecordAudioSource.FilePipeStartInfo(tempFile));

            // Act: collect the first chunk.
            float[]? captured = null;
            using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(15));
            await foreach (var chunk in source.CaptureAsync("test-device", cts.Token))
            {
                captured = chunk;
                break; // we only need the first chunk
            }

            // Assert
            captured.Should().NotBeNull("at least one chunk must be yielded");
            var chunk0 = captured!;
            chunk0.Should().HaveCount(ChunkFloats);
            for (int i = 0; i < expected.Length; i++)
                chunk0[i].Should().BeApproximately(expected[i], precision: 1e-6f,
                    because: $"float at index {i} must match the raw bytes written");
        }
        finally
        {
            File.Delete(tempFile);
        }
    }

    // Task 12.3
    [Fact(DisplayName = "FR-003: ArecordAudioSource throws AudioCaptureException when process exits non-zero")]
    public async Task CaptureAsync_ThrowsAudioCaptureException_WhenProcessExitsNonZero()
    {
        // Arrange: stub that exits immediately with code 1.
        var source = new ArecordAudioSource(_ => ArecordAudioSource.FailingStartInfo());

        // Act & Assert: iterating must throw AudioCaptureException.
        var action = async () =>
        {
            await foreach (var _ in source.CaptureAsync("test-device", CancellationToken.None))
            {
                // should not yield any chunks
            }
        };

        await action.Should()
            .ThrowAsync<AudioCaptureException>(
                because: "arecord exiting non-zero signals a capture failure");
    }
}

/// <summary>
/// <see cref="IAudioSource"/> that throws a given exception on the first iteration.
/// Used to simulate device-not-found and other capture failures.
/// </summary>
internal sealed class FaultyAudioSource : IAudioSource
{
    private readonly Exception _exception;

    public int SampleRate   => 12_000;
    public int ChannelCount => 1;

    public FaultyAudioSource(Exception exception) => _exception = exception;

    public async IAsyncEnumerable<float[]> CaptureAsync(
        string deviceId,
        [System.Runtime.CompilerServices.EnumeratorCancellation] CancellationToken ct)
    {
        await Task.Yield(); // ensure the exception is thrown asynchronously
        throw _exception;
#pragma warning disable CS0162
        yield break;        // satisfies the compiler's async-enumerable requirement
#pragma warning restore CS0162
    }

    public ValueTask DisposeAsync() => ValueTask.CompletedTask;
}

// ── WasapiAudioDeviceProvider MTA thread test ─────────────────────────────────

// Task 12.1 — Windows-only: the fix is that enumeration works from an MTA thread.
public sealed class WasapiAudioDeviceProviderTests
{
    [Fact(DisplayName = "FR-003: WasapiAudioDeviceProvider.GetDevicesAsync succeeds when called from an MTA thread")]
    public async Task GetDevicesAsync_Succeeds_FromMtaThread()
    {
        if (!OperatingSystem.IsWindows())
        {
            // WASAPI is not available on non-Windows platforms — skip silently.
            return;
        }

        var tcs = new TaskCompletionSource<IReadOnlyList<OpenWSFZ.Abstractions.AudioDeviceInfo>>(
            TaskCreationOptions.RunContinuationsAsynchronously);

        // Explicitly create an MTA thread (thread-pool threads are MTA, but this makes it explicit).
        var mta = new Thread(async () =>
        {
            try
            {
                var provider = new PlatformAudioDeviceProvider();
                var devices  = await provider.GetDevicesAsync();
                tcs.SetResult(devices);
            }
            catch (Exception ex)
            {
                tcs.SetException(ex);
            }
        });
        mta.SetApartmentState(ApartmentState.MTA);
        mta.IsBackground = true;
        mta.Start();

        var act = async () => await tcs.Task;

        await act.Should()
            .NotThrowAsync(
                because: "GetDevicesAsync must not throw when called from an MTA thread — " +
                         "the STA fix ensures COM is initialised on the correct thread");
    }

    // T-1 — defect fix: enumeration failures must be logged, not silently swallowed.
    [Fact(DisplayName = "P4-Audio-T1: WasapiAudioDeviceProvider logs Warning and returns empty list when enumeration throws")]
    public async Task GetDevicesAsync_LogsWarningAndReturnsEmptyList_WhenEnumerationThrows()
    {
        if (!OperatingSystem.IsWindows())
            return; // WASAPI is not available on non-Windows platforms — skip silently.

#if WASAPI_SUPPORTED
        // Arrange: a logger that captures warning calls, plus a seam that simulates a COM failure.
        var capturingLogger = new CapturingLogger<WasapiAudioDeviceProvider>();
        var provider = new WasapiAudioDeviceProvider(
            capturingLogger,
            () => throw new InvalidOperationException("Simulated COM failure"));

        // Act
        var devices = await provider.GetDevicesAsync();

        // Assert
        devices.Should().BeEmpty(
            "no devices were collected before the exception was thrown");
        capturingLogger.HasWarning.Should().BeTrue(
            "a Warning must be logged so that WASAPI failures are visible in the application log");
#endif
    }
}
