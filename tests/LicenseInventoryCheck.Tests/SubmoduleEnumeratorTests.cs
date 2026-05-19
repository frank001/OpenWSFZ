using FluentAssertions;
using LicenseInventoryCheck;
using Xunit;

namespace LicenseInventoryCheck.Tests;

public sealed class SubmoduleEnumeratorTests
{
    [Fact(DisplayName = "P0-Tool: Submodule with a LICENSE file is enumerated with its SPDX identifier")]
    public void Enumerate_SubmoduleWithLicense_ReturnsEntry()
    {
        var root = Path.Combine(Path.GetTempPath(), $"sub-test-{Guid.NewGuid():N}");
        var subDir = Path.Combine(root, "native", "ft8_lib");
        Directory.CreateDirectory(subDir);
        File.WriteAllText(Path.Combine(subDir, "LICENSE"),
            "MIT License\nCopyright (c) ...");

        try
        {
            var entries = SubmoduleEnumerator.Enumerate(root);

            entries.Should().ContainSingle(e =>
                e.Name == "ft8_lib" &&
                e.Licence == "MIT" &&
                e.Kind == DependencyKind.NativeSubmodule);
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }

    [Fact(DisplayName = "P0-Tool: Submodule without a recognised licence file fails the run")]
    public void Enumerate_SubmoduleWithoutLicense_ThrowsInvalidOperationException()
    {
        var root = Path.Combine(Path.GetTempPath(), $"sub-test-{Guid.NewGuid():N}");
        var subDir = Path.Combine(root, "native", "unlicensed_lib");
        Directory.CreateDirectory(subDir);
        // No licence file written.

        try
        {
            var act = () => SubmoduleEnumerator.Enumerate(root);

            act.Should().Throw<InvalidOperationException>()
                .WithMessage("*unlicensed_lib*");
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }

    [Fact(DisplayName = "P0-Tool: No /native/ directory produces an empty submodule list")]
    public void Enumerate_NoNativeDirectory_ReturnsEmpty()
    {
        var root = Path.Combine(Path.GetTempPath(), $"sub-test-{Guid.NewGuid():N}");
        Directory.CreateDirectory(root);

        try
        {
            var entries = SubmoduleEnumerator.Enumerate(root);

            entries.Should().BeEmpty();
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }

    [Fact(DisplayName = "P0-Tool: Submodule with LICENCE.txt (British spelling) is enumerated")]
    public void Enumerate_SubmoduleWithLicenceTxt_ReturnsEntry()
    {
        var root = Path.Combine(Path.GetTempPath(), $"sub-test-{Guid.NewGuid():N}");
        var subDir = Path.Combine(root, "native", "british_lib");
        Directory.CreateDirectory(subDir);
        File.WriteAllText(Path.Combine(subDir, "LICENCE.txt"),
            "MIT License\nCopyright ...");

        try
        {
            var entries = SubmoduleEnumerator.Enumerate(root);

            entries.Should().ContainSingle(e => e.Name == "british_lib" && e.Licence == "MIT");
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }
}
