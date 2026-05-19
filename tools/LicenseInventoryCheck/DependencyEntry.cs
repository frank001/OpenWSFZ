namespace LicenseInventoryCheck;

/// <summary>Represents one enumerated dependency (NuGet package or native submodule).</summary>
public sealed record DependencyEntry(
    string Name,
    string Version,
    string Licence,
    DependencyKind Kind,
    string Provenance);

public enum DependencyKind
{
    NuGet,
    NativeSubmodule,
}
