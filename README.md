# Command Conversation

A Home Assistant conversation agent that pipes the recognised speech into **any local command**
and speaks back whatever the command prints.

Home Assistant has plenty of conversation agents that talk to an HTTP API — OpenAI-compatible
ones, and a generic HTTP forwarder. There was nothing that just runs a program. This does that,
and nothing else: **stdin in, stdout out**.

That makes the backend a text field. A shell script, a Python program, a CLI tool, an SSH call
to another machine — if it reads stdin and writes stdout, it can answer your voice assistant.

## How it works

```
Assist pipeline
  └─ conversation.<your_agent>
       └─ your command
            transcript → stdin
            stdout     → spoken answer
```

The transcript is written to the command's **stdin**. It is never interpolated into the command
line, so nothing spoken can be mistaken for shell syntax. Context is passed as environment
variables instead:

| Variable | Contents |
| --- | --- |
| `HA_CONVERSATION_ID` | Conversation/session id; stable across turns of one conversation |
| `HA_DEVICE_ID` | Device that captured the speech |
| `HA_SATELLITE_ID` | Satellite entity id, if any |
| `HA_LANGUAGE` | Language of the request |
| `HA_AGENT_ID` | This agent's entity id |

Exit non-zero, print nothing, or run past the timeout, and the configured error message is
spoken instead. stderr is logged, never spoken.

## Installation

Copy `custom_components/command_conversation` into your Home Assistant `config/custom_components/`
directory and restart. Then **Settings → Devices & services → Add integration → Command
Conversation**.

Requires Home Assistant 2025.4 or newer.

## Configuration

| Option | Meaning |
| --- | --- |
| **Command** | Run via the shell. Receives the transcript on stdin. |
| **Timeout** | Seconds before the process is killed (default 60). |
| **Languages** | Comma-separated, e.g. `de`. Leave empty for "any language" — but read the warning below. |
| **Error message** | Spoken when the command fails. |

All of them can be changed later from the integration's options — no restart, no code change.

### Set the Languages option

Leaving **Languages** empty makes the agent report `MATCH_ALL`, and Home Assistant then feeds
the **speech-to-text** language into local intent matching instead of the pipeline language:

```python
if self.pipeline.conversation_language == MATCH_ALL:
    input_language = self.pipeline.stt_language or ...
```

That matters if your STT language is a regional variant with no intents file of its own. For
`de-AT`, `DefaultAgent._load_intents` passes a **set** to the language matcher, and since
neither `de` nor `de-CH` is Austrian they tie — with the winner decided by Python's
per-process randomised string hash. Measured on Home Assistant 2026.7.1, four of five processes
picked `de-CH`, so a German assistant silently loaded **Swiss German** intents and matched
almost nothing. Custom sentences broke too, since they load from
`custom_sentences/<variant>/`.

Naming the language here avoids all of it.

## Example: Claude Code as the backend

The integration is not tied to any particular tool. This is just what the author runs.

Home Assistant is in a container and the CLI is on the host, so the command is an SSH call:

```
ssh -T -o BatchMode=yes -o ConnectTimeout=5 user@localhost
```

No command after the host — a **forced command** in `~/.ssh/authorized_keys` supplies it, so
that key cannot obtain a shell:

```
command="/home/user/bin/ha-agent",no-agent-forwarding,no-port-forwarding,no-pty,no-user-rc,no-X11-forwarding ssh-rsa AAAA...
```

And the wrapper it forces:

```bash
#!/usr/bin/env bash
set -euo pipefail
cd /home/user/empty-workdir          # no project context
exec timeout 55 claude -p \
  --model claude-haiku-4-5-20251001 \
  --permission-prompts none \
  --disallowed-tools "Task,Bash,BashOutput,KillShell,Glob,Grep,Read,Edit,Write,NotebookEdit,WebFetch,WebSearch,TodoWrite,Skill,ExitPlanMode,AskUserQuestion" \
  --append-system-prompt "Answer in at most two short sentences, plain prose, no markdown."
```

### Think about what your command can do

Whatever you configure runs with the privileges of the Home Assistant process, triggered by
**anything spoken near the microphone** — including false wake-word triggers. If the backend is
an agentic tool with file and shell access, your voice assistant is a remote code execution
path. The example above uses four independent restraints: a forced command that cannot get a
shell, auto-denied permission prompts, an explicit tool deny list, and an empty working
directory.

Prefer a narrow wrapper script over a clever one-liner, and keep the sharp tools switched off.

## Notes and limitations

- **Latency is whatever your command costs.** The Claude Code example measures 5–7 s warm, of
  which about 4 s is CLI startup rather than model time. A long-running local service will be
  much faster than spawning a process per utterance.
- **No multi-turn by default.** Each invocation is independent. `HA_CONVERSATION_ID` is provided
  so a backend can thread sessions itself.
- **No Home Assistant control.** The agent does not declare
  `ConversationEntityFeature.CONTROL`; the command gets the transcript and nothing else, and
  cannot read or change entity state. Combined with *Prefer handling commands locally*, the
  built-in intent matcher handles the house and your command only sees what it could not.
- Output over 16 kB is truncated before it reaches text-to-speech.

## Licence

MIT — see [LICENSE](LICENSE).
