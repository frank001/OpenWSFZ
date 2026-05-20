namespace OpenWSFZ.Web;

/// <summary>Returns the assembly version string for use in status/diagnostic output.</summary>
internal static class AssemblyVersion
{
    public static string Get() =>
        typeof(AssemblyVersion).Assembly.GetName().Version?.ToString() ?? "0.0.0";
}
