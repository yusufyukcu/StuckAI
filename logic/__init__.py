# Logic module
"""
Business logic components for Video Scene Analyzer
"""

# Import subprocess utilities to prevent CMD windows from appearing
from .windows_subprocess import run_hidden, popen_hidden, install_global_no_console_patch

# Note: Global patch is not installed here to avoid conflicts with asyncio
# It will be installed later when the main application starts

__all__ = [
    'run_hidden',
    'popen_hidden', 
    'install_global_no_console_patch'
] 