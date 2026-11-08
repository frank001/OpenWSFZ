using System.Text.Json.Serialization;

namespace OpenWSFZ.Abstractions;

/// <summary>
/// COH-FB-AUDIO: which audio the coherent fallback reads (<c>decoder.coherentFallbackAudio</c>). The candidate list (the snapshot) is the same in
/// every mode; only the PCM the fallback measures differs. Serialised as its name (<c>"Original"</c> / <c>"Residual"</c> / <c>"Both"</c>) via
/// <see cref="JsonStringEnumConverter{TEnum}"/>; the names are read case-insensitively, as the other decoder enums are.
/// </summary>
[JsonConverter(typeof(JsonStringEnumConverter<CoherentFallbackAudio>))]
public enum CoherentFallbackAudio
{
    /// <summary>The cycle's normalised input audio: the fallback exactly as it was before this key existed.</summary>
    Original = 0,

    /// <summary>
    /// The cycle's last residual buffer (decoded signals subtracted): the third pass's own buffer when it ran, else the residual pass's buffer,
    /// else (neither completed, or Normal depth) the original audio. The default.
    /// </summary>
    Residual = 1,

    /// <summary>
    /// The fallback runs on the original audio AND on the residual buffer (as for <see cref="Residual"/>), and the two result sets are merged
    /// by payload before selection and publication; where both found a payload the residual row is kept. When no residual buffer is
    /// available the original audio is run once.
    /// </summary>
    Both = 2,
}
