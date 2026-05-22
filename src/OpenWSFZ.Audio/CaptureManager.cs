using System.Threading.Channels;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Audio;

/// <summary>
/// Manages the lifecycle of a single audio capture session.
/// Wraps an <see cref="IAudioSource"/> and exposes a <see cref="ChannelReader{T}"/>
/// that Phase 5 (FT8 decoder) consumes.
/// </summary>
public sealed class CaptureManager : IAsyncDisposable
{
    private readonly IAudioSource _source;
    private readonly Channel<float[]> _channel;

    private CancellationTokenSource? _cts;
    private Task? _captureTask;
    private volatile bool _isCapturing;

    /// <summary>True while a capture session is actively running.</summary>
    /// <remarks>
    /// <para>
    /// This flag may briefly read <c>true</c> even when no audio is flowing.
    /// <see cref="StartAsync"/> sets the flag synchronously before the background
    /// capture task begins; if <see cref="IAudioSource.CaptureAsync"/> throws before
    /// yielding any chunks (e.g. device not found or <see cref="AudioCaptureException"/>),
    /// there is a short window where <c>IsCapturing == true</c> but no data is being
    /// produced. The flag self-corrects to <c>false</c> once the <c>finally</c> block
    /// in the capture task executes.
    /// </para>
    /// <para>
    /// Phase 5 consumers must not treat <c>IsCapturing == true</c> as a guarantee that
    /// chunks will be delivered to <see cref="Samples"/>.
    /// </para>
    /// </remarks>
    public bool IsCapturing => _isCapturing;

    /// <summary>
    /// Raised when the capture session terminates abnormally (device not found,
    /// device disconnected, or any other unrecoverable error).
    /// Invoked on a thread-pool thread; subscribers must be thread-safe.
    /// </summary>
    public event Action<Exception>? CaptureFailed;

    /// <summary>
    /// A reader over the live PCM sample channel.
    /// The channel is bounded (capacity 16) with <c>DropOldest</c> overflow
    /// so the capture thread never blocks even when the consumer stalls.
    /// </summary>
    public ChannelReader<float[]> Samples => _channel.Reader;

    public CaptureManager(IAudioSource source)
    {
        _source = source;
        _channel = Channel.CreateBounded<float[]>(new BoundedChannelOptions(16)
        {
            FullMode     = BoundedChannelFullMode.DropOldest,
            SingleWriter = true,
            SingleReader = false,
        });
    }

    /// <summary>
    /// Stops any running capture session and starts a new one for
    /// <paramref name="deviceId"/>.
    /// </summary>
    public async Task StartAsync(string deviceId, CancellationToken ct = default)
    {
        await StopAsync();

        _cts = CancellationTokenSource.CreateLinkedTokenSource(ct);
        var linkedCt = _cts.Token;

        // Mark as capturing before the task starts so callers can observe
        // IsCapturing == true immediately after StartAsync returns.
        _isCapturing = true;

        _captureTask = Task.Run(async () =>
        {
            try
            {
                await foreach (var chunk in _source.CaptureAsync(deviceId, linkedCt))
                {
                    await _channel.Writer.WriteAsync(chunk, linkedCt);
                }
            }
            catch (OperationCanceledException) when (linkedCt.IsCancellationRequested)
            {
                // Normal shutdown — swallow.
            }
            catch (Exception ex)
            {
                // Device not found, device disconnected, or any other capture failure.
                // Surface via event; the finally block still resets IsCapturing.
                CaptureFailed?.Invoke(ex);
            }
            finally
            {
                _isCapturing = false;
            }
        });
    }

    /// <summary>
    /// Cancels the active capture session and waits for it to drain
    /// (up to 2 seconds). Safe to call when no session is running.
    /// </summary>
    public async Task StopAsync()
    {
        var cts = _cts;
        if (cts is null) return;

        cts.Cancel();

        var task = _captureTask;
        if (task is not null)
        {
            try
            {
                await task.WaitAsync(TimeSpan.FromSeconds(2));
            }
            catch (TimeoutException) { }
            catch (OperationCanceledException) { }
            catch (Exception) { }
        }

        cts.Dispose();
        _cts         = null;
        _captureTask = null;
        _isCapturing = false;
    }

    /// <inheritdoc/>
    public async ValueTask DisposeAsync()
    {
        await StopAsync();
        _channel.Writer.TryComplete();
    }
}
