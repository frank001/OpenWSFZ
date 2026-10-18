using System.Text.Json.Serialization;

namespace OpenWSFZ.Abstractions;

/// <summary>
/// third-pass-deep (#240, step 1): how many subtract-and-decode rounds a cycle gets after pass 0.
/// Serialised as its name (<c>"Normal"</c> / <c>"Deep"</c>) via <see cref="JsonStringEnumConverter{TEnum}"/>.
/// </summary>
[JsonConverter(typeof(JsonStringEnumConverter<DecodingDepth>))]
public enum DecodingDepth
{
    /// <summary>
    /// Pass 0 and, when <c>decoder.subtractionEnabled</c> is on, the residual pass: exactly the decoder as it was before
    /// the third pass existed (bit-for-bit). The default.
    /// </summary>
    Normal = 0,

    /// <summary>
    /// <see cref="Normal"/> plus one more incremental subtract-and-decode round on the residual buffer (the third pass,
    /// published as batch 3). Additive only; it shares the 13 s cycle budget. Has an effect only while the residual
    /// pass is on.
    /// </summary>
    Deep = 1,
}
