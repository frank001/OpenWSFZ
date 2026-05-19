using FluentAssertions;
using LicenseInventoryCheck;
using Xunit;

namespace LicenseInventoryCheck.Tests;

public sealed class LicencePolicyTests
{
    // --- Allow-list checks ---

    [Fact(DisplayName = "P0-Tool: MIT-licensed dependency passes the allow-list check")]
    public void IsAllowed_Mit_ReturnsTrue()
    {
        LicencePolicy.IsAllowed("MIT").Should().BeTrue();
    }

    [Fact(DisplayName = "P0-Tool: Apache-2.0 dependency passes the allow-list check")]
    public void IsAllowed_Apache2_ReturnsTrue()
    {
        LicencePolicy.IsAllowed("Apache-2.0").Should().BeTrue();
    }

    [Fact(DisplayName = "P0-Tool: BSD-3-Clause dependency passes the allow-list check")]
    public void IsAllowed_Bsd3_ReturnsTrue()
    {
        LicencePolicy.IsAllowed("BSD-3-Clause").Should().BeTrue();
    }

    [Fact(DisplayName = "P0-Tool: Apache-2.0 OR MIT (SPDX-OR) dependency passes because MIT is allowed")]
    public void IsAllowed_SpdxOrWithAllowedAlternative_ReturnsTrue()
    {
        LicencePolicy.IsAllowed("Apache-2.0 OR MIT").Should().BeTrue();
    }

    [Fact(DisplayName = "P0-Tool: GPL-3.0-only dependency fails the allow-list check")]
    public void IsAllowed_Gpl3_ReturnsFalse()
    {
        LicencePolicy.IsAllowed("GPL-3.0-only").Should().BeFalse();
    }

    [Fact(DisplayName = "P0-Tool: GPL-2.0-only dependency fails the allow-list check")]
    public void IsAllowed_Gpl2_ReturnsFalse()
    {
        LicencePolicy.IsAllowed("GPL-2.0-only").Should().BeFalse();
    }

    [Fact(DisplayName = "P0-Tool: LGPL-3.0 dependency fails the allow-list check")]
    public void IsAllowed_Lgpl3_ReturnsFalse()
    {
        LicencePolicy.IsAllowed("LGPL-3.0").Should().BeFalse();
    }

    [Fact(DisplayName = "P0-Tool: Unknown licence fails and requests explicit policy review")]
    public void IsAllowed_Unknown_ReturnsFalse()
    {
        LicencePolicy.IsAllowed("unknown").Should().BeFalse();
    }

    [Fact(DisplayName = "P0-Tool: Empty licence expression fails the allow-list check")]
    public void IsAllowed_Empty_ReturnsFalse()
    {
        LicencePolicy.IsAllowed(string.Empty).Should().BeFalse();
    }

    [Fact(DisplayName = "P0-Tool: SPDX-OR where both alternatives are blocked fails the check")]
    public void IsAllowed_SpdxOrBothBlocked_ReturnsFalse()
    {
        LicencePolicy.IsAllowed("GPL-2.0-only OR GPL-3.0-only").Should().BeFalse();
    }

    // --- FluentAssertions pin rule ---

    [Fact(DisplayName = "P0-Tool: FluentAssertions 6.x is accepted by project policy")]
    public void IsFluentAssertionsBlocked_Version6_ReturnsFalse()
    {
        LicencePolicy.IsFluentAssertionsBlocked("FluentAssertions", "6.12.0").Should().BeFalse();
    }

    [Fact(DisplayName = "P0-Tool: FluentAssertions 7.0.0 is rejected by project policy")]
    public void IsFluentAssertionsBlocked_Version700_ReturnsTrue()
    {
        LicencePolicy.IsFluentAssertionsBlocked("FluentAssertions", "7.0.0").Should().BeTrue();
    }

    [Fact(DisplayName = "P0-Tool: FluentAssertions 7.1.0 is rejected by project policy")]
    public void IsFluentAssertionsBlocked_Version710_ReturnsTrue()
    {
        LicencePolicy.IsFluentAssertionsBlocked("FluentAssertions", "7.1.0").Should().BeTrue();
    }

    [Fact(DisplayName = "P0-Tool: An unrelated package named differently is not subject to the FluentAssertions rule")]
    public void IsFluentAssertionsBlocked_DifferentPackage_ReturnsFalse()
    {
        LicencePolicy.IsFluentAssertionsBlocked("SomeOtherPackage", "7.0.0").Should().BeFalse();
    }
}
