namespace LicenseInventoryCheck;

/// <summary>
/// Allowed SPDX licence identifiers for NuGet packages and native submodules.
/// Also handles SPDX-OR expressions — a package passes if at least one alternative is allowed.
/// </summary>
public static class LicencePolicy
{
    private static readonly HashSet<string> AllowedSpdx = new(StringComparer.OrdinalIgnoreCase)
    {
        "MIT",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "Apache-2.0",
        "CC0-1.0",
        "0BSD",
        "ISC",
        // PortAudio has its own bespoke permissive licence; identified by its SPDX-like name.
        "LicenseRef-PortAudio",
    };

    /// <summary>
    /// Returns <c>true</c> when <paramref name="spdxExpression"/> is allowed by project policy.
    /// Handles SPDX-OR expressions: "A OR B" passes when either A or B is allowed.
    /// </summary>
    public static bool IsAllowed(string spdxExpression)
    {
        if (string.IsNullOrWhiteSpace(spdxExpression))
        {
            return false;
        }

        // Split on " OR " (case-insensitive per SPDX spec) and check if any alternative is allowed.
        var parts = spdxExpression.Split(new[] { " OR " }, StringSplitOptions.RemoveEmptyEntries);
        return parts.Any(p => AllowedSpdx.Contains(p.Trim()));
    }

    /// <summary>
    /// Checks whether <paramref name="packageId"/> at <paramref name="version"/> violates
    /// the FluentAssertions pin policy (≥ 7.0 is blocked due to licence change).
    /// </summary>
    public static bool IsFluentAssertionsBlocked(string packageId, string version)
    {
        if (!packageId.Equals("FluentAssertions", StringComparison.OrdinalIgnoreCase))
        {
            return false;
        }

        return IsVersionAtLeast(version, 7, 0);
    }

    private static bool IsVersionAtLeast(string version, int major, int minor)
    {
        // Parse a simple "major.minor[.patch[.build]]" version string.
        var parts = version.Split('.');
        if (parts.Length < 2)
        {
            return false;
        }

        if (!int.TryParse(parts[0], out int maj))
        {
            return false;
        }

        if (!int.TryParse(parts[1], out int min))
        {
            return false;
        }

        return maj > major || (maj == major && min >= minor);
    }
}
