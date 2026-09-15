"""Validate the immutable container setup, then replace this process with the bot."""
import os
import subprocess
import sys


subprocess.run([sys.executable, "deployment_check.py", "--local"], check=True)
if os.getenv('RUN_BROWSER_DIAGNOSTICS', '').strip() == '1':
    subprocess.run([sys.executable, '-u', 'browser_diagnostics.py'], check=False)
os.execv(sys.executable, [sys.executable, "main.py"])
