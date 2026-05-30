namespace LicenseInventoryCheck;

/// <summary>
/// Enumerates git submodules under <c>/native/</c> and reads their licence files.
/// </summary>
public static class SubmoduleEnumerator
{
    private static readonly string[] LicenceFileNames =
    [
        "LICENSE", "LICENCE", "LICENSE.txt", "LICENCE.txt",
    ];

    /// <summary>
    /// Walks the <c>/native/</c> directory under <paramref name="solutionRoot"/> for
    /// submodule directories. Returns an empty list when the directory does not exist.
    /// </summary>
    public static IReadOnlyList<DependencyEntry> Enumerate(string solutionRoot)
    {
        var nativeDir = Path.Combine(solutionRoot, "native");
        if (!Directory.Exists(nativeDir))
        {
            return Array.Empty<DependencyEntry>();
        }

        // When .gitmodules declares at least one native/* entry, use that list as an allow-list
        // to skip non-submodule directories (e.g. ft8_lib_build/ build-output).
        // When .gitmodules is absent or has no native/* entries, enumerate all directories
        // (preserves legacy behaviour and keeps the unit tests working with mock directories
        // that have no .gitmodules).
        var gitSubmodulePaths = ReadGitSubmodulePaths(solutionRoot, "native");
        bool filterByGitmodules = gitSubmodulePaths.Count > 0;

        var entries = new List<DependencyEntry>();

        foreach (var dir in Directory.EnumerateDirectories(nativeDir))
        {
            var name = Path.GetFileName(dir);

            // Skip directories that are not declared git submodules (only when the filter is active).
            if (filterByGitmodules && !gitSubmodulePaths.Contains(name))
                continue;
            var licenceFile = LicenceFileNames
                .Select(f => Path.Combine(dir, f))
                .FirstOrDefault(File.Exists);

            if (licenceFile is null)
            {
                throw new InvalidOperationException(
                    $"Native submodule '{name}' has no recognised licence file " +
                    $"(expected one of: {string.Join(", ", LicenceFileNames)}) at '{dir}'.");
            }

            var spdx = InferSpdxFromLicenceFile(licenceFile);
            var sha = ReadPinnedSha(solutionRoot, name);

            entries.Add(new DependencyEntry(
                Name: name,
                Version: sha,
                Licence: spdx,
                Kind: DependencyKind.NativeSubmodule,
                Provenance: licenceFile));
        }

        return entries;
    }

    private static string InferSpdxFromLicenceFile(string path)
    {
        // Heuristic: read the first few lines and look for known SPDX identifiers.
        var content = File.ReadAllText(path);

        if (content.Contains("MIT License", StringComparison.OrdinalIgnoreCase) ||
            content.Contains("MIT licence", StringComparison.OrdinalIgnoreCase))
        {
            return "MIT";
        }

        if (content.Contains("Apache License, Version 2.0", StringComparison.OrdinalIgnoreCase))
        {
            return "Apache-2.0";
        }

        if (content.Contains("BSD 3-Clause", StringComparison.OrdinalIgnoreCase))
        {
            return "BSD-3-Clause";
        }

        if (content.Contains("BSD 2-Clause", StringComparison.OrdinalIgnoreCase))
        {
            return "BSD-2-Clause";
        }

        if (content.Contains("ISC License", StringComparison.OrdinalIgnoreCase))
        {
            return "ISC";
        }

        if (content.Contains("PortAudio", StringComparison.OrdinalIgnoreCase))
        {
            return "LicenseRef-PortAudio";
        }

        // Unknown — will fail the policy check.
        return "unknown";
    }

    /// <summary>
    /// Reads <c>.gitmodules</c> from <paramref name="solutionRoot"/> and returns the
    /// set of directory names (final path component) of submodules whose path starts
    /// with <paramref name="prefix"/> (e.g. "native").  Returns an empty set when
    /// <c>.gitmodules</c> does not exist or is unreadable.
    /// </summary>
    private static HashSet<string> ReadGitSubmodulePaths(string solutionRoot, string prefix)
    {
        var gitmodulesPath = Path.Combine(solutionRoot, ".gitmodules");
        if (!File.Exists(gitmodulesPath))
            return new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        var result = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var line in File.ReadLines(gitmodulesPath))
        {
            var trimmed = line.Trim();
            if (!trimmed.StartsWith("path", StringComparison.OrdinalIgnoreCase)) continue;
            // Format: "path = native/ft8_lib"
            var eq = trimmed.IndexOf('=');
            if (eq < 0) continue;
            var path = trimmed[(eq + 1)..].Trim();
            if (path.StartsWith(prefix + "/", StringComparison.OrdinalIgnoreCase) ||
                path.StartsWith(prefix + "\\", StringComparison.OrdinalIgnoreCase))
            {
                // Extract the directory name after the prefix separator.
                result.Add(Path.GetFileName(path));
            }
        }

        return result;
    }

    private static string ReadPinnedSha(string solutionRoot, string submoduleName)
    {
        // Read the SHA from .gitmodules + git ls-tree HEAD native/<name>
        // For portability, we invoke git directly.
        try
        {
            var psi = new System.Diagnostics.ProcessStartInfo("git",
                $"ls-tree HEAD native/{submoduleName}")
            {
                WorkingDirectory = solutionRoot,
                RedirectStandardOutput = true,
                UseShellExecute = false,
            };
            using var proc = System.Diagnostics.Process.Start(psi);
            var output = proc?.StandardOutput.ReadToEnd() ?? string.Empty;
            bool exited = proc?.WaitForExit(5_000) ?? true;   // 5-second timeout
            if (!exited)
            {
                proc?.Kill();
            }

            // Output format: "<mode> commit <sha>\t<path>"
            var parts = output.Split(' ', '\t');
            if (parts.Length >= 3 && parts[1] == "commit")
            {
                return parts[2].Trim();
            }
        }
        catch
        {
            // git not available or not a git repo — fall through to "unknown".
        }

        return "unknown";
    }
}
