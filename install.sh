#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Setting up vocal-synth-mcp..."
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

if [ -z "${VOCAL_SYNTH_DIFFSINGER_HOME:-}" ]; then
    echo ""
    echo "VOCAL_SYNTH_DIFFSINGER_HOME is not set."
    echo "Clone openvpi/DiffSinger separately, install its own requirements.txt"
    echo "(PyTorch >=2.4.0 matched to your CUDA version), then set:"
    echo "  export VOCAL_SYNTH_DIFFSINGER_HOME=/path/to/DiffSinger"
    echo "See docs/INSTALLATION.md for full steps."
fi

echo "Done. Run 'vocal-synth-mcp' (inside .venv) to start the server."
