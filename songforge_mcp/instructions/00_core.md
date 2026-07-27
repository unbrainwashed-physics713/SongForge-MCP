# SongForge-MCP

Generates full EDM/vocal tracks via ACE-Step 1.5 — singing performance and
instrumental together, from a caption + full lyrics. This server never
invents lyrics or musical direction; that reasoning happens in conversation
with the user before any tool call.

## Workflow

1. If the request is vague, ask conversationally for whatever's missing:
   genre/subgenre, reference artists' *sound*, mood, subject matter, and
   (only if likely to matter to the user) BPM/key/length. Don't ask about
   things already specified or things fine to leave to your judgment.
2. Draft the caption (genre/mood/instrumentation/vocal-style tags) and
   lyrics. Ask whether the user wants to supply lyrics or have you write
   them; user-supplied lyrics are used as given, just reformatted with
   `[verse]`/`[chorus]`/`[bridge]` tags. Written-by-you lyrics must be
   original, not adapted from a real song. Confirm caption + lyrics with
   the user before generating. **Always come up with a real song title**
   (or use one the user gives) and pass it as `song_title` on the
   `generate_vocal_track` call — it names the output file on disk instead
   of leaving it as a bare timestamp/UUID.
3. If a real artist is named as the style target, never put their name in
   `caption`/`lyrics` — translate their sound into descriptive genre/
   production/vocal-style language instead. This server does not clone a
   specific real person's voice.
4. If the user gives a reference (local file or YouTube link) for its
   sound, pass it as `reference_audio_path`/`reference_youtube_url` on the
   `generate_vocal_track` call itself — don't just acknowledge it in chat.
   **Warn before using it**: reference audio conditions on a real acoustic
   latent from the clip and has produced vocals that go out of tune. Don't
   attach it silently; let the user decide. Don't offer it unprompted.
   **Don't suggest Remix mode as a safer alternative.** Remix has the same
   tuning risk plus a worse one: it can reproduce the source's own melody
   and apparent lyrics even when given different lyrics to sing — a
   copyright exposure, not just a quality issue. If the user explicitly
   wants Remix anyway, state both risks plainly first. `remix_melody_retention`
   and `remix_no_fsq` are not fixes for garbled vocals — testing found
   every setting only trades one failure mode (garbled vocals) for the
   other (a near-exact copy of the source).
5. Call `generate_vocal_track` with the confirmed caption/lyrics (plus any
   reference). It returns a `job_id` immediately without waiting for
   generation. Tell the user generation started in one short message, then
   poll `check_vocal_track_status(job_id)` — it already waits briefly
   server-side, so no extra delay needed. **Stay quiet while polling**;
   only speak again after a couple of minutes with no result, or once it
   reaches `"complete"`/`"error"`. Narrating every poll wastes the user's
   budget for no benefit.

   The `progress` fraction commonly plateaus around 0.5 for several
   minutes before jumping straight to complete — this value comes
   directly from ACE-Step's own progress display, and the plateau is
   normal (a later pipeline phase doesn't update it). State this as fact,
   not as a hedge ("this can happen"). Treat it as a real problem only if
   `check_vocal_track_status` itself errors or stops responding, or
   elapsed time badly exceeds this server's generation timeout.
5.5. **If a specific BPM or key was part of the agreed creative direction
   (not just a mood description), set it explicitly via
   `advanced_settings` (e.g. `{"BPM (Beats Per Minute)": 150, "Key": "F minor"}`)
   — don't rely on caption prose alone ("dark", "minor-key feel") to get
   there; ACE-Step doesn't reliably infer tempo/key from mood language.**
   Even then, treat the result as unverified: ACE-Step's `Key`/`BPM`
   fields are soft hints, not hard constraints, and have been observed
   landing on a completely different key/mode (not just an adjacent one)
   even when set explicitly — a real, measured case, not a hypothetical.
   Once a job completes, call `analyze_reference_audio` on the finished
   `audio_path` and compare its measured `bpm`/`key`/`mode` against what
   was actually intended **before** telling the user it's done. If they
   don't reasonably match (especially a major/minor mismatch — this
   flips the entire emotional character of a track, not a minor
   deviation), say so plainly and offer to regenerate rather than
   presenting a mismatched result as a finished deliverable and leaving
   the user to catch it by ear.
6. Only split out the vocal if the user explicitly asks for it — never
   automatically. The full mix is the default deliverable. When you do
   need the stems, **prefer `generate_vocal_track(..., split_stems=True)`
   over a separate `split_vocal_stems` call** — it runs in the same job
   and returns `vocals_path`/`instrumental_path` directly from
   `check_vocal_track_status`, with no path to relay between two tool
   calls. `split_vocal_stems` still exists for splitting a file from an
   earlier, already-completed job — **it also returns a `job_id`
   immediately and must be polled with `check_vocal_track_status` exactly
   like `generate_vocal_track`, not awaited as a single blocking call.**
   It only accepts files this server already produced. Splitting is
   idempotent — calling it again on a file already split returns the
   existing stems in well under a second instead of re-running
   separation, so if you've lost track of an earlier vocals_path/
   instrumental_path (e.g. a long conversation), it is always cheap and
   safe to call it again on the same audio_path rather than regenerating
   the whole song from scratch. Some synth/reverb bleed into the vocal
   stem is a known limitation of the separation
   itself, not a bug.
7. Read the returned `diagnostics`. If something's off, decide whether to
   adjust caption/lyrics/`advanced_settings` and retry, or ask the user —
   this server never retries or adjusts on its own.

## ACE-Step modes

ACE-Step exposes more modes than this server uses; understanding them
avoids reaching for the wrong tool.

**Reference Audio** (`reference_audio_path`/`reference_youtube_url`) is
mode-independent — available in every mode except Simple and Extract.
Mechanism: samples three 10s chunks (front/middle/back), VAE-encodes them
into one acoustic latent, conditions the whole generation on it. Carries
real acoustic/harmonic content, not just timbre — this is the source of
the tuning-corruption risk in step 4, regardless of mode.

**Source Audio** means something different per mode:
- *Custom*: unused for generation.
- *Remix* (`remix_source_path`/`remix_source_youtube_url`): the entire
  structural basis for a "cover" task — takes the whole mixed source
  (vocals + instrumental together, never separated) as one structural
  code sequence. No mechanism to keep one part while regenerating another.
- *Repaint*: regenerates a specific time range, preserving the rest.
- *Extract*: isolates a single track from a mix. Requires ACE-Step's Base
  model, not configured on this server — `split_vocal_stems` (BS-Roformer)
  is the working substitute and needs no Base model.
- *Lego*: adds one new track to existing audio. Base-model-only.
- *Complete*: given a partial track (e.g. vocal-only), generates the
  missing tracks around it. Base-model-only. This is the architecturally
  correct "keep the vocal, get a new instrumental" tool — Remix is not.
  The Base model (`acestep-v15-xl-base`) is a real, downloadable
  checkpoint (same mechanism as the XL-SFT checkpoint in use), just not
  set up on this server yet; using it means launching with
  `--config_path acestep-v15-xl-base` instead. Not currently integrated —
  see the recommended workflow below for the interim approach.

## Preparing a named voice reference library

When the user wants to use a particular named voice, call
`prepare_voice_reference(voice_name)` with no `youtube_url` first — never
skip straight to asking for a link or generating without checking. Two
outcomes:
- Clips already exist (`status: "found"`) — check
  `meets_recommended_minimum`. If False, tell the user how much material
  exists (`total_duration_seconds`) and that more is needed before
  treating it as ready; don't silently proceed as if one clip were
  enough.
- None exist (`status: "not_found"`) — ask the user to paste a YouTube
  link for a song featuring that voice, recommending an acoustic version
  if one exists (sparser instrumentation separates into a cleaner
  vocal), and set the expectation up front that one video is very
  unlikely to be enough on its own. Never search for or guess a link
  yourself.

Once given a link, call `prepare_voice_reference(voice_name, youtube_url)`
— returns a `job_id`, poll with `check_vocal_track_status` exactly like
`generate_vocal_track`. Repeat with additional links until
`meets_recommended_minimum` is True. This is for the user's own private
reference material — see the copyright/right-of-publicity concerns
already discussed for extracting a real, identifiable person's voice
from commercial recordings; that judgment call belongs to the user, but
must be surfaced, not silently assumed.

## Recommended workflow for "new instrumental under an existing vocal"

ACE-Step Custom mode is the default/primary path — it produces a full
song (vocals + instrumental together in one pass) reliably. Remix mode
stays available only on explicit request, never as a fallback.

Generating a real vocal's instrumental independently (extract the real
vocal from an existing song, generate a new instrumental separately to
fit it) was tried and does not work reliably:
- ACE-Step's `Key` field and Reference Audio are soft hints, not hard
  constraints — requested keys have landed on closely related but wrong
  keys.
- The overall key matters far less than the actual chord-by-chord
  progression, which is not reliably recoverable from audio via DSP
  (`audio_analysis.py` measures BPM/key only, deliberately not chords —
  see its docstring). Real chord charts (via web search against sites
  like Chordify/Ultimate-Guitar for an identified song) are the reliable
  source.
- Independently generated audio doesn't share a beat grid with the real
  vocal even at a matching BPM — reliable frame-accurate beat alignment
  between separately generated/recorded audio isn't solved here.

None of this applies within a single Custom-mode generation — vocals and
instrumental share one beat grid natively.

**Recommended path for a from-scratch song plus an editable DAW start**:
`generate_vocal_track` (Custom mode) → `split_vocal_stems` for the
instrumental → `transcribe_instrumental_to_midi`. That tool returns FOUR
MIDI files: a flat transcription (`midi_path`, every note layered
together — not usable as a DAW starting point on its own) plus a
heuristic split into `bass_midi_path`/`melody_midi_path`/
`chords_midi_path` (by pitch register and note-overlap density — not
real instrument classification, but genuinely separate, assignable
parts). **Neither this tool's own result nor Reaper's own MIDI tools
expose real note content from an external file — only a path and a note
count.** If asked to recreate, describe, or import a transcribed MIDI
file's actual notes anywhere (including into Reaper via note-by-note
tools rather than a direct file import), call `get_midi_notes(midi_path)`
first to get real pitch/start/end/velocity data. Without it, there is no
real data to work from — attempting to reconstruct the notes anyway
produces fabricated content, not the real transcription, which has
happened and is a real, confirmed failure mode, not a hypothetical one.
`get_midi_notes` is paginated (`offset`/`max_results`, default 500) since
a real transcription can have hundreds of notes.

**Import the three split tracks as separate Reaper tracks, not
the flat one.** Importing audio/MIDI into an actual Reaper project (e.g.
via `reaper-mcp`) happens one level up, in whatever session has both
servers available — not this server's job, and this server has no way to
enforce it: before importing anything into Reaper, check what you've
already imported earlier in this same conversation (and, if reaper-mcp
offers a way to inspect the project's existing tracks, check that too)
rather than assuming nothing exists yet. Every generate/split/transcribe
tool in this server is idempotent — calling one again on a file already
processed returns the same real result instantly rather than redoing
the work — specifically so that re-checking before importing is always
cheap, never a reason to skip the check.

**Every path this server returns (`audio_path`, `midi_path`, `vocals_path`,
`instrumental_path`) is already a real, absolute Windows path, resolved on
the machine this server runs on — use that exact string directly as the
argument to another tool (e.g. `reaper-mcp`'s import).** Never scan a
folder or list directory contents to "find" the file instead of using the
value already returned to you — this has repeatedly produced wrong
results, including picking up unrelated leftover files from an entirely
different, older, unrelated audio project on the same machine that
happens to share part of its folder name. If you don't have a path a
tool returned, that's a reason to call the tool again, not to search the
filesystem. Never assume the file lives under the ACE-Step installation
directory (it doesn't — this server copies its result into its own output
folder, separate from ACE-Step's own working files), and never ask the
user to locate the file manually in File Explorer. You do not need
filesystem access yourself to do this correctly — you only need to relay
the string one tool returned as the argument to the next tool call.

**This server never attaches playable audio inline — every tool returns
file paths only, as plain text.** An earlier version did attach inline
audio and it caused real, repeated client-side failures ("unsupported
format") that corrupted the whole tool response, not just the audio
player — this was removed for that reason. If you ever see an
"unsupported format" error on a call to this server, that's a symptom of
something else going wrong (check the actual error), not a normal
by-product of a successful generation.

## Things not to guess at

- Reference audio carries real acoustic content, not just vocal timbre —
  it can influence instrumentation/production texture. It never carries
  melody, rhythm, or lyrics; `lyrics` still fully controls what's sung.
- Remix mode is not a safer alternative to reference audio — it's worse
  (same tuning risk, plus melody/lyric bleed-through). Treat it as
  discouraged by default; see step 4 for the required warning if a user
  insists on it.
- Leave `advanced_settings` empty for normal use. Every unnamed field
  stays at ACE-Step's own default, the only configuration proven
  reliable. An unrecognized label raises a clear error rather than
  silently doing nothing — that's a safety net, not permission to guess
  values.

## Output

`check_vocal_track_status` (on completion) and `split_vocal_stems` return
real file paths plus diagnostics — never inline audio. A completed job
gives the full mix; `split_vocal_stems` returns separated vocal/
instrumental stems. For a custom arrangement built around just the vocal, use
`split_vocal_stems` and build the rest elsewhere (e.g. via reaper-mcp) —
don't treat the generated mix as a finished master.
