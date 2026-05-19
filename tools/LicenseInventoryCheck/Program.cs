using LicenseInventoryCheck;

// ---------------------------------------------------------------------------
// LicenseInventoryCheck — enforces the dependency-licence policy.
//
// Usage:
//   LicenseInventoryCheck --solution-root <path> [--report <path>]
//
// Exit codes:
//   0 — all dependencies use allowed licences
//   1 — one or more policy violations (details in report and stdout)
//   2 — bad arguments or I/O error (e.g. restore not run)
// ---------------------------------------------------------------------------

if (args.Length == 0 || args.Contains("--help") || args.Contains("-h"))
{
    PrintHelp();
    return 0;
}

string? solutionRoot = null;
string? reportPath = null;

for (int i = 0; i < args.Length; i++)
{
    switch (args[i])
    {
        case "--solution-root":
            solutionRoot = NextArg(args, ref i, "--solution-root");
            break;
        case "--report":
            reportPath = NextArg(args, ref i, "--report");
            break;
        default:
            Console.Error.WriteLine($"error: unknown argument '{args[i]}'");
            return 2;
    }
}

if (solutionRoot is null)
{
    Console.Error.WriteLine("error: --solution-root <path> is required");
    return 2;
}

if (!Directory.Exists(solutionRoot))
{
    Console.Error.WriteLine($"error: solution root not found: {solutionRoot}");
    return 2;
}

reportPath ??= "licence-inventory.md";

// --- Enumerate NuGet dependencies ---
List<DependencyEntry> entries = new();
try
{
    var nuget = NuGetEnumerator.Enumerate(solutionRoot);
    entries.AddRange(nuget);
    Console.WriteLine($"Found {nuget.Count} NuGet dependency package(s)");
}
catch (InvalidOperationException ex)
{
    Console.Error.WriteLine($"error: {ex.Message}");
    return 2;
}

// --- Enumerate native submodules ---
try
{
    var submodules = SubmoduleEnumerator.Enumerate(solutionRoot);
    entries.AddRange(submodules);
    Console.WriteLine($"Found {submodules.Count} native submodule(s)");
}
catch (InvalidOperationException ex)
{
    // A submodule missing its licence file is a hard stop.
    Console.Error.WriteLine($"error: {ex.Message}");
    // Still emit report for what we found so far.
    LicenceReportEmitter.Emit(reportPath, entries, new[] { ex.Message });
    return 1;
}

// --- Policy checks ---
var violations = new List<string>();

foreach (var entry in entries)
{
    // FluentAssertions ≥ 7.0 block rule.
    if (LicencePolicy.IsFluentAssertionsBlocked(entry.Name, entry.Version))
    {
        violations.Add(
            $"{entry.Name} {entry.Version}: version 7.0+ is blocked by project policy " +
            "(FluentAssertions changed to a commercial licence in 7.0; " +
            "pin must stay on the last 6.x release — see dependency-licence-policy spec).");
        continue;
    }

    if (!LicencePolicy.IsAllowed(entry.Licence))
    {
        violations.Add(
            $"{entry.Name} {entry.Version}: licence '{entry.Licence}' is not on the allow-list. " +
            "Review required — see dependency-licence-policy spec.");
    }
}

// --- Emit report (always, even on failure) ---
try
{
    LicenceReportEmitter.Emit(reportPath, entries, violations);
    Console.WriteLine($"Report written to: {reportPath}");
}
catch (Exception ex)
{
    Console.Error.WriteLine($"warning: could not write report: {ex.Message}");
}

if (violations.Count > 0)
{
    Console.Error.WriteLine();
    Console.Error.WriteLine($"FAIL: {violations.Count} policy violation(s):");
    foreach (var v in violations)
    {
        Console.Error.WriteLine($"  {v}");
    }
    return 1;
}

Console.WriteLine("PASS: all dependencies use allowed licences.");
return 0;

// ---------------------------------------------------------------------------

static void PrintHelp()
{
    Console.WriteLine("""
        LicenseInventoryCheck — enforces the dependency-licence policy.

        Usage:
          LicenseInventoryCheck --solution-root <path> [--report <path>]

        Arguments:
          --solution-root <path>   Path to the repository / solution root (required)
          --report <path>          Output path for licence-inventory.md
                                   (default: ./licence-inventory.md)
          --help                   Show this help and exit

        Exit codes:
          0   All dependencies use allowed licences
          1   One or more policy violations
          2   Bad arguments or I/O error (e.g. dotnet restore not run)

        The tool reads obj/project.assets.json files (produced by dotnet restore)
        and walks /native/ for git submodules. Run dotnet restore first.
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
