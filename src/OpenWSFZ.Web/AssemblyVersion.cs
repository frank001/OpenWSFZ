using System.Reflection;

namespace OpenWSFZ.Web;

/// <summary>
/// Returns the assembly version string for status and diagnostic output.
/// Prefers <see cref="AssemblyInformationalVersionAttribute"/> (carries the semantic
/// version from <c>&lt;Version&gt;</c> in the project file and survives AOT trimming)
/// over the four-component assembly version.
/// </summary>
internal static class AssemblyVersion
{
    // Resolved once at startup. Custom attributes on the assembly are
    // preserved by the AOT trimmer by default — this is safe.
    private static readonly string s_version = Resolve();

    public static string Get() => s_version;

    private static string Resolve() =>
        typeof(AssemblyVersion).Assembly
            .GetCustomAttribute<AssemblyInformationalVersionAttribute>()
            ?.InformationalVersion
        ?? typeof(AssemblyVersion).Assembly.GetName().Version?.ToString()
        ?? "0.0.0";
}
