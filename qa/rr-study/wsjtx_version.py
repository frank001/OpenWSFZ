"""WSJT-X appraiser version: record it, and refuse a Q-prefix battery on WSJT-X >= 3.0 (QA tooling).

Why: WSJT-X 3.x added `callok` (lib/77bit/packjt77.f90) which rejects every standard callsign starting with Q, and the synthetic
S1-S8 truth set is Q-prefix only (NFR-021), so a 3.x appraiser decodes none of it and every between-appraiser row is void
(found 2026-10-11; 2.7.0 has no `callok`). Architect, REFERENCE-SET 2026-10-11: "record the WSJT-X version string on every sweep and
refuse a Q-prefix battery when the appraiser is >= 3.0". An unrecorded or unparseable version is refused too (uncertainty disqualifies).
"""
import re

_VERSION_RX = re.compile(r"(\d+)\.(\d+)(?:\.(\d+))?")
Q_PREFIX_MAX_EXCLUSIVE = (3, 0)      # first WSJT-X version that rejects Q-prefix callsigns


def parse_version(text):
    """-> (major, minor, patch) from the first dotted number in `text`, or None."""
    if not text:
        return None
    m = _VERSION_RX.search(str(text))
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)


def check(text):
    """Returns {"recorded": str|None, "parsed": "x.y.z"|None, "checks": {...}} for arm_config.json.

    checks.wsjtx_version_recorded           the string parses to a version
    checks.wsjtx_version_supports_q_prefix  parsed and below 3.0 (a battery with Q-prefix truth may run)
    """
    v = parse_version(text)
    return {
        "recorded": text if text else None,
        "parsed": ".".join(str(x) for x in v) if v else None,
        "checks": {
            "wsjtx_version_recorded": v is not None,
            "wsjtx_version_supports_q_prefix": v is not None and v < Q_PREFIX_MAX_EXCLUSIVE,
        },
    }
