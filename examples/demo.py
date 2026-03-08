"""envcore demo — demonstrates runtime import tracing.

Run with:  envcore trace examples/demo.py
"""

import json   # stdlib — will be filtered out
import os     # stdlib — will be filtered out
import sys    # stdlib — will be filtered out

# Third-party imports that envcore itself does NOT use.
# These will appear in the generated manifest.
import pytest
import coverage

print("Hello from the envcore demo script!")
print(f"Python {sys.version}")
print(f"CWD: {os.getcwd()}")
print(f"pytest version: {pytest.__version__}")
