using System.Reflection;

namespace OpenWSFZ.Web;

/// <summary>
/// Returns the assembly version string for status and diagnostic output.
/// Prefers <see cref="AssemblyInformationalVersionAttribute"/> (carries the semantic
/// version from <c>&lt;Version&gt;</c> in the project file, itself read from the
/// repository-root <c>VERSION</c> file — see openspec/specs/release-versioning — and
/// survives AOT trimming) over the four-component assembly version. Not internal because
/// <see cref="OpenWSFZ.Daemon.WelcomeBannerEmitter"/>, in a different assembly, needs it too.
/// </summary>
public static class AssemblyVersion
{
    // Resolved once at startup. Custom attributes on the assembly are
    // preserved by the AOT trimmer by default — this is safe.
    private static readonly string s_version = Resolve();

    public static string Get() => s_version;

    private static string Resolve()
    {
        var informational = typeof(AssemblyVersion).Assembly
            .GetCustomAttribute<AssemblyInformationalVersionAttribute>()
            ?.InformationalVersion;

        if (informational is not null)
        {
            // Strip build metadata (everything after '+') — the full git SHA is noise
            // in an API response. The clean semver e.g. "0.30" is what clients expect.
            var plusIndex = informational.IndexOf('+');
            return plusIndex >= 0 ? informational[..plusIndex] : informational;
        }

        return typeof(AssemblyVersion).Assembly.GetName().Version?.ToString()
               ?? "0.0.0";
    }
}
