namespace OpenWSFZ.Abstractions;

/// <summary>
/// The exchange point at which to engage a QSO mid-sequence (D-CALLER-012).
/// Used by <see cref="IQsoController.EngageAtAsync"/>.
/// </summary>
public enum EngagePoint
{
    /// <summary>
    /// Reply to a plain signal report: TX <c>PARTNER OURS R+00</c> → enter WaitRr73.
    /// Used when the decode carries a bare signal report (e.g. <c>PD2FZ W1ABC -07</c>).
    /// </summary>
    SendReport = 1,

    /// <summary>
    /// Confirm a roger-report or RRR: TX <c>PARTNER OURS RR73</c> → QsoComplete.
    /// Used when the decode carries <c>R±NN</c> or <c>RRR</c>
    /// (e.g. <c>PD2FZ W1ABC R-07</c>, <c>PD2FZ W1ABC RRR</c>).
    /// </summary>
    SendRr73 = 2,

    /// <summary>
    /// Send the final 73: TX <c>PARTNER OURS 73</c> → QsoComplete.
    /// Used when the decode carries <c>RR73</c>
    /// (e.g. <c>PD2FZ W1ABC RR73</c>).
    /// </summary>
    Send73 = 3,
}
