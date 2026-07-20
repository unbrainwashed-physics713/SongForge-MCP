# Installation

## 1. Install this package

```bash
./install.sh    # or install.bat on Windows
```

This creates a `.venv` and installs `vocal-synth-mcp` plus its dev
dependencies (`pytest`, `pytest-asyncio`, `g2p_en`).

`g2p_en` (lyric → phoneme conversion) depends on NLTK corpus data
(`cmudict`, `averaged_perceptron_tagger_eng`) that downloads
automatically on first use if not already cached locally. This requires
network access the first time `synthesize_vocal`/`build_ds_file` actually
runs; for an offline or CI deployment, pre-download it once with:

```bash
python -c "import nltk; nltk.download('cmudict'); nltk.download('averaged_perceptron_tagger_eng')"
```

## 2. Set up DiffSinger separately

DiffSinger is not a Python dependency of this project — it's a
separately-cloned checkout this server subprocesses into.

```bash
git clone https://github.com/openvpi/DiffSinger.git
cd DiffSinger
python -m venv .venv-diffsinger
source .venv-diffsinger/bin/activate   # .venv-diffsinger\Scripts\activate on Windows
pip install torch>=2.4.0   # match this to your CUDA version first — see pytorch.org
pip install -r requirements.txt
```

Set `VOCAL_SYNTH_DIFFSINGER_HOME` to point at that clone:

```bash
export VOCAL_SYNTH_DIFFSINGER_HOME=/path/to/DiffSinger        # macOS/Linux
setx VOCAL_SYNTH_DIFFSINGER_HOME "C:\path\to\DiffSinger"       # Windows
```

## 3. Install a voicebank

v1 ships configured for the LUNAI Project's "Katyusha" voicebank (see
`vocal_synth_mcp_shared/voicebanks.py` for the full license summary —
non-commercial use is fine with attribution, commercial use needs
written per-character permission from LUNAI first).

1. Download the voicebank from LUNAI Project's GitHub releases
   (`github.com/lunaiproject/lunai_singers`).
2. Extract the DiffSinger checkpoint from its OpenUtau packaging into
   `$VOCAL_SYNTH_DIFFSINGER_HOME/checkpoints/lunai_katyusha/` (the folder
   name must match the `experiment` value in `voicebanks.py`).
3. To use a different voicebank instead, add a new entry to
   `VOICEBANK_REGISTRY` in `vocal_synth_mcp_shared/voicebanks.py` — one
   dataclass instance, no other code changes needed.

## 4. Run

```bash
vocal-synth-mcp
```

Add it to your MCP client config (Claude Desktop/Code) alongside
reaper-mcp, same as any other stdio MCP server.
