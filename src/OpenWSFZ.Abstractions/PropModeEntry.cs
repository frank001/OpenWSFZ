namespace OpenWSFZ.Abstractions;

/// <summary>
/// Represents a single propagation mode entry in the operator's propagation mode list (qso-log-dialog).
/// </summary>
/// <param name="Protocol">
/// The digital mode this entry applies to, e.g. <c>"FT8"</c>.
/// Supports any protocol string so future modes can be added without schema changes.
/// </param>
/// <param name="Value">
/// The ADIF <c>PROP_MODE</c> field value, e.g. <c>"TR"</c>.
/// May be empty for the "Not specified" option.
/// </param>
/// <param name="Description">
/// A human-readable label, e.g. <c>"Tropospheric Ducting"</c>.
/// </param>
public sealed record PropModeEntry(
    string Protocol,
    string Value,
    string Description);
