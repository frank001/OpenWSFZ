using TraceabilityCheck;

// ---------------------------------------------------------------------------
// TraceabilityCheck — enforces rubric criteria C1 and C4.
//
// Usage:
//   TraceabilityCheck --requirements <path> --assemblies <path>... [--report <path>]
//
// Exit codes:
//   0 — all requirements mapped; no stale references
//   1 — one or more unmapped or stale IDs (details in report and stdout)
//   2 — bad arguments or I/O error
// ---------------------------------------------------------------------------

if (args.Length == 0 || args.Contains("--help") || args.Contains("-h"))
{
    PrintHelp();
    return 0;
}

string? requirementsPath = null;
string? reportPath = null;
string? debtFilePath = null;
var assemblyPaths = new List<string>();

for (int i = 0; i < args.Length; i++)
{
    switch (args[i])
    {
        case "--requirements":
            requirementsPath = NextArg(args, ref i, "--requirements");
            break;
        case "--assemblies":
            // Consume all following non-flag tokens as assembly paths.
            while (i + 1 < args.Length && !args[i + 1].StartsWith("--", StringComparison.Ordinal))
            {
                assemblyPaths.Add(args[++i]);
            }
            break;
        case "--report":
            reportPath = NextArg(args, ref i, "--report");
            break;
        case "--debt-file":
            debtFilePath = NextArg(args, ref i, "--debt-file");
            break;
        default:
            Console.Error.WriteLine($"error: unknown argument '{args[i]}'");
            return 2;
    }
}

if (requirementsPath is null)
{
    Console.Error.WriteLine("error: --requirements <path> is required");
    return 2;
}

if (assemblyPaths.Count == 0)
{
    Console.Error.WriteLine("error: at least one assembly path must follow --assemblies");
    return 2;
}

reportPath ??= "traceability.md";

// --- Parse requirements ---
if (!File.Exists(requirementsPath))
{
    Console.Error.WriteLine($"error: requirements file not found: {requirementsPath}");
    return 2;
}

IReadOnlySet<string> knownIds;
try
{
    var content = File.ReadAllText(requirementsPath);
    knownIds = RequirementsParser.Parse(content);
}
catch (FormatException ex)
{
    Console.Error.WriteLine($"error: {ex.Message}");
    return 2;
}

Console.WriteLine($"Found {knownIds.Count} requirement IDs in {requirementsPath}");

// --- Scan assemblies ---
var missingAssemblies = assemblyPaths.Where(p => !File.Exists(p)).ToList();
if (missingAssemblies.Count > 0)
{
    foreach (var p in missingAssemblies)
    {
        Console.Error.WriteLine($"error: assembly not found: {p}");
    }
    return 2;
}

IReadOnlyList<TestEntry> tests;
try
{
    tests = TestAssemblyScanner.Scan(assemblyPaths);
}
catch (Exception ex)
{
    Console.Error.WriteLine($"error scanning assemblies: {ex.Message}");
    return 2;
}

Console.WriteLine($"Found {tests.Count} non-skipped test(s) across {assemblyPaths.Count} assembly(ies)");

// --- Load debt file (optional) ---
IReadOnlySet<string> debtIds = new HashSet<string>(StringComparer.Ordinal);
if (debtFilePath is not null)
{
    if (!File.Exists(debtFilePath))
    {
        Console.Error.WriteLine($"error: debt file not found: {debtFilePath}");
        return 2;
    }

    debtIds = DebtFileParser.Parse(debtFilePath);
    Console.WriteLine($"Loaded {debtIds.Count} pending requirement ID(s) from debt file: {debtFilePath}");
}

// --- Analyse ---
var analyser = new TraceabilityAnalyser(knownIds, tests, debtIds);
var result = analyser.Analyse();

// --- Emit report (always, even on failure) ---
try
{
    ReportEmitter.Emit(reportPath, result, debtIds);
    Console.WriteLine($"Report written to: {reportPath}");
}
catch (Exception ex)
{
    Console.Error.WriteLine($"warning: could not write report: {ex.Message}");
}

// --- Surface failures ---
if (result.UnmappedIds.Count > 0)
{
    Console.Error.WriteLine();
    Console.Error.WriteLine($"FAIL: {result.UnmappedIds.Count} requirement(s) not mapped to any test:");
    foreach (var id in result.UnmappedIds)
    {
        Console.Error.WriteLine($"  {id}");
    }
}

if (result.StaleReferences.Count > 0)
{
    Console.Error.WriteLine();
    Console.Error.WriteLine($"FAIL: {result.StaleReferences.Count} test(s) reference unknown requirement ID(s):");
    foreach (var (id, testName) in result.StaleReferences)
    {
        Console.Error.WriteLine($"  {id}  (in: {testName})");
    }
}

if (result.IsSuccess)
{
    Console.WriteLine("PASS: all requirements are mapped and all references are valid.");
    return 0;
}

return 1;

// ---------------------------------------------------------------------------

static void PrintHelp()
{
    Console.WriteLine("""
        TraceabilityCheck — enforces requirement-traceability rubric criteria C1 and C4.

        Usage:
          TraceabilityCheck --requirements <path> --assemblies <path>... [options]

        Arguments:
          --requirements <path>    Path to REQUIREMENTS.md (required)
          --assemblies <path>...   One or more paths to compiled .NET test assemblies (required)
          --report <path>          Output path for traceability.md (default: ./traceability.md)
          --debt-file <path>       Path to traceability-debt.md; IDs listed are excluded from
                                   the missing-mapping check (grace-period mechanism).
                                   Remove an ID once its implementing phase lands tests.
          --help                   Show this help and exit

        Exit codes:
          0   All requirements mapped (or pending in debt file); no stale references
          1   One or more unmapped or stale IDs
          2   Bad arguments or I/O error
        """);
}

static string NextArg(string[] args, ref int i, string flag)
{
    if (i + 1 >= args.Length)
    {
        Console.Error.WriteLine($"error: {flag} requires a value");
        Environment.Exit(2);
    }
    return args[++i];
}
