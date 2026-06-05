"""Make the `synth` package importable when tests run from qa/rr-study/."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
