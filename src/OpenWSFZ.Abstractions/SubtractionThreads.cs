namespace OpenWSFZ.Abstractions;

/// <summary>
/// Resolves <see cref="DecoderConfig.SubtractionMaxThreads"/> to the effective number of residual-pass fit
/// workers (sub-feas-speed-redesign A4). One pure function, shared by the decoder (per cycle) and by
/// <c>POST /api/v1/config</c> (clamp-with-warning), so the two can never disagree.
/// </summary>
public static class SubtractionThreads
{
    /// <summary>Logical processors kept free for capture, the web UI and a co-resident WSJT-X in auto mode.</summary>
    public const int AutoReservedProcessors = 2;

    /// <summary>
    /// The effective worker count for <paramref name="configured"/> on a machine with
    /// <paramref name="processorCount"/> logical processors: <c>0</c> is auto, <c>max(1, processorCount - 2)</c>;
    /// any other value is clamped to <c>[1, processorCount]</c>.
    /// </summary>
    /// <param name="configured">The configured value (<c>0</c> when the key is absent).</param>
    /// <param name="processorCount">Logical processor count (values below 1 are treated as 1).</param>
    /// <param name="wasClamped"><c>true</c> when a non-zero value had to be moved into range.</param>
    public static int Resolve(int configured, int processorCount, out bool wasClamped)
    {
        int cpus = Math.Max(1, processorCount);
        wasClamped = false;
        if (configured == 0)
            return Math.Max(1, cpus - AutoReservedProcessors);

        int clamped = Math.Clamp(configured, 1, cpus);
        wasClamped = clamped != configured;
        return clamped;
    }
}
