namespace OpenWSFZ.Ft8.Subfeas;

/// <summary>
/// coh-fb-residual: chooses which audio the coherent fallback reads.
///
/// <para>
/// <b>REPLAY ONLY. Not a user setting, never merged.</b> The probe asks whether the coherent fallback confirms more
/// candidates when it reads the cycle's last residual buffer (decoded signals subtracted) instead of the original
/// audio. It is read from the environment variable <see cref="EnvironmentVariable"/> once, when an
/// <see cref="Ft8Decoder"/> is constructed; it is never a config key and never read per cycle.
/// </para>
///
/// <list type="bullet">
/// <item><b>Active</b> only for the exact value <c>residual</c> (ordinal, case-sensitive). Unset, empty, <c>RESIDUAL</c>,
/// <c>1</c> or anything else: inactive and silent, behaviour exactly as before.</item>
/// <item>The candidate snapshot is untouched: only the PCM handed to the fallback differs.</item>
/// </list>
/// </summary>
internal static class CohFallbackAudio
{
    /// <summary>Name of the replay-only environment variable.</summary>
    internal const string EnvironmentVariable = "OPENWSFZ_COHFB_AUDIO";

    /// <summary>The one value that activates the switch.</summary>
    internal const string ResidualValue = "residual";

    /// <summary>Log label: the fallback read the original (normalised) audio, switch off.</summary>
    internal const string LabelOriginal = "original";

    /// <summary>Log label: the fallback read the third pass's own subtracted buffer (third-pass outcome <c>ran</c>).</summary>
    internal const string LabelResidual3 = "residual3";

    /// <summary>Log label: the fallback read the residual pass's buffer (no third-pass buffer was usable).</summary>
    internal const string LabelResidual2 = "residual2";

    /// <summary>Log label: the switch was set but there was no usable residual buffer, so the original audio was read.</summary>
    internal const string LabelResidualUnavailable = "residual-unavailable";

    /// <summary>True only for the exact value <see cref="ResidualValue"/> (ordinal).</summary>
    internal static bool IsActive(string? raw) => string.Equals(raw, ResidualValue, StringComparison.Ordinal);

    /// <summary>
    /// Picks the PCM the fallback reads, and the <c>audio=</c> log label. The returned buffer is only ever read by the
    /// caller (it is the decoder's own array, not a copy): it must not be mutated or pooled while the fallback runs.
    /// </summary>
    /// <param name="active">The construction-time switch (<see cref="IsActive"/>).</param>
    /// <param name="original">The cycle's normalised PCM (what the fallback reads on <c>main</c>).</param>
    /// <param name="deep">The cycle ran at Deep depth (only Deep keeps a residual report).</param>
    /// <param name="report">The residual pass's report; <c>null</c> on Normal depth.</param>
    /// <param name="third">The third pass's result; <c>null</c> when the third pass did not get as far as running.</param>
    /// <returns>
    /// Preference: (a) the third pass's own subtracted copy when it <c>ran</c> (fitted and subtracted something, not
    /// abandoned, not failed); else (b) the residual pass's buffer. Unavailable (original audio, label
    /// <see cref="LabelResidualUnavailable"/>) when not Deep, no report, the residual pass was abandoned or failed, its
    /// buffer is missing, or it fitted nothing.
    /// </returns>
    internal static (float[] Buffer, string Label) Select(
        bool active,
        float[] original,
        bool deep,
        SubtractionPass.ResidualPassReport? report,
        SubtractionPass.ThirdPassResult? third)
    {
        if (!active) return (original, LabelOriginal);

        if (!deep
            || report is null
            || report.DeadlineAbandoned
            || report.ContainedException
            || report.Residual is null
            || report.FittedSignals == 0)
            return (original, LabelResidualUnavailable);

        if (third is { Outcome: SubtractionPass.ThirdPassOutcome.Ran, Residual: { } thirdBuffer })
            return (thirdBuffer, LabelResidual3);

        return (report.Residual, LabelResidual2);
    }
}
