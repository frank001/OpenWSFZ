using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Daemon;

/// <summary>
/// No-op <see cref="IPttController"/> used on non-Windows platforms where WASAPI is
/// unavailable.  All operations log at Debug level and complete immediately.
/// </summary>
public sealed class NullPttController : IPttController
{
    private readonly ILogger<NullPttController> _logger;

    public NullPttController(ILogger<NullPttController> logger)
        => _logger = logger;

    public void LoadAudio(float[] samples)
        => _logger.LogDebug("NullPttController.LoadAudio: {Samples} samples (no-op on non-Windows).",
            samples.Length);

    public Task KeyDownAsync(CancellationToken ct = default)
    {
        _logger.LogDebug("NullPttController.KeyDownAsync: no-op on non-Windows platform.");
        return Task.CompletedTask;
    }

    public Task KeyUpAsync(CancellationToken ct = default)
    {
        _logger.LogDebug("NullPttController.KeyUpAsync: no-op on non-Windows platform.");
        return Task.CompletedTask;
    }

    public ValueTask DisposeAsync() => ValueTask.CompletedTask;
}
