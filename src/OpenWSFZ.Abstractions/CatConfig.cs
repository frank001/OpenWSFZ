namespace OpenWSFZ.Abstractions;

/// <summary>
/// CAT rig connection configuration (FR-031).
/// All fields have defaults so a partial or absent <c>cat</c> JSON key loads without error.
/// </summary>
public sealed record CatConfig
{
    /// <summary>
    /// Whether CAT polling is active. Default: <c>false</c>.
    /// When <c>false</c> no serial port or TCP connection is opened and
    /// the daemon behaves as if CAT did not exist (FR-034).
    /// </summary>
    public bool Enabled { get; init; } = false;

    /// <summary>
    /// Selects the transport implementation.
    /// Recognised values: <c>"SerialCat"</c> (direct serial) and <c>"RigCtld"</c> (TCP to rigctld).
    /// Unknown values log a Warning and disable CAT (FR-034).
    /// Default: <c>"SerialCat"</c>.
    /// </summary>
    public string RigModel { get; init; } = "SerialCat";

    /// <summary>
    /// Serial port name.
    /// Platform default: <c>COM6</c> on Windows, <c>/dev/ttyUSB0</c> on Linux,
    /// <c>/dev/cu.usbserial</c> on macOS.
    /// Used only when <see cref="RigModel"/> is <c>"SerialCat"</c>.
    /// </summary>
    public string SerialPort { get; init; } =
        OperatingSystem.IsWindows() ? "COM6" :
        OperatingSystem.IsMacOS()   ? "/dev/cu.usbserial" :
                                      "/dev/ttyUSB0";

    /// <summary>
    /// Serial port baud rate. Default: <c>9600</c>.
    /// Used only when <see cref="RigModel"/> is <c>"SerialCat"</c>.
    /// </summary>
    public int BaudRate { get; init; } = 9600;

    /// <summary>
    /// Hostname or IP address of the <c>rigctld</c> daemon. Default: <c>"127.0.0.1"</c>.
    /// Used only when <see cref="RigModel"/> is <c>"RigCtld"</c>.
    /// </summary>
    public string RigctldHost { get; init; } = "127.0.0.1";

    /// <summary>
    /// TCP port of the <c>rigctld</c> daemon. Default: <c>4532</c>.
    /// Used only when <see cref="RigModel"/> is <c>"RigCtld"</c>.
    /// </summary>
    public int RigctldPort { get; init; } = 4532;

    /// <summary>
    /// How often to query the rig in seconds. Range: 1–60. Default: <c>1</c>.
    /// Values outside the valid range are clamped with a Warning (FR-034).
    /// </summary>
    public int PollIntervalSeconds { get; init; } = 1;

    /// <summary>
    /// Last successfully-polled VFO-A frequency in MHz, persisted across restarts (FR-039).
    /// Written only by <c>CatPollingService</c>; never exposed as an editable UI field.
    /// <c>null</c> until at least one successful poll has been persisted.
    /// </summary>
    public double? LastPolledFrequencyMHz { get; init; } = null;
}
