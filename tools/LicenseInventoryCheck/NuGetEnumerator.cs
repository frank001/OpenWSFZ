using System.Text.Json;
using System.Xml.Linq;

namespace LicenseInventoryCheck;

/// <summary>
/// Enumerates NuGet dependencies (direct and transitive) by reading
/// each project's <c>obj/project.assets.json</c>.
/// </summary>
public static class NuGetEnumerator
{
    /// <summary>
    /// Maps well-known legacy <c>licenseUrl</c> values (GitHub blobs / raw URLs that
    /// pre-date the <c>licenses.nuget.org</c> convention) to their SPDX identifiers.
    /// Keyed by case-insensitive URL prefix so minor path variations (e.g., casing,
    /// trailing slash) are still caught.
    /// </summary>
    private static readonly (string UrlPrefix, string Spdx)[] KnownLicenceUrls =
    [
        // dotnet/corefx (and dotnet/runtime successor) — MIT
        ("https://github.com/dotnet/corefx/blob/master/LICENSE",         "MIT"),
        ("https://github.com/dotnet/runtime/blob/master/LICENSE",        "MIT"),
        ("https://raw.githubusercontent.com/dotnet/corefx/master/LICENSE", "MIT"),
        // xunit — Apache-2.0
        ("https://raw.githubusercontent.com/xunit/xunit/master/license", "Apache-2.0"),
        ("https://github.com/xunit/xunit/blob/master/license",           "Apache-2.0"),
        // NuGet client libs — Apache-2.0
        ("https://raw.githubusercontent.com/NuGet/NuGet.Client/dev/LICENSE.txt", "Apache-2.0"),
    ];

    /// <summary>
    /// Walks <paramref name="solutionRoot"/> for <c>project.assets.json</c> files.
    /// Throws <see cref="InvalidOperationException"/> when none are found (restore not run).
    /// </summary>
    public static IReadOnlyList<DependencyEntry> Enumerate(string solutionRoot)
    {
        var assetFiles = Directory
            .EnumerateFiles(solutionRoot, "project.assets.json", SearchOption.AllDirectories)
            .Where(p => p.Contains(Path.DirectorySeparatorChar + "obj" + Path.DirectorySeparatorChar))
            .ToList();

        if (assetFiles.Count == 0)
        {
            throw new InvalidOperationException(
                "No project.assets.json files were found under the solution root. " +
                "Run 'dotnet restore' before invoking LicenseInventoryCheck.");
        }

        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var entries = new List<DependencyEntry>();

        foreach (var assetFile in assetFiles)
        {
            ParseAssetsFile(assetFile, seen, entries);
        }

        return entries;
    }

    private static void ParseAssetsFile(
        string assetFile, HashSet<string> seen, List<DependencyEntry> entries)
    {
        using var stream = File.OpenRead(assetFile);
        using var doc = JsonDocument.Parse(stream);

        // Collect package cache folders so we can find .nuspec files.
        var packageFolders = new List<string>();
        if (doc.RootElement.TryGetProperty("packageFolders", out var foldersEl))
        {
            foreach (var folder in foldersEl.EnumerateObject())
            {
                packageFolders.Add(folder.Name);
            }
        }

        if (!doc.RootElement.TryGetProperty("libraries", out var libs))
        {
            return;
        }

        foreach (var prop in libs.EnumerateObject())
        {
            // key is "PackageName/1.2.3"
            var slash = prop.Name.IndexOf('/');
            if (slash < 0)
            {
                continue;
            }

            var name = prop.Name[..slash];
            var version = prop.Name[(slash + 1)..];
            var key = $"{name}/{version}";

            if (!seen.Add(key))
            {
                continue;
            }

            // Only care about "package" type (not "project").
            if (prop.Value.TryGetProperty("type", out var typeEl) &&
                typeEl.GetString() is not "package")
            {
                continue;
            }

            // 1. Try licenseExpression embedded in the assets file (modern packages).
            string licence = "unknown";
            if (prop.Value.TryGetProperty("licenseExpression", out var licEl) &&
                licEl.GetString() is string lic && !string.IsNullOrWhiteSpace(lic))
            {
                licence = lic;
            }
            else
            {
                // 2. Fall back to reading the .nuspec from the package cache.
                //    Handles both modern <license type="expression"> and legacy
                //    <licenseUrl>https://licenses.nuget.org/SPDX-ID</licenseUrl>.
                licence = TryReadLicenceFromNuspec(name, version, packageFolders)
                          ?? "unknown";
            }

            entries.Add(new DependencyEntry(
                Name: name,
                Version: version,
                Licence: licence,
                Kind: DependencyKind.NuGet,
                Provenance: assetFile));
        }
    }

    /// <summary>
    /// Attempts to read the SPDX licence expression for a package from its
    /// <c>.nuspec</c> file in the NuGet package cache.
    /// Handles modern <c>&lt;license type="expression"&gt;</c> elements and
    /// the legacy <c>&lt;licenseUrl&gt;https://licenses.nuget.org/SPDX&lt;/licenseUrl&gt;</c>
    /// convention (where the SPDX identifier is the last path segment of the URL).
    /// Returns <c>null</c> when the file is absent or the licence cannot be determined.
    /// </summary>
    private static string? TryReadLicenceFromNuspec(
        string packageId, string version, IReadOnlyList<string> packageFolders)
    {
        foreach (var folder in packageFolders)
        {
            // NuGet cache layout: <root>/<id-lowercase>/<version>/<id-lowercase>.nuspec
            var nuspecPath = Path.Combine(
                folder,
                packageId.ToLowerInvariant(),
                version,
                packageId.ToLowerInvariant() + ".nuspec");

            if (!File.Exists(nuspecPath))
            {
                continue;
            }

            try
            {
                var xdoc = XDocument.Load(nuspecPath);
                var ns = xdoc.Root?.Name.Namespace ?? XNamespace.None;

                // Modern format: <license type="expression">MIT</license>
                var licenseEl = xdoc.Descendants(ns + "license").FirstOrDefault();
                if (licenseEl != null &&
                    string.Equals(
                        licenseEl.Attribute("type")?.Value,
                        "expression",
                        StringComparison.OrdinalIgnoreCase) &&
                    !string.IsNullOrWhiteSpace(licenseEl.Value))
                {
                    return licenseEl.Value.Trim();
                }

                // Legacy format: <licenseUrl>https://licenses.nuget.org/MIT</licenseUrl>
                // The SPDX identifier is the last path segment of the NuGet licence URL.
                const string nugetLicenceBase = "https://licenses.nuget.org/";
                var licenseUrl = xdoc.Descendants(ns + "licenseUrl")
                                     .FirstOrDefault()?.Value;
                if (!string.IsNullOrWhiteSpace(licenseUrl) &&
                    licenseUrl.StartsWith(nugetLicenceBase, StringComparison.OrdinalIgnoreCase))
                {
                    var spdxId = licenseUrl[nugetLicenceBase.Length..].Trim();
                    if (!string.IsNullOrEmpty(spdxId))
                    {
                        return spdxId;
                    }
                }

                // Well-known GitHub / raw URLs that pre-date the licenses.nuget.org convention.
                if (!string.IsNullOrWhiteSpace(licenseUrl))
                {
                    foreach (var (prefix, spdx) in KnownLicenceUrls)
                    {
                        if (licenseUrl.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
                        {
                            return spdx;
                        }
                    }
                }
            }
            catch
            {
                // Malformed or unreadable .nuspec — skip and fall through to "unknown".
            }
        }

        return null;
    }
}
