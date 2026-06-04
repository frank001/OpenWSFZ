using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Rig;

/// <summary>
/// Creates <see cref="IRadioConnection"/> instances based on the configured
/// <see cref="CatConfig.RigModel"/> string (FR-031).
///
/// <para>
/// Recognised values:
/// <list type="bullet">
///   <item><c>"SerialCat"</c> → <see cref="SerialCatConnection"/></item>
///   <item><c>"RigCtld"</c>  → <see cref="RigctldConnection"/></item>
/// </list>
/// </para>
/// </summary>
public static class RigModelFactory
{
    /// <summary>
    /// Creates an <see cref="IRadioConnection"/> appropriate for the supplied config.
    /// </summary>
    /// <param name="config">CAT configuration (must be non-null).</param>
    /// <param name="loggerFactory">
    /// Optional logger factory; when supplied, serial I/O bytes are emitted at Debug level
    /// for <c>SerialCat</c> connections.
    /// </param>
    /// <returns>A new, not-yet-connected <see cref="IRadioConnection"/>.</returns>
    /// <exception cref="ArgumentException">
    /// <paramref name="config"/>.<see cref="CatConfig.RigModel"/> is not a recognised value.
    /// </exception>
    public static IRadioConnection Create(CatConfig config, ILoggerFactory? loggerFactory = null)
    {
        ArgumentNullException.ThrowIfNull(config);

        return config.RigModel switch
        {
            "SerialCat" => new SerialCatConnection(
                               config.SerialPort, config.BaudRate,
                               loggerFactory?.CreateLogger<SerialCatConnection>()),
            "RigCtld"   => new RigctldConnection(config.RigctldHost, config.RigctldPort),
            _           => throw new ArgumentException(
                               $"Unknown rigModel '{config.RigModel}'. " +
                               "Recognised values: \"SerialCat\", \"RigCtld\".",
                               nameof(config)),
        };
    }
}
