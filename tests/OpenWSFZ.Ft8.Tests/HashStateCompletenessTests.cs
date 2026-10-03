using System.Text.RegularExpressions;
using FluentAssertions;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// decode-early-batch-panel task 2.4 (FR-083, HK-026): the completeness of the native decode-state image is checked
/// <b>mechanically</b>, not trusted. A2b compares saved images, so it can only see the globals the image contains; this
/// test scans the native sources for every mutable file-scope static and every thread-local static and fails when one is
/// neither in the image nor recorded as exempt (with its reason) in the <c>HSM-IMAGE</c> / <c>HSM-EXEMPT</c> manifest
/// block of <c>ft8_shim.c</c>. A global added to the shim without being listed therefore fails the build, instead of
/// silently re-opening R4.
///
/// <para>
/// Source text is read straight from the repository, so the test sees what is committed. It also fails when the manifest
/// names a variable that no longer exists, when a name is listed twice, and when the bodies of
/// <c>ft8_hash_state_save</c> or <c>ft8_hash_state_restore</c> do not both mention every <c>HSM-IMAGE</c> variable.
/// </para>
/// </summary>
public sealed class HashStateCompletenessTests
{
    private static string RepoRoot()
    {
        for (var dir = new DirectoryInfo(AppContext.BaseDirectory); dir is not null; dir = dir.Parent)
            if (File.Exists(Path.Combine(dir.FullName, "OpenWSFZ.slnx"))) return dir.FullName;
        throw new InvalidOperationException("OpenWSFZ.slnx not found above " + AppContext.BaseDirectory);
    }

    private static string ShimPath(string root) => Path.Combine(root, "src", "OpenWSFZ.Ft8", "Native", "ft8_shim.c");

    private static IEnumerable<string> NativeSources(string root)
    {
        yield return ShimPath(root);
        yield return Path.Combine(root, "native", "ft8_lib_build", "patched", "ft8", "decode.c");
        yield return Path.Combine(root, "native", "ft8_lib_build", "patched", "common", "monitor.c");
        foreach (var f in Directory.EnumerateFiles(Path.Combine(root, "native", "ft8_lib_vendor"), "*.c", SearchOption.AllDirectories))
        {
            // The vendored refine/tests are standalone programs, not part of libft8.
            if (f.Contains(Path.DirectorySeparatorChar + "tests" + Path.DirectorySeparatorChar)) continue;
            yield return f;
        }
    }

    // A mutable variable declaration: `static` (optionally `_Thread_local`), no `const`, a declarator name followed by
    // `[`, `=` or `;`, and no `(` before that (which would make it a function or a function-pointer declarator).
    private static readonly Regex Declaration = new(
        @"^(?<indent>\s*)(?:static\s+)?(?:_Thread_local\s+)?(?<head>[^=;()]*?)\b(?<name>[A-Za-z_]\w*)\s*(?:\[[^\]]*\]\s*)*(?:=|;)",
        RegexOptions.Compiled);

    /// <summary>Every mutable file-scope static and thread-local static in <paramref name="source"/>, by name.</summary>
    internal static SortedSet<string> ScanMutableStatics(string source, string fileLabel, List<string> problems)
    {
        var names = new SortedSet<string>(StringComparer.Ordinal);
        int selftestDepth = 0;                                   // inside #ifdef SUBFEAS_SELFTEST (a standalone test main)
        int ifDepth       = 0;
        int selftestAt    = -1;
        foreach (var raw in source.Split('\n'))
        {
            var line = raw.TrimEnd('\r');
            var trimmed = line.TrimStart();
            if (trimmed.StartsWith("#if", StringComparison.Ordinal))
            {
                ifDepth++;
                if (trimmed.StartsWith("#ifdef SUBFEAS_SELFTEST", StringComparison.Ordinal)) { selftestDepth++; selftestAt = ifDepth; }
            }
            else if (trimmed.StartsWith("#endif", StringComparison.Ordinal))
            {
                if (selftestDepth > 0 && ifDepth == selftestAt) { selftestDepth--; selftestAt = -1; }
                ifDepth--;
            }
            if (selftestDepth > 0) continue;

            bool isStatic = Regex.IsMatch(line, @"^\s*static\s");
            bool isTls    = Regex.IsMatch(line, @"\b_Thread_local\b|__declspec\(thread\)|\b__thread\b|\bthread_local\b");
            if (!isStatic && !isTls) continue;
            if (Regex.IsMatch(line, @"\bconst\b")) continue;       // immutable tables
            if (trimmed.StartsWith("//") || trimmed.StartsWith("*") || trimmed.StartsWith("/*")) continue;

            var m = Declaration.Match(line);
            if (!m.Success) continue;                               // a function definition or declaration
            if (line.IndexOf('(') >= 0 && line.IndexOf('(') < line.IndexOfAny(['=', ';'])) continue;

            string name = m.Groups["name"].Value;
            if (m.Groups["indent"].Length > 0)
                problems.Add($"{fileLabel}: function-local static or thread-local '{name}' (indented declaration): list it in the HSM manifest or remove it");
            names.Add(name);
        }
        return names;
    }

    private static (SortedSet<string> Image, SortedSet<string> Exempt, List<string> Problems) ReadManifest(string shim)
    {
        var image  = new SortedSet<string>(StringComparer.Ordinal);
        var exempt = new SortedSet<string>(StringComparer.Ordinal);
        var problems = new List<string>();
        foreach (Match m in Regex.Matches(shim, @"^\s*\*\s*HSM-(?<kind>IMAGE|EXEMPT)\s+(?<name>[A-Za-z_]\w*)", RegexOptions.Multiline))
        {
            var set = m.Groups["kind"].Value == "IMAGE" ? image : exempt;
            if (!set.Add(m.Groups["name"].Value)) problems.Add($"manifest lists '{m.Groups["name"].Value}' twice");
        }
        foreach (var both in image.Intersect(exempt)) problems.Add($"'{both}' is listed as both HSM-IMAGE and HSM-EXEMPT");
        return (image, exempt, problems);
    }

    /// <summary>The text of a top-level C function body starting at the line that declares <paramref name="signature"/>.</summary>
    private static string FunctionBody(string source, string signature)
    {
        int start = source.IndexOf(signature, StringComparison.Ordinal);
        start.Should().BeGreaterThan(-1, $"{signature} must exist in the shim");
        int open = source.IndexOf('{', start);
        int depth = 0;
        for (int i = open; i < source.Length; i++)
        {
            if (source[i] == '{') depth++;
            else if (source[i] == '}' && --depth == 0) return source.Substring(open, i - open + 1);
        }
        throw new InvalidOperationException("unbalanced braces after " + signature);
    }

    [Fact(DisplayName = "FR-083: 2.4a every mutable static and thread-local static in the native sources is in the saved image or recorded as exempt, and the manifest names nothing that no longer exists")]
    public void EveryNativeGlobal_IsInTheImageOrExempt()
    {
        string root = RepoRoot();
        var problems = new List<string>();

        var (image, exempt, manifestProblems) = ReadManifest(File.ReadAllText(ShimPath(root)));
        problems.AddRange(manifestProblems);

        var found = new SortedSet<string>(StringComparer.Ordinal);
        foreach (var file in NativeSources(root))
            foreach (var n in ScanMutableStatics(File.ReadAllText(file), Path.GetFileName(file), problems))
                found.Add(n);

        var listed = new SortedSet<string>(image.Union(exempt), StringComparer.Ordinal);
        foreach (var n in found.Except(listed))
            problems.Add($"'{n}' is a mutable static in the native sources but is neither HSM-IMAGE nor HSM-EXEMPT: if the decode writes it, add it to the saved image; otherwise record why it cannot carry an early decode into a final one");
        foreach (var n in listed.Except(found))
            problems.Add($"the manifest names '{n}' but no such mutable static exists in the native sources");

        problems.Should().BeEmpty();
        image.Should().NotBeEmpty();
    }

    [Fact(DisplayName = "FR-083: 2.4b the bodies of ft8_hash_state_save and ft8_hash_state_restore both mention every HSM-IMAGE variable")]
    public void SaveAndRestore_MentionEveryImageVariable()
    {
        string shim = File.ReadAllText(ShimPath(RepoRoot()));
        var (image, _, _) = ReadManifest(shim);

        string save    = FunctionBody(shim, "int ft8_hash_state_save(");
        string restore = FunctionBody(shim, "int ft8_hash_state_restore(");

        var missingFromSave    = image.Where(n => !Regex.IsMatch(save,    $@"\b{n}\b")).ToList();
        var missingFromRestore = image.Where(n => !Regex.IsMatch(restore, $@"\b{n}\b")).ToList();
        missingFromSave.Should().BeEmpty("the save must copy every variable of the image");
        missingFromRestore.Should().BeEmpty("the restore must write back every variable of the image");
    }

    // ── The scanner itself, on synthetic text (it must flag a new global and ignore what it should) ─────────────────

    [Fact(DisplayName = "FR-083: 2.4c the scanner finds a new file-scope static and a new thread-local, and ignores constants, functions and comments")]
    public void Scanner_FindsNewGlobals_IgnoresTheRest()
    {
        const string text = """
            static int g_new_counter = 0;
            static _Thread_local float tls_new_scratch[8];
            static const int k_table[4] = {1,2,3,4};
            static void helper(int x) { }
            static ftx_hash_if_t s_if = { cb_a, cb_b };
            // static int g_in_comment = 0;
             * static int g_in_block = 0;
            """;
        var problems = new List<string>();
        var names = ScanMutableStatics(text, "synthetic.c", problems);

        names.Should().Equal("g_new_counter", "s_if", "tls_new_scratch");
        problems.Should().BeEmpty();
    }

    [Fact(DisplayName = "FR-083: 2.4d the scanner flags a function-local static")]
    public void Scanner_FlagsAFunctionLocalStatic()
    {
        const string text = "void f(void)\n{\n    static int hidden = 0;\n}\n";
        var problems = new List<string>();
        ScanMutableStatics(text, "synthetic.c", problems).Should().Contain("hidden");
        problems.Should().ContainSingle().Which.Should().Contain("function-local");
    }
}
