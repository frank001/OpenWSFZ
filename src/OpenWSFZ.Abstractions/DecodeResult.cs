using System.Text.Json.Serialization;

namespace OpenWSFZ.Abstractions;

/// <summary>
/// Represents a single decoded FT8 message from one 15-second cycle.
/// </summary>
/// <param name="Time">UTC cycle start, formatted as <c>HH:mm:ss</c>.</param>
/// <param name="Snr">Signal-to-noise ratio in dB, relative to the 2500 Hz noise floor.</param>
/// <param name="Dt">Timing offset in seconds of the transmission within the cycle.</param>
/// <param name="FreqHz">Audio frequency offset in Hz of the strongest tone.</param>
/// <param name="Message">Decoded message text, or a 20-character hex string for unrecognised types.</param>
/// <param name="Region">
/// Advisory continent/entity region resolved from the message's primary
/// callsign-position token (<c>region-lookup</c> capability), or <c>null</c> on a
/// lookup miss, a missing/malformed <c>callsign-regions.json</c>, or when no
/// <see cref="ICallsignRegionStore"/> was supplied to the decoder. The frontend
/// renders <c>null</c> as <c>"Unknown"</c>. Never affects decode acceptance.
/// </param>
/// <param name="WorkedBefore">
/// Advisory, band-aware "worked before" state resolved from the message's primary
/// callsign-position token against the <c>ADIF.log</c> history
/// (<c>qso-confirmation</c>/<c>qso-confirmation-band-awareness</c> capabilities) across five
/// tri-state dimensions, or <c>null</c> when resolution fails or no
/// <see cref="IWorkedBeforeIndex"/> was supplied to the decoder — the frontend treats a
/// <c>null</c> field identically to <see cref="WorkedBeforeInfo.None"/> (every indicator
/// empty). Never affects decode acceptance.
/// </param>
/// <param name="Band">
/// The session's current active band this decode was made on (e.g. <c>"40m"</c>), using the
/// same naming convention as the Settings → Frequencies tab's Description column
/// (<c>qso-confirmation-band-awareness</c> capability's shared band-name table) — the exact
/// same value threaded into <see cref="IWorkedBeforeIndex.Resolve"/> as <c>currentBand</c> for
/// this same decode, so the Band column and the worked-before indicators on one row always
/// agree. <c>null</c> when the current band cannot be resolved (no CAT, no manual fallback
/// configured, or the resolved frequency falls outside all known amateur bands) — the frontend
/// renders <c>null</c> as an empty cell. Never affects decode acceptance.
/// </param>
public sealed record DecodeResult(
    string             Time,
    int                Snr,
    double             Dt,
    int                FreqHz,
    string             Message,
    RegionInfo?        Region       = null,
    WorkedBeforeInfo?  WorkedBefore = null,
    string?            Band         = null)
{
    /// <summary>
    /// COH-FALLBACK Stage 2 (R11): the decode's provenance, <c>0</c> = the ordinary pass 0 / pass 1, <c>1</c> = the residual or third
    /// pass, <c>2</c> = the coherent-extraction fallback. Internal metadata for the replay harness and the per-cycle log: it is
    /// <b>not serialised</b> (the decode panel, ALL.TXT and the UDP datagrams are unchanged) and is part of the record's equality.
    /// </summary>
    [JsonIgnore]
    public int Path { get; init; }

    /// <summary>
    /// The <see cref="Path"/> value of an XC-BUILD template decode (batch 6): a message inferred from a prior transmission and confirmed against this cycle's residual, not decoded from it.
    /// The decoder's own <c>Ft8Decoder.PathTemplate</c> is the same number (a test pins the equality); it lives here so the daemon (PSK Reporter) need not depend on a decoder internal.
    /// </summary>
    public const int PathTemplate = 3;

    /// <summary>
    /// CQ-AP: where the decode came from, <see cref="OpenWSFZ.Abstractions.ApKind.None"/> for every ordinary decode (always, with
    /// <c>decoder.cqApEnabled</c> off) and <see cref="OpenWSFZ.Abstractions.ApKind.Cq"/> for one the CQ a-priori attempt made. Internal metadata for the
    /// replay harness, the per-cycle log and the PSK Reporter exclusion: it is <b>not serialised</b> (the decode panel, ALL.TXT and the UDP datagrams are
    /// unchanged) and is part of the record's equality.
    /// </summary>
    [JsonIgnore]
    public ApKind ApKind { get; init; }
}
