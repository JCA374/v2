"""
This file contains pytest configurations and shared fixtures.
It automatically runs when pytest starts.
"""

import os
import sys

# Add the parent directory to the path so tests can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
