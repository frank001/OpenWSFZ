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
    /// <param name="port">The port Kestrel bound to.</param>
    /// <param name="isBackgroundWorker">
    /// <see langword="true"/> when this instance is running as a detached background worker
    /// (daemon-background-mode, <c>--background-worker</c>). A background worker's stdout is
    /// not guaranteed valid once it has detached from its inherited console — the banner write
    /// is skipped entirely (design.md Decision 6 / daemon-host's modified "Welcome banner on
    /// startup" requirement) rather than attempted and left to fail. Defaults to
    /// <see langword="false"/> so existing callers/tests are unaffected.
    /// </param>
    public static void Emit(int port, bool isBackgroundWorker = false)
    {
        if (isBackgroundWorker)
            return;

        Console.Out.WriteLine($"OpenWSFZ v{AssemblyVersion.Get()} listening on http://127.0.0.1:{port} — open this in your browser.");
    }
}
