namespace OpenWSFZ.Ft8.Interop;

/// <summary>
/// Thrown by <see cref="Ft8LibInterop.DecodeAll"/> when the native
/// <c>ft8_decode_all</c> SEH wrapper catches an access violation (return
/// code -2, Windows only).
///
/// <para>
/// <see cref="Ft8Decoder"/> catches this exception in <c>DecodeAsync</c>,
/// logs a WARNING with the cycle timestamp, and returns an empty result list
/// so the decode cycle is skipped gracefully without terminating the process.
/// Callers of <see cref="Ft8Decoder.DecodeAsync"/> never see this exception.
/// </para>
///
/// <para>
/// The access violation is caused by defect D-006 (root cause unknown; under
/// investigation).  The SEH wrapper is containment, not a fix; every
/// occurrence should be correlated with crash-dump evidence (WER LocalDumps
/// or ProcDump) to identify the faulting instruction.
/// </para>
/// </summary>
internal sealed class NativeAccessViolationException : Exception
{
    public NativeAccessViolationException()
        : base(
            "Access violation (0xC0000005) caught by the SEH wrapper in " +
            "ft8_decode_all (Windows only). The decode cycle is aborted; " +
            "the process continues.")
    { }
}
