namespace OpenWSFZ.Daemon;

/// <summary>
/// Writes the welcome banner to stdout once the HTTP listener is ready.
/// Invoked from <see cref="Microsoft.Extensions.Hosting.IHostApplicationLifetime.ApplicationStarted"/>
/// in <c>Program.cs</c>.
/// </summary>
internal static class WelcomeBannerEmitter
{
    /// <summary>
    /// Writes the welcome banner for the given <paramref name="port"/> to stdout.
    /// The banner contains the loopback URL so the operator knows where to point their browser.
    /// </summary>
    public static void Emit(int port)
    {
        Console.Out.WriteLine($"OpenWSFZ listening on http://127.0.0.1:{port} — open this in your browser.");
    }
}
