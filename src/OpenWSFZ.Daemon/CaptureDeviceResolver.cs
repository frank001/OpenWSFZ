using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Daemon;

/// <summary>
/// The outcome kind of <see cref="CaptureDeviceResolver.Resolve"/> (capture-device-reresolution
/// #187, design.md Decision 1).
/// </summary>
public enum CaptureDeviceResolutionKind
{
    /// <summary>The configured ID is present in the enumerated devices and available — use it.</summary>
    UseConfigured,
    /// <summary>Exactly one available device's name matches the configured friendly name — adopt its ID.</summary>
    Adopt,
    /// <summary>Zero available devices match the configured friendly name.</summary>
    NotFound,
    /// <summary>Two or more available devices match the configured friendly name.</summary>
    Ambiguous,
    /// <summary>Enumeration returned nothing, or the configured friendly name is null.</summary>
    CannotResolve,
}

/// <summary>
/// The result of <see cref="CaptureDeviceResolver.Resolve"/>.
/// </summary>
/// <param name="Kind">Which outcome this is.</param>
/// <param name="NewId">
/// The adopted device's ID — set only when <paramref name="Kind"/> is
/// <see cref="CaptureDeviceResolutionKind.Adopt"/>.
/// </param>
/// <param name="MatchCount">
/// The number of available devices whose name matched the configured friendly name — 0 for
/// <see cref="CaptureDeviceResolutionKind.NotFound"/>, 1 for
/// <see cref="CaptureDeviceResolutionKind.Adopt"/>, ≥2 for
/// <see cref="CaptureDeviceResolutionKind.Ambiguous"/>. Meaningless (0) for
/// <see cref="CaptureDeviceResolutionKind.UseConfigured"/>/<see cref="CaptureDeviceResolutionKind.CannotResolve"/>.
/// </param>
public sealed record CaptureDeviceResolution(
    CaptureDeviceResolutionKind Kind,
    string? NewId = null,
    int MatchCount = 0);

/// <summary>
/// Resolves which capture device to use for an automatic capture start (capture-device-
/// reresolution #187, design.md Decisions 1 and 2). A pure function over an already-enumerated
/// device list — no I/O, no async — deliberately, so it is trivially table-tested.
///
/// <para>
/// Called before every <em>automatic</em> capture start (startup auto-start, restart after a
/// capture failure, watchdog restart) — never for an operator-initiated device change through
/// <c>POST /api/v1/config</c> (design's explicit non-goal: an ID the operator just set is never
/// re-resolved).
/// </para>
/// </summary>
public static class CaptureDeviceResolver
{
    /// <summary>
    /// Resolves <paramref name="configuredId"/>/<paramref name="configuredName"/> against
    /// <paramref name="devices"/> per design.md Decisions 1–2:
    /// <list type="bullet">
    /// <item><description>
    /// <see cref="CaptureDeviceResolutionKind.CannotResolve"/> when <paramref name="devices"/> is
    /// empty or <paramref name="configuredName"/> is <see langword="null"/> — there is nothing
    /// better to try than the configured ID unchanged.
    /// </description></item>
    /// <item><description>
    /// <see cref="CaptureDeviceResolutionKind.UseConfigured"/> when <paramref name="configuredId"/>
    /// is present in <paramref name="devices"/> and that entry's <see cref="AudioDeviceInfo.Available"/>
    /// is <see langword="true"/> — <strong>even if its current name differs from
    /// <paramref name="configuredName"/></strong>. An operator-chosen device is never
    /// second-guessed by name.
    /// </description></item>
    /// <item><description>
    /// Otherwise, matches every <em>available</em> device whose <see cref="AudioDeviceInfo.Name"/>
    /// is byte-for-byte (<see cref="StringComparison.Ordinal"/> — no trim, no case-fold, no
    /// substring) equal to <paramref name="configuredName"/>: exactly one match →
    /// <see cref="CaptureDeviceResolutionKind.Adopt"/> (that device's ID); zero →
    /// <see cref="CaptureDeviceResolutionKind.NotFound"/>; two or more →
    /// <see cref="CaptureDeviceResolutionKind.Ambiguous"/>. An unavailable (e.g. disabled) device
    /// is never counted as a match, even if its name matches exactly.
    /// </description></item>
    /// </list>
    /// </summary>
    public static CaptureDeviceResolution Resolve(
        string? configuredId,
        string? configuredName,
        IReadOnlyList<AudioDeviceInfo> devices)
    {
        if (devices.Count == 0 || configuredName is null)
            return new CaptureDeviceResolution(CaptureDeviceResolutionKind.CannotResolve);

        if (configuredId is not null)
        {
            foreach (var device in devices)
            {
                if (device.Available && string.Equals(device.Id, configuredId, StringComparison.Ordinal))
                    return new CaptureDeviceResolution(CaptureDeviceResolutionKind.UseConfigured);
            }
        }

        string? matchedId = null;
        var matchCount = 0;
        foreach (var device in devices)
        {
            if (device.Available && string.Equals(device.Name, configuredName, StringComparison.Ordinal))
            {
                matchCount++;
                matchedId = device.Id;
            }
        }

        return matchCount switch
        {
            0 => new CaptureDeviceResolution(CaptureDeviceResolutionKind.NotFound, MatchCount: 0),
            1 => new CaptureDeviceResolution(CaptureDeviceResolutionKind.Adopt, NewId: matchedId, MatchCount: 1),
            _ => new CaptureDeviceResolution(CaptureDeviceResolutionKind.Ambiguous, MatchCount: matchCount),
        };
    }
}
