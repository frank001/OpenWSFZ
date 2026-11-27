using System.Reflection;
using FluentAssertions;
using OpenWSFZ.Ft8.Interop;
using Xunit;
using Xunit.Abstractions;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// The lean members of <see cref="IFt8NativeInterop"/> have no default body: an implementer with a different parameter list must fail to COMPILE, not land silently on a default
/// (twice on 2026-11-27 an empty default for <c>DecodeLeanXcRound</c> disabled the XC round in a replay harness). This test fails if a default body is ever added back.
/// </summary>
public sealed class InteropLeanMembersHaveNoDefaultTests(ITestOutputHelper output)
{
    [Fact(DisplayName = "IFt8NativeInterop: every lean member (DecodeLeanCycle x2, DecodeLeanXcRound, LeanShutdown) is abstract, with no default body")]
    public void LeanMembers_AreAbstract()
    {
        var lean = typeof(IFt8NativeInterop).GetMethods(BindingFlags.Public | BindingFlags.Instance)
            .Where(m => m.Name.Contains("Lean", StringComparison.Ordinal)).ToArray();
        output.WriteLine("checked: " + string.Join("; ", lean.Select(m => $"{m.Name}({m.GetParameters().Length} parameters)")));
        lean.Select(m => m.Name).Should().BeEquivalentTo("DecodeLeanCycle", "DecodeLeanCycle", "DecodeLeanXcRound", "LeanShutdown");
        lean.Should().OnlyContain(m => m.IsAbstract, "a default body would let a signature change go unnoticed");
    }
}
