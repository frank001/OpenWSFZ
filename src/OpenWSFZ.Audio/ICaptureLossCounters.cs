namespace OpenWSFZ.Audio;

/// <summary>
/// Optional capability of an <see cref="OpenWSFZ.Abstractions.IAudioSource"/> that can observe
/// audio lost below the managed code (today only the <c>arecord</c> source, which reads the
/// child's stderr).  Sources that cannot observe such loss simply do not implement it and the
/// counters read 0.  Values are process-lifetime: a capture restart never resets them.
/// </summary>
internal interface ICaptureLossCounters
{
    /// <summary>Number of overrun reports received from the capture subprocess.</summary>
    long CaptureOverrunCount { get; }
}
