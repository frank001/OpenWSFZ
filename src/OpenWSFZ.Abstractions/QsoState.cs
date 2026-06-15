namespace OpenWSFZ.Abstractions;

/// <summary>
/// States of the FT8 QSO answerer state machine (FR-047).
/// </summary>
public enum QsoState
{
    /// <summary>Listening; ready to answer a CQ.</summary>
    Idle,

    /// <summary>Transmitting the initial answer: <c>PARTNER OURS GRID</c>.</summary>
    TxAnswer,

    /// <summary>Waiting for the partner's signal report.</summary>
    WaitReport,

    /// <summary>Transmitting the roger report: <c>PARTNER OURS R+00</c>.</summary>
    TxReport,

    /// <summary>Waiting for the partner's RR73 or RRR.</summary>
    WaitRr73,

    /// <summary>Transmitting 73: <c>PARTNER OURS 73</c>.</summary>
    Tx73,

    /// <summary>QSO complete; writing ADIF record; transitioning back to Idle.</summary>
    QsoComplete,
}
