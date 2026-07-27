# Token/context usage optimization

Every MCP tool's name, description, and input schema gets sent to the
model on every turn where tools are available — this is not specific to
this server, it's how the underlying Messages API works (stateless per
call; there's no "the model already knows this from earlier" shortcut for
tool definitions). Anthropic's prompt caching can make an unchanged block
much cheaper to resend, but whether and how a client applies that is
entirely up to the client (e.g. Claude Desktop) — an MCP server has no
mechanism to request or control caching from its own code. The one thing
a server author fully controls is the *size* of what gets sent, and
whether that content stays stable across turns (so a cache, if the client
applies one, isn't invalidated by a fresh edit).

## Real, measured numbers (2026-07-23)

Measured via `mcp.list_tools()` — description length + `str(inputSchema)`
length, summed across every registered tool, plus `load_instructions()`
for the system-instructions block:

| | Before | After |
|---|---|---|
| Tool schemas (all 5 tools) | 20,639 chars (~5,159 tokens) | 9,678 chars (~2,419 tokens) |
| `00_core.md` instructions | ~18,000 chars | 11,507 chars (later grew to ~13.6K as new features were documented) |

`generate_vocal_track`'s docstring alone accounted for more than half of
the original tool-schema total (12,590 of 20,639 chars) — it had
accumulated extensive "confirmed by a real test..." narration that
duplicated, in much more verbose form, warnings already covered in
`00_core.md`. Trimmed to state the same facts (what's risky, what to do)
without re-narrating the investigation that established them.

## What was done

1. **Trimmed every tool's docstring and `00_core.md`** to state
   conclusions/rules plainly instead of narrating the testing history
   that established them. The "why" that matters for correct behavior
   (e.g. reference audio detunes vocals, Remix mode risks copyright
   exposure) was kept; the specific test methodology that confirmed it
   was cut, since a tool docstring gets resent every turn regardless of
   whether anyone needs that history again.
2. **Made every long-running tool idempotent** (`SeparatorClient.separate`,
   `transcribe_to_midi`) — calling one again on an input already processed
   returns the existing result in milliseconds instead of re-running real
   work. This doesn't reduce per-turn token cost directly, but it makes
   the *practical impact* of the AI losing track of earlier results (a
   real, observed failure mode in long conversations) cheap instead of
   wasteful.
3. **Converted every tool that does real work to the job/poll pattern**
   (`generate_vocal_track`, `split_vocal_stems`, `analyze_reference_audio`,
   `transcribe_instrumental_to_midi`) — a tool call returns a `job_id`
   immediately rather than blocking, and `check_vocal_track_status` polls
   with a capped wait (25s). This exists because of a real, confirmed
   failure: Claude Desktop treated long blocking calls (measured at
   30-50s+) as failed/stuck even when they were genuinely still working.
   The tradeoff: polling means multiple full-price round-trips (each
   paying the entire tool-schema + instructions + conversation-history
   cost) instead of one, which is itself a real token cost — but the
   alternative (a client giving up and reporting false failures) is worse
   than the token cost of polling.
4. **Did NOT increase `check_vocal_track_status`'s 25s poll-wait cap** to
   reduce the number of poll round-trips, despite that being a real lever
   — the confirmed danger zone for blocking calls (30-50s+) is close
   enough to a plausible higher cap that guessing wrong risks
   reintroducing the exact "looks stuck" failure class point 3 exists to
   prevent. Left alone without live-tested evidence it's safe to raise.

## What did NOT get trimmed, and why

**reaper-mcp's tool surface was investigated but deliberately left
unchanged.** It's a separate project (`D:\DansProject\Reaper-MCP`) with
its own built-in profile system (`REAPER_MCP_PROFILE` env var — `full`,
`composition`, `mixing`, `analysis`, `minimal`) that could cut its
per-turn footprint from ~23,745 tokens (`full`, 164 tools) down to as low
as ~3,048 tokens (`minimal`). This was tempting and was briefly applied
(`composition` profile) before being reverted. **Confirmed with the user:
they use both composition-side (tracks/MIDI/tempo) and mixing/FX-side
(EQ/compression/sidechain/sends) tools regularly** — no profile smaller
than `full` is safe to use without risking a tool they actively rely on
becoming unavailable. Do not re-attempt trimming reaper-mcp's profile
without re-confirming this hasn't changed; the token savings are real and
large, but breaking a tool the user depends on is a much worse outcome
than the tokens saved.

## Practical recommendations (for a human using this system, not this
server's own code)

- Start a new conversation per work phase (generate → new conversation →
  split/transcribe → new conversation → Reaper import) rather than one
  long-running conversation for an entire pipeline. Conversation history
  accumulates and gets resent every turn on top of the fixed tool-schema
  cost — this compounds badly in a single long conversation and is
  avoided entirely by starting fresh.
- Avoid iterative, incremental edits to tool docstrings/instructions once
  they're correct. Each edit is a guaranteed cache-invalidation event (if
  the client applies caching at all) — batch changes instead of polishing
  wording repeatedly across a session.
