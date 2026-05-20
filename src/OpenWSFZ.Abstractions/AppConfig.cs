namespace OpenWSFZ.Abstractions;

/// <summary>
/// Operator configuration persisted to the config file.
/// Phase 2 schema: audio device selection and port.
/// Future phases will add FT8 parameters, UI preferences, etc.
/// </summary>
public sealed record AppConfig(
    string? AudioDeviceName = null,
    int     Port            = 8080);
