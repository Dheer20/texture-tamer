#!/bin/sh
# How to run all tests (Git Bash, from the project folder):
#   sh tests/run_tests.sh
# 1. builds dist/texture_tamer-<version>.zip
# 2. installs it into a throw-away Blender profile in tests/_blender_user
#    (your normal Blender settings are not touched)
# 3. runs the name test (plain Python) and the Blender test (headless)
# Make the messy test copies once first:
#   blender -b --factory-startup --python tests/make_messy_sets.py
set -e
# Override with BLENDER=... / PYTHON=... if yours live elsewhere.
B="${BLENDER:-C:/Program Files/Blender Foundation/Blender 5.3/blender.exe}"
PY="${PYTHON:-python}"
cd "$(dirname "$0")/.."
rm -rf dist && mkdir dist
"$B" --factory-startup --command extension validate source/texture_tamer
"$B" --factory-startup --command extension build --source-dir source/texture_tamer --output-dir dist
export BLENDER_USER_RESOURCES="$(pwd)/tests/_blender_user"
"$B" --factory-startup --command extension install-file -r user_default -e dist/texture_tamer-*.zip
"$PY" tests/test_names.py
"$B" -b --factory-startup --python tests/test_blender.py 2>&1 | grep -E "PASS|FAIL|RESULT|Error|Traceback|line [0-9]"
