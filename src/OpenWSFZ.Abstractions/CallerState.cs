namespace OpenWSFZ.Abstractions;

/// <summary>
/// States of the FT8 QSO caller state machine (qso-caller feature).
/// Used by <c>QsoCallerService</c>; the existing <see cref="QsoState"/> enum
/// (answerer states) is unchanged.
/// </summary>
public enum CallerState
{
    /// <summary>Listening; not calling CQ.</summary>
    Idle,

    /// <summary>Transmitting: <c>CQ {callsign} {grid}</c>.</summary>
    TxCq,

    /// <summary>Waiting for a station to respond to the CQ.</summary>
    WaitAnswer,

    /// <summary>Transmitting signal report: <c>{partner} {callsign} +00</c>.</summary>
    TxReport,

    /// <summary>Waiting for partner's <c>R+{report}</c> (to send RR73).</summary>
    WaitRr73,

    /// <summary>Transmitting: <c>{partner} {callsign} RR73</c>.</summary>
    TxRr73,

    /// <summary>QSO complete; writing ADIF record; transitioning back to Idle.</summary>
    QsoComplete,
}
