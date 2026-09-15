#!/bin/sh
# One-command setup for macOS and Linux. Finds a Python 3 and runs bootstrap.py,
# which checks your tools and sets up the backend and the app.
#
#   sh setup.sh            set everything up
#   sh setup.sh --run      ...then start the server and launch the app
#   sh setup.sh --help     all options
set -e
cd "$(dirname "$0")"
for py in python3.12 python3.11 python3 python; do
  if command -v "$py" >/dev/null 2>&1 && "$py" -c 'import sys; sys.exit(sys.version_info < (3, 8))' >/dev/null 2>&1; then
    exec "$py" bootstrap.py "$@"
  fi
done
echo "Python 3 is required. Install Python 3.12 from https://www.python.org/downloads/ and re-run." >&2
exit 1
