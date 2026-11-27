using OpenWSFZ.Ft8.Interop;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Test-only base for the fakes of <see cref="IFt8NativeInterop"/> that do NOT model the lean engine. The interface has no default body for its four lean members (a changed
/// signature must fail to compile, not land on a silent default), so each fake either implements them itself or derives from this class, which says "not modelled" explicitly:
/// the decode methods throw, the shutdown is a no-op. A fake that runs the lean path must implement the members itself and never derive from this class.
/// A derived class lists the interface again (<c>: NonLeanInteropBase, IFt8NativeInterop</c>); the inherited public members implement it.
/// </summary>
internal abstract class NonLeanInteropBase
{
    private const string NotModelled = "This interop does not model the lean engine.";

    public LeanCycleOutcome DecodeLeanCycle(float[] pcm, LeanCycleParams request) => throw new NotSupportedException(NotModelled);

    public LeanCycleOutcome DecodeLeanCycle(float[] pcm, LeanCycleParams request, Action<LeanRound0>? onRound0) => throw new NotSupportedException(NotModelled);

    public LeanCycleOutcome DecodeLeanXcRound(float[] pcm, LeanCycleParams request, float[] residual, IReadOnlyList<LeanXcDetection> detections) => throw new NotSupportedException(NotModelled);

    public void LeanShutdown() { }
}
