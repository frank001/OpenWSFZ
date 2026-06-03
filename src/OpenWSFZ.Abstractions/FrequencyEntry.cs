namespace OpenWSFZ.Abstractions;

/// <summary>
/// Represents a single working frequency entry in the operator's frequency list (FR-042).
/// </summary>
/// <param name="Protocol">
/// The digital mode this entry applies to, e.g. <c>"FT8"</c>.
/// Supports any protocol string so future modes can be added without schema changes.
/// </param>
/// <param name="FrequencyMHz">The VFO-A dial frequency in megahertz.</param>
/// <param name="Description">
/// A human-readable label for the frequency, e.g. <c>"40m"</c>. May be empty.
/// </param>
public sealed record FrequencyEntry(
    string Protocol,
    double FrequencyMHz,
    string Description);
