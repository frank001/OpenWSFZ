using OpenWSFZ.Web;

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
    /// The banner contains the loopback URL so the operator knows where to point their browser,
    /// and the running build's version (see <see cref="AssemblyVersion"/>, sourced from the
    /// repository-root <c>VERSION</c> file — the canonical source per openspec/specs/release-versioning).
    /// </summary>
    public static void Emit(int port)
    {
        Console.Out.WriteLine($"OpenWSFZ v{AssemblyVersion.Get()} listening on http://127.0.0.1:{port} — open this in your browser.");
    }
}
