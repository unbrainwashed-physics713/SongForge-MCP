# Tools

`generate_vocal_track` and `check_vocal_track_status` are a start/poll
pair, not two independent tools — see why in
[`docs/ARCHITECTURE.md`](ARCHITECTURE.md#why-generation-is-a-startpoll-pair-not-one-blocking-call).
`split_vocal_stems` is a single blocking call (separation is short).
Once finished, both the completed job and `split_vocal_stems` return
their audio inline as playable content — the result can be listened to
directly in the conversation — alongside the JSON payload shown below.

## `generate_vocal_track(caption, lyrics, reference_audio_path=None, reference_youtube_url=None, advanced_settings=None, output_format="wav", remix_source_path=None, remix_source_youtube_url=None, remix_strength=0.5) -> dict`

Starts generating a complete original track — vocals and instrumentation
together — via ACE-Step 1.5. **Returns immediately** with a `job_id`; it
does not wait for generation to finish.

**Arguments**

- `caption` *(required)* — genre, mood, instrumentation, and vocal-style
  description, e.g. `"melodic dubstep, female vocals, dreamy, atmospheric,
  150 BPM"`. Genre and production descriptors are the right level of
  detail; naming a specific real artist as the intended voice is
  deliberately avoided here in favor of describing their characteristic
  sound (see [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) for why).
- `lyrics` *(required)* — full original lyrics using ACE-Step's section
  tags: `[verse]`, `[pre-chorus]`, `[chorus]`, `[bridge]`, `[outro]`, or
  `[instrumental]` / `[inst]` for a section with no vocals. At least one
  section tag is required.
- `reference_audio_path` *(optional)* — a local audio file to use as a
  style reference. Confirmed from ACE-Step's own source: this conditions
  the model on a real acoustic latent of the reference clip (the same VAE
  encoder used for real audio), not a narrow vocal-timbre-only signal —
  so besides voice character, it plausibly nudges instrumentation and
  production texture toward the reference too. It never determines
  melody, rhythm, or what's actually sung — that's fully controlled by
  `lyrics`. Exactly how strongly it competes against `caption` hasn't
  been confirmed by ear in this project; if a specific instrument needs
  to be dominant, name it explicitly in `caption` rather than relying on
  a reference clip alone. Mutually exclusive with `reference_youtube_url`.
- `reference_youtube_url` *(optional)* — a YouTube URL to use as the same
  kind of style reference; the audio is downloaded automatically first.
  Same caveats as `reference_audio_path` above.
- `advanced_settings` *(optional)* — a map of exact ACE-Step UI field
  names to override values, e.g. `{"Guidance Scale": 8.5, "Seed":
  "12345"}`. Intended for correcting a specific setting when a result
  isn't right; every field not listed here keeps ACE-Step's own default.
- `output_format` *(optional, default `"wav"`)* — one of `"wav"`, `"flac"`,
  `"mp3"`, `"opus"`, `"aac"`, `"wav32"`. Defaults to uncompressed WAV
  rather than ACE-Step's own MP3 default, since it's the more useful
  format for importing into a DAW for further production — at the cost
  of a much larger file (tens of MB, vs a few for MP3). Pass `"mp3"`
  explicitly if a smaller file matters more than editing quality for a
  given request.
- `remix_source_path` / `remix_source_youtube_url` *(optional)* —
  **actively discouraged.** Switches to ACE-Step's Remix mode, using the
  given audio as a structural base. A real test in this project found two
  confirmed problems: (1) harmony/tuning quality no better than
  `reference_audio_path`'s own confirmed problems, and (2) the source
  track's own recognizable melody and apparent lyrics bled into the
  output even when completely different, original lyrics were supplied —
  a real copyright exposure, not just a quality issue, and a direct
  contradiction of ACE-Step's own documented design for this mode.
  Mutually exclusive with each other and with `reference_audio_path`/
  `reference_youtube_url`. Prefer describing the desired vibe in
  `caption` instead.
- `remix_strength` *(optional, default `0.5`)* — 0.0-1.0, only meaningful
  alongside `remix_source_path`/`remix_source_youtube_url`. Confirmed
  *not* to reliably prevent the source's own content from bleeding
  through even at low values (0.3 was tested and still bled through).

**Returns**

```json
{ "job_id": "5e9d2b3a-..." }
```

**Raises** `SongForgeMCPError` — `MISSING_PARAMETER` / `INVALID_PARAMETER`
(empty or malformed caption/lyrics, both reference sources given at
once, `reference_audio_path` doesn't exist or isn't a real audio file,
`output_format` isn't one of the supported values). Validation happens
synchronously before the job starts, so these are raised immediately, not
discovered later via `check_vocal_track_status`.

## `check_vocal_track_status(job_id, wait_seconds=25.0) -> list`

Polls a `generate_vocal_track` job. If the job is still running, this
blocks server-side for up to `wait_seconds` (capped at 25s) before
replying — deliberately, so the calling model can just call this again
immediately on a `"running"` result rather than needing to add its own
delay between polls, which keeps the number of round-trips (and the
narration temptation that comes with each one) down for a multi-minute
generation.

**Arguments**

- `job_id` *(required)* — the `job_id` a prior `generate_vocal_track`
  call returned.
- `wait_seconds` *(optional, default 25.0)* — how long this call may
  block if still running before returning `"running"` anyway.

**Returns** — a list whose first item is one of:

```json
{ "status": "running", "progress": 0.4, "message": "Generating - 40%" }
```
```json
{ "status": "error", "error": "[SYNTHESIS_FAILED] ACE-Step reported: ..." }
```
```json
{
  "status": "complete",
  "audio_path": "C:\\...\\renders\\....wav",
  "diagnostics": {
    "generation_seconds": 82.8,
    "duration_seconds": 214.3,
    "used_reference_audio": false,
    "output_format": "wav"
  },
  "note": "... the file already exists on disk and can be opened directly ..."
}
```

On `"complete"`, the rendered track is also returned as playable audio (a
second list item) — the `note` field exists because not every MCP client
renders that inline yet; `audio_path` is always a reliable fallback.

**Raises** `SongForgeMCPError` — `FILE_NOT_FOUND` (unrecognized `job_id`
— jobs live in memory only and don't survive a server restart).

## `split_vocal_stems(audio_path) -> list`

Separates a generated track into an isolated vocal stem and an isolated
instrumental stem. Unlike generation, this blocks until done — real
separations were measured at 5-15 seconds, comfortably inside any
reasonable client timeout, so it doesn't need the job/poll treatment.

**Arguments**

- `audio_path` *(required)* — path to a file this server previously
  produced, typically the `audio_path` from a completed
  `generate_vocal_track` job. Must resolve inside this server's own
  output folder — see
  [`docs/ARCHITECTURE.md`](ARCHITECTURE.md#file-access-boundaries) for
  why this is deliberately stricter than `reference_audio_path` above.

**Returns** — both stems as playable audio, plus:

```json
{
  "vocals_path": "C:\\...\\stems\\..._(Vocals)_....wav",
  "instrumental_path": "C:\\...\\stems\\..._(Instrumental)_....wav"
}
```

Separation quality is good but not perfect — some bleed from
instrumentation into the vocal stem is an observed limitation of the
current separation model, not something a retry will fix.

**Raises** `SongForgeMCPError` — `FILE_NOT_FOUND`, `INVALID_PARAMETER`
(path exists but isn't inside this server's output folder, or isn't a
real audio file), `SEPARATOR_NOT_CONFIGURED` (see
[`docs/INSTALLATION.md`](INSTALLATION.md)), `SUBPROCESS_TIMEOUT`,
`SEPARATION_FAILED`.

## `play_audio(audio_path) -> dict`

Plays a file this server previously produced, on demand. A completed
`generate_vocal_track` already auto-plays its result via the OS's own
default app for the file type (Media Player on Windows) — this tool is
the fallback for when that didn't work or wasn't seen, or for replaying
an earlier result later in the conversation.

**Arguments**

- `audio_path` *(required)* — a file this server previously produced.
  Must resolve inside this server's own output folder, same restriction
  as `split_vocal_stems`' `audio_path` above.

**Returns**

```json
{"status": "playing", "audio_path": "C:\\...\\renders\\....wav"}
```

**Raises** `SongForgeMCPError` — `FILE_NOT_FOUND`, `INVALID_PARAMETER`
(path exists but isn't inside this server's output folder, or isn't a
real audio file).

## `generate_vocal_track_takes(caption, lyrics, num_takes=3, reference_audio_path=None, reference_youtube_url=None, advanced_settings=None, output_format="wav", song_title=None) -> dict`

Same as `generate_vocal_track`, but runs `num_takes` (2-5) independent
generations sequentially, each with its own random seed, and measures
each result with the same analysis `analyze_reference_audio` uses (BPM,
key, mode) so results can actually be compared rather than just picking
whichever one finished first. Runs sequentially, not in parallel — this
server's GPU is a single shared resource, and this project has already
measured what happens when generations contend for it (see CHANGELOG).
Takes roughly `num_takes` times as long as a single generation.

**Returns** `{"job_id": str}` — poll `check_vocal_track_status` exactly
as for `generate_vocal_track`. On completion, returns `{"takes": [...]}`,
one entry per take in order: `{"audio_path", "seed", "diagnostics", "measured": {"bpm", "key", "mode", "key_confidence"}}`.
A take that individually fails is recorded as `{"seed", "error"}` instead
— one bad take doesn't fail the whole job.

**Raises** `SongForgeMCPError` — same as `generate_vocal_track`, plus
`VALUE_OUT_OF_RANGE` if `num_takes` isn't between 2 and 5.

## `list_generated_tracks(limit=50) -> list[dict]`

Lists finished tracks sitting in this server's output folder, newest
first — for when a past generation's `job_id` has been lost (jobs are
in-memory only and don't survive a server restart) or you want to see
what's already been made. Doesn't include split-out stems, only full-mix
renders.

**Returns** a list of `{"path", "filename", "size_bytes", "modified_at", "duration_seconds"}` (duration is best-effort, `None` if it couldn't be read).

## `list_recent_jobs(limit=20) -> list[dict]`

Lists recent background jobs from any of this server's job-based tools,
newest first — for when a `job_id` has been lost mid-conversation.

**Returns** a list of `{"job_id", "status", "progress", "message", "created_at"}`
— call `check_vocal_track_status` for a job's full result.

## `delete_generated_track(audio_path) -> dict`

Moves a file this server previously produced into a `.trash` subfolder —
**not a permanent delete.** Deliberately reversible: a calling model (or
a manipulated/injected instruction) being wrong about what's safe to
remove should never be able to permanently destroy a generation. To
actually reclaim disk space, empty `.trash` yourself via File Explorer —
there's no tool for that, on purpose.

**Returns** `{"status": "moved_to_trash", "audio_path": ..., "trash_path": ...}`.

**Raises** `SongForgeMCPError` — `FILE_NOT_FOUND`, `INVALID_PARAMETER`
(path outside the output folder).

## `edit_audio_track(audio_path, trim_start_seconds=None, trim_end_seconds=None, fade_in_seconds=None, fade_out_seconds=None, output_format=None) -> dict`

Starts trimming and/or fading a file this server previously produced.
Writes a **new** file — never overwrites the original. `output_format`
is `"wav"`, `"flac"`, or `"mp3"` (defaults to the source file's own
format if it's one of these three, otherwise `"wav"`); mp3 output
requires `ffmpeg` on PATH (see `docs/INSTALLATION.md`), since soundfile
can only write wav/flac directly.

**Returns** `{"job_id": str}` — poll `check_vocal_track_status` exactly
as for `generate_vocal_track`. On completion, returns `{"audio_path", "duration_seconds", "output_format"}`.

**Raises** `SongForgeMCPError` — `FILE_NOT_FOUND`, `INVALID_PARAMETER`
(path outside the output folder, unsupported `output_format`),
`VALUE_OUT_OF_RANGE` (trim range outside the file's duration, fades
longer than the trimmed clip), `SUBPROCESS_FAILED`/`SUBPROCESS_TIMEOUT`
(mp3 conversion via ffmpeg).

## Example request

> "Write me an original melodic dubstep track in the style of Illenium —
> a female vocal, dreamy and a little melancholic, about holding on to a
> memory. Full verse/chorus/bridge structure. Give me the vocal
> separated out afterward so I can build my own instrumental around it."

Claude would work out the caption and full original lyrics, confirm them
with you, call `generate_vocal_track`, tell you generation has started,
poll `check_vocal_track_status` every 20-30 seconds — narrating progress
to you between calls — and once complete, call `split_vocal_stems` on
the result.
