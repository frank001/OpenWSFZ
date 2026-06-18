namespace OpenWSFZ.Ft8;

/// <summary>
/// Minimal interface for supplying AP bit constraints to the FT8 decoder (H6, D-001).
///
/// <para>
/// Implemented by <see cref="Ft8Decoder"/>. Extracted as an interface so that
/// <c>QsoAnswererService</c> (in <c>OpenWSFZ.Daemon</c>) can inject it without
/// taking a dependency on the concrete <see cref="Ft8Decoder"/> type.
/// </para>
/// </summary>
public interface IApConstraintSink
{
    /// <summary>
    /// Supplies AP bit constraints for the next decode cycle (H6 directed AP decode, D-001).
    /// Call before <see cref="Ft8Decoder.DecodeAsync"/> during active QSO states.
    /// Pass <c>null</c> to disable AP decode (the default; shim behaves as pre-20260020).
    /// </summary>
    void SetApConstraints(Ft8ApConstraints? constraints);
}
