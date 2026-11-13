using System.Globalization;
using OpenWSFZ.Ft8.Dsp;
// QA tool (XC-BUILD 200-pair numeric comparison): S_E* of the Developer's detector on the same (buffer, centre, tones) the desk library scored. Numbers out, no text.
var inv = CultureInfo.InvariantCulture;
foreach (var line in File.ReadLines(args[0]))
{
    var p = line.Split('\t');
    var raw = File.ReadAllBytes(p[0]);
    var pcm = new float[raw.Length / 4];
    Buffer.BlockCopy(raw, 0, pcm, 0, raw.Length);
    var tones = p[3].Split(',').Select(byte.Parse).ToArray();
    var r = CrossCycleTemplateDetector.Search(pcm, double.Parse(p[1], inv), double.Parse(p[2], inv), tones);
    Console.WriteLine(string.Join("\t", r.SStar.ToString("R", inv), r.FreqHz.ToString("R", inv), r.Dt.ToString("R", inv)));
}
