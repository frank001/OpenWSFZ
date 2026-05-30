using System.Runtime.InteropServices;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Skips the test on non-Windows platforms.
///
/// <para>
/// <c>libft8.dll</c> is compiled for Windows x64 only in p12.
/// Cross-platform native binary support (Linux <c>.so</c>, macOS <c>.dylib</c>)
/// is deferred to a future change.  Tests that exercise the P/Invoke path are
/// therefore Windows-only until that work is done.
/// </para>
/// </summary>
public sealed class WindowsOnlyFactAttribute : FactAttribute
{
    public WindowsOnlyFactAttribute()
    {
        if (!RuntimeInformation.IsOSPlatform(OSPlatform.Windows))
            Skip = "libft8.dll is Windows x64 only. Cross-platform support is a future phase.";
    }
}

/// <summary>Skips the theory on non-Windows platforms (same rationale as <see cref="WindowsOnlyFactAttribute"/>).</summary>
public sealed class WindowsOnlyTheoryAttribute : TheoryAttribute
{
    public WindowsOnlyTheoryAttribute()
    {
        if (!RuntimeInformation.IsOSPlatform(OSPlatform.Windows))
            Skip = "libft8.dll is Windows x64 only. Cross-platform support is a future phase.";
    }
}
