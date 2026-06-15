namespace OpenWSFZ.Daemon;

/// <summary>
/// Immutable value type capturing the data logged at the end of a completed QSO (FR-048).
///
/// <para>
/// All times are UTC.  <see cref="DialFrequencyMHz"/> of <c>0.0</c> indicates that no
/// radio frequency is known; <see cref="AdifLogWriter"/> omits the FREQ and BAND fields
/// when this value is zero.
/// </para>
/// </summary>
public readonly record struct QsoRecord
{
    /// <summary>Callsign of the contacted station (partner).</summary>
    public string  PartnerCallsign  { get; init; }

    /// <summary>Maidenhead grid locator of the contacted station, or <c>null</c> if unknown.</summary>
    public string? PartnerGrid      { get; init; }

    /// <summary>
    /// RST report sent to the partner (FT8 dB offset notation, e.g. <c>"+00"</c>).
    /// </summary>
    public string  RstSent          { get; init; }

    /// <summary>
    /// RST report received from the partner (FT8 dB offset notation, e.g. <c>"+05"</c>).
    /// </summary>
    public string  RstRcvd          { get; init; }

    /// <summary>UTC timestamp when the QSO began (first TX keyed).</summary>
    public DateTime QsoStartUtc     { get; init; }

    /// <summary>UTC timestamp when the QSO ended (73 sent).</summary>
    public DateTime QsoEndUtc       { get; init; }

    /// <summary>Operator's callsign (from <c>tx.callsign</c>).</summary>
    public string  OperatorCallsign { get; init; }

    /// <summary>Operator's grid locator (from <c>tx.grid</c>).</summary>
    public string  OperatorGrid     { get; init; }

    /// <summary>
    /// Radio dial frequency in MHz at the time of the QSO (from <c>decodeLog.dialFrequencyMHz</c>).
    /// <c>0.0</c> means unknown — FREQ and BAND fields are omitted from the ADIF record.
    /// </summary>
    public double  DialFrequencyMHz { get; init; }
}
