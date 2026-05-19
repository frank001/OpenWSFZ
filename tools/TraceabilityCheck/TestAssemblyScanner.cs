using System.Reflection;
using System.Runtime.Loader;
using System.Text.RegularExpressions;

namespace TraceabilityCheck;

/// <summary>
/// Reflects over compiled test assemblies to extract test display names,
/// skipping any test that carries a non-null <c>Skip</c> attribute argument.
/// </summary>
public static class TestAssemblyScanner
{
    // Leading requirement IDs: "FR-001, NFR-002: description"
    private static readonly Regex LeadingIds = new(
        @"^((?:FR|NFR)-\d{3})(?:\s*,\s*((?:FR|NFR)-\d{3}))*\s*:",
        RegexOptions.Compiled);

    /// <summary>
    /// Returns all (displayName, assemblyPath) pairs for non-skipped tests across
    /// all supplied <paramref name="assemblyPaths"/>.
    /// </summary>
    public static IReadOnlyList<TestEntry> Scan(IEnumerable<string> assemblyPaths)
    {
        var results = new List<TestEntry>();

        foreach (var path in assemblyPaths)
        {
            var ctx = new AssemblyLoadContext(name: null, isCollectible: true);
            try
            {
                var assembly = ctx.LoadFromAssemblyPath(Path.GetFullPath(path));
                ScanAssembly(assembly, path, results);
            }
            finally
            {
                ctx.Unload();
            }
        }

        return results;
    }

    private static void ScanAssembly(Assembly assembly, string path, List<TestEntry> results)
    {
        foreach (var type in assembly.GetTypes())
        {
            foreach (var method in type.GetMethods(BindingFlags.Public | BindingFlags.Instance | BindingFlags.Static))
            {
                if (TryGetTestEntry(method, path, out var entry))
                {
                    results.Add(entry!);
                }
            }
        }
    }

    private static bool TryGetTestEntry(MethodInfo method, string assemblyPath, out TestEntry? entry)
    {
        entry = null;

        string? displayName = null;
        bool isFact = false;
        bool isTheory = false;
        bool isSkipped = false;

        foreach (var attr in method.GetCustomAttributesData())
        {
            var typeName = attr.AttributeType.FullName ?? attr.AttributeType.Name;

            if (typeName is "Xunit.FactAttribute")
            {
                isFact = true;
                (displayName, isSkipped) = ReadDisplayNameAndSkip(attr, method.Name, displayName, isSkipped);
            }
            else if (typeName is "Xunit.TheoryAttribute")
            {
                isTheory = true;
                (displayName, isSkipped) = ReadDisplayNameAndSkip(attr, method.Name, displayName, isSkipped);
            }
        }

        if (!isFact && !isTheory)
        {
            return false;
        }

        if (isSkipped)
        {
            return false;
        }

        entry = new TestEntry(displayName ?? method.Name, assemblyPath);
        return true;
    }

    private static (string? displayName, bool isSkipped) ReadDisplayNameAndSkip(
        CustomAttributeData attr, string methodName, string? existingDisplayName, bool existingSkipped)
    {
        string? displayName = existingDisplayName;
        bool isSkipped = existingSkipped;

        foreach (var arg in attr.NamedArguments)
        {
            if (arg.MemberName == "DisplayName" && arg.TypedValue.Value is string dn)
            {
                displayName = dn;
            }
            else if (arg.MemberName == "Skip" && arg.TypedValue.Value is string skip && !string.IsNullOrEmpty(skip))
            {
                isSkipped = true;
            }
        }

        return (displayName, isSkipped);
    }

    /// <summary>
    /// Extracts leading requirement IDs from a test display name.
    /// Returns an empty collection for display names without a leading "FR-### ...: " prefix.
    /// </summary>
    public static IReadOnlyList<string> ExtractIds(string displayName)
    {
        var match = LeadingIds.Match(displayName);
        if (!match.Success)
        {
            return Array.Empty<string>();
        }

        var ids = new List<string>();
        // Group 1 is the first ID; group 2 captures subsequent IDs (last match only).
        // We need to find all comma-separated IDs before the colon.
        var prefix = displayName[..displayName.IndexOf(':')];
        var idRegex = new Regex(@"(?:FR|NFR)-\d{3}");
        foreach (Match m in idRegex.Matches(prefix))
        {
            ids.Add(m.Value);
        }

        return ids;
    }
}

/// <summary>Represents a single non-skipped test method's display name.</summary>
public sealed record TestEntry(string DisplayName, string AssemblyPath);
