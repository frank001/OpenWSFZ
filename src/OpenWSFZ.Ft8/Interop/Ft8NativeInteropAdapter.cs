namespace OpenWSFZ.Ft8.Interop;

/// <summary>
/// Production implementation of <see cref="IFt8NativeInterop"/> that
/// delegates to the static <see cref="Ft8LibInterop"/> P/Invoke binding.
///
/// <para>
/// Sealed and stateless — safe to share as a static singleton.
/// </para>
/// </summary>
internal sealed class Ft8NativeInteropAdapter : IFt8NativeInterop
{
    public int MaxDecodePasses
        => Ft8LibInterop.MaxDecodePasses;

    /// <inheritdoc/>
    /// <exception cref="NativeAccessViolationException">
    /// Re-thrown from <see cref="Ft8LibInterop.DecodeAll"/> when the native
    /// shim's SEH wrapper catches an access violation.
    /// </exception>
    public Ft8NativeResult[] DecodeAll(float[] pcm)
        => Ft8LibInterop.DecodeAll(pcm);

    public int[] GetLastPassCounts(int maxPasses)
        => Ft8LibInterop.GetLastPassCounts(maxPasses);

    public float GetLastNoiseFloorDb()
        => Ft8LibInterop.GetLastNoiseFloorDb();
}
