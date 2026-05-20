namespace OpenWSFZ.Daemon;

/// <summary>
/// CLI-derived launch options parsed before host construction.
/// </summary>
internal sealed record LaunchOptions(int? Port = null, string? ConfigPath = null)
{
    /// <summary>
    /// Parses <paramref name="args"/> and returns a <see cref="LaunchOptions"/> instance.
    /// Recognised arguments:
    /// <list type="bullet">
    ///   <item><c>--port &lt;n&gt;</c> — bind port override (when absent, the persisted config value is used)</item>
    ///   <item><c>--config &lt;path&gt;</c> — override config file path (default: platform/env-var resolution)</item>
    /// </list>
    /// Unknown arguments are silently ignored (forward-compatible).
    /// </summary>
    public static LaunchOptions Parse(string[] args)
    {
        int?    port       = null;
        string? configPath = null;

        for (int i = 0; i < args.Length - 1; i++)
        {
            if (args[i] == "--port" && int.TryParse(args[i + 1], out var p) && p is > 0 and < 65536)
            {
                port = p;
                i++;
            }
            else if (args[i] == "--config" && !string.IsNullOrWhiteSpace(args[i + 1]))
            {
                configPath = args[i + 1];
                i++;
            }
        }

        return new LaunchOptions(Port: port, ConfigPath: configPath);
    }
}
