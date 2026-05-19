namespace OpenWSFZ.Daemon;

/// <summary>
/// CLI-derived launch options for Phase 1.
/// Superseded by <c>IConfigSnapshot</c> in Phase 2 when the TOML config system lands;
/// <c>--port</c> will remain as a runtime override above config.
/// </summary>
internal sealed record LaunchOptions(int Port = 8080)
{
    /// <summary>
    /// Parses <paramref name="args"/> and returns a <see cref="LaunchOptions"/> instance.
    /// Recognised arguments:
    /// <list type="bullet">
    ///   <item><c>--port &lt;n&gt;</c> — bind port (default 8080)</item>
    /// </list>
    /// Unknown arguments are silently ignored (forward-compatible for Phase 2 args).
    /// </summary>
    public static LaunchOptions Parse(string[] args)
    {
        int port = 8080;

        for (int i = 0; i < args.Length - 1; i++)
        {
            if (args[i] == "--port" && int.TryParse(args[i + 1], out var p) && p is > 0 and < 65536)
            {
                port = p;
                i++;
            }
        }

        return new LaunchOptions(Port: port);
    }
}
