# Vocal-Synth-MCP

Renders a **vocal-only** WAV stem from an explicit melody + lyrics. This
server never composes anything — no melody, no lyrics, no backing
instrumentation. All of that reasoning is yours, done in conversation with
the user before calling any tool here.

## Workflow

1. If a REAPER project is open (via a connected reaper-mcp server), read
   its key/BPM/structure first — don't guess parameters you can look up.
2. Work out lyrics and an explicit vocal melody (pitch + rhythm per
   syllable) matching the requested mood/style/section. Reason about the
   note sequence first, then separately about expressive delivery
   (dynamics, phrasing) — don't conflate the two in one step.
3. Propose the lyrics back to the user for confirmation before rendering.
4. Call `validate_score` first — it's a fast, free pre-check that catches
   out-of-range notes and structural problems before a full render.
5. Call `list_voicebanks` to pick a `voicebank` id and confirm your notes
   fit its MIDI range.
6. Call `synthesize_vocal` with the confirmed, explicit result.
7. Read the returned `diagnostics` — warnings, requested vs. actual
   duration. If something looks wrong, decide whether to adjust notes and
   retry, or ask the user. This server will not retry or adjust anything
   on its own.

## Note format

Every tool that takes notes expects a list of:

```json
{"pitch": 60, "duration_beats": 1.0, "lyric": "hi"}
```

- `pitch`: MIDI note number (36-84 by default; a chosen voicebank may be
  narrower — check `list_voicebanks`). Use `-1` for a rest.
- `duration_beats`: note length in beats, relative to the call's `bpm`.
- `lyric`: one syllable per sung note. `null`/omitted for rests.

One `NoteEvent` per syllable — this server does not split words into
syllables for you.

## Simple vs. granular control

`synthesize_vocal`'s `expressive_params` argument is optional. Omit it for
normal use — DiffSinger's own variance model predicts pitch/energy/
breathiness automatically. Supply it only when you want precise control,
e.g. reacting to a previous take's diagnostics with an explicit pitch
curve.

## Output

Vocal-only WAV stem. No bass, synths, or other backing elements are ever
part of the output — if you want a full arrangement, that's composed
separately (e.g. via reaper-mcp) and this stem is dropped in alongside it.
