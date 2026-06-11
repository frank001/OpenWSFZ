"""R&R study harness package.

NFR-022: reconfigure stdout to UTF-8 with replacement so that Greek letters,
Unicode minus signs, and other non-ASCII characters in study output never raise
UnicodeEncodeError on a Windows cp1252 console.  Placing this here ensures it
fires for every script that imports any harness.* submodule.
"""
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
