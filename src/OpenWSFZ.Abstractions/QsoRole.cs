namespace OpenWSFZ.Abstractions;

/// <summary>
/// The role currently active in the QSO controller.
/// Exposed via <see cref="IQsoController.Role"/> so the web layer can include it in
/// API responses and WebSocket events.
/// </summary>
public enum QsoRole
{
    /// <summary>The answerer role (<c>QsoAnswererService</c>).</summary>
    Answerer,

    /// <summary>The caller role (<c>QsoCallerService</c>).</summary>
    Caller,
}
