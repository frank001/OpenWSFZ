using FluentAssertions;
using OpenWSFZ.Ft8.Interop;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Unit tests for <see cref="Ft8LibInterop.EncodeMessage"/> — the managed wrapper
/// around the native <c>ft8_encode_message</c> shim entry point (shim 20260017).
/// </summary>
public sealed class Ft8EncodeMessageTests
{
    /// <summary>
    /// A valid standard FT8 message using fictional Q-prefix callsigns (NFR-021).
    /// </summary>
    private const string ValidMessage = "Q1OFZ Q1TST JO33";

    // ── Happy-path ────────────────────────────────────────────────────────────

    [Fact(DisplayName = "EncodeMessage: valid message encodes to exactly 79 tones all in [0,7]")]
    public void EncodeMessage_ValidMessage_Produces79TonesInRange()
    {
        // Arrange
        var tones = new byte[Ft8LibInterop.EncodedToneCount];

        // Act — must not throw
        Ft8LibInterop.EncodeMessage(ValidMessage, tones);

        // Assert
        tones.Should().HaveCount(79, "FT8 always produces 79 symbols");
        tones.Should().OnlyContain(t => t <= 7,
            "tone indices must be in [0, 7] — FT8 is 8-FSK");
    }

    [Fact(DisplayName = "EncodeMessage: EncodedToneCount constant is 79")]
    public void EncodedToneCount_Is79()
    {
        Ft8LibInterop.EncodedToneCount.Should().Be(79);
    }

    [Fact(DisplayName = "EncodeMessage: larger buffer works — only first 79 elements are written")]
    public void EncodeMessage_LargerBuffer_WritesFirst79Elements()
    {
        // Arrange
        var tones = new byte[100]; // larger than needed
        tones[79] = 0xFF;         // sentinel — must not be overwritten

        // Act
        Ft8LibInterop.EncodeMessage(ValidMessage, tones);

        // Assert: first 79 elements filled with valid tones
        tones[..79].Should().OnlyContain(t => t <= 7);
        // Sentinel byte untouched — native shim respects tones_capacity
        tones[79].Should().Be(0xFF, "native shim must not write past index 78");
    }

    // ── Error paths ───────────────────────────────────────────────────────────

    [Fact(DisplayName = "EncodeMessage: short buffer (< 79) throws ArgumentException without calling native")]
    public void EncodeMessage_ShortBuffer_ThrowsArgumentException()
    {
        // Arrange — buffer with only 78 elements
        var shortBuffer = new byte[78];

        // Act & Assert
        var act = () => Ft8LibInterop.EncodeMessage(ValidMessage, shortBuffer);
        act.Should().ThrowExactly<ArgumentException>()
           .WithParameterName("tonesOut")
           .WithMessage("*79*");
    }

    [Fact(DisplayName = "EncodeMessage: message longer than 35 characters throws InvalidOperationException")]
    public void EncodeMessage_TooLongMessage_ThrowsInvalidOperationException()
    {
        // Arrange — 36-character message; FT8 max is 35 chars
        var longMessage = new string('Q', 36);
        var tones       = new byte[Ft8LibInterop.EncodedToneCount];

        // Act & Assert
        var act = () => Ft8LibInterop.EncodeMessage(longMessage, tones);
        act.Should().ThrowExactly<InvalidOperationException>()
           .WithMessage("*could not pack*");
    }

    [Fact(DisplayName = "EncodeMessage: empty message throws InvalidOperationException")]
    public void EncodeMessage_EmptyMessage_ThrowsInvalidOperationException()
    {
        var tones = new byte[Ft8LibInterop.EncodedToneCount];
        var act   = () => Ft8LibInterop.EncodeMessage("", tones);
        act.Should().ThrowExactly<InvalidOperationException>();
    }
}
