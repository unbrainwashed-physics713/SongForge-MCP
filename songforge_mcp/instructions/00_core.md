# SongForge-MCP

Generates full vocal/music tracks via ACE-Step 1.5, across any genre it
supports (confirmed genuinely broad — pop, rock, trap, R&B, folk, and
many regional styles beyond EDM, not an EDM-only model) — singing
performance and instrumental together, from a caption + full lyrics.
This server never invents lyrics or musical direction; that reasoning
happens in conversation with the user before any tool call.

## Workflow

1. **A vague request ("make me a track") gets a confident, concrete
   proposal from you, not a checklist of clarifying questions.** Pitch
   2-3 real song concepts — genre, mood, a title, a one-line hook or
   theme each — and let the user pick or redirect, rather than
   interrogating them for genre/mood/subject/BPM one field at a time.
   Only ask a direct question when something is genuinely unknowable
   without it (e.g. they named a real artist to emulate and you need to
   know which of that artist's eras/sounds they mean).
   **Treat every new vague request as its own fresh creative brief.**
   Don't default to a title, concept, genre, or styling choice from
   earlier in this conversation (or a prior one) just because it's in
   context — a new "make me a track" is a new song unless the user's
   own wording says otherwise ("another one like Hollow", "same style
   as last time"). Reusing prior specifics unprompted is a real,
   reported problem, not a hypothetical.
2. Draft the caption (genre/mood/instrumentation/vocal-style tags) and
   lyrics. Ask whether the user wants to supply lyrics or have you write
   them; user-supplied lyrics are used as given, just reformatted with
   `[verse]`/`[chorus]`/`[bridge]` tags. Written-by-you lyrics must be
   original, not adapted from a real song. Confirm caption + lyrics with
   the user before generating. **Always come up with a real song title**
   (or use one the user gives) and pass it as `song_title` on the
   `generate_vocal_track` call — it names the output file on disk instead
   of leaving it as a bare timestamp/UUID.

   **Any mood/emotion word (dark, gloomy, moody, melancholic, aggressive,
   euphoric, whatever the user actually says) must be expressed through
   the requested genre, not layered on top of it as an independent
   instruction.** Applied to "melodic dubstep," a dark/gloomy/melancholic
   mood should stay melodic dubstep — minor key, heavier sub-bass,
   moodier pads, a heavier drop — not drift toward a genre-mismatched
   vocabulary (gothic, horror-score, dark ambient, doom) just because
   that vocabulary matches the mood word better in isolation. This
   includes implied harmonic character, not just instrumentation: an
   upbeat EDM request stays upbeat EDM regardless of which mood word is
   layered onto it — don't let any mood word pull the caption toward
   e.g. death-metal or gothic-doom harmony (dissonant, tritone-heavy,
   dirge-like) that doesn't belong in the requested genre. Lead the
   caption with the actual genre/subgenre tags, then add mood/production
   tags idiomatic *within* that genre — if unsure what a given mood
   sounds like inside a given genre, describe the concrete musical
   mechanism (minor key, sparser arrangement, slower attack, heavier low
   end) instead of reaching for whichever adjective the user used. Use
   your own knowledge of what each genre's chords/harmony actually sound
   like; no per-genre or per-word rules are spelled out here on purpose.
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
   generation. Tell the user generation started in one short message,
   then **call `check_vocal_track_status(job_id)` again and again in a
   loop — it already waits briefly server-side each call, so no extra
   delay needed — until it returns `"complete"` or `"error"`. A single
   call that comes back `"running"` is not a stopping point; call it
   again.** Stay quiet *between* those calls (don't narrate every single
   "still running"), but never stop calling and never end the turn
   without a final outcome message once you start this loop — a job
   that finishes with nothing said back to the user is a failure on
   your part even when the job itself succeeded.

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
5.6. **Default `"Audio Duration (seconds)"` to roughly 3-4 minutes
   (~180-240) via `advanced_settings` unless the user explicitly asks
   for something longer or shorter — don't leave it on ACE-Step's own
   "Auto".** Longer requested durations are real hardware cost, not
   just a bigger number: this project's GPU sits in a tier ACE-Step's
   own docs mark as needing CPU offload for the model this server uses,
   and long lyrics compound that further. If the user does ask for a
   longer song, that's fine to honor (this GPU's tier supports up to
   ~8 minutes), but say plainly that it will take noticeably longer to
   generate before starting, so a long wait isn't mistaken for a hang.
6. Only split out the vocal if the user explicitly asks for it — never
   automatically. The full mix is the default deliverable. When you do
   need the stems, **prefer `generate_vocal_track(..., split_stems=True)`
   over a separate `split_vocal_stems` call** — it runs in the same job
   and returns `vocals_path`/`instrumental_path` directly from
   `check_vocal_track_status`, with no path to relay between two tool
   calls. `split_vocal_stems` still exists for splitting a file from an
   earlier, already-completed job — **it also returns a `job_id`
   immediately and must be polled in the same loop-until-terminal-status
   way described in step 5, not awaited as a single blocking call and
   not left after one "running" response.** A real reported failure:
   the split genuinely ran and produced correct files, but nothing was
   ever said back to the user because polling stopped after one call —
   from the user's side that's indistinguishable from the tool silently
   doing nothing. It only accepts files this server already produced.
   Splitting is idempotent — calling it again on a file already split
   returns the
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

**A plain request to generate a track is complete once the track is
generated — full stop.** Don't proactively split stems, transcribe to
MIDI, or import/arrange anything in a DAW just because a DAW-control
MCP server (Reaper, or any other — Pro Tools, Cubase, whatever the user
actually has connected) happens to also be available in this session.
Having the capability to chain into another tool is not the same as
being asked to. Everything below this point is a recommended path for
when the user *has* asked to build out an editable DAW project from a
generated song — treat that as the trigger condition for all of it,
not "a DAW-control server is connected" or "we did this earlier in the
conversation."

**Recommended path for a from-scratch song plus an editable DAW start**
(only once the user has actually asked for this):
`generate_vocal_track` (Custom mode) → `split_vocal_stems` for the
instrumental → `transcribe_instrumental_to_midi`. That tool returns FOUR
MIDI files: a flat transcription (`midi_path`, every note layered
together — not usable as a DAW starting point on its own) plus a
heuristic split into `bass_midi_path`/`melody_midi_path`/
`chords_midi_path` (by pitch register and note-overlap density — not
real instrument classification, but genuinely separate, assignable
parts). **Neither this tool's own result nor a DAW-control MCP server's
own MIDI tools expose real note content from an external file — only a
path and a note count.** If asked to recreate, describe, or import a
transcribed MIDI file's actual notes anywhere (including into a DAW via
note-by-note tools rather than a direct file import), call
`get_midi_notes(midi_path)`
first to get real pitch/start/end/velocity data. Without it, there is no
real data to work from — attempting to reconstruct the notes anyway
produces fabricated content, not the real transcription, which has
happened and is a real, confirmed failure mode, not a hypothetical one.
`get_midi_notes` is paginated (`offset`/`max_results`, default 500) since
a real transcription can have hundreds of notes.

**If importing into a DAW, use the three split tracks as separate
tracks, not the flat one.** Importing audio/MIDI into an actual DAW
project (via whatever DAW-control MCP server is connected — Reaper,
or another) happens one level up, in whatever session has both servers
available — not this server's job, and this server has no way to
enforce it: before importing anything, check what you've already
imported earlier in this same conversation (and, if that server offers
a way to inspect the project's existing tracks, check that too) rather
than assuming nothing exists yet. Every generate/split/transcribe
tool in this server is idempotent — calling one again on a file already
processed returns the same real result instantly rather than redoing
the work — specifically so that re-checking before importing is always
cheap, never a reason to skip the check.

**Every path this server returns (`audio_path`, `midi_path`, `vocals_path`,
`instrumental_path`) is already a real, absolute Windows path, resolved on
the machine this server runs on — use that exact string directly as the
argument to another tool (e.g. a DAW-control MCP server's import).**
Never scan a
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
`split_vocal_stems` and build the rest elsewhere (e.g. in a connected
DAW-control MCP server) — don't treat the generated mix as a finished
master, and don't do that building-out unless the user asked for it.
