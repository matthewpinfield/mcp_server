#!/bin/bash

# The full path to the python executable INSIDE the venv
VENV_PYTHON="/mnt/caseSSD/continue_custom_rag/venv/bin/python3"

# The full path to the python script you want to run
PYTHON_SCRIPT="/mnt/caseSSD/continue_custom_rag/optimal_server.py"

# 'exec' replaces the shell with the python process.
# This is the correct way to run a script inside a venv from another script.
exec "$VENV_PYTHON" "$PYTHON_SCRIPT"
