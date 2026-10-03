using System.Text;
using System.Text.RegularExpressions;
using FluentAssertions;
using Xunit;
using Xunit.Abstractions;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// decode-early-batch-panel task 2.4 (FR-083, HK-026; Architect ruling <c>bffb4c95</c> s0b): the completeness of the native
/// decode-state image is checked <b>mechanically</b>, over <b>every native source compiled into <c>libft8</c></b>, not
/// trusted. A2b compares saved images, so it only sees the globals the image contains; this test therefore
/// <list type="number">
///   <item>derives the compiled source set from the build scripts (<c>rebuild_shim.bat</c> and <c>build_linux.sh</c>), asserts
///   the two agree, that no <c>.c</c> file under <c>native/ft8_lib_vendor</c> or <c>native/ft8_lib_build/patched</c> sits
///   outside it, and scans exactly that set (a source added to the build and not to the scan, or the reverse, fails);</item>
///   <item>finds every <b>mutable</b> variable in those sources: file-scope <c>static</c> or plain global, thread-local
///   static, and function-scope <c>static</c> local (<c>const</c> tables are immutable and skipped);</item>
///   <item>requires each to be classified in the manifest block of <c>ft8_shim.c</c> as exactly one of
///   <c>HSM-IMAGE</c> (in the saved image), <c>HSM-RESET FILE:LINE</c> (reset or assigned per call, evidence line inside a
///   function on the pass-0 path) or <c>HSM-NOWRITE FILE:LINE</c> (not written on the pass-0 path);</item>
///   <item>checks the evidence: the cited line exists and names the variable; a RESET line lies in a function reachable from the
///   pass-0 entry points; and for NOWRITE <b>no function reachable from the pass-0 entry points assigns the variable</b>
///   (a conservative call graph over the compiled sources, following function-pointer tables);</item>
///   <item>fails on an unclassified variable, on a manifest entry naming a variable that no longer exists, and when the bodies of
///   <c>ft8_hash_state_save</c> or <c>ft8_hash_state_restore</c> do not both mention every <c>HSM-IMAGE</c> variable.</item>
/// </list>
/// The full scan table is written to the test output (variable, file:line, class).
///
/// <para><b>Blind spots, said plainly:</b> a <c>const</c>-qualified declaration is treated as immutable even if it is a pointer
/// that could be re-pointed; the call graph follows identifier mentions, not real C semantics (macros are not expanded), so it
/// can only over-approximate reachability, never under-approximate it by missing a direct call; a write through a pointer to a
/// variable is not seen. A2b and A2 are the other half.</para>
/// </summary>
public sealed class HashStateCompletenessTests(ITestOutputHelper output)
{
    // ── Locating the sources ──────────────────────────────────────────────────────────────────────────────────────

    private static string RepoRoot()
    {
        for (var dir = new DirectoryInfo(AppContext.BaseDirectory); dir is not null; dir = dir.Parent)
            if (File.Exists(Path.Combine(dir.FullName, "OpenWSFZ.slnx"))) return dir.FullName;
        throw new InvalidOperationException("OpenWSFZ.slnx not found above " + AppContext.BaseDirectory);
    }

    private const string ShimRel   = "src/OpenWSFZ.Ft8/Native/ft8_shim.c";
    private const string VendorRel = "native/ft8_lib_vendor";
    private const string PatchedRel = "native/ft8_lib_build/patched";

    /// <summary>The compiled source set named by <c>rebuild_shim.bat</c> (repo-relative, forward slashes).</summary>
    internal static SortedSet<string> CompiledFromBat(string batText)
    {
        var set = new SortedSet<string>(StringComparer.Ordinal);
        foreach (Match m in Regex.Matches(batText, @"%FT8_ROOT%\\((?:native\\ft8_lib_vendor|native\\ft8_lib_build\\patched|src\\OpenWSFZ\.Ft8\\Native)\\[^""\s]*?\.c)""?"))
            set.Add(m.Groups[1].Value.Replace('\\', '/'));
        return set;
    }

    /// <summary>The compiled source set named by <c>build_linux.sh</c> (repo-relative, forward slashes).</summary>
    internal static SortedSet<string> CompiledFromLinux(string shText)
    {
        var map = new Dictionary<string, string>
        {
            ["$LIB_SRC"]  = VendorRel,
            ["$PATCHED"]  = PatchedRel,
            ["$SRC_DIR"]  = "src/OpenWSFZ.Ft8/Native",
        };
        var set = new SortedSet<string>(StringComparer.Ordinal);
        foreach (Match m in Regex.Matches(shText, @"""(\$(?:LIB_SRC|PATCHED|SRC_DIR))/([^""]+?\.c)"""))
            set.Add(map[m.Groups[1].Value] + "/" + m.Groups[2].Value);
        return set;
    }

    private static SortedSet<string> CompiledSet(string root, out SortedSet<string> bat, out SortedSet<string> linux)
    {
        bat   = CompiledFromBat(File.ReadAllText(Path.Combine(root, "native/ft8_lib_build/rebuild_shim.bat")));
        linux = CompiledFromLinux(File.ReadAllText(Path.Combine(root, "native/ft8_lib_build/build_linux.sh")));
        return bat;
    }

    // ── A small C reader: comments and strings blanked, functions and variables found ────────────────────────────

    internal sealed record CFunction(string Name, int StartLine, int EndLine, string Body);
    internal sealed record CVariable(string Name, int Line, string Statement, bool FunctionLocal);

    internal sealed class CFile
    {
        public string Label = "";
        public string[] RawLines = [];
        public List<CFunction> Functions = [];
        public List<CVariable> Variables = [];
        public List<string> Problems = [];
    }

    /// <summary>Blanks comments, string and char literals, preprocessor lines and the SUBFEAS_SELFTEST region; keeps every newline.</summary>
    private static string Clean(string src)
    {
        var sb = new StringBuilder(src.Length);
        for (int i = 0; i < src.Length; i++)
        {
            char c = src[i];
            if (c == '/' && i + 1 < src.Length && src[i + 1] == '/')
            {
                while (i < src.Length && src[i] != '\n') { sb.Append(' '); i++; }
                i--; continue;
            }
            if (c == '/' && i + 1 < src.Length && src[i + 1] == '*')
            {
                i += 2; sb.Append("  ");
                while (i + 1 < src.Length && !(src[i] == '*' && src[i + 1] == '/')) { sb.Append(src[i] == '\n' ? '\n' : ' '); i++; }
                sb.Append("  "); i++; continue;
            }
            if (c == '"' || c == '\'')
            {
                char q = c; sb.Append(' '); i++;
                while (i < src.Length && src[i] != q)
                {
                    if (src[i] == '\\') { sb.Append(' '); i++; }
                    sb.Append(i < src.Length && src[i] == '\n' ? '\n' : ' '); i++;
                }
                sb.Append(' '); continue;
            }
            sb.Append(c);
        }

        // Preprocessor lines (with continuations) and the self-test region.
        var lines = sb.ToString().Split('\n');
        int ifDepth = 0, selftestAt = -1;
        bool continued = false;
        for (int n = 0; n < lines.Length; n++)
        {
            var t = lines[n].TrimStart();
            bool isDirective = continued || t.StartsWith('#');
            if (t.StartsWith('#'))
            {
                var d = Regex.Replace(t, @"^#\s*", "#");
                if (d.StartsWith("#if", StringComparison.Ordinal))
                {
                    ifDepth++;
                    if (d.StartsWith("#ifdef SUBFEAS_SELFTEST", StringComparison.Ordinal)) selftestAt = ifDepth;
                }
                else if (d.StartsWith("#endif", StringComparison.Ordinal))
                {
                    if (ifDepth == selftestAt) { lines[n] = ""; selftestAt = -1; ifDepth--; continue; }
                    ifDepth--;
                }
            }
            continued = isDirective && lines[n].TrimEnd().EndsWith('\\');
            if (isDirective || selftestAt > 0) lines[n] = "";
        }
        return string.Join('\n', lines);
    }

    private static readonly Regex Ident = new(@"[A-Za-z_]\w*", RegexOptions.Compiled);

    internal static CFile Parse(string rawSource, string label)
    {
        var file = new CFile { Label = label, RawLines = rawSource.Replace("\r\n", "\n").Split('\n') };
        string text = Clean(rawSource.Replace("\r\n", "\n"));
        var textLines = text.Split('\n');

        var stmt = new StringBuilder();
        int stmtLine = -1, line = 1;
        for (int i = 0; i < text.Length; i++)
        {
            char c = text[i];
            if (c == '\n') { line++; if (stmt.Length > 0) stmt.Append(' '); continue; }
            if (stmt.Length == 0 && char.IsWhiteSpace(c)) continue;
            if (stmtLine < 0 && !char.IsWhiteSpace(c)) stmtLine = line;

            if (c == '{')
            {
                // find the matching brace
                int depth = 0, j = i, endLine = line, startLine = line;
                for (; j < text.Length; j++)
                {
                    if (text[j] == '\n') endLine++;
                    else if (text[j] == '{') depth++;
                    else if (text[j] == '}' && --depth == 0) break;
                }
                string head = Regex.Replace(stmt.ToString(), @"\s+", " ").Trim();
                if (head.EndsWith(')'))
                {
                    // a function definition: name = the identifier before the first '('
                    int paren = head.IndexOf('(');
                    var before = Ident.Matches(head[..paren]);
                    string name = before.Count > 0 ? before[^1].Value : "?";
                    string body = text.Substring(i, j - i + 1);
                    file.Functions.Add(new CFunction(name, stmtLine, endLine, body));
                    // function-local statics, with their lines
                    foreach (Match lm in Regex.Matches(body, @"\b(?:static|_Thread_local|__thread)\b[^;{}]*;"))
                    {
                        var decl = Regex.Replace(lm.Value, @"\s+", " ").Trim();
                        if (Regex.IsMatch(decl, @"\bconst\b")) continue;
                        int declLine = startLine + body.Take(lm.Index).Count(ch => ch == '\n');
                        string left = decl.Contains('=') ? decl[..decl.IndexOf('=')] : decl.TrimEnd(';');
                        var cleaned = Regex.Replace(left, @"\[[^\]]*\]", " ");
                        var ids = Ident.Matches(cleaned);
                        if (ids.Count > 0)
                            file.Variables.Add(new CVariable(ids[^1].Value, declLine, decl, true));
                    }
                    stmt.Clear(); stmtLine = -1;
                }
                else
                {
                    // an initialiser or a struct body: keep its text (callback tables name functions) and go on to the ';'
                    stmt.Append('{').Append(Regex.Replace(text.Substring(i + 1, j - i - 1), @"\s+", " ")).Append('}');
                }
                line = endLine; i = j;
                continue;
            }

            if (c == ';')
            {
                string s = Regex.Replace(stmt.ToString(), @"\s+", " ").Trim();
                AddStatement(file, s, stmtLine);
                stmt.Clear(); stmtLine = -1;
                continue;
            }
            stmt.Append(c);
        }
        return file;
    }

    private static void AddStatement(CFile file, string s, int lineNo)
    {
        if (s.Length == 0) return;
        if (Regex.IsMatch(s, @"^(typedef|extern)\b")) return;
        if (Regex.IsMatch(s, @"\bconst\b")) return;                  // immutable table
        if (Regex.IsMatch(s, @"^(struct|union|enum)\s+\w+\s*\{[^}]*\}$")) return;
        string left = s.Contains('=') ? s[..s.IndexOf('=')] : s;
        if (left.Contains('(') && !Regex.IsMatch(left, @"\(\s*\*")) return;     // a function prototype
        foreach (var part in left.Split(','))
        {
            var cleaned = Regex.Replace(part, @"\[[^\]]*\]", " ");
            var ids = Ident.Matches(cleaned);
            if (ids.Count == 0) continue;
            string name = ids[^1].Value;
            if (name is "static" or "extern" or "unsigned" or "int" or "char" or "float" or "double" or "void") continue;
            file.Variables.Add(new CVariable(name, lineNo, s, false));
        }
    }

    // ── Manifest ─────────────────────────────────────────────────────────────────────────────────────────────────

    internal sealed record Entry(string Kind, string Name, string? File, int Line);

    internal static (List<Entry> Entries, List<string> Problems) ReadManifest(string shim)
    {
        var entries  = new List<Entry>();
        var problems = new List<string>();
        foreach (Match m in Regex.Matches(shim,
                     @"^\s*\*\s*HSM-(?<kind>IMAGE|RESET|NOWRITE)\s+(?<name>[A-Za-z_]\w*)(?:\s+(?<file>[\w.]+):(?<line>\d+))?",
                     RegexOptions.Multiline))
        {
            string kind = m.Groups["kind"].Value, name = m.Groups["name"].Value;
            bool hasEvidence = m.Groups["file"].Success;
            if (kind == "IMAGE" && hasEvidence) problems.Add($"HSM-IMAGE {name} must not carry FILE:LINE evidence");
            if (kind != "IMAGE" && !hasEvidence) problems.Add($"HSM-{kind} {name} needs FILE:LINE evidence");
            entries.Add(new Entry(kind, name, hasEvidence ? m.Groups["file"].Value : null,
                                  hasEvidence ? int.Parse(m.Groups["line"].Value) : 0));
        }
        foreach (var g in entries.GroupBy(e => e.Name).Where(g => g.Count() > 1))
            problems.Add($"'{g.Key}' is classified {g.Count()} times ({string.Join(", ", g.Select(e => e.Kind))})");
        return (entries, problems);
    }

    // ── Reachability from the pass-0 entry points ────────────────────────────────────────────────────────────────

    /// <summary>The managed early decode calls these (plus the diagnostics getters, which only read thread-locals).</summary>
    internal static readonly string[] Pass0Roots =
    [
        "ft8_decode_all", "ft8_set_ap_bits", "ft8_get_last_pass_counts", "ft8_get_last_candidate_counts",
        "ft8_get_last_noise_floor_db", "ft8_get_last_llr_stats", "ft8_hash_state_size", "ft8_hash_state_save",
        "ft8_hash_state_restore",
    ];

    /// <summary>
    /// Every function reachable from <paramref name="roots"/> by identifier mention, following file-scope variables whose
    /// declaration mentions functions (a callback table such as <c>s_hash_if</c>). Conservative: it can only over-approximate.
    /// </summary>
    internal static HashSet<string> Reachable(IReadOnlyList<CFile> files, IEnumerable<string> roots)
    {
        var funcs = new Dictionary<string, List<CFunction>>(StringComparer.Ordinal);
        foreach (var f in files.SelectMany(x => x.Functions))
        {
            if (!funcs.TryGetValue(f.Name, out var l)) funcs[f.Name] = l = [];
            l.Add(f);
        }
        var varStmt = new Dictionary<string, List<string>>(StringComparer.Ordinal);
        foreach (var v in files.SelectMany(x => x.Variables).Where(v => !v.FunctionLocal))
        {
            if (!varStmt.TryGetValue(v.Name, out var l)) varStmt[v.Name] = l = [];
            l.Add(v.Statement);
        }

        var seen  = new HashSet<string>(StringComparer.Ordinal);
        var queue = new Queue<string>(roots);
        var seenVars = new HashSet<string>(StringComparer.Ordinal);
        while (queue.Count > 0)
        {
            var name = queue.Dequeue();
            if (!funcs.TryGetValue(name, out var defs)) continue;
            if (!seen.Add(name)) continue;
            foreach (var def in defs)
                foreach (Match m in Ident.Matches(def.Body))
                {
                    var id = m.Value;
                    if (funcs.ContainsKey(id) && !seen.Contains(id)) queue.Enqueue(id);
                    if (varStmt.TryGetValue(id, out var stmts) && seenVars.Add(id))
                        foreach (var st in stmts)
                            foreach (Match m2 in Ident.Matches(st))
                                if (funcs.ContainsKey(m2.Value) && !seen.Contains(m2.Value)) queue.Enqueue(m2.Value);
                }
        }
        return seen;
    }

    /// <summary>True when <paramref name="body"/> assigns, increments, decrements or bulk-writes <paramref name="name"/>.</summary>
    internal static bool Writes(string body, string name)
    {
        string n = Regex.Escape(name);
        return Regex.IsMatch(body,
            $@"\b{n}\b\s*(\[[^\]]*\]\s*)*(\.\w+\s*|->\w+\s*)*(=(?!=)|\+\+|--|[-+*/|&^%]=|<<=|>>=)"
          + $@"|(\+\+|--)\s*{n}\b"
          + $@"|\b(memset|memcpy|memmove|strcpy|strncpy)\s*\(\s*&?{n}\b");
    }

    // ── The scan, shared by the tests ────────────────────────────────────────────────────────────────────────────

    private sealed record Scan(
        string Root, SortedSet<string> Compiled, List<CFile> Files, List<Entry> Entries, List<string> Problems,
        Dictionary<string, CVariable> Found, Dictionary<string, string> FileOfVariable);

    private Scan RunScan()
    {
        string root = RepoRoot();
        var compiled = CompiledSet(root, out _, out _);
        var problems = new List<string>();

        var files = new List<CFile>();
        foreach (var rel in compiled)
        {
            var path = Path.Combine(root, rel);
            if (!File.Exists(path)) { problems.Add($"compiled source {rel} does not exist"); continue; }
            files.Add(Parse(File.ReadAllText(path), rel));
        }

        var (entries, manifestProblems) = ReadManifest(File.ReadAllText(Path.Combine(root, ShimRel)));
        problems.AddRange(manifestProblems);

        var found = new Dictionary<string, CVariable>(StringComparer.Ordinal);
        var fileOf = new Dictionary<string, string>(StringComparer.Ordinal);
        foreach (var f in files)
            foreach (var v in f.Variables)
            {
                if (!found.ContainsKey(v.Name)) { found[v.Name] = v; fileOf[v.Name] = f.Label; }
            }
        return new Scan(root, compiled, files, entries, problems, found, fileOf);
    }

    [Fact(DisplayName = "FR-083: 2.4e the scanned source set is exactly the compiled set: the Windows and Linux build lists agree, and no .c file under the vendored or patched trees sits outside them")]
    public void ScannedSet_IsTheCompiledSet()
    {
        string root = RepoRoot();
        var compiled = CompiledSet(root, out var bat, out var linux);

        linux.Should().Equal(bat, "rebuild_shim.bat and build_linux.sh must compile the same sources (a source added to one build only)");
        compiled.Should().Contain(ShimRel);
        compiled.Count.Should().BeGreaterThan(10, "the build lists were parsed");

        var onDisk = new SortedSet<string>(StringComparer.Ordinal);
        foreach (var dir in new[] { VendorRel, PatchedRel })
            foreach (var f in Directory.EnumerateFiles(Path.Combine(root, dir), "*.c", SearchOption.AllDirectories))
            {
                var rel = Path.GetRelativePath(root, f).Replace('\\', '/');
                if (rel.Contains("/tests/")) continue;                 // standalone programs, not part of libft8
                onDisk.Add(rel);
            }
        onDisk.Except(compiled).Should().BeEmpty("a native source that is not compiled into libft8 must not hide beside the compiled ones: add it to the build or to this test's exclusions");
        compiled.Except(onDisk.Append(ShimRel)).Should().BeEmpty("every compiled source must exist");
    }

    [Fact(DisplayName = "FR-083: 2.4a every mutable variable in every native source compiled into libft8 is in the saved image, reset per call (FILE:LINE) or not written on the pass-0 path (FILE:LINE), and the manifest names nothing that no longer exists")]
    public void EveryNativeVariable_IsClassified_WithEvidence()
    {
        var scan = RunScan();
        var problems = new List<string>(scan.Problems);
        foreach (var f in scan.Files) problems.AddRange(f.Problems);

        var listed = scan.Entries.Select(e => e.Name).ToHashSet(StringComparer.Ordinal);
        foreach (var (name, v) in scan.Found.OrderBy(kv => kv.Key, StringComparer.Ordinal))
            if (!listed.Contains(name))
                problems.Add($"{scan.FileOfVariable[name]}:{v.Line}: mutable variable '{name}' is not classified. If the pass-0 decode can write it, add it to the saved image (HSM-IMAGE); if it is reset per call, add HSM-RESET with FILE:LINE; if the pass-0 path never writes it, add HSM-NOWRITE with FILE:LINE");
        foreach (var e in scan.Entries)
            if (!scan.Found.ContainsKey(e.Name))
                problems.Add($"the manifest classifies '{e.Name}' but no such mutable variable exists in the compiled sources");

        // Evidence.
        var fileByBase = scan.Files.GroupBy(f => Path.GetFileName(f.Label)).ToDictionary(g => g.Key, g => g.ToList());
        var reachable = Reachable(scan.Files, Pass0Roots);
        var reachableBodies = scan.Files.SelectMany(f => f.Functions).Where(fn => reachable.Contains(fn.Name)).ToList();

        var table = new StringBuilder();
        table.AppendLine("variable | declared at | class | evidence");
        foreach (var e in scan.Entries.OrderBy(x => x.Kind).ThenBy(x => x.Name, StringComparer.Ordinal))
        {
            string declared = scan.Found.TryGetValue(e.Name, out var dv) ? $"{scan.FileOfVariable[e.Name]}:{dv.Line}" : "(missing)";
            string evidence = "";
            if (e.Kind != "IMAGE" && e.File is not null)
            {
                if (!fileByBase.TryGetValue(e.File, out var cands) || cands.Count != 1)
                {
                    problems.Add($"{e.Kind} {e.Name}: evidence file '{e.File}' is not exactly one compiled source");
                    continue;
                }
                var cf = cands[0];
                evidence = $"{cf.Label}:{e.Line}";
                if (e.Line < 1 || e.Line > cf.RawLines.Length)
                {
                    problems.Add($"{e.Kind} {e.Name}: evidence {evidence} is outside the file");
                    continue;
                }
                if (!Regex.IsMatch(cf.RawLines[e.Line - 1], $@"\b{Regex.Escape(e.Name)}\b"))
                    problems.Add($"{e.Kind} {e.Name}: evidence line {evidence} does not mention the variable: '{cf.RawLines[e.Line - 1].Trim()}'");

                if (e.Kind == "RESET")
                {
                    var owner = cf.Functions.FirstOrDefault(fn => fn.StartLine <= e.Line && e.Line <= fn.EndLine);
                    if (owner is null || !reachable.Contains(owner.Name))
                        problems.Add($"RESET {e.Name}: evidence {evidence} is not inside a function on the pass-0 path (found: {owner?.Name ?? "none"})");
                }
                else // NOWRITE
                {
                    foreach (var fn in reachableBodies)
                        if (Writes(fn.Body, e.Name))
                            problems.Add($"NOWRITE {e.Name}: pass-0-path function '{fn.Name}' assigns it, so it is NOT 'not written on the pass-0 path'. A state-leak candidate: STOP and tell QA (a native change with a new shim number)");
                }
            }
            table.AppendLine($"{e.Name} | {declared} | {e.Kind} | {evidence}");
        }
        output.WriteLine(table.ToString());
        output.WriteLine($"compiled sources scanned ({scan.Compiled.Count}): {string.Join(", ", scan.Compiled)}");
        output.WriteLine($"functions reachable from the pass-0 roots: {reachable.Count}");

        problems.Should().BeEmpty();
        scan.Entries.Count(e => e.Kind == "IMAGE").Should().BeGreaterThan(0);
    }

    [Fact(DisplayName = "FR-083: 2.4b the bodies of ft8_hash_state_save and ft8_hash_state_restore both mention every HSM-IMAGE variable")]
    public void SaveAndRestore_MentionEveryImageVariable()
    {
        string root = RepoRoot();
        var shim = Parse(File.ReadAllText(Path.Combine(root, ShimRel)), ShimRel);
        var (entries, _) = ReadManifest(File.ReadAllText(Path.Combine(root, ShimRel)));
        var image = entries.Where(e => e.Kind == "IMAGE").Select(e => e.Name).ToList();

        string save    = shim.Functions.Single(f => f.Name == "ft8_hash_state_save").Body;
        string restore = shim.Functions.Single(f => f.Name == "ft8_hash_state_restore").Body;

        image.Where(n => !Regex.IsMatch(save,    $@"\b{n}\b")).Should().BeEmpty("the save must copy every variable of the image");
        image.Where(n => !Regex.IsMatch(restore, $@"\b{n}\b")).Should().BeEmpty("the restore must write back every variable of the image");
    }

    [Fact(DisplayName = "FR-083: 2.4f the call graph is real: it reaches the ft8 core and the callbacks, and does not reach the residual pass")]
    public void CallGraph_ReachesTheCore_AndNotTheResidualPass()
    {
        var scan = RunScan();
        var reachable = Reachable(scan.Files, Pass0Roots);

        reachable.Should().Contain(["ft8_decode_all", "ftx_find_candidates", "ftx_message_decode", "cb_lookup_hash", "cb_save_hash", "hash_table_add"],
            "the graph follows ordinary calls and the s_hash_if callback table");
        reachable.Should().NotContain(["ft8_subfeas_fit_signal", "ft8_subfeas_pool_configure", "ft8_set_diagnostics_enabled"],
            "the residual pass and the diagnostics switch are not on the pass-0 path");
    }

    // ── The scanner itself, on synthetic text (it must flag what it should and ignore the rest) ─────────────────────

    [Fact(DisplayName = "FR-083: 2.4c the scanner finds a mutable file-scope static, a plain global, a thread-local and a function-local static, and ignores constants, prototypes, typedefs and comments")]
    public void Scanner_FindsMutableVariables_IgnoresTheRest()
    {
        const string text = """
            static int g_new_counter = 0;
            int g_plain_global;
            static _Thread_local float tls_new_scratch[8];
            static const int k_table[4] = {1,2,3,4};
            static void helper(int x);
            static void helper(int x) { static int hidden = 0; hidden += x; }
            typedef struct { int a; } thing_t;
            extern int g_elsewhere;
            struct tag { int b; };
            static callback_t s_if = { cb_a, cb_b };
            // static int g_in_comment = 0;
            /* static int g_in_block = 0; */
            #if 0
            static int g_in_directive_branch_is_still_seen = 0;
            #endif
            """;
        var file = Parse(text, "synthetic.c");

        file.Variables.Select(v => v.Name).Should().BeEquivalentTo(
            ["g_new_counter", "g_plain_global", "tls_new_scratch", "hidden", "s_if", "g_in_directive_branch_is_still_seen"]);
        file.Variables.Single(v => v.Name == "hidden").FunctionLocal.Should().BeTrue();
        file.Functions.Select(f => f.Name).Should().Equal("helper");
    }

    [Fact(DisplayName = "FR-083: 2.4d the SUBFEAS_SELFTEST region (a standalone test main) is not scanned")]
    public void Scanner_SkipsTheSelfTestRegion()
    {
        const string text = "static int g_real = 0;\n#ifdef SUBFEAS_SELFTEST\nstatic int run_case(void)\n{\n    static float pcm[10];\n    return 0;\n}\n#endif\nstatic int g_after = 0;\n";
        Parse(text, "synthetic.c").Variables.Select(v => v.Name).Should().BeEquivalentTo(["g_real", "g_after"]);
    }

    [Fact(DisplayName = "FR-083: 2.4g the write detector sees assignments, increments, compound assignments and bulk writes, and not reads or comparisons")]
    public void WriteDetector()
    {
        Writes("g_x = 1;", "g_x").Should().BeTrue();
        Writes("g_x[i] = 1;", "g_x").Should().BeTrue();
        Writes("g_x++;", "g_x").Should().BeTrue();
        Writes("--g_x;", "g_x").Should().BeTrue();
        Writes("g_x += 2;", "g_x").Should().BeTrue();
        Writes("memset(g_x, 0, 4);", "g_x").Should().BeTrue();
        Writes("s.field = 1;", "s").Should().BeTrue();
        Writes("if (g_x == 1) return g_x;", "g_x").Should().BeFalse();
        Writes("int y = g_x + 1; foo(&g_x_other);", "g_x").Should().BeFalse();
    }
}
