using System.Text.Json;

namespace LicenseInventoryCheck;

/// <summary>
/// Enumerates NuGet dependencies (direct and transitive) by reading
/// each project's <c>obj/project.assets.json</c>.
/// </summary>
public static class NuGetEnumerator
{
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

        // libraries section: { "Name/Version": { "type": "package", ... } }
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

            // Try to read the licence expression from the assets file.
            // NuGet embeds it under libraries.<key>.licenseExpression (in newer formats)
            // or we fall back to "unknown" and let the policy check flag it.
            string licence = "unknown";
            if (prop.Value.TryGetProperty("licenseExpression", out var licEl) &&
                licEl.GetString() is string lic && !string.IsNullOrWhiteSpace(lic))
            {
                licence = lic;
            }

            entries.Add(new DependencyEntry(
                Name: name,
                Version: version,
                Licence: licence,
                Kind: DependencyKind.NuGet,
                Provenance: assetFile));
        }
    }
}
