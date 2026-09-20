using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Web;

/// <summary>
/// Returned by <c>GET /api/v1/decoder/params</c> (<c>decoder-param-readout</c> capability, shim
/// 20260054): the native decoder's whole parameter table, read from the native library on every
/// request.
/// </summary>
/// <param name="ShimVersion">
/// The native library's own ABI sentinel (<c>ft8_lib_version_check</c>) as read at startup — the
/// same value <see cref="DaemonStatus.ShimVersion"/> reports.
/// </param>
/// <param name="Entries">
/// Every decoder parameter, runtime-settable first, in the native table's order. Never empty: an
/// unavailable native library is a 503, not an empty list.
/// </param>
public sealed record DecoderParamsResponse(int ShimVersion, DecoderParamEntry[] Entries);
