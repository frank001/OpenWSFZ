using FluentAssertions;
using LicenseInventoryCheck;
using Xunit;

namespace LicenseInventoryCheck.Tests;

public sealed class NuGetEnumeratorTests
{
    [Fact(DisplayName = "P0-Tool: Missing project.assets.json halts the run with a clear error")]
    public void Enumerate_NoAssetsFiles_ThrowsInvalidOperationException()
    {
        var emptyDir = Path.Combine(Path.GetTempPath(), $"lic-test-empty-{Guid.NewGuid():N}");
        Directory.CreateDirectory(emptyDir);
        try
        {
            var act = () => NuGetEnumerator.Enumerate(emptyDir);

            act.Should().Throw<InvalidOperationException>()
                .WithMessage("*dotnet restore*");
        }
        finally
        {
            Directory.Delete(emptyDir, recursive: true);
        }
    }

    [Fact(DisplayName = "P0-Tool: Direct NuGet reference is enumerated from project.assets.json")]
    public void Enumerate_ValidAssetsFile_ReturnsDependencies()
    {
        // Arrange: write a minimal project.assets.json that declares xunit.
        var root = Path.Combine(Path.GetTempPath(), $"lic-test-{Guid.NewGuid():N}");
        var objDir = Path.Combine(root, "src", "MyProject", "obj");
        Directory.CreateDirectory(objDir);

        var assetsContent = """
            {
              "version": 3,
              "libraries": {
                "xunit/2.9.3": {
                  "type": "package",
                  "licenseExpression": "MIT"
                }
              }
            }
            """;
        File.WriteAllText(Path.Combine(objDir, "project.assets.json"), assetsContent);

        try
        {
            var entries = NuGetEnumerator.Enumerate(root);

            entries.Should().ContainSingle(e => e.Name == "xunit" && e.Version == "2.9.3" && e.Licence == "MIT");
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }

    [Fact(DisplayName = "P0-Tool: Duplicate packages across multiple project.assets.json files are deduplicated")]
    public void Enumerate_DuplicateAcrossProjects_DeduplicatesResult()
    {
        var root = Path.Combine(Path.GetTempPath(), $"lic-test-{Guid.NewGuid():N}");
        var obj1 = Path.Combine(root, "proj1", "obj");
        var obj2 = Path.Combine(root, "proj2", "obj");
        Directory.CreateDirectory(obj1);
        Directory.CreateDirectory(obj2);

        const string assets = """
            {
              "version": 3,
              "libraries": {
                "xunit/2.9.3": { "type": "package", "licenseExpression": "MIT" }
              }
            }
            """;

        File.WriteAllText(Path.Combine(obj1, "project.assets.json"), assets);
        File.WriteAllText(Path.Combine(obj2, "project.assets.json"), assets);

        try
        {
            var entries = NuGetEnumerator.Enumerate(root);

            entries.Where(e => e.Name == "xunit").Should().ContainSingle();
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }

    [Fact(DisplayName = "P0-Tool: Package with <license type=\"file\"> resolves via KnownFileLicences table")]
    public void Enumerate_LicenceTypeFile_ResolvedViaKnownTable()
    {
        // Arrange: a synthetic NuGet cache with a .nuspec using <license type="file">.
        var root     = Path.Combine(Path.GetTempPath(), $"lic-test-{Guid.NewGuid():N}");
        var objDir   = Path.Combine(root, "src", "MyProject", "obj");
        var cacheDir = Path.Combine(root, "fakecache");
        Directory.CreateDirectory(objDir);

        // Write the .nuspec for the package into the fake cache.
        foreach (var (pkgId, _) in NuGetEnumerator.KnownFileLicences)
        {
            var nuspecDir = Path.Combine(cacheDir, pkgId.ToLowerInvariant(), "1.0.0");
            Directory.CreateDirectory(nuspecDir);
            File.WriteAllText(
                Path.Combine(nuspecDir, pkgId.ToLowerInvariant() + ".nuspec"),
                $"""
                <?xml version="1.0"?>
                <package xmlns="http://schemas.microsoft.com/packaging/2013/05/nuspec.xsd">
                  <metadata>
                    <id>{pkgId}</id>
                    <version>1.0.0</version>
                    <license type="file">license.txt</license>
                    <licenseUrl>https://aka.ms/deprecateLicenseUrl</licenseUrl>
                  </metadata>
                </package>
                """);

            // Write the project.assets.json referencing the package and the fake cache.
            File.WriteAllText(
                Path.Combine(objDir, "project.assets.json"),
                $$"""
                {
                  "version": 3,
                  "packageFolders": { "{{cacheDir.Replace("\\", "\\\\")}}" : {} },
                  "libraries": {
                    "{{pkgId}}/1.0.0": { "type": "package" }
                  }
                }
                """);

            try
            {
                var entries = NuGetEnumerator.Enumerate(root);

                var entry = entries.Single(e =>
                    string.Equals(e.Name, pkgId, StringComparison.OrdinalIgnoreCase));

                entry.Licence.Should().Be(
                    NuGetEnumerator.KnownFileLicences[pkgId],
                    $"KnownFileLicences must resolve '{pkgId}' to its known SPDX expression");
            }
            finally
            {
                Directory.Delete(root, recursive: true);
            }
        }
    }
}
