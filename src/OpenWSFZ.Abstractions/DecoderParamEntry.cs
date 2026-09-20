namespace OpenWSFZ.Abstractions;

/// <summary>
/// One row of the native decoder's parameter table (<c>decoder-param-readout</c> capability,
/// shim 20260054): a decoder parameter as the native library itself reports it.
/// </summary>
/// <remarks>
/// This is a <b>readout</b>. <see cref="Value"/> is what the native decoder would use now, which is
/// not necessarily what <c>app.json</c> says: the daemon applies <c>DecoderConfig</c> to the
/// native library at startup and on every settings change, and the native library is the only
/// authority on what it is actually running with. Showing <see cref="Value"/> beside
/// <see cref="Default"/> is the point of the feature (a harness running the compiled default
/// <c>osd_nhard_max</c> 60 while the live app runs 40 went unnoticed across several
/// experiments).
/// </remarks>
/// <param name="Name">
/// The native name: a runtime value's lower-case setter name (<c>osd_nhard_max</c>), or a
/// compile-time constant's macro name (<c>K_MAX_CANDIDATES</c>).
/// </param>
/// <param name="Kind">
/// <see cref="DecoderParamKind.Runtime"/> or <see cref="DecoderParamKind.CompileTime"/>.
/// </param>
/// <param name="Value">
/// What the native decoder would use now. For a float parameter this is the shortest decimal that
/// round-trips the float (0.1, not 0.10000000149011612), so the operator sees the number that was set.
/// </param>
/// <param name="Default">
/// The compiled-in default. Equal to <paramref name="Value"/> for a compile-time constant.
/// </param>
public sealed record DecoderParamEntry(string Name, string Kind, double Value, double Default);

/// <summary>The two values <see cref="DecoderParamEntry.Kind"/> can take, as they appear on the wire.</summary>
public static class DecoderParamKind
{
    /// <summary>Settable at run time (the value can differ from the compiled-in default).</summary>
    public const string Runtime = "runtime";

    /// <summary>A constant the decode path reads; it can only change by rebuilding the native library.</summary>
    public const string CompileTime = "compile-time";
}
