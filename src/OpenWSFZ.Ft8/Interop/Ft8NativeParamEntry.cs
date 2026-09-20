using System.Runtime.InteropServices;

namespace OpenWSFZ.Ft8.Interop;

/// <summary>
/// Mirror of the C <c>Ft8ParamEntry</c> struct from <c>ft8_shim.h</c> (decoder-param-readout,
/// shim 20260054): one row of the native decoder parameter table returned by
/// <c>ft8_get_decoder_params</c>.
///
/// Layout (must match <c>sizeof(Ft8ParamEntry)</c> = 72 bytes in the native shim, which the
/// shim itself asserts with a <c>_Static_assert</c>):
/// <code>
///   offset  0 : char   Name[48]     (NUL-terminated, zero-padded)
///   offset 48 : double Value        what the native decoder would use NOW
///   offset 56 : double DefaultValue the compiled-in default
///   offset 64 : int    Kind         0 = compile-time constant, 1 = runtime-settable
///   offset 68 : int    Reserved     0
///   total     : 72 bytes — no padding
/// </code>
/// </summary>
[StructLayout(LayoutKind.Sequential, CharSet = CharSet.Ansi)]
internal struct Ft8NativeParamEntry
{
    /// <summary>Capacity of the native <c>name</c> buffer, including the terminating NUL.</summary>
    public const int NameCapacity = 48;

    /// <summary><c>Kind</c> value of a compile-time constant (<c>FT8_PARAM_KIND_COMPILE_TIME</c>).</summary>
    public const int KindCompileTime = 0;

    /// <summary><c>Kind</c> value of a runtime-settable value (<c>FT8_PARAM_KIND_RUNTIME</c>).</summary>
    public const int KindRuntime = 1;

    /// <summary>
    /// The C struct <c>sizeof(Ft8ParamEntry)</c> = 72. Verified by
    /// <see cref="Ft8LibInterop.GetDecoderParams"/> before the table is read.
    /// </summary>
    public const int ExpectedNativeSizeBytes = 72;

    /// <summary>
    /// The parameter's native name: a runtime value's setter name (<c>osd_nhard_max</c>) or a
    /// compile-time constant's macro name (<c>K_MAX_CANDIDATES</c>).
    /// </summary>
    [MarshalAs(UnmanagedType.ByValTStr, SizeConst = NameCapacity)]
    public string Name;

    /// <summary>What the native decoder would use now. A float is widened exactly.</summary>
    public double Value;

    /// <summary>The compiled-in default; equal to <see cref="Value"/> for a compile-time entry.</summary>
    public double DefaultValue;

    /// <summary><see cref="KindCompileTime"/> or <see cref="KindRuntime"/>.</summary>
    public int Kind;

    /// <summary>Reserved; 0.</summary>
    public int Reserved;
}
