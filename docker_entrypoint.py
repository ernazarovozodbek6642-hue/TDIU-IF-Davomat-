"""Validate the immutable container setup, then replace this process with the bot."""
import os
import subprocess
import sys


subprocess.run([sys.executable, "deployment_check.py", "--local"], check=True)
os.execv(sys.executable, [sys.executable, "main.py"])
